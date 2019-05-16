#!/usr/bin/env python
from __future__ import print_function

import os
import sys

import igc_lib
import lib.dumpers as dumpers


def print_flight_details(flight):
    print("Flight:", flight)
    print("Takeoff:", flight.takeoff_fix)
    thermals = flight.thermals
    glides = flight.glides
    for i in range(max(len(thermals), len(glides))):
        if i < len(glides):
            print("  glide[%d]:" % i, glides[i])
        if i < len(thermals):
            print("  thermal[%d]:" % i, thermals[i])
    print("Landing:", flight.landing_fix)


def dump_flight(flight, input_file):
    input_base_file = os.path.splitext(input_file)[0]
    wpt_file = "%s-thermals.wpt" % input_base_file
    cup_file = "%s-thermals.cup" % input_base_file
    thermals_csv_file = "%s-thermals.csv" % input_base_file
    flight_csv_file = "%s-flight.csv" % input_base_file
    kml_file = "%s-flight.kml" % input_base_file

    print("Dumping thermals to %s, %s and %s" %
          (wpt_file, cup_file, thermals_csv_file))
    dumpers.dump_thermals_to_wpt_file(flight, wpt_file, True)
    dumpers.dump_thermals_to_cup_file(flight, cup_file)

    print("Dumping flight to %s and %s" % (kml_file, flight_csv_file))
    dumpers.dump_flight_to_csv(flight, flight_csv_file, thermals_csv_file)
    dumpers.dump_flight_to_kml(flight, kml_file)


def main():
    if len(sys.argv) < 2:
        print("Usage: %s file.igc [file.lkt]" % sys.argv[0])
        sys.exit(1)

    input_file = sys.argv[1]
    task_file = None
    if len(sys.argv) > 2:
        task_file = sys.argv[2]

    flight = igc_lib.Flight.create_from_file(input_file)
    if not flight.valid:
        print("Provided flight is invalid:")
        print(flight.notes)
        sys.exit(1)

    print_flight_details(flight)
    dump_flight(flight, input_file)

    if task_file:
        task = igc_lib.Task.create_from_lkt_file(task_file)
        reached_turnpoints = task.check_flight(flight)
        for t, fix in enumerate(reached_turnpoints):
            print("Turnpoint[%d] achieved at:" % t, fix.rawtime)


if __name__ == "__main__":
    main()
