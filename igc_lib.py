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
from Bio.Alphabet import Alphabet
from Bio.HMM.MarkovModel import MarkovModelBuilder
from xml.dom.minidom import parse
import xml.dom.minidom
from collections import defaultdict

EARTH_RADIUS_KM=6371.0


def _sphere_distance(lat1, lon1, lat2, lon2):
    """Computes the great circle distance on a unit sphere.

    All angles and the return value are in radians.

    Args:
        lat1: A float, latitude of the first point.
        lon1: A float, longitude of the first point.
        lat2: A float, latitude of the second point.
        lon2: A float, latitude of the second point.

    Returns:
        The computed great circle distance on a sphere.
    """
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
    return 2.0 * math.asin(math.sqrt(a))


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

    return hms((time/3600), (time%3600)/60, time%60)

class Turnpoint:
    """ single turnpoint in a task.
    
    Attributes: 
        lat: latitude as a float in degrees DD.DD
        lon: longitude as a float in degrees DD.DD
        radius: radius of cylinder or line in km
        sort: type of turnpoint; start_exit, start_enter, cylinder, ESS, goal_cylinder, goal_line
        
    """
    def __init__(self, lat, lon, radius, sort):
        self.lat = lat
        self.lon = lon
        self.radius = radius
        self.sort = sort
        

    def in_radius(self, fix):
        """Computes great circle distance in kilometers to a GNSSFix.
        returns true if the fix is within the radius"""
        lat1, lon1, lat2, lon2 = map(math.radians, [self.lat, self.lon, fix.lat, fix.lon])
        
        if (EARTH_RADIUS_KM * _sphere_distance(lat1, lon1, lat2, lon2)) < self.radius:
            return True
        else:
            return False
        
        
