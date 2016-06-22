import math
import unittest

import geo


class TestSphereDistance(unittest.TestCase):

    def testAlongTheEquator(self):
        for lon_start in [0.0, 10.0, 20.0, 35.0]:
            for lon_end in [0.0, 5.0, 10.0, 45.0, 90.0, 180.0]:
                self.assertAlmostEqual(
                    geo.sphere_distance(
                        lat1=math.radians(0.0), lon1=math.radians(lon_start),
                        lat2=math.radians(0.0), lon2=math.radians(lon_end)),
                    math.radians(math.fabs(lon_start - lon_end)))

    def testEquatorToNorthPole(self):
        for lon in [0.0, 15.0, 45.0, 90.0, 180.0, 270.0]:
            self.assertAlmostEqual(
                geo.sphere_distance(
                    lat1=math.radians(0.0), lon1=math.radians(lon),
                    lat2=math.radians(90.0), lon2=math.radians(lon)),
                math.radians(90.0))

    def testNorthPoleToSouthPole(self):
        self.assertAlmostEqual(
            geo.sphere_distance(
                lat1=math.radians(90.0), lon1=math.radians(0.0),
                lat2=math.radians(-90.0), lon2=math.radians(0.0)),
            math.radians(180.0))

    def testFewExampleValues(self):
        self.assertAlmostEqual(
            geo.sphere_distance(
                lat1=math.radians(45.0), lon1=math.radians(10.0),
                lat2=math.radians(20.0), lon2=math.radians(15.0)),
            math.radians(25.34062553))

        self.assertAlmostEqual(
            geo.sphere_distance(
                lat1=math.radians(-19.0), lon1=math.radians(-3.0),
                lat2=math.radians(-20.0), lon2=math.radians(20.0)),
            math.radians(21.68698928))

        self.assertAlmostEqual(
            geo.sphere_distance(
                lat1=math.radians(-20.0), lon1=math.radians(10.0),
                lat2=math.radians(20.0), lon2=math.radians(-45.0)),
            math.radians(67.07642430))


class TestEarthDistance(unittest.TestCase):

    def testLondonToNewYork(self):
        self.assertAlmostEqual(
            geo.earth_distance(
                lat1=51.507222, lon1=-0.1275,
                lat2=40.7127, lon2=-74.0059),
            5570.24850942)

    def testHonoluluToKualaLumpur(self):
        self.assertAlmostEqual(
            geo.earth_distance(
                lat1=21.3, lon1=-157.816667,
                lat2=3.133333, lon2=101.683333),
            10964.7402894)

    def testSmallDistance(self):
        # Almost 10 meters
        self.assertAlmostEqual(
            geo.earth_distance(
                lat1=46.46338889, lon1=6.51755271,
                lat2=46.46339444, lon2=6.51768333),
            0.0100236)

    def testMediumDistance(self):
        # Almost 1000 meters
        self.assertAlmostEqual(
            geo.earth_distance(
                lat1=46.44307778, lon1=6.44688056,
                lat2=46.44813889, lon2=6.45766932),
            1.00000024)


class TestBearingTo(unittest.TestCase):

    def testEquatorToNorthPole(self):
        for lon in [0.0, 15.0, 45.0, 90.0, 180.0, 270.0]:
            self.assertAlmostEqual(
                geo.bearing_to(
                    lat1=0.0, lon1=lon,
                    lat2=90.0, lon2=lon),
                0.0)

    def testEquatorToSouthPole(self):
        for lon in [0.0, 15.0, 45.0, 90.0, 180.0, 270.0]:
            self.assertAlmostEqual(
                geo.bearing_to(
                    lat1=0.0, lon1=lon,
                    lat2=-90.0, lon2=lon),
                180.0)

    def testEquatorFacingEast(self):
        self.assertAlmostEqual(
            geo.bearing_to(
                lat1=0.0, lon1=0.0,
                lat2=0.0, lon2=15.0),
            90.0)

    def testEquatorFacingWest(self):
        self.assertAlmostEqual(
            geo.bearing_to(
                lat1=0.0, lon1=0.0,
                lat2=0.0, lon2=-15.0),
            -90.0)

    def testLondonToNewYork(self):
        self.assertAlmostEqual(
            geo.bearing_to(
                lat1=51.507222, lon1=-0.1275,
                lat2=40.7127, lon2=-74.0059),
            -71.67013491)

    def testHonoluluToKualaLumpur(self):
        self.assertAlmostEqual(
            geo.bearing_to(
                lat1=21.3, lon1=-157.816667,
                lat2=3.133333, lon2=101.683333),
            -83.202673931)
