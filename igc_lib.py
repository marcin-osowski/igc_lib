#!/usr/bin/env python
import math
import re
import datetime
import collections
from Bio.Alphabet import Alphabet
from Bio.HMM.MarkovModel import MarkovModelBuilder

import igc_lib_config

def sphere_distance(lat1, lon1, lat2, lon2):
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


def strip_non_printable_chars(string):
    """Filters a string removing non-printable characters.
    
    Args:
        string: A string to be filtered.

    Returns:
        A string, where non-printable characters are removed.
    """
    printable = set("0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKL"
                    "MNOPQRSTUVWXYZ!\"#$%&\'()*+,-./:;<=>?@[\\]^_`{|}~ ")
    return filter(lambda x: x in printable, string)


def rawtime_float_to_hms(timef):
    """Converts time from floating point seconds to hours/minutes/seconds.
    
    Args:
        timef: A floating point time in seconds to be converted
        
    Returns:
        A namedtuple with hours, minutes and seconds elements
    """
    time = int(round(timef))
    hms = collections.namedtuple('hms', ['hours', 'minutes', 'seconds'])
    
    return hms((time/3600), (time%3600)/60, time%60)

def degrees_float_to_degrees_minutes_seconds(dd):
    """Converts time from floating point degrees to degrees/minutes/floating point seconds.
    
    Args:
        dd: Floating point degrees to be converted
        
    Returns:
        A namedtuple with degrees, minutes and floating point seconds elements
    """
    ddmmss = collections.namedtuple('ddmmss', ['degrees', 'minutes', 'seconds'])
    negative = dd < 0
    dd = abs(dd)
    minutes,seconds = divmod(dd*3600,60)
    degrees,minutes = divmod(minutes,60)
    if negative:
        if degrees > 0:
            degrees = -degrees
        elif minutes > 0:
            minutes = -minutes
        else:
            seconds = -seconds
    return ddmmss(degrees,minutes,seconds)

class GNSSFix:
    """Stores single GNSS flight recorder fix (a B-record).

        Raw attributes:
            rawtime: a float, time since last midnight, UTC, seconds
            timestamp: a float, true timestamp (i.e. since epoch), UTC, seconds
            lat: a float, latitude in degrees
            lon: a float, longitude in degrees
            validity: a string, GPS validity information from flight recorder
            press_alt: a float, pressure altitude, meters
            gnss_alt: a float, GNSS altitude, meters
            extras: a string, B record extensions

        Derived attributes:
            alt: a float, either press_alt or gnss_alt
            gsp: a float, current ground speed, km/h
            bearing: a float, aircraft bearing, in degrees
            bearing_change_rate: a float, bearing change rate, degrees/second
            flying: a bool, whether this fix is during a flight
            circling: a bool, whether this fix is inside a thermal
    """
    @staticmethod
    def build_from_B_record(B_record_line):
        """Creates CNSSFix object from IGC B-record line."""
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
        return (("GNSSFix(rawtime=%02d:%02d:%02d, lat=%f, lon=%f, "
                 "validity=%s, press_alt=%.1f, gnss_alt=%.1f, extras=%s)") %
                    (rawtime_float_to_hms(self.rawtime) + (self.lat, self.lon,
                     self.validity, self.press_alt, self.gnss_alt, self.extras)))

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
        return igc_lib_config.EARTH_RADIUS_KM * sphere_distance(lat1, lon1, lat2, lon2)

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
    """Stores information about a single thermal in a flight.

    Attributes:
        enter_fix: a GNSSFix, entry point of the thermal
        exit_fix: a GNSSFix, exit point of the thermal
    """
    def __init__(self, enter_fix, exit_fix):
        self.enter_fix = enter_fix
        self.exit_fix = exit_fix

    def rawtime_change(self):
        """Returns the time spent in the thermal."""
        return self.exit_fix.rawtime - self.enter_fix.rawtime

    def alt_change(self):
        """Returns the altitude gained/lost in the thermal."""
        return self.exit_fix.alt - self.enter_fix.alt

    def vertical_velocity(self):
        """Returns average vertical velocity in the thermal."""
        if math.fabs(self.rawtime_change()) < 1e-7:
            return 0.0
        return self.alt_change() / self.rawtime_change()

    def acceptable(self):
        """Verifies the thermal against configured limits."""
        vv = self.vertical_velocity()
        if (vv > igc_lib_config.MAX_THERMAL_VERTICAL_VEL
            or vv < igc_lib_config.MIN_THERMAL_VERTICAL_VEL):
            return False
        return self.rawtime_change() >= igc_lib_config.MIN_RAWTIME_CIRCLING - 1e-5

    def __repr__(self):
        return self.__str__()

    def __str__(self):
        return ("Thermal(vertical_velocity=%.2f [m/s], enter=%s, exit=%s)" %
                     (self.vertical_velocity(), str(self.enter_fix), str(self.exit_fix)))
    
