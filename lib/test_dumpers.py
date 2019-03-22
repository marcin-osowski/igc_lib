import os
import shutil
import unittest
import tempfile

import igc_lib
import lib.dumpers as dumpers


class TestDumpers(unittest.TestCase):

    def setUp(self):
        igc_file = 'testfiles/napret.igc'
        self.flight = igc_lib.Flight.create_from_file(igc_file)
        self.tmp_output_dir = tempfile.mkdtemp()

    def tearDown(self):
        # Best-effort removal of temporary output files
        shutil.rmtree(self.tmp_output_dir, ignore_errors=True)

    def assertFileNotEmpty(self, filename):
        self.assertTrue(os.path.isfile(filename))
        self.assertGreater(os.path.getsize(filename), 0)

    def testWptDumpNotEmpty(self):
        tmp_wpt_file = os.path.join(self.tmp_output_dir, 'thermals.wpt')
        dumpers.dump_thermals_to_wpt_file(self.flight, tmp_wpt_file)
        self.assertFileNotEmpty(tmp_wpt_file)

    def testCupDumpNotEmpty(self):
        tmp_cup_file = os.path.join(self.tmp_output_dir, 'thermals.cup')
        dumpers.dump_thermals_to_cup_file(self.flight, tmp_cup_file)
        self.assertFileNotEmpty(tmp_cup_file)

    def testKmlDumpNotEmpty(self):
        tmp_kml_file = os.path.join(self.tmp_output_dir, 'flight.kml')
        dumpers.dump_flight_to_kml(self.flight, tmp_kml_file)
        self.assertFileNotEmpty(tmp_kml_file)

    def testCsvDumpsNotEmpty(self):
        tmp_csv_track = os.path.join(self.tmp_output_dir, 'flight.csv')
        tmp_csv_thermals = os.path.join(self.tmp_output_dir, 'thermals.csv')
        dumpers.dump_flight_to_csv(
            self.flight, tmp_csv_track, tmp_csv_thermals)
        self.assertFileNotEmpty(tmp_csv_track)
        self.assertFileNotEmpty(tmp_csv_thermals)
