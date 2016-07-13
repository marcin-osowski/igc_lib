"""A simple library for parsing IGC files.

Main abstraction defined in this file is the Flight class, which
represents a parsed IGC file. A Flight is a collection of:
    GNNSFix objects, one per B record in the original file,
    IGC metadata, extracted from A/I/H records
    a list of detected Thermals,
    a list of detected Glides.

For example usage see the attached igc_lib_demo.py file. Please note
that after creating a Flight instance you should always check for its
validity via the `valid` attribute prior to using it, as many IGC
records are broken.
"""

import collections
import datetime
import math
import re
import xml.dom.minidom
from collections import defaultdict

import lib.viterbi
import lib.geo


def _strip_non_printable_chars(string):
    """Filters a string removing non-printable characters.

    Args:
        string: A string to be filtered.

    Returns:
        A string, where non-printable characters are removed.
    """
    printable = set("0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKL"
                    "MNOPQRSTUVWXYZ!\"#$%&\'()*+,-./:;<=>?@[\\]^_`{|}~ ")
    return filter(lambda x: x in printable, string)


def _rawtime_float_to_hms(timef):
    """Converts time from floating point seconds to hours/minutes/seconds.

    Args:
        timef: A floating point time in seconds to be converted

    Returns:
        A namedtuple with hours, minutes and seconds elements
    """
    time = int(round(timef))
    hms = collections.namedtuple('hms', ['hours', 'minutes', 'seconds'])

    return hms((time/3600), (time % 3600)/60, time % 60)


class Turnpoint:
    """A single turnpoint in a Task.

    Attributes:
        lat: a float, latitude in degrees
        lon: a float, longitude in degrees
        radius: a float, radius of cylinder or line in km
        kind: type of turnpoint; "start_exit", "start_enter", "cylinder",
        "End_of_speed_section", "goal_cylinder", "goal_line"
    """

    def __init__(self, lat, lon, radius, kind):
        self.lat = lat
        self.lon = lon
        self.radius = radius
        self.kind = kind
        assert kind in ["start_exit", "start_enter", "cylinder",
                        "End_of_speed_section", "goal_cylinder",
                        "goal_line"], \
            "turnpoint type is not valid: %r" % kind

    def in_radius(self, fix):
        """Checks whether the provided GNSSFix is within the radius"""
        distance = lib.geo.earth_distance(self.lat, self.lon, fix.lat, fix.lon)
        return distance < self.radius