class Glide:

    def __init__(self, enter_fix, exit_fix, track_length):
        self.enter_fix = enter_fix
        self.exit_fix = exit_fix
        self.track_length = track_length

    def rawtime_change(self):
        return self.exit_fix.rawtime - self.enter_fix.rawtime
                               
    def speed(self):
        return self.track_length / (self.rawtime_change() / 3600.0)
       
    
    def alt_change(self):
        return self.enter_fix.alt - self.exit_fix.alt 
                               
    def glide_ratio(self):
        if math.fabs(self.rawtime_change()) < 1e-7:
            return 0.0
        return (self.track_length * 1000.0) / self.alt_change()
    
    def duration(self):
        hms = rawtime_float_to_hms(self.rawtime_change())
        return ("%d m %d s" % (hms.minutes, hms.seconds))
        

    
    def __repr__(self):
        return self.__str__()
 
    def __str__(self):
        return ("Glide (distance=%.2f km, speed =%.2f kph, average L/D = %.2f :1 duration= %s, start=%s, end=%s)" %
                     (self.track_length, self.speed(), self.glide_ratio(), self.duration(), str(self.enter_fix), str(self.exit_fix)))                                                                        
                                                                     
class Flight:
    """Parses IGC file, detects thermals and checks for record anomalies.

    Attributes (the list is not complete):
        fixes: a list of GNSSFix objects, one per each valid B record
        thermals: a list of Thermal objects, the detected thermals
        valid: a bool, whether the supplied record is considered valid
        notes: a list of strings, warnings and errors encountered while
        parsing/validating the file
    """

    @staticmethod
    def create_from_file(filename):
        """Creates an instance of Flight from a given file.

        Args:
            filename: A string, the name of the input IGC file.

        Returns:
            An instance of Flight built from the supplied IGC file.
        """
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
        flight = Flight(fixes, a_records, h_records, i_records)
        return flight

    def __init__(self, fixes, a_records, h_records, i_records):
        """Initializer of the Flight class. Do not use directly."""
        self.fixes = fixes
        self.valid = True
        self.notes = []
        if len(fixes) < igc_lib_config.MIN_FIXES:
            self.notes.append(
                "Error: This file has %d fixes, less than "
                "the minimum %d." % (len(fixes), igc_lib_config.MIN_FIXES))
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
        self.fr_manuf_code = strip_non_printable_chars(a_records[0][1:4])
        self.fr_uniq_id = strip_non_printable_chars(a_records[0][4:7])

    def _parse_i_records(self, i_records):
        """Parses the IGC I records.

        I records contain a description of extensions used in B records.
        """
        self.i_record = strip_non_printable_chars(" ".join(i_records))

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
                dd, mm, yy = map(strip_non_printable_chars, match.groups())
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
                (self.glider_type,) = map(strip_non_printable_chars, match.groups())
        elif record[0:5] == 'HFDTM':
            match = re.match(
                'HFDTM(\d\d\d)[ A-Z]*:[ ]*(.*)',
                record, flags=re.IGNORECASE)
            if match:
                code, name = map(strip_non_printable_chars, match.groups())
                self.fr_gps_datum = "%s-%s" % (code, name)
        elif record[0:5] == 'HFRFW' or record[0:5] == 'HFRHW':
            match = re.match(
                'HFR[FH]W[ ]*FIRMWARE[ ]*VERSION[ ]*:[ ]*(.*)',
                record, flags=re.IGNORECASE)
            if match:
                (self.fr_firmware_version,) = map(strip_non_printable_chars, match.groups())
            match = re.match(
                'HFR[FH]W[ ]*HARDWARE[ ]*VERSION[ ]*:[ ]*(.*)',
                record, flags=re.IGNORECASE)
            if match:
                (self.fr_hardware_version,) = map(strip_non_printable_chars, match.groups())
        elif record[0:5] == 'HFFTY':
            match = re.match(
                'HFFTY[ ]*FR[ ]*TYPE[ ]*:[ ]*(.*)',
                record, flags=re.IGNORECASE)
            if match:
                (self.fr_recorder_type,) = map(strip_non_printable_chars, match.groups())
        elif record[0:5] == 'HFGPS':
            match = re.match('HFGPS(?:[: ]|(?:GPS))*(.*)', record, flags=re.IGNORECASE)
            if match:
                (self.fr_gps_receiver,) = map(strip_non_printable_chars, match.groups())
        elif record[0:5] == 'HFPRS':
            match = re.match(
                'HFPRS[ ]*PRESS[ ]*ALT[ ]*SENSOR[ ]*:[ ]*(.*)',
                record, flags=re.IGNORECASE)
            if match:
                (self.fr_pressure_sensor,) = map(strip_non_printable_chars, match.groups())
        elif record[0:5] == 'HFCCL':
            match = re.match(
                'HFCCL[ ]*COMPETITION[ ]*CLASS[ ]*:[ ]*(.*)',
                record, flags=re.IGNORECASE)
            if match:
                (self.competition_class,) = map(strip_non_printable_chars, match.groups())

    def __str__(self):
        descr = "Flight(valid=%s, fixes: %d" % (str(self.valid), len(self.fixes))
        if self.__dict__.get('thermals', None) is not None:
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
                if press_alt_delta / rawtime_delta > igc_lib_config.MAX_PRESS_ALT_CHANGE:
                    press_huge_changes_num += 1
                else:
                    press_chgs_sum += press_alt_delta 
                if gnss_alt_delta / rawtime_delta > igc_lib_config.MAX_GNSS_ALT_CHANGE:
                    gnss_huge_changes_num += 1
                else:
                    gnss_chgs_sum += gnss_alt_delta
            if (self.fixes[i].press_alt > igc_lib_config.MAX_PRESS_ALT
                or self.fixes[i].press_alt < igc_lib_config.MIN_PRESS_ALT):
                press_alt_violations_num += 1
            if (self.fixes[i].gnss_alt > igc_lib_config.MAX_GNSS_ALT
                or self.fixes[i].gnss_alt < igc_lib_config.MIN_GNSS_ALT):
                gnss_alt_violations_num += 1
        press_chgs_avg = press_chgs_sum / float(len(self.fixes) - 1)
        gnss_chgs_avg = gnss_chgs_sum / float(len(self.fixes) - 1)

        press_alt_ok = True
        if press_chgs_avg < igc_lib_config.MIN_PRESS_ALT_CHANGE:
            self.notes.append(
                "Warning: average pressure altitude change between fixes is: %f. "
                "It is lower than the minimum: %f"
                    % (press_chgs_avg, igc_lib_config.MIN_PRESS_ALT_CHANGE))
            press_alt_ok = False

        if press_huge_changes_num > igc_lib_config.MAX_PRESS_ALT_CHANGE_NUM:
            self.notes.append(
                "Warning: too many high changes in pressure altitude: %d. "
                "Maximum allowed: %d."
                    % (press_huge_changes_num, igc_lib_config.MAX_PRESS_ALT_CHANGE_NUM))
            press_alt_ok = False

        if press_alt_violations_num > igc_lib_config.ALLOWED_PRESS_ALT_VIOLATION_NUM:
            self.notes.append(
                "Warning: too many fixes exceed pressure alt limits: %d. "
                "Maximum allowed: %d."
                    % (press_alt_violations_num, igc_lib_config.ALLOWED_PRESS_ALT_VIOLATION_NUM))
            press_alt_ok = False

        gnss_alt_ok = True
        if gnss_chgs_avg < igc_lib_config.MIN_GNSS_ALT_CHANGE:
            self.notes.append(
                "Warning: average gnss altitude change between fixes is: %f. "
                "It is lower than the minimum: %f."
                    % (gnss_chgs_avg, igc_lib_config.MIN_GNSS_ALT_CHANGE))
            gnss_alt_ok = False

        if gnss_huge_changes_num > igc_lib_config.MAX_GNSS_ALT_CHANGE_NUM:
            self.notes.append(
                "Warning: too many high changes in gnss altitude: %d. "
                "Maximum allowed: %d."
                    % (gnss_huge_changes_num, igc_lib_config.MAX_GNSS_ALT_CHANGE_NUM))
            gnss_alt_ok = False

        if gnss_alt_violations_num > igc_lib_config.ALLOWED_GNSS_ALT_VIOLATION_NUM:
            self.notes.append(
                "Warning: too many fixes exceed gnss alt limits: %d. "
                "Maximum allowed: %d."
                    % (gnss_alt_violations_num, igc_lib_config.ALLOWED_GNSS_ALT_VIOLATION_NUM))
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

            if f0.rawtime > f1.rawtime and f1.rawtime + DAY < f0.rawtime + 200.0:
                # Day switch
                days_added += 1
                rawtime_to_add += DAY
                f1.rawtime += DAY

            if not (igc_lib_config.MIN_RAWTIME_BETWEEN_FIXES < f1.rawtime - f0.rawtime + 1e-5 and
                    igc_lib_config.MAX_RAWTIME_BETWEEN_FIXES > f1.rawtime - f0.rawtime - 1e-5):
                rawtime_between_fix_exceeded += 1

        if rawtime_between_fix_exceeded > igc_lib_config.MAX_RAWTIME_BETWEEN_FIX_EXCEED:
            self.notes.append(
                "Error: too many fixes intervals exceed rawtime constraints. "
                " Allowed %d fixes, found %d fixes."
                    % (igc_lib_config.MAX_RAWTIME_BETWEEN_FIX_EXCEED, rawtime_between_fix_exceeded))
            self.valid = False
        if days_added > igc_lib_config.MAX_NEW_DAYS_IN_FLIGHT:
            self.notes.append(
                "Error: too many rawtimes the flight crossed UTC 0:00 barrier. "
                "Allowed %d times, found %d times."
                    % (igc_lib_config.MAX_NEW_DAYS_IN_FLIGHT, days_added))
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
        """Adds boolean flag .flying to self.fixes, and chooses takeoff/landing fixes."""
        flight_list = []
        for fix in self.fixes:
            if fix.gsp > igc_lib_config.MIN_GSP_FLIGHT:
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
        Therefore we compute rates between points that are at least X seconds
        apart.
        """
        def find_prev_fix(curr_fix):
            """Computes the previous fix to be used in bearing rate change calculation."""
            prev_fix = None
            for i in xrange(curr_fix - 1, 0, -1):
                time_dist = math.fabs(self.fixes[curr_fix].timestamp
                    - self.fixes[i].timestamp)
                if time_dist + 1e-7 > igc_lib_config.FIX_TIME_DIST_FOR_CIRCLING:
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
                rawtime_change = self.fixes[prev_fix].rawtime - self.fixes[curr_fix].rawtime
                self.fixes[curr_fix].bearing_change_rate = bearing_change/rawtime_change

    def _compute_circling(self):
        """Adds .circling to self.fixes."""
        rate_change_list = []
        for fix in self.fixes:
            bearing_change_enough = (
                math.fabs(fix.bearing_change_rate) > igc_lib_config.DEG_PER_SEC_MIN_FOR_CIRCLING)
            if fix.flying and bearing_change_enough:
                rate_change_list.append('C')
            else:
                rate_change_list.append('S')

        state_alphabet = Alphabet()
        state_alphabet.letters = list("cs")
        emissions_alphabet = Alphabet()
        emissions_alphabet.letters = list("CS")

        mmb = MarkovModelBuilder(state_alphabet, emissions_alphabet)
        mmb.set_initial_probabilities({'c': 0.0971, 's': 0.9029})
        mmb.allow_all_transitions()
        mmb.set_transition_score('c', 'c', 0.9402)
        mmb.set_transition_score('c', 's', 0.0598)
        mmb.set_transition_score('s', 'c', 0.0539)
        mmb.set_transition_score('s', 's', 0.9461)
        mmb.set_emission_score('c', 'C', 0.8128)
        mmb.set_emission_score('c', 'S', 0.1872)
        mmb.set_emission_score('s', 'C', 0.1601)
        mmb.set_emission_score('s', 'S', 0.8399)
        mm = mmb.get_markov_model()

        (output, score) = mm.viterbi(rate_change_list, state_alphabet)

        for i in xrange(len(self.fixes)):
            self.fixes[i].circling = (output[i] == 'c')

    def _find_thermals(self):
        """Goes through the fixes and finds the thermals.
        
        Every point not in a thermal is put into a glide.
        
        If we get to end of the fixes and there is still an open glide (i.e. flight not finishing in a valid thermal)
        the glide will be closed. 
        """
        self.thermals = []
        self.glides = []
        circling_now = False
        gliding_now = False
        first_fix = None
        first_glide_fix = None
        last_glide_fix = None
        distance = 0.0# if we get to end of self.fixes and there is still an open glide (i.e. flight not finishing in a valid thermal)
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
                if thermal.acceptable():
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
            
    def dump_thermals_to_wpt_file(self,wptfilename, endpoints=False): 
        """Converts time from floating point seconds to hours/minutes/seconds.
    
    
        Args:
            wptfilename: File to be written. If it exists it will be overwritten.
            endpoints: optional argument. If true thermal endpoints as well as startpoints will be written with suffix END in the waypoint label
               
        """
    #write a .wpt file in Geo format with the thermal start locations as waypoints. Optional flag to also record end loctions
        with open(wptfilename, 'w') as wpt:
            wpt.write("$FormatGEO\n")
            
            for x, thermal in enumerate(self.thermals):
                lat = degrees_float_to_degrees_minutes_seconds(self.thermals[x].enter_fix.lat)
                lon = degrees_float_to_degrees_minutes_seconds(self.thermals[x].enter_fix.lon)
                wpt.write("%02d        " % x)
                wpt.write("N %02d %02d %05.2f    " % (lat.degrees, lat.minutes, lat.seconds))
                wpt.write("E %03d %02d %05.2f     " % (lon.degrees, lon.minutes, lon.seconds))
                wpt.write("          %d\n" % self.thermals[x].enter_fix.gnss_alt)
                
                if endpoints:
                    lat = degrees_float_to_degrees_minutes_seconds(self.thermals[x].exit_fix.lat)
                    lon = degrees_float_to_degrees_minutes_seconds(self.thermals[x].exit_fix.lon)
                    wpt.write("%02dEND     " % x)
                    wpt.write("N %02d %02d %05.2f    " % (lat.degrees, lat.minutes, lat.seconds))
                    wpt.write("E %03d %02d %05.2f     " % (lon.degrees, lon.minutes, lon.seconds))
                    wpt.write("          %d\n" % self.thermals[x].exit_fix.gnss_alt)
                    
                               
            

if __name__ == "__main__":
    import sys
    if len(sys.argv) != 2:
        print "Please pass an .igc file in argv"
    wptfilename = "thermals.wpt"
    flight = Flight.create_from_file(sys.argv[1])
    print "flight =", flight
    print "fixes[0] =", flight.fixes[0]
    x = 0
    flight.dump_thermals_to_wpt_file(wptfilename,True)
    for x, thermal in enumerate(flight.thermals):
       
        print "glide[%d] " % x, flight.glides[x]
        print "thermals[%d] = " % x, flight.thermals[x]
        
 
   
