import unittest

import lib.viterbi as viterbi


class TestSimpleViterbiDecoder(unittest.TestCase):

    def setUp(self):
        self.init_probs = [0.5, 0.5]
        self.transition_probs = [
            [0.9, 0.1],
            [0.1, 0.9],
        ]
        self.emission_probs = [
            [0.7, 0.3],
            [0.3, 0.7],
        ]
        self.decoder = viterbi.SimpleViterbiDecoder(
            init_probs=self.init_probs,
            transition_probs=self.transition_probs,
            emission_probs=self.emission_probs)

    def assertDecode(self, emissions, expected_result):
        result = self.decoder.decode(emissions)
        self.assertListEqual(result, expected_result)

    def testEmptyDecode(self):
        self.assertDecode([], [])

    def testSimpleDecodeZeros(self):
        for i in range(20):
            data = [0] * i
            self.assertDecode(data, data)

    def testSimpleDecodeOnes(self):
        for i in range(20):
            data = [1] * i
            self.assertDecode(data, data)

    def testMixedIdentityDecode(self):
        data = [0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 1, 1, 1]
        self.assertDecode(data, data)

    def testIgnoresSmallFluctuationsZeros(self):
        data = [1, 0, 0, 0, 1, 1, 0, 0, 0]
        expected_result = [0, 0, 0, 0, 0, 0, 0, 0, 0]
        self.assertDecode(data, expected_result)

    def testIgnoresSmallFluctuationsOnes(self):
        data = [1, 0, 1, 1, 0, 0, 1, 1, 1]
        expected_result = [1, 1, 1, 1, 1, 1, 1, 1, 1]
        self.assertDecode(data, expected_result)
