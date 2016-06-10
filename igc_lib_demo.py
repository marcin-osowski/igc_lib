#!/usr/bin/env python
import os
import sys

import igc_lib
import dumpers


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print "Please pass an .igc file in argv"
        sys.exit(1)

    input_file = sys.argv[1]
    input_base_file = os.path.splitext(input_file)[0]
    wpt_file = "%s-thermals.wpt" % input_base_file
    cup_file = "%s-thermals.cup" % input_base_file
    thermals_csv_file = "%s-thermals.csv" % input_base_file
    flight_csv_file = "%s-flight.csv" % input_base_file
    kml_file = "%s-flight.kml" % input_base_file

    flight = igc_lib.Flight.create_from_file(input_file)
    print "flight =", flight
    print "fixes[0] =", flight.fixes[0]
    for x, (thermal, glide) in enumerate(zip(flight.thermals, flight.glides)):
        print "glide[%d] = " % x, glide
        print "thermals[%d] = " % x, thermal

    print "Dumping thermals to %s, %s and %s" % (wpt_file, cup_file, thermals_csv_file)
    dumpers.dump_thermals_to_wpt_file(flight, wpt_file, True)
    dumpers.dump_thermals_to_cup_file(flight, cup_file)

    print "Dumping flight to %s and %s" % (kml_file, flight_csv_file)
    dumpers.dump_flight_to_csv(flight, flight_csv_file, thermals_csv_file)
    dumpers.dump_flight_to_kml(flight, kml_file)
