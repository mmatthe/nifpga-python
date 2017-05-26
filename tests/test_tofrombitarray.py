import unittest
import sys
import os
import numpy as np
import numpy.testing as nt


sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from nifpga import FixpointDatatype, ComplexFixpointDatatype, ClusterDatatype


class TestFixpointToBitarray(unittest.TestCase):
    def _check(self, integer, fractional, signed, value, expected):
        F = FixpointDatatype("bla", integer, fractional, signed)

        result = F.toBoolArray(value)
        self.assertEqual(result.dtype, np.uint8)
        nt.assert_array_equal(result, expected.astype(np.uint8))

    def test_integer_0(self):
        self._check(8, 0, True, 0, np.zeros(8))

if __name__ == '__main__':
    unittest.main()
