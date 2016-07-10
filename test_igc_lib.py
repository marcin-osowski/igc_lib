import unittest

import igc_lib


class TestNapretTaskParsing(unittest.TestCase):

    def setUp(self):
        test_file = 'testfiles/napret.lkt'
        self.task = igc_lib.Task.create_from_lkt_file(test_file)

    def testTaskHasStartTime(self):
        self.assertAlmostEqual(self.task.start_time, 12*3600)

    def testTaskHasEndTime(self):
        self.assertAlmostEqual(self.task.end_time, 23*3600 + 59*60 + 59)

    def testTaskHasTurnpoints(self):
        self.assertEqual(len(self.task.turnpoints), 11)
        self.assertEqual(self.task.turnpoints[0].kind, "start_enter")

    def testTaskHasTurnpointsWithRadius(self):
        self.assertGreaterEqual(min(map(lambda turnpoint: turnpoint.radius,
                                        self.task.turnpoints)), 0.2)
        self.assertLessEqual(max(map(lambda turnpoint: turnpoint.radius,
                                     self.task.turnpoints)), 4)

    def testTaskHasTurnpointsWithLatitude(self):
        self.assertEqual(max(map(lambda turnpoint: int(turnpoint.lat / 46),
                                 self.task.turnpoints)), 1)

    def testTaskHasTurnpointsWithLongitude(self):
        self.assertEqual(max(map(lambda turnpoint: int(turnpoint.lon / 12),
                                 self.task.turnpoints)), 1)


class TestNapretFlightParsing(unittest.TestCase):

    def setUp(self):
        test_file = 'testfiles/napret.igc'
        self.flight = igc_lib.Flight.create_from_file(test_file)

    def testFileParsesOK(self):
        self.assertTrue(self.flight.valid)
        self.assertListEqual(self.flight.notes, [])

    def testBothPressureSensorsAreOK(self):
        self.assertTrue(self.flight.press_alt_valid)
        self.assertTrue(self.flight.gnss_alt_valid)

    def testChosesPressureSensor(self):
        self.assertEqual(self.flight.alt_source, 'PRESS')

    def testMetadataIsCorrectlyRead(self):
        self.assertEqual(self.flight.fr_manuf_code, 'XGD')
        self.assertEqual(self.flight.fr_uniq_id, 'jos')
        self.assertFalse(hasattr(self.flight, 'i_record'))
        # 2016-04-03 0:00 UTC
        self.assertAlmostEqual(self.flight.date_timestamp, 1459641600.0)
        self.assertEqual(self.flight.glider_type, 'test_glider')
        self.assertEqual(self.flight.competition_class,
                         'test_competition_class')
        self.assertFalse(hasattr(self.flight, 'fr_firmware_version'))
        self.assertFalse(hasattr(self.flight, 'fr_hardware_version'))
        self.assertFalse(hasattr(self.flight, 'fr_recorder_type'))
        self.assertFalse(hasattr(self.flight, 'fr_gps_receiver'))
        self.assertFalse(hasattr(self.flight, 'fr_pressure_sensor'))

    def testBRecordsParsing(self):
        self.assertEqual(len(self.flight.fixes), 5380)

    def testFixesHaveCorrectIndices(self):
        for i, fix in enumerate(self.flight.fixes):
            self.assertEqual(i, fix.index)

    def testFlightsDetection(self):
        # Basic test, there should be at least one thermal
        self.assertGreater(len(self.flight.thermals), 0)

    def testGlidesDetection(self):
        # Basic test, there should be at least one glide
        self.assertGreater(len(self.flight.glides), 0)

    def testSomeFixesAreInFlight(self):
        self.assertTrue(
            any(map(lambda fix: fix.flying, self.flight.fixes)))

    def testSomeFixesAreNotInFlight(self):
        self.assertTrue(
            any(map(lambda fix: not fix.flying, self.flight.fixes)))

    def testSomeFixesAreInCircling(self):
        self.assertTrue(
            any(map(lambda fix: fix.circling, self.flight.fixes)))

    def testSomeFixesAreNotInCircling(self):
        self.assertTrue(
            any(map(lambda fix: not fix.circling, self.flight.fixes)))