class Task:
    """Stores a single flight task definition

    Checks if a Flight has achieved the turnpoints in the Task.

    Attributes:
        turnpoints: A list of Turnpoint objects.
        start_time: Raw time (seconds past midnight). The time the race starts.
                    The pilots must start at or after this time.
        end_time: Raw time (seconds past midnight). The time the race ends.
                  The pilots must finish the race at or before this time.
                  No credit is given for distance covered after this time.
    """

    @staticmethod
    def create_from_lkt_file(filename):
        """ Creates Task from LK8000 task file, which is in xml format.
            LK8000 does not have End of Speed Section or task finish time.
            For the goal, at the moment, Turnpoints can't handle goal cones or
            lines, for this reason we default to goal_cylinder.
        """

        # Open XML document using minidom parser
        DOMTree = xml.dom.minidom.parse(filename)
        task = DOMTree.documentElement

        # Get the taskpoints, waypoints and time gate
        # TODO: add code to handle if these tags are missing.
        taskpoints = task.getElementsByTagName("taskpoints")[0]
        waypoints = task.getElementsByTagName("waypoints")[0]
        gate = task.getElementsByTagName("time-gate")[0]
        tpoints = taskpoints.getElementsByTagName("point")
        wpoints = waypoints.getElementsByTagName("point")
        start_time = gate.getAttribute("open-time")

        start_hours, start_minutes = start_time.split(':')
        start_time = int(start_hours) * 3600 + int(start_minutes) * 60
        end_time = 23*3600 + 59*60 + 59  # default end_time of 23:59:59

        # Create a dictionary of names and a list of longitudes and latitudes
        # as the waypoints co-ordinates are stored separate to turnpoint
        # details.
        coords = defaultdict(list)

        for point in wpoints:
            name = point.getAttribute("name")
            longitude = float(point.getAttribute("longitude"))
            latitude = float(point.getAttribute("latitude"))
            coords[name].append(longitude)
            coords[name].append(latitude)

        # Create list of turnpoints
        turnpoints = []
        for point in tpoints:
            lat = coords[point.getAttribute("name")][1]
            lon = coords[point.getAttribute("name")][0]
            radius = float(point.getAttribute("radius"))/1000

            if point == tpoints[0]:
                # It is the first turnpoint, the start
                if point.getAttribute("Exit") == "true":
                    kind = "start_exit"
                else:
                    kind = "start_enter"
            else:
                if point == tpoints[-1]:
                    # It is the last turnpoint, i.e. the goal
                    if point.getAttribute("type") == "line":
                        # TODO(kuaka): change to 'line' once we can process it
                        kind = "goal_cylinder"
                    else:
                        kind = "goal_cylinder"
                else:
                    # All turnpoints other than the 1st and the last are
                    # "cylinders". In theory they could be
                    # "End_of_speed_section" but this is not supported by
                    # LK8000. For paragliders it would be safe to assume
                    # that the 2nd to last is always "End_of_speed_section".
                    kind = "cylinder"

            turnpoint = Turnpoint(lat, lon, radius, kind)
            turnpoints.append(turnpoint)
        task = Task(turnpoints, start_time, end_time)
        return task

    def __init__(self, turnpoints, start_time, end_time):
        self.turnpoints = turnpoints
        self.start_time = start_time
        self.end_time = end_time

    def check_flight(self, flight):
        """ Checks a Flight object against the task.

            Args:
                flight: a Flight object

            Returns:
                a list of GNSSFixes of when turnpoints were achieved.
        """
        reached_turnpoints = []
        proceed_to_start = False
        t = 0
        for fix in flight.fixes:
            if t >= len(self.turnpoints):
                # Pilot has arrived in goal (last turnpoint) so we can stop.
                break

            if self.end_time < fix.rawtime:
                # Task has ended
                break

            # Pilot must have at least 1 fix inside the start after the start
            # time, then exit.
            if self.turnpoints[t].kind == "start_exit":
                if proceed_to_start:
                    if not self.turnpoints[t].in_radius(fix):
                        reached_turnpoints.append(fix)  # pilot has started
                        t += 1
                if fix.rawtime > self.start_time and not proceed_to_start:
                    if self.turnpoints[t].in_radius(fix):
                        # Pilot is inside start after the start time.
                        proceed_to_start = True

            # Pilot must have at least 1 fix outside the start after
            # the start time, then enter.
            elif self.turnpoints[t].kind == "start_enter":
                if proceed_to_start:
                    if self.turnpoints[t].in_radius(fix):
                        # Pilot has started
                        reached_turnpoints.append(fix)
                        t += 1
                if fix.rawtime > self.start_time and not proceed_to_start:
                    if not self.turnpoints[t].in_radius(fix):
                        # Pilot is outside start after the start time.
                        proceed_to_start = True

            elif self.turnpoints[t].kind in ["cylinder",
                                             "End_of_speed_section",
                                             "goal_cylinder"]:
                if self.turnpoints[t].in_radius(fix):
                    # pilot has achieved turnpoint
                    reached_turnpoints.append(fix)
                    t += 1
            else:
                assert False, (
                    "Unknown turnpoint kind: %s" % self.turnpoints[t].kind)

        return reached_turnpoints


