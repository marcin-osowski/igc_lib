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

    def testHasTakeoff(self):
        self.assertTrue(hasattr(self.flight, 'takeoff_fix'))

    def testHasLanding(self):
        self.assertTrue(hasattr(self.flight, 'landing_fix'))

    def testSomeFixesAreInCircling(self):
        self.assertTrue(
            any(map(lambda fix: fix.circling, self.flight.fixes)))

    def testSomeFixesAreNotInCircling(self):
        self.assertTrue(
            any(map(lambda fix: not fix.circling, self.flight.fixes)))

    def testThermalsAreAfterTakeoff(self):
        takeoff_index = self.flight.takeoff_fix.index
        for thermal in self.flight.thermals:
            self.assertGreaterEqual(thermal.enter_fix.index, takeoff_index)
            self.assertGreaterEqual(thermal.exit_fix.index, takeoff_index)

    def testThermalsAreBeforeLanding(self):
        landing_index = self.flight.landing_fix.index
        for thermal in self.flight.thermals:
            self.assertLessEqual(thermal.enter_fix.index, landing_index)
            self.assertLessEqual(thermal.exit_fix.index, landing_index)

    def testGlidesAreAfterTakeoff(self):
        takeoff_index = self.flight.takeoff_fix.index
        for glide in self.flight.glides:
            self.assertGreaterEqual(glide.enter_fix.index, takeoff_index)
            self.assertGreaterEqual(glide.exit_fix.index, takeoff_index)

    def testGlidesAreBeforeLanding(self):
        landing_index = self.flight.landing_fix.index
        for glide in self.flight.glides:
            self.assertLessEqual(glide.enter_fix.index, landing_index)
            self.assertLessEqual(glide.exit_fix.index, landing_index)


class TestNoTimeIncrementFlightParsing(unittest.TestCase):

    def setUp(self):
        test_file = 'testfiles/no_time_increment.igc'
        self.flight = igc_lib.Flight.create_from_file(test_file)

    def testFileParsesOK(self):
        self.assertTrue(self.flight.valid)
        self.assertListEqual(self.flight.notes, [])

    def testBRecordsParsing(self):
        # There are 200 B records in the file, but the last
        # 50 do not increment the time, and therefore should be dropped.
        self.assertEqual(len(self.flight.fixes), 150)


class TestOlsztynFlightParsing(unittest.TestCase):

    def setUp(self):
        test_file = 'testfiles/olsztyn.igc'
        self.flight = igc_lib.Flight.create_from_file(test_file)

    def testFileParsesOK(self):
        self.assertTrue(self.flight.valid)
        self.assertListEqual(self.flight.notes, [])

    def testMetadataIsCorrectlyRead(self):
        self.assertEqual(self.flight.fr_manuf_code, 'LXN')
        self.assertEqual(self.flight.fr_uniq_id, 'ABC')
        self.assertEqual(
            self.flight.i_record,
            'I073638FXA3941ENL4246TAS4751GSP5254TRT5559VAT6063OAT')
        # 2011-09-02 0:00 UTC
        self.assertAlmostEqual(self.flight.date_timestamp, 1314921600.0)
        self.assertEqual(self.flight.glider_type, 'test_glider_xx')
        self.assertEqual(self.flight.competition_class,
                         'some_competition_class')
        self.assertEqual(self.flight.fr_firmware_version, '2.2')
        self.assertEqual(self.flight.fr_hardware_version, '2')
        self.assertEqual(self.flight.fr_recorder_type,
                         'LXNAVIGATION,LX8000F')
        self.assertEqual(self.flight.fr_gps_receiver,
                         'uBLOX LEA-4S-2,16,max9000m')
        self.assertEqual(self.flight.fr_pressure_sensor,
                         'INTERSEMA,MS5534A,max10000m')

    def testBRecordsParsing(self):
        self.assertEqual(len(self.flight.fixes), 2469)


class TestNewZealandFlightParsing(unittest.TestCase):

    def setUp(self):
        test_file = 'testfiles/new_zealand.igc'
        self.flight = igc_lib.Flight.create_from_file(test_file)

    def testFileParsesOK(self):
        self.assertTrue(self.flight.valid)
        self.assertListEqual(self.flight.notes, [])
