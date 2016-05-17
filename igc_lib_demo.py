#!/usr/bin/env python
import os
import sys

import igc_lib


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print "Please pass an .igc file in argv"
        sys.exit(1)

    input_file = sys.argv[1]
    input_base_file = os.path.splitext(input_file)[0]
    wpt_file = "%s-thermals.wpt" % input_base_file
    cup_file = "%s-thermals.cup" % input_base_file

    flight = igc_lib.Flight.create_from_file(input_file)
    print "flight =", flight
    print "fixes[0] =", flight.fixes[0]
    for x, (thermal, glide) in enumerate(zip(flight.thermals, flight.glides)):
        print "glide[%d] " % x, glide
        print "thermals[%d] = " % x, thermal

    print "Dumping thermals to %s and %s" % (wpt_file, cup_file)
    flight.dump_thermals_to_wpt_file(wpt_file, True)
    flight.dump_thermals_to_cup_file(cup_file)