class GNSSFix:
    """Stores single GNSS flight recorder fix (a B-record).

    Raw attributes (i.e. attributes read directly from the B record):
        rawtime: a float, time since last midnight, UTC, seconds
        lat: a float, latitude in degrees
        lon: a float, longitude in degrees
        validity: a string, GPS validity information from flight recorder
        press_alt: a float, pressure altitude, meters
        gnss_alt: a float, GNSS altitude, meters
        extras: a string, B record extensions

    Derived attributes:
        index: an integer, the position of the fix in the IGC file
        timestamp: a float, true timestamp (since epoch), UTC, seconds
        alt: a float, either press_alt or gnss_alt
        gsp: a float, current ground speed, km/h
        bearing: a float, aircraft bearing, in degrees
        bearing_change_rate: a float, bearing change rate, degrees/second
        flying: a bool, whether this fix is during a flight
        circling: a bool, whether this fix is inside a thermal
    """

    @staticmethod
    def build_from_B_record(B_record_line, index):
        """Creates GNSSFix object from IGC B-record line.

        Args:
            B_record_line: a string, B record line from an IGC file
            index: the zero-based position of the fix in the parent IGC file

        Returns:
            The created GNSSFix object
        """
        match = re.match(
            '^B' + '(\d\d)(\d\d)(\d\d)'
            + '(\d\d)(\d\d)(\d\d\d)([NS])'
            + '(\d\d\d)(\d\d)(\d\d\d)([EW])'
            + '([AV])' + '([-\d]\d\d\d\d)' + '([-\d]\d\d\d\d)'
            + '([0-9a-zA-Z]*).*$', B_record_line)
        if match is None:
            return None
        (hours, minutes, seconds,
         lat_deg, lat_min, lat_min_dec, lat_sign,
         lon_deg, lon_min, lon_min_dec, lon_sign,
         validity, press_alt, gnss_alt,
         extras) = match.groups()

        rawtime = (float(hours)*60.0 + float(minutes))*60.0 + float(seconds)

        lat = float(lat_deg)
        lat += float(lat_min) / 60.0
        lat += float(lat_min_dec) / 1000.0 / 60.0
        if lat_sign == 'S':
            lat = -lat

        lon = float(lon_deg)
        lon += float(lon_min) / 60.0
        lon += float(lon_min_dec) / 1000.0 / 60.0
        if lon_sign == 'W':
            lon = -lon

        press_alt = float(press_alt)
        gnss_alt = float(gnss_alt)

        return GNSSFix(rawtime, lat, lon, validity, press_alt, gnss_alt,
                       index, extras)

    def __init__(self, rawtime, lat, lon, validity, press_alt, gnss_alt,
                 index, extras):
        """Initializer of GNSSFix. Not meant to be used directly."""
        self.rawtime = rawtime
        self.lat = lat
        self.lon = lon
        self.validity = validity
        self.press_alt = press_alt
        self.gnss_alt = gnss_alt
        self.index = index
        self.extras = extras
        self.flight = None

    def set_flight(self, flight):
        """Sets parent Flight object."""
        self.flight = flight
        if self.flight.alt_source == "PRESS":
            self.alt = self.press_alt
        elif self.flight.alt_source == "GNSS":
            self.alt = self.gnss_alt
        else:
            assert(False)
        self.timestamp = self.rawtime + flight.date_timestamp

    def __repr__(self):
        return self.__str__()

    def __str__(self):
        return (
            "GNSSFix(rawtime=%02d:%02d:%02d, lat=%f, lon=%f, altitide=%.1f)" %
            (_rawtime_float_to_hms(self.rawtime) +
             (self.lat, self.lon, self.alt)))

    def bearing_to(self, other):
        """Computes bearing in degrees to another GNSSFix."""
        return lib.geo.bearing_to(self.lat, self.lon, other.lat, other.lon)

    def distance_to(self, other):
        """Computes great circle distance in kilometers to another GNSSFix."""
        return lib.geo.earth_distance(self.lat, self.lon, other.lat, other.lon)

    def to_B_record(self):
        """Reconstructs an IGC B-record."""
        rawtime = int(self.rawtime)
        hours = rawtime / 3600
        minutes = (rawtime % 3600) / 60
        seconds = rawtime % 60

        if self.lat < 0.0:
            lat = -self.lat
            lat_sign = 'S'
        else:
            lat = self.lat
            lat_sign = 'N'
        lat = int(round(lat*60000.0))
        lat_deg = lat / 60000
        lat_min = (lat % 60000) / 1000
        lat_min_dec = lat % 1000

        if self.lon < 0.0:
            lon = -self.lon
            lon_sign = 'W'
        else:
            lon = self.lon
            lon_sign = 'E'
        lon = int(round(lon*60000.0))
        lon_deg = lon / 60000
        lon_min = (lon % 60000) / 1000
        lon_min_dec = lon % 1000

        validity = self.validity
        press_alt = int(self.press_alt)
        gnss_alt = int(self.gnss_alt)
        extras = self.extras

        return (
            "B" +
            "%02d%02d%02d" % (hours, minutes, seconds) +
            "%02d%02d%03d%s" % (lat_deg, lat_min, lat_min_dec, lat_sign) +
            "%03d%02d%03d%s" % (lon_deg, lon_min, lon_min_dec, lon_sign) +
            validity +
            "%05d%05d" % (press_alt, gnss_alt) +
            extras)


class Thermal:
    """Represents a single thermal detected in a flight.

    Attributes:
        enter_fix: a GNSSFix, entry point of the thermal
        exit_fix: a GNSSFix, exit point of the thermal
    """
    def __init__(self, enter_fix, exit_fix):
        self.enter_fix = enter_fix
        self.exit_fix = exit_fix

    def time_change(self):
        """Returns the time spent in the thermal, seconds."""
        return self.exit_fix.rawtime - self.enter_fix.rawtime

    def alt_change(self):
        """Returns the altitude gained/lost in the thermal, meters."""
        return self.exit_fix.alt - self.enter_fix.alt

    def vertical_velocity(self):
        """Returns average vertical velocity in the thermal, m/s."""
        if math.fabs(self.time_change()) < 1e-7:
            return 0.0
        return self.alt_change() / self.time_change()

    def __repr__(self):
        return self.__str__()

    def __str__(self):
        hms = _rawtime_float_to_hms(self.time_change())
        return ("Thermal(vertical_velocity=%.2f m/s, duration=%dm %ds)" %
                (self.vertical_velocity(), hms.minutes, hms.seconds))