class Task:
    
    
    @staticmethod
    def create_from_lkt_file(filename):
        """ Creates Task from LK8000 task file, which is in xml format.
            LK8000 does not have ESS or task finish time.
            For the goal, at the moment, Turnpoints can't handle goal cones or lines, for this reason we default to goal_cylinder.
        """
        
        turnpoints = []
                
        # Open XML document using minidom parser
        DOMTree = xml.dom.minidom.parse(filename)
        task = DOMTree.documentElement

        # Get the taskpoints, waypoints and time gate
        taskpoints = task.getElementsByTagName("taskpoints")[0]
        waypoints = task.getElementsByTagName("waypoints")[0]
        gate = task.getElementsByTagName("time-gate")[0]

        tpoints = taskpoints.getElementsByTagName("point")

        wpoints = waypoints.getElementsByTagName("point")

        start_time = gate.getAttribute("open-time")

        start_time = int(start_time.split(':')[0])*3600 + int(start_time.split(':')[1])*60
        
        #create a dictionary of names and a list of longitudes and latitudes as the waypoints co-ordinates are stored separate to turnpoint details
        coords = defaultdict(list)
        
        for point in wpoints:    
            coords[point.getAttribute("name")].append(float(point.getAttribute("longitude")))
            coords[point.getAttribute("name")].append(float(point.getAttribute("latitude")))
            
        # create list of turnpoints    
        for point in tpoints:
            lat = coords[point.getAttribute("name")][1]
            lon = coords[point.getAttribute("name")][0]
            radius = float(point.getAttribute("radius"))/1000
            
            if point.getAttribute("idx") == "0":
                if point.getAttribute("Exit") == "true":
                    sort = "start_exit"
                else:
                    sort = "start_enter"
            else:
                if point == tpoints[-1]:   # if it is the last turnpoint i.e. the goal
                    if point.getAttribute("type") == "line":
                        sort = "goal_cylinder"     # to change one line can be processed.
                    else:
                        sort = "goal_cylinder"
                else:
                    sort = "cylinder"
            
                      
            turnpoint = Turnpoint(lat, lon, radius, sort)
            turnpoints.append(turnpoint)
        task = Task(turnpoints, start_time)
        return task
    
    
    def __init__(self, turnpoints, start_time, end_time=86399):  #finish_time defaults to 23:59
        self.turnpoints = turnpoints
        self.start_time = start_time
        self.end_time = end_time
        
        
        
    def check_flight(self, flight):
        """ Checks a flight object against the task. 
            Args:
                   flight: a flight object
            Returns:
                    a list of rawtimes of when turnpoints were achieved.
            
        """
        turnpoint_times = []   
    
        proceed_to_start = False
        t=0
        
        for fix in flight.fixes:
        
            
                if self.turnpoints[t].sort == "start_exit": #pilot must have at least 1 fix inside the start after the start time then exit
                    if proceed_to_start:
                        if not self.turnpoints[t].in_radius(fix):
                            turnpoint_times.append(fix.rawtime)  #pilot has started
                            t += 1
                    if fix.rawtime > self.start_time and not proceed_to_start:
                        if self.turnpoints[t].in_radius(fix):
                            proceed_to_start = True         #pilot is inside start after the start time.
                        
                if self.turnpoints[t].sort == "start_enter":  #pilot must have at least 1 fix outside the start after the start time then enter
                    if proceed_to_start:
                        if self.turnpoints[t].in_radius(fix):
                            turnpoint_times.append(fix.rawtime)  #pilot has started
                            t += 1
                    if fix.rawtime > self.start_time and not proceed_to_start:   
                        if not self.turnpoints[t].in_radius(fix):
                            proceed_to_start = True         #pilot is outside start after the start time.    
            
                if self.turnpoints[t].sort in ["cylinder", "ESS", "goal_cylinder"]:
                    if self.turnpoints[t].in_radius(fix):
                            turnpoint_times.append(fix.rawtime)  #pilot has achieved turnpoint
                            t += 1
                                                  
                            if t >= len(self.turnpoints):
                                break  # pilot has arrived in goal (last turnpoint) so we can stop.
        return turnpoint_times       
        
    
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
        timestamp: a float, true timestamp (since epoch), UTC, seconds
        alt: a float, either press_alt or gnss_alt
        gsp: a float, current ground speed, km/h
        bearing: a float, aircraft bearing, in degrees
        bearing_change_rate: a float, bearing change rate, degrees/second
        flying: a bool, whether this fix is during a flight
        circling: a bool, whether this fix is inside a thermal
    """

    @staticmethod
    def build_from_B_record(B_record_line):
        """Creates GNSSFix object from IGC B-record line.

        Args:
            B_record_line: a string, B record line from an IGC file

        Returns:
            The created GNSSFix object
        """
        match = re.match('^B' + '(\d\d)(\d\d)(\d\d)' + '(\d\d)(\d\d)(\d\d\d)([NS])'
                              + '(\d\d\d)(\d\d)(\d\d\d)([EW])' + '([AV])'
                              + '([-\d]\d\d\d\d)' + '([-\d]\d\d\d\d)'
                              + '([0-9a-zA-Z]*).*$', B_record_line)
        if match is None:
            return None
        (hours, minutes, seconds,
         lat_deg, lat_min, lat_min_dec, lat_sign,
         lon_deg, lon_min, lon_min_dec, lon_sign,
         validity, press_alt, gnss_alt, extras) = match.groups()

        rawtime = (float(hours)*60.0 + float(minutes))*60.0 + float(seconds)

        lat = float(lat_deg) + (float(lat_min) + float(lat_min_dec)/1000.0)/60.0
        if lat_sign == 'S':
            lat = -lat

        lon = float(lon_deg) + (float(lon_min) + float(lon_min_dec)/1000.0)/60.0
        if lon_sign == 'W':
            lon = -lon

        press_alt = float(press_alt)
        gnss_alt = float(gnss_alt)

        return GNSSFix(rawtime, lat, lon, validity, press_alt, gnss_alt, extras)

    def __init__(self, rawtime, lat, lon, validity, press_alt, gnss_alt, extras):
        """Initializer of GNSSFix. Not meant to be used directly."""
        self.rawtime = rawtime
        self.lat = lat
        self.lon = lon
        self.validity = validity
        self.press_alt = press_alt
        self.gnss_alt = gnss_alt
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
        return (("GNSSFix(rawtime=%02d:%02d:%02d, lat=%f, lon=%f, altitide=%.1f)") %
                    (_rawtime_float_to_hms(self.rawtime)
                     + (self.lat, self.lon, self.alt)))

    def bearing_to(self, other):
        """Computes bearing in degrees to another GNSSFix."""
        lat1, lon1, lat2, lon2 = map(math.radians, [self.lat, self.lon, other.lat, other.lon])
        dLon = lon2 - lon1
        y = math.sin(dLon) * math.cos(lat2)
        x = (math.cos(lat1) * math.sin(lat2)
              - math.sin(lat1) * math.cos(lat2) * math.cos(dLon))
        return math.degrees(math.atan2(y, x))

    def distance_to(self, other):
        """Computes great circle distance in kilometers to another GNSSFix."""
        lat1, lon1, lat2, lon2 = map(math.radians, [self.lat, self.lon, other.lat, other.lon])
        return EARTH_RADIUS_KM * _sphere_distance(lat1, lon1, lat2, lon2)

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

        return (("B")
                  + ("%02d%02d%02d" % (hours, minutes, seconds))
                  + ("%02d%02d%03d%s" % (lat_deg, lat_min, lat_min_dec, lat_sign))
                  + ("%03d%02d%03d%s" % (lon_deg, lon_min, lon_min_dec, lon_sign))
                  + (validity)
                  + ("%05d%05d" % (press_alt, gnss_alt))
                  + (extras))


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
        return ("Glide(dist=%.2f km, avg_speed=%.2f kph, avg L/D=%.2f duration=%dm %ds)" %
                (self.track_length, self.speed(), self.glide_ratio(), hms.minutes, hms.seconds))


class FlightParsingConfig(object):
    """Configuration for parsing an IGC file.

    Defines a set of parameters used to validate a file, and to detect
    thermals and flight mode. Details in individual functions.
    """

    # Flight validation options/limits.
    def min_fixes(self):
        """Minimum number of fixes in a file."""
        return 50

    def max_seconds_between_fixes(self):
        """Maximum time between fixes, seconds.

        Soft limit, some fixes are allowed to exceed."""
        return 30.0

    def min_seconds_between_fixes(self):
        """Minimum time between fixes, seconds.

        Soft limit, some fixes are allowed to exceed."""
        return 1.0

    def max_time_violations(self):
        """Maximum number of fixes exceeding time between fix constraints."""
        return 10

    def max_new_days_in_flight(self):
        """Maximum number of times a file can cross the 0:00 UTC time."""
        return 2

    def min_avg_abs_alt_change(self):
        """Minimum average of absolute values of altitude changes in a file.

        This is needed to discover altitude sensors (either pressure or
        gps) that report either always constant altitude, or almost
        always constant altitude, and therefore are invalid. The unit
        is meters/fix.
        """
        return 0.01

    def max_alt_change_rate(self):
        """Maximum altitude change per second between fixes, meters per second.

        Soft limit, some fixes are allowed to exceed."""
        return 50.0

    def max_alt_change_violations(self):
        """Maximum number of fixes that can exceed the altitude change limit."""
        return 3

    def max_alt(self):
        """Absolute maximum altitude, meters."""
        return 10000.0

    def min_alt(self):
        """Absolute minimum altitude, meters."""
        return -600.0

    # Thermals and flight detection parameters.
    def min_gsp_flight(self):
        """Minimum ground speed to switch to flight mode, km/h."""
        return 20.0

    def min_bearing_change_circling(self):
        """Minimum bearing change to enter a thermal, deg/sec."""
        return 6.0

    def min_time_for_bearing_change(self):
        """Minimum time between fixes to calculate bearing change, seconds.

        See the usage for a more detailed comment on why this is useful.
        """
        return 5.0

    def min_time_for_thermal(self):
        """Minimum time to consider circling a thermal, seconds."""
        return 60.0


class Flight:
    """Parses IGC file, detects thermals and checks for record anomalies.

    Before using an instance of Flight check the `valid` attribute. An
    invalid Flight instance is not usable.

    General sttributes:
        valid: a bool, whether the supplied record is considered valid
        notes: a list of strings, warnings and errors encountered while
        parsing/validating the file
        fixes: a list of GNSSFix objects, one per each valid B record
        thermals: a list of Thermal objects, the detected thermals
        glides: a list of Glide objects, the glides between thermals

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
                    fix = GNSSFix.build_from_B_record(line)
                    if fix is not None:
                        fixes.append(fix)
                elif line[0] == 'I':
                    i_records.append(line)
                elif line[0] == 'H':
                    h_records.append(line)
                else:
                    pass # Do not parse any other types of IGC records
        flight = Flight(fixes, a_records, h_records, i_records, config)
        return flight

    def __init__(self, fixes, a_records, h_records, i_records, config):
        """Initializer of the Flight class. Do not use directly."""
        self.config = config
        self.fixes = fixes
        self.valid = True
        self.notes = []
        if len(fixes) < self.config.min_fixes():
            self.notes.append(
                "Error: This file has %d fixes, less than "
                "the minimum %d." % (len(fixes), self.config.min_fixes()))
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
            self.notes.append("Error: neither pressure nor gnss altitude is valid.")
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
            match = re.match('HFDTE(\d\d)(\d\d)(\d\d)', record, flags=re.IGNORECASE)
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
                (self.glider_type,) = map(_strip_non_printable_chars, match.groups())
        elif record[0:5] == 'HFRFW' or record[0:5] == 'HFRHW':
            match = re.match(
                'HFR[FH]W[ ]*FIRMWARE[ ]*VERSION[ ]*:[ ]*(.*)',
                record, flags=re.IGNORECASE)
            if match:
                (self.fr_firmware_version,) = map(_strip_non_printable_chars, match.groups())
            match = re.match(
                'HFR[FH]W[ ]*HARDWARE[ ]*VERSION[ ]*:[ ]*(.*)',
                record, flags=re.IGNORECASE)
            if match:
                (self.fr_hardware_version,) = map(_strip_non_printable_chars, match.groups())
        elif record[0:5] == 'HFFTY':
            match = re.match(
                'HFFTY[ ]*FR[ ]*TYPE[ ]*:[ ]*(.*)',
                record, flags=re.IGNORECASE)
            if match:
                (self.fr_recorder_type,) = map(_strip_non_printable_chars, match.groups())
        elif record[0:5] == 'HFGPS':
            match = re.match('HFGPS(?:[: ]|(?:GPS))*(.*)', record, flags=re.IGNORECASE)
            if match:
                (self.fr_gps_receiver,) = map(_strip_non_printable_chars, match.groups())
        elif record[0:5] == 'HFPRS':
            match = re.match(
                'HFPRS[ ]*PRESS[ ]*ALT[ ]*SENSOR[ ]*:[ ]*(.*)',
                record, flags=re.IGNORECASE)
            if match:
                (self.fr_pressure_sensor,) = map(_strip_non_printable_chars, match.groups())
        elif record[0:5] == 'HFCCL':
            match = re.match(
                'HFCCL[ ]*COMPETITION[ ]*CLASS[ ]*:[ ]*(.*)',
                record, flags=re.IGNORECASE)
            if match:
                (self.competition_class,) = map(_strip_non_printable_chars, match.groups())

    def __str__(self):
        descr = "Flight(valid=%s, fixes: %d" % (str(self.valid), len(self.fixes))
        if hasattr(self, 'thermals'):
            descr += ", thermals: %d" % len(self.thermals)
        descr += ")"
        return descr

    def _check_altitudes(self):
        press_alt_violations_num = 0;
        gnss_alt_violations_num = 0;
        press_huge_changes_num = 0;
        gnss_huge_changes_num = 0;
        press_chgs_sum = 0.0
        gnss_chgs_sum = 0.0
        for i in xrange(len(self.fixes) - 1):
            press_alt_delta = math.fabs(self.fixes[i+1].press_alt - self.fixes[i].press_alt)
            gnss_alt_delta = math.fabs(self.fixes[i+1].gnss_alt - self.fixes[i].gnss_alt)
            rawtime_delta = math.fabs(self.fixes[i+1].rawtime - self.fixes[i].rawtime)
            if rawtime_delta > 0.5:
                if press_alt_delta / rawtime_delta > self.config.max_alt_change_rate():
                    press_huge_changes_num += 1
                else:
                    press_chgs_sum += press_alt_delta
                if gnss_alt_delta / rawtime_delta > self.config.max_alt_change_rate():
                    gnss_huge_changes_num += 1
                else:
                    gnss_chgs_sum += gnss_alt_delta
            if (self.fixes[i].press_alt > self.config.max_alt()
                or self.fixes[i].press_alt < self.config.min_alt()):
                press_alt_violations_num += 1
            if (self.fixes[i].gnss_alt > self.config.max_alt()
                or self.fixes[i].gnss_alt < self.config.min_alt()):
                gnss_alt_violations_num += 1
        press_chgs_avg = press_chgs_sum / float(len(self.fixes) - 1)
        gnss_chgs_avg = gnss_chgs_sum / float(len(self.fixes) - 1)

        press_alt_ok = True
        if press_chgs_avg < self.config.min_avg_abs_alt_change():
            self.notes.append(
                "Warning: average pressure altitude change between fixes is: %f. "
                "It is lower than the minimum: %f."
                    % (press_chgs_avg, self.config.min_avg_abs_alt_change()))
            press_alt_ok = False

        if press_huge_changes_num > self.config.max_alt_change_violations():
            self.notes.append(
                "Warning: too many high changes in pressure altitude: %d. "
                "Maximum allowed: %d."
                    % (press_huge_changes_num, self.config.max_alt_change_violations()))
            press_alt_ok = False

        if press_alt_violations_num > 0:
            self.notes.append(
                "Warning: pressure altitude limits exceeded in %d fixes."
                    % (press_alt_violations_num))
            press_alt_ok = False

        gnss_alt_ok = True
        if gnss_chgs_avg < self.config.min_avg_abs_alt_change():
            self.notes.append(
                "Warning: average gnss altitude change between fixes is: %f. "
                "It is lower than the minimum: %f."
                    % (gnss_chgs_avg, self.config.min_avg_abs_alt_change()))
            gnss_alt_ok = False

        if gnss_huge_changes_num > self.config.max_alt_change_violations():
            self.notes.append(
                "Warning: too many high changes in gnss altitude: %d. "
                "Maximum allowed: %d."
                    % (gnss_huge_changes_num, self.config.max_alt_change_violations()))
            gnss_alt_ok = False

        if gnss_alt_violations_num > 0:
            self.notes.append(
                "Warning: gnss altitude limits exceeded in %d fixes."
                    % (gnss_alt_violations_num))
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

            if f0.rawtime > f1.rawtime and f1.rawtime + DAY < f0.rawtime + 200.0:
                # Day switch
                days_added += 1
                rawtime_to_add += DAY
            f1.rawtime += rawtime_to_add

            time_change = f1.rawtime - f0.rawtime
            if time_change < self.config.min_seconds_between_fixes() - 1e-5:
                rawtime_between_fix_exceeded += 1
            if time_change > self.config.max_seconds_between_fixes() + 1e-5:
                rawtime_between_fix_exceeded += 1

        if rawtime_between_fix_exceeded > self.config.max_time_violations():
            self.notes.append(
                "Error: too many fixes intervals exceed time between fixes "
                "constraints. Allowed %d fixes, found %d fixes."
                    % (self.config.max_time_violations(),
                       rawtime_between_fix_exceeded))
            self.valid = False
        if days_added > self.config.max_new_days_in_flight():
            self.notes.append(
                "Error: too many times did the flight cross the UTC 0:00 "
                "barrier. Allowed %d times, found %d times."
                    % (self.config.max_new_days_in_flight(), days_added))
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

    def _compute_flight(self):
        """Adds boolean flag .flying to self.fixes."""
        flight_list = []
        for fix in self.fixes:
            if fix.gsp > self.config.min_gsp_flight():
                flight_list.append("F")
            else:
                flight_list.append("S")

        state_alphabet = Alphabet()
        state_alphabet.letters = list("fs")
        emissions_alphabet = Alphabet()
        emissions_alphabet.letters = list("FS")

        mmb = MarkovModelBuilder(state_alphabet, emissions_alphabet)
        mmb.set_initial_probabilities({'s': 0.5963, 'f': 0.4037})
        mmb.allow_all_transitions()
        mmb.set_transition_score('s', 's', 0.9999)
        mmb.set_transition_score('s', 'f', 0.0001)
        mmb.set_transition_score('f', 's', 0.0001)
        mmb.set_transition_score('f', 'f', 0.9999)
        mmb.set_emission_score('s', 'F', 0.0010)
        mmb.set_emission_score('s', 'S', 0.9990)
        mmb.set_emission_score('f', 'F', 0.9500)
        mmb.set_emission_score('f', 'S', 0.0500)
        mm = mmb.get_markov_model()

        (output, score) = mm.viterbi(flight_list, state_alphabet)

        for fix, output in zip(self.fixes, output):
            fix.flying = (output == 'f')

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
            """Computes the previous fix to be used in bearing rate change calculation."""
            prev_fix = None
            for i in xrange(curr_fix - 1, 0, -1):
                time_dist = math.fabs(self.fixes[curr_fix].timestamp
                    - self.fixes[i].timestamp)
                if time_dist + 1e-7 > self.config.min_time_for_bearing_change():
                    prev_fix = i
                    break
            return prev_fix

        for curr_fix in xrange(len(self.fixes)):
            prev_fix = find_prev_fix(curr_fix)

            if prev_fix is None:
                self.fixes[curr_fix].bearing_change_rate = 0.0
            else:
                bearing_change = self.fixes[prev_fix].bearing - self.fixes[curr_fix].bearing
                if math.fabs(bearing_change) > 180.0:
                    if bearing_change < 0.0:
                        bearing_change += 360.0
                    else:
                        bearing_change -= 360.0
                time_change = self.fixes[prev_fix].timestamp - self.fixes[curr_fix].timestamp
                self.fixes[curr_fix].bearing_change_rate = bearing_change/time_change

    def _circling_emissions(self):
        """Generates raw circling/straight emissions from bearing change."""
        emissions_list = []
        for fix in self.fixes:
            bearing_change = math.fabs(fix.bearing_change_rate)
            bearing_change_enough = (
                bearing_change > self.config.min_bearing_change_circling())
            if fix.flying and bearing_change_enough:
                emissions_list.append('C')
            else:
                emissions_list.append('S')
        return ''.join(emissions_list)

    def _compute_circling(self):
        """Adds .circling to self.fixes."""
        emissions = self._circling_emissions()

        state_alphabet = Alphabet()
        state_alphabet.letters = list("cs")
        emissions_alphabet = Alphabet()
        emissions_alphabet.letters = list("CS")

        mmb = MarkovModelBuilder(state_alphabet, emissions_alphabet)
        mmb.set_initial_probabilities({'c': 0.05, 's': 0.95})
        mmb.allow_all_transitions()
        mmb.set_transition_score('c', 'c', 0.970)
        mmb.set_transition_score('c', 's', 0.030)
        mmb.set_transition_score('s', 'c', 0.017)
        mmb.set_transition_score('s', 's', 0.983)
        mmb.set_emission_score('c', 'C', 0.902)
        mmb.set_emission_score('c', 'S', 0.098)
        mmb.set_emission_score('s', 'C', 0.061)
        mmb.set_emission_score('s', 'S', 0.939)
        mm = mmb.get_markov_model()

        (output, score) = mm.viterbi(emissions, state_alphabet)

        for i in xrange(len(self.fixes)):
            self.fixes[i].circling = (output[i] == 'c')

    def _find_thermals(self):
        """Goes through the fixes and finds the thermals.

        Every point not in a thermal is put into a glide.If we get to end of
        the fixes and there is still an open glide (i.e. flight not finishing
        in a valid thermal) the glide will be closed.
        """
        self.thermals = []
        self.glides = []
        circling_now = False
        gliding_now = False
        first_fix = None
        first_glide_fix = None
        last_glide_fix = None
        distance = 0.0
        for fix in self.fixes:
            if not circling_now and fix.circling:
                # Just started circling
                circling_now = True
                first_fix = fix
                distance_start_circling = distance
            elif circling_now and not fix.circling:
                # Just ended circling
                circling_now = False
                thermal = Thermal(first_fix, fix)
                if thermal.time_change() > self.config.min_time_for_thermal() - 1e-5:
                    self.thermals.append(thermal)
                    # glide ends at start of thermal
                    glide = Glide(first_glide_fix, first_fix, distance_start_circling)
                    self.glides.append(glide)
                    gliding_now = False

            if gliding_now:
                distance = distance + fix.distance_to(last_glide_fix)
                last_glide_fix = fix
            else:
                #just started gliding
                first_glide_fix = fix
                last_glide_fix = fix
                gliding_now = True
                distance = 0.0

        if gliding_now:
            glide = Glide(first_glide_fix, last_glide_fix, distance)
            self.glides.append(glide)

