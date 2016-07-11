#!/usr/bin/env python
import os
import sys

import igc_lib
import lib.dumpers


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print "Usage: %s file.igc [file.lkt]" % sys.argv[0]
        sys.exit(1)

    input_file = sys.argv[1]
    if len(sys.argv) > 2:
        task_file = sys.argv[2]

    input_base_file = os.path.splitext(input_file)[0]
    wpt_file = "%s-thermals.wpt" % input_base_file
    cup_file = "%s-thermals.cup" % input_base_file
    thermals_csv_file = "%s-thermals.csv" % input_base_file
    flight_csv_file = "%s-flight.csv" % input_base_file
    kml_file = "%s-flight.kml" % input_base_file

    flight = igc_lib.Flight.create_from_file(input_file)
    print "Flight:", flight
    if not flight.valid:
        print "Provided flight is invalid:"
        print flight.notes
        sys.exit(1)

    print "Takeoff:", flight.takeoff_fix
    for x, (thermal, glide) in enumerate(zip(flight.thermals, flight.glides)):
        print "  glide[%d]:" % x, glide
        print "  thermal[%d]:" % x, thermal
    print "Landing:", flight.landing_fix

    print "Dumping thermals to %s, %s and %s" % (
        wpt_file, cup_file, thermals_csv_file)
    lib.dumpers.dump_thermals_to_wpt_file(flight, wpt_file, True)
    lib.dumpers.dump_thermals_to_cup_file(flight, cup_file)

    print "Dumping flight to %s and %s" % (kml_file, flight_csv_file)
    lib.dumpers.dump_flight_to_csv(flight, flight_csv_file, thermals_csv_file)
    lib.dumpers.dump_flight_to_kml(flight, kml_file)

    if len(sys.argv) > 2:
        task = igc_lib.Task.create_from_lkt_file(task_file)
        reached_turnpoints = task.check_flight(flight)
        for t, fix in enumerate(reached_turnpoints):
            print "Turnpoint[%d] achieved at:" % t, fix.rawtime