class Glide:
    """Represents a single glide detected in a flight.

    Glides are portions of the recorded track between thermals.

    Attributes:
        enter_fix: a GNSSFix, entry point of the glide
        exit_fix: a GNSSFix, exit point of the glide
        track_length: a float, the total length, in kilometers, of the recorded
        track, between the entry point and the exit point; note that this is
        not the same as the distance between these points
    """

    def __init__(self, enter_fix, exit_fix, track_length):
        self.enter_fix = enter_fix
        self.exit_fix = exit_fix
        self.track_length = track_length

    def time_change(self):
        """Returns the time spent in the glide, seconds."""
        return self.exit_fix.timestamp - self.enter_fix.timestamp

    def speed(self):
        """Returns the average speed in the glide, km/h."""
        return self.track_length / (self.time_change() / 3600.0)

    def alt_change(self):
        """Return the overall altitude change in the glide, meters."""
        return self.enter_fix.alt - self.exit_fix.alt

    def glide_ratio(self):
        """Returns the L/D of the glide."""
        if math.fabs(self.alt_change()) < 1e-7:
            return 0.0
        return (self.track_length * 1000.0) / self.alt_change()

    def __repr__(self):
        return self.__str__()

    def __str__(self):
        hms = _rawtime_float_to_hms(self.time_change())
        return (
            ("Glide(dist=%.2f km, avg_speed=%.2f kph, "
             "avg L/D=%.2f duration=%dm %ds)") % (
                self.track_length, self.speed(), self.glide_ratio(),
                hms.minutes, hms.seconds))


class FlightParsingConfig(object):
    """Configuration for parsing an IGC file.

    Defines a set of parameters used to validate a file, and to detect
    thermals and flight mode. Details in comments.
    """

    #
    # Flight validation parameters.
    #

    # Minimum number of fixes in a file.
    min_fixes = 50

    # Maximum time between fixes, seconds.
    # Soft limit, some fixes are allowed to exceed.
    max_seconds_between_fixes = 50.0

    # Minimum time between fixes, seconds.
    # Soft limit, some fixes are allowed to exceed.
    min_seconds_between_fixes = 1.0

    # Maximum number of fixes exceeding time between fix constraints.
    max_time_violations = 10

    # Maximum number of times a file can cross the 0:00 UTC time.
    max_new_days_in_flight = 2

    # Minimum average of absolute values of altitude changes in a file.
    # This is needed to discover altitude sensors (either pressure or
    # gps) that report either always constant altitude, or almost
    # always constant altitude, and therefore are invalid. The unit
    # is meters/fix.
    min_avg_abs_alt_change = 0.01

    # Maximum altitude change per second between fixes, meters per second.
    # Soft limit, some fixes are allowed to exceed."""
    max_alt_change_rate = 50.0

    # Maximum number of fixes that exceed the altitude change limit.
    max_alt_change_violations = 3

    # Absolute maximum altitude, meters.
    max_alt = 10000.0

    # Absolute minimum altitude, meters.
    min_alt = -600.0

    #
    # Thermals and flight detection parameters.
    #

    # Minimum ground speed to switch to flight mode, km/h.
    min_gsp_flight = 20.0

    # Minimum bearing change to enter a thermal, deg/sec.
    min_bearing_change_circling = 6.0

    # Minimum time between fixes to calculate bearing change, seconds.
    # See the usage for a more detailed comment on why this is useful.
    min_time_for_bearing_change = 5.0

    # Minimum time to consider circling a thermal, seconds.
    min_time_for_thermal = 60.0


