import collections
import simplekml
from pathlib2 import Path


def _degrees_float_to_degrees_minutes_seconds(dd, lon_or_lat):
    """Converts from floating point degrees to degrees/minutes/seconds.

    Args:
        dd: a float, degrees to be converted
        lon_or_lat: a string, argument used to calculate the hemisphere;
        options are 'lon' - for longitude or 'lat' - for latitude

    Returns:
        A namedtuple with hemisphere, degrees, minutes and floating point
        seconds elements.
    """
    ddmmss = collections.namedtuple(
        'ddmmss', ['hemisphere', 'degrees', 'minutes', 'seconds'])
    negative = dd < 0
    dd = abs(dd)
    minutes, seconds = divmod(dd * 3600, 60)
    degrees, minutes = divmod(minutes, 60)
    if lon_or_lat == 'lon':
        hemisphere = 'E'
    elif lon_or_lat == 'lat':
        hemisphere = 'N'

    if negative:
        if lon_or_lat == 'lon':
            hemisphere = 'W'
        elif lon_or_lat == 'lat':
            hemisphere = 'S'

    return ddmmss(hemisphere, degrees, minutes, seconds)


def dump_thermals_to_wpt_file(flight, wptfilename_local, endpoints=False):
    """Dump flight's thermals to a .wpt file in Geo format.

    Args:
        flight: an igc_lib.Flight, the flight to be written
        wptfilename_local: File to be written. If it exists it will be overwritten.
        endpoints: optional argument. If true thermal endpoints as well
        as startpoints will be written with suffix END in the waypoint label.
    """
    wptfilename = Path(wptfilename_local).expanduser().absolute()
    with wptfilename.open('w') as wpt:
        wpt.write(u"$FormatGEO\n")

        for x, thermal in enumerate(flight.thermals):
            lat = _degrees_float_to_degrees_minutes_seconds(
                flight.thermals[x].enter_fix.lat, 'lat')
            lon = _degrees_float_to_degrees_minutes_seconds(
                flight.thermals[x].enter_fix.lon, 'lon')
            wpt.write(u"%02d        " % x)
            wpt.write(u"%s %02d %02d %05.2f    " % (
                lat.hemisphere, lat.degrees, lat.minutes, lat.seconds))
            wpt.write(u"%s %03d %02d %05.2f     " % (
                lon.hemisphere, lon.degrees, lon.minutes, lon.seconds))
            wpt.write(u"          %d\n" % flight.thermals[x].enter_fix.gnss_alt)

            if endpoints:
                lat = _degrees_float_to_degrees_minutes_seconds(
                    flight.thermals[x].exit_fix.lat, 'lat')
                lon = _degrees_float_to_degrees_minutes_seconds(
                    flight.thermals[x].exit_fix.lon, 'lon')
                wpt.write(u"%02dEND     " % x)
                wpt.write(u"%s %02d %02d %05.2f    " % (
                    lat.hemisphere, lat.degrees, lat.minutes, lat.seconds))
                wpt.write(u"%s %03d %02d %05.2f     " % (
                    lon.hemisphere, lon.degrees, lon.minutes, lon.seconds))
                wpt.write(u"          %d\n" % (
                    flight.thermals[x].exit_fix.gnss_alt))


def dump_thermals_to_cup_file(flight, cup_filename_local):
    """Dump flight's thermals to a .cup file (SeeYou).

    Args:
        flight: an igc_lib.Flight, the flight to be written
        cup_filename_local: a string, the name of the file to be written.
    """
    cup_filename = Path(cup_filename_local).expanduser().absolute()
    with cup_filename.open('wt') as wpt:
        wpt.write(u'name,code,country,lat,')
        wpt.write(u'lon,elev,style,rwdir,rwlen,freq,desc,userdata,pics\n')

        def write_fix(name, fix):
            lat = _degrees_float_to_degrees_minutes_seconds(fix.lat, 'lat')
            lon = _degrees_float_to_degrees_minutes_seconds(fix.lon, 'lon')
            wpt.write(u'"%s",,,%02d%02d.%03d%s,' % (
                name, lat.degrees, lat.minutes,
                int(round(lat.seconds/60.0*1000.0)), lat.hemisphere))
            wpt.write(u'%03d%02d.%03d%s,%fm,,,,,,,' % (
                lon.degrees, lon.minutes,
                int(round(lon.seconds/60.0*1000.0)), lon.hemisphere,
                fix.gnss_alt))
            wpt.write(u'\n')

        for i, thermal in enumerate(flight.thermals):
            write_fix(u'%02d' % i, thermal.enter_fix)
            write_fix(u'%02d_END' % i, thermal.exit_fix)


def dump_flight_to_kml(flight, kml_filename_local):
    """Dumps the flight to KML format.

    Args:
        flight: an igc_lib.Flight, the flight to be saved
        kml_filename_local: a string, the name of the output file
    """
    assert flight.valid
    kml = simplekml.Kml()

    def add_point(name, fix):
        kml.newpoint(name=name, coords=[(fix.lon, fix.lat)])

    coords = []
    for fix in flight.fixes:
        coords.append((fix.lon, fix.lat))
    kml.newlinestring(coords=coords)

    add_point(name="Takeoff", fix=flight.takeoff_fix)
    add_point(name="Landing", fix=flight.landing_fix)

    for i, thermal in enumerate(flight.thermals):
        add_point(name="thermal_%02d" % i, fix=thermal.enter_fix)
        add_point(name="thermal_%02d_END" % i, fix=thermal.exit_fix)
        kml_filename = Path(kml_filename_local).expanduser().absolute()
    kml.save(kml_filename.as_posix())


def dump_flight_to_csv(flight, track_filename_local, thermals_filename_local):
    """Dumps flight data to CSV files.

    Args:
        flight: an igc_lib.Flight, the flight to be written
        track_filename_local: a string, the name of the output CSV with track data
        thermals_filename_local: a string, the name of the output CSV with thermal data
    """
    track_filename = Path(track_filename_local).expanduser().absolute()
    with track_filename.open('wt') as csv:
        csv.write(u"timestamp,lat,lon,bearing,bearing_change_rate,"
                  u"gsp,flying,circling\n")
        for fix in flight.fixes:
            csv.write(u"%f,%f,%f,%f,%f,%f,%s,%s\n" % (
                fix.timestamp, fix.lat, fix.lon,
                fix.bearing, fix.bearing_change_rate,
                fix.gsp, str(fix.flying), str(fix.circling)))

    thermals_filename = Path(thermals_filename_local).expanduser().absolute()
    with thermals_filename.open('wt') as csv:
        csv.write(u"timestamp_enter,timestamp_exit\n")
        for thermal in flight.thermals:
            csv.write(u"%f,%f\n" % (
                thermal.enter_fix.timestamp, thermal.exit_fix.timestamp))