class Flight:
    """Parses IGC file, detects thermals and checks for record anomalies.

    Before using an instance of Flight check the `valid` attribute. An
    invalid Flight instance is not usable. For an explaination why is
    a Flight invalid see the `notes` attribute.

    General attributes:
        valid: a bool, whether the supplied record is considered valid
        notes: a list of strings, warnings and errors encountered while
        parsing/validating the file
        fixes: a list of GNSSFix objects, one per each valid B record
        thermals: a list of Thermal objects, the detected thermals
        glides: a list of Glide objects, the glides between thermals
        takeoff_fix: a GNSSFix object, the fix at which takeoff was detected
        landing_fix: a GNSSFix object, the fix at which landing was detected

    IGC metadata attributes (some might be missing if the flight does not
    define them):
        glider_type: a string, the declared glider type
        competition_class: a string, the declared competition class
        fr_manuf_code: a string, the flight recorder manufaturer code
        fr_uniq_id: a string, the flight recorded unique id
        i_record: a string, the I record (describing B record extensions)
        fr_firmware_version: a string, the version of the recorder firmware
        fr_hardware_version: a string, the version of the recorder hardware
        fr_recorder_type: a string, the type of the recorder
        fr_gps_receiver: a string, the used GPS receiver
        fr_pressure_sensor: a string, the used pressure sensor

    Other attributes:
        alt_source: a string, the chosen altitude sensor,
        either "PRESS" or "GNSS"
        press_alt_valid: a bool, whether the pressure altitude sensor is OK
        gnss_alt_valid: a bool, whether the GNSS altitude sensor is OK
    """

    @staticmethod
    def create_from_file(filename, config_class=FlightParsingConfig):
        """Creates an instance of Flight from a given file.

        Args:
            filename: a string, the name of the input IGC file
            config_class: a class that implements FlightParsingConfig

        Returns:
            An instance of Flight built from the supplied IGC file.
        """
        config = config_class()
        fixes = []
        a_records = []
        i_records = []
        h_records = []
        with open(filename, 'r') as flight_file:
            for line in flight_file:
                line = line.replace('\n', '').replace('\r', '')
                if not line:
                    continue
                if line[0] == 'A':
                    a_records.append(line)
                elif line[0] == 'B':
                    fix = GNSSFix.build_from_B_record(line, index=len(fixes))
                    if fix is not None:
                        if fixes and math.fabs(fix.rawtime - fixes[-1].rawtime) < 1e-5:
                            # The time did not change since the previous fix.
                            # Ignore this fix.
                            pass
                        else:
                            fixes.append(fix)
                elif line[0] == 'I':
                    i_records.append(line)
                elif line[0] == 'H':
                    h_records.append(line)
                else:
                    # Do not parse any other types of IGC records
                    pass
        flight = Flight(fixes, a_records, h_records, i_records, config)
        return flight

    def __init__(self, fixes, a_records, h_records, i_records, config):
        """Initializer of the Flight class. Do not use directly."""
        self._config = config
        self.fixes = fixes
        self.valid = True
        self.notes = []
        if len(fixes) < self._config.min_fixes:
            self.notes.append(
                "Error: This file has %d fixes, less than "
                "the minimum %d." % (len(fixes), self._config.min_fixes))
            self.valid = False
            return

        self._check_altitudes()
        if not self.valid:
            return

        self._check_fix_rawtime()
        if not self.valid:
            return

        if self.press_alt_valid:
            self.alt_source = "PRESS"
        elif self.gnss_alt_valid:
            self.alt_source = "GNSS"
        else:
            self.notes.append(
                "Error: neither pressure nor gnss altitude is valid.")
            self.valid = False
            return

        if a_records:
            self._parse_a_records(a_records)
        if i_records:
            self._parse_i_records(i_records)
        if h_records:
            self._parse_h_records(h_records)

        if not hasattr(self, 'date_timestamp'):
            self.notes.append("Error: no date record (HFDTE) in the file")
            self.valid = False
            return

        for fix in self.fixes:
            fix.set_flight(self)

        self._compute_ground_speeds()
        self._compute_flight()
        self._compute_takeoff_landing()
        if not hasattr(self, 'takeoff_fix'):
            self.notes.append("Error: did not detect takeoff.")
            self.valid = False
            return

        self._compute_bearings()
        self._compute_bearing_change_rates()
        self._compute_circling()
        self._find_thermals()

    def _parse_a_records(self, a_records):
        """Parses the IGC A record.

        A record contains the flight recorder manufacturer ID and
        device unique ID.
        """
        self.fr_manuf_code = _strip_non_printable_chars(a_records[0][1:4])
        self.fr_uniq_id = _strip_non_printable_chars(a_records[0][4:7])

    def _parse_i_records(self, i_records):
        """Parses the IGC I records.

        I records contain a description of extensions used in B records.
        """
        self.i_record = _strip_non_printable_chars(" ".join(i_records))

    def _parse_h_records(self, h_records):
        """Parses the IGC H records.

        H records (header records) contain a lot of interesting metadata
        about the file, such as the date of the flight, name of the pilot,
        glider type, competition class, recorder accuracy and more.
        Consult the IGC manual for details.
        """
        for record in h_records:
            self._parse_h_record(record)

    def _parse_h_record(self, record):
        if record[0:5] == 'HFDTE':
            match = re.match(
                'HFDTE(\d\d)(\d\d)(\d\d)',
                record, flags=re.IGNORECASE)
            if match:
                dd, mm, yy = map(_strip_non_printable_chars, match.groups())
                year = int("20%s" % yy)
                month = int(mm)
                day = int(dd)
                if 1 <= month <= 12 and 1 <= day <= 31:
                    epoch = datetime.datetime(year=1970, month=1, day=1)
                    date = datetime.datetime(year=year, month=month, day=day)
                    self.date_timestamp = (date - epoch).total_seconds()
        elif record[0:5] == 'HFGTY':
            match = re.match(
                'HFGTY[ ]*GLIDER[ ]*TYPE[ ]*:[ ]*(.*)',
                record, flags=re.IGNORECASE)
            if match:
                (self.glider_type,) = map(
                    _strip_non_printable_chars, match.groups())
        elif record[0:5] == 'HFRFW' or record[0:5] == 'HFRHW':
            match = re.match(
                'HFR[FH]W[ ]*FIRMWARE[ ]*VERSION[ ]*:[ ]*(.*)',
                record, flags=re.IGNORECASE)
            if match:
                (self.fr_firmware_version,) = map(
                    _strip_non_printable_chars, match.groups())
            match = re.match(
                'HFR[FH]W[ ]*HARDWARE[ ]*VERSION[ ]*:[ ]*(.*)',
                record, flags=re.IGNORECASE)
            if match:
                (self.fr_hardware_version,) = map(
                    _strip_non_printable_chars, match.groups())
        elif record[0:5] == 'HFFTY':
            match = re.match(
                'HFFTY[ ]*FR[ ]*TYPE[ ]*:[ ]*(.*)',
                record, flags=re.IGNORECASE)
            if match:
                (self.fr_recorder_type,) = map(_strip_non_printable_chars,
                                               match.groups())
        elif record[0:5] == 'HFGPS':
            match = re.match(
                'HFGPS(?:[: ]|(?:GPS))*(.*)',
                record, flags=re.IGNORECASE)
            if match:
                (self.fr_gps_receiver,) = map(_strip_non_printable_chars,
                                              match.groups())
        elif record[0:5] == 'HFPRS':
            match = re.match(
                'HFPRS[ ]*PRESS[ ]*ALT[ ]*SENSOR[ ]*:[ ]*(.*)',
                record, flags=re.IGNORECASE)
            if match:
                (self.fr_pressure_sensor,) = map(_strip_non_printable_chars,
                                                 match.groups())
        elif record[0:5] == 'HFCCL':
            match = re.match(
                'HFCCL[ ]*COMPETITION[ ]*CLASS[ ]*:[ ]*(.*)',
                record, flags=re.IGNORECASE)
            if match:
                (self.competition_class,) = map(_strip_non_printable_chars,
                                                match.groups())

    def __str__(self):
        descr = "Flight(valid=%s, fixes: %d" % (
            str(self.valid), len(self.fixes))
        if hasattr(self, 'thermals'):
            descr += ", thermals: %d" % len(self.thermals)
        descr += ")"
        return descr

    def _check_altitudes(self):
        press_alt_violations_num = 0
        gnss_alt_violations_num = 0
        press_huge_changes_num = 0
        gnss_huge_changes_num = 0
        press_chgs_sum = 0.0
        gnss_chgs_sum = 0.0
        for i in xrange(len(self.fixes) - 1):
            press_alt_delta = math.fabs(
                self.fixes[i+1].press_alt - self.fixes[i].press_alt)
            gnss_alt_delta = math.fabs(
                self.fixes[i+1].gnss_alt - self.fixes[i].gnss_alt)
            rawtime_delta = math.fabs(
                self.fixes[i+1].rawtime - self.fixes[i].rawtime)
            if rawtime_delta > 0.5:
                if (press_alt_delta / rawtime_delta >
                        self._config.max_alt_change_rate):
                    press_huge_changes_num += 1
                else:
                    press_chgs_sum += press_alt_delta
                if (gnss_alt_delta / rawtime_delta >
                        self._config.max_alt_change_rate):
                    gnss_huge_changes_num += 1
                else:
                    gnss_chgs_sum += gnss_alt_delta
            if (self.fixes[i].press_alt > self._config.max_alt
                    or self.fixes[i].press_alt < self._config.min_alt):
                press_alt_violations_num += 1
            if (self.fixes[i].gnss_alt > self._config.max_alt or
                    self.fixes[i].gnss_alt < self._config.min_alt):
                gnss_alt_violations_num += 1
        press_chgs_avg = press_chgs_sum / float(len(self.fixes) - 1)
        gnss_chgs_avg = gnss_chgs_sum / float(len(self.fixes) - 1)

        press_alt_ok = True
        if press_chgs_avg < self._config.min_avg_abs_alt_change:
            self.notes.append(
                "Warning: average pressure altitude change between fixes "
                "is: %f. It is lower than the minimum: %f."
                % (press_chgs_avg, self._config.min_avg_abs_alt_change))
            press_alt_ok = False

        if press_huge_changes_num > self._config.max_alt_change_violations:
            self.notes.append(
                "Warning: too many high changes in pressure altitude: %d. "
                "Maximum allowed: %d."
                % (press_huge_changes_num,
                   self._config.max_alt_change_violations))
            press_alt_ok = False

        if press_alt_violations_num > 0:
            self.notes.append(
                "Warning: pressure altitude limits exceeded in %d fixes."
                % (press_alt_violations_num))
            press_alt_ok = False

        gnss_alt_ok = True
        if gnss_chgs_avg < self._config.min_avg_abs_alt_change:
            self.notes.append(
                "Warning: average gnss altitude change between fixes is: %f. "
                "It is lower than the minimum: %f."
                % (gnss_chgs_avg, self._config.min_avg_abs_alt_change))
            gnss_alt_ok = False

        if gnss_huge_changes_num > self._config.max_alt_change_violations:
            self.notes.append(
                "Warning: too many high changes in gnss altitude: %d. "
                "Maximum allowed: %d."
                % (gnss_huge_changes_num,
                   self._config.max_alt_change_violations))
            gnss_alt_ok = False

        if gnss_alt_violations_num > 0:
            self.notes.append(
                "Warning: gnss altitude limits exceeded in %d fixes." %
                gnss_alt_violations_num)
            gnss_alt_ok = False

        self.press_alt_valid = press_alt_ok
        self.gnss_alt_valid = gnss_alt_ok

    def _check_fix_rawtime(self):
        """Checks for rawtime anomalies, fixes 0:00 UTC crossing.

        The B records do not have fully qualified timestamps (just the current
        time in UTC), therefore flights that cross 0:00 UTC need special
        handling.
        """
        DAY = 24.0 * 60.0 * 60.0
        days_added = 0
        rawtime_to_add = 0.0
        rawtime_between_fix_exceeded = 0
        for i in xrange(1, len(self.fixes)):
            f0 = self.fixes[i-1]
            f1 = self.fixes[i]
            f1.rawtime += rawtime_to_add

            if (f0.rawtime > f1.rawtime and
                    f1.rawtime + DAY < f0.rawtime + 200.0):
                # Day switch
                days_added += 1
                rawtime_to_add += DAY
                f1.rawtime += DAY

            time_change = f1.rawtime - f0.rawtime
            if time_change < self._config.min_seconds_between_fixes - 1e-5:
                rawtime_between_fix_exceeded += 1
            if time_change > self._config.max_seconds_between_fixes + 1e-5:
                rawtime_between_fix_exceeded += 1

        if rawtime_between_fix_exceeded > self._config.max_time_violations:
            self.notes.append(
                "Error: too many fixes intervals exceed time between fixes "
                "constraints. Allowed %d fixes, found %d fixes."
                % (self._config.max_time_violations,
                   rawtime_between_fix_exceeded))
            self.valid = False
        if days_added > self._config.max_new_days_in_flight:
            self.notes.append(
                "Error: too many times did the flight cross the UTC 0:00 "
                "barrier. Allowed %d times, found %d times."
                % (self._config.max_new_days_in_flight, days_added))
            self.valid = False

    def _compute_ground_speeds(self):
        """Adds ground speed info (km/h) to self.fixes."""
        self.fixes[0].gsp = 0.0
        for i in xrange(1, len(self.fixes)):
            dist = self.fixes[i].distance_to(self.fixes[i-1])
            rawtime = self.fixes[i].rawtime - self.fixes[i-1].rawtime
            if math.fabs(rawtime) < 1e-5:
                self.fixes[i].gsp = 0.0
            else:
                self.fixes[i].gsp = dist/rawtime*3600.0

    def _flying_emissions(self):
        """Generates raw flying/not flying emissions from ground speed.

        Standing (i.e. not flying) is encoded as 0, flying is encoded as 1.
        Exported to a separate function to be used in Baum-Welch parameters
        learning.
        """
        emissions = []
        for fix in self.fixes:
            if fix.gsp > self._config.min_gsp_flight:
                emissions.append(1)
            else:
                emissions.append(0)

        return emissions

    def _compute_flight(self):
        """Adds boolean flag .flying to self.fixes."""
        emissions = self._flying_emissions()
        decoder = lib.viterbi.SimpleViterbiDecoder(
            # More likely to start the log standing, i.e. not in flight
            init_probs=[0.80, 0.20],
            transition_probs=[
                [0.9926, 0.0074],  # transitions from standing
                [0.0003, 0.9997],  # transitions from flying
            ],
            emission_probs=[
                [0.974, 0.026],  # emissions from standing
                [0.031, 0.969],  # emissions from flying
            ])

        output = decoder.decode(emissions)

        for fix, output in zip(self.fixes, output):
            fix.flying = (output == 1)

    def _compute_takeoff_landing(self):
        """Finds the takeoff and landing fixes in the log.

        Takeoff fix is the first fix in the flying mode. Landing fix
        is the next fix after the last fix in the flying mode or the
        last fix in the file.
        """
        takeoff_fix = None
        landing_fix = None
        was_flying = False
        for fix in self.fixes:
            if fix.flying and takeoff_fix is None:
                takeoff_fix = fix
            if not fix.flying and was_flying:
                landing_fix = fix
            was_flying = fix.flying

        if takeoff_fix is None:
            # No takeoff found.
            return

        if landing_fix is None:
            # Landing on the last fix
            landing_fix = self.fixes[-1]

        self.takeoff_fix = takeoff_fix
        self.landing_fix = landing_fix

    def _compute_bearings(self):
        """Adds bearing info to self.fixes."""
        for i in xrange(len(self.fixes) - 1):
            self.fixes[i].bearing = self.fixes[i].bearing_to(self.fixes[i+1])
        self.fixes[-1].bearing = self.fixes[-2].bearing

    def _compute_bearing_change_rates(self):
        """Adds bearing change rate info to self.fixes.

        Computing bearing change rate between neighboring fixes proved
        itself to be noisy on tracks recorded with minimum interval (1 second).
        Therefore we compute rates between points that are at least
        min_time_for_bearing_change seconds apart.
        """
        def find_prev_fix(curr_fix):
            """Computes the previous fix to be used in bearing rate change."""
            prev_fix = None
            for i in xrange(curr_fix - 1, 0, -1):
                time_dist = math.fabs(self.fixes[curr_fix].timestamp -
                                      self.fixes[i].timestamp)
                if (time_dist >
                        self._config.min_time_for_bearing_change - 1e-7):
                    prev_fix = i
                    break
            return prev_fix

        for curr_fix in xrange(len(self.fixes)):
            prev_fix = find_prev_fix(curr_fix)

            if prev_fix is None:
                self.fixes[curr_fix].bearing_change_rate = 0.0
            else:
                bearing_change = (self.fixes[prev_fix].bearing -
                                  self.fixes[curr_fix].bearing)
                if math.fabs(bearing_change) > 180.0:
                    if bearing_change < 0.0:
                        bearing_change += 360.0
                    else:
                        bearing_change -= 360.0
                time_change = (self.fixes[prev_fix].timestamp -
                               self.fixes[curr_fix].timestamp)
                change_rate = bearing_change/time_change
                self.fixes[curr_fix].bearing_change_rate = change_rate

    def _circling_emissions(self):
        """Generates raw circling/straight emissions from bearing change.

        Staight flight is encoded as 0, circling is encoded as 1. Exported
        to a separate function to be used in Baum-Welch parameters learning.
        """
        emissions = []
        for fix in self.fixes:
            bearing_change = math.fabs(fix.bearing_change_rate)
            bearing_change_enough = (
                bearing_change > self._config.min_bearing_change_circling)
            if fix.flying and bearing_change_enough:
                emissions.append(1)
            else:
                emissions.append(0)
        return emissions

    def _compute_circling(self):
        """Adds .circling to self.fixes."""
        emissions = self._circling_emissions()
        decoder = lib.viterbi.SimpleViterbiDecoder(
            # More likely to start in straight flight than in circling
            init_probs=[0.80, 0.20],
            transition_probs=[
                [0.982, 0.018],  # transitions from straight flight
                [0.030, 0.970],  # transitions from circling
            ],
            emission_probs=[
                [0.942, 0.058],  # emissions from straight flight
                [0.093, 0.907],  # emissions from circling
            ])

        output = decoder.decode(emissions)

        for i in xrange(len(self.fixes)):
            self.fixes[i].circling = (output[i] == 1)

    def _find_thermals(self):
        """Go through the fixes and find the thermals.

        Every point not in a thermal is put into a glide.If we get to end of
        the fixes and there is still an open glide (i.e. flight not finishing
        in a valid thermal) the glide will be closed.
        """
        takeoff_index = self.takeoff_fix.index
        landing_index = self.landing_fix.index
        flight_fixes = self.fixes[takeoff_index:landing_index + 1]

        self.thermals = []
        self.glides = []
        circling_now = False
        gliding_now = False
        first_fix = None
        first_glide_fix = None
        last_glide_fix = None
        distance = 0.0
        for fix in flight_fixes:
            if not circling_now and fix.circling:
                # Just started circling
                circling_now = True
                first_fix = fix
                distance_start_circling = distance
            elif circling_now and not fix.circling:
                # Just ended circling
                circling_now = False
                thermal = Thermal(first_fix, fix)
                if (thermal.time_change() >
                        self._config.min_time_for_thermal - 1e-5):
                    self.thermals.append(thermal)
                    # glide ends at start of thermal
                    glide = Glide(first_glide_fix, first_fix,
                                  distance_start_circling)
                    self.glides.append(glide)
                    gliding_now = False

            if gliding_now:
                distance = distance + fix.distance_to(last_glide_fix)
                last_glide_fix = fix
            else:
                # just started gliding
                first_glide_fix = fix
                last_glide_fix = fix
                gliding_now = True
                distance = 0.0

        if gliding_now:
            glide = Glide(first_glide_fix, last_glide_fix, distance)
            self.glides.append(glide)
