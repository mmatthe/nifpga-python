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

    def test_positive_integer(self):
        self._check(8, 0, True, 0, np.zeros(8))
        self._check(8, 0, True, 1, np.array([0,0,0,0,0,0,0,1]))

    def test_negative_integer(self):
        self._check(8, 0, True, -1, np.array([1,1,1,1,1,1,1,1]))

    def test_fraction12(self):
        self._check(1,1, True, 0.5, np.array([0,1]))
        self._check(4,1, True, 0.5, np.array([0,0,0,0,1]))
        self._check(4,4, True, 0.5, np.array([0,0,0,0,1,0,0,0]))

    def test_negative_fraction12(self):
        self._check(1,1, True, -0.5, np.array([1,1]))
        self._check(4,1, True, -0.5, np.array([1,1,1,1,1]))
        self._check(4,4, True, -0.5, np.array([1,1,1,1,1,0,0,0]))

class TestComplexFixpointToBitarray(unittest.TestCase):
    def _check(self, integer, fractional, value, expected):
        F = ComplexFixpointDatatype("bla", integer, fractional)

        result = F.toBoolArray(value)
        self.assertEqual(result.dtype, np.uint8)
        nt.assert_array_equal(result, expected.astype(np.uint8))

    def test_positive_integer(self):
        self._check(4, 0, 0, np.zeros(8))
        self._check(4, 0, 1, np.array([0,0,0,1,0,0,0,0]))

    def test_negative_integer(self):
        self._check(4, 0, -1, np.array([1,1,1,1,0,0,0,0]))

    def test_imaginary(self):
        self._check(4, 0, 0+1j, np.array([0,0,0,0,0,0,0,1]))
        self._check(4, 0, 0-1j, np.array([0,0,0,0,1,1,1,1]))

    def test_fractional(self):
        self._check(2, 3, 0.5+0.25j, np.array([0,0,1,0,0, 0,0,0,1,0]))
        self._check(2, 3, 0.5-0.25j, np.array([0,0,1,0,0, 1,1,1,1,0]))

class TestFixpointFromBoolArray(unittest.TestCase):
    def _check(self, integer, fractional, signed, boolarray, expected):
        F = FixpointDatatype("bla", integer, fractional, signed)

        boolarray = boolarray.astype(np.uint8)
        value = F.fromBoolArray(boolarray)
        self.assertEqual(value, expected)

    def test_positive_integer(self):
        self._check(8,0,True,np.array([0,0,0,0,0,0,0,0]), 0)
        self._check(8,0,True,np.array([0,0,0,0,0,0,0,1]), 1)
        self._check(8,0,True,np.array([0,0,0,0,1,1,0,0]), 12)

    def test_negative_integer(self):
        self._check(8, 0, True, np.array([1,1,1,1,1,1,1,1]), -1)
        self._check(4, 0, True, np.array([1,1,1,0]), -2)
        self._check(4, 0, True, np.array([1,1,0,1]), -3)
        self._check(4, 0, True, np.array([1,1,0,0]), -4)
        self._check(4, 0, True, np.array([1,0,1,1]), -5)

    def test_fractional(self):
        self._check(4,4, True, np.array([0,0,0,0,0,1,0,0]), 0.25)

class TestComplexFixpointToBoolArray(unittest.TestCase):
    def _check(self, integer, fractional, boolarray, expected):
        F = ComplexFixpointDatatype("bla", integer, fractional)

        boolarray = boolarray.astype(np.uint8)
        value = F.fromBoolArray(boolarray)
        self.assertEqual(value, expected)

    def test_integer(self):
        self._check(2,2,np.array([0,1,0,0,0,0,0,0]), 1)
        self._check(2,2,np.array([0,1,0,0,0,0,1,0]), 1+0.5j)

class TestClusterDatatype(unittest.TestCase):
    def test_containsElements(self):
        elements = [("e1", FixpointDatatype("",4,4,True)),
                    ("e2", FixpointDatatype("",8,4,False)),
                    ("e3", ComplexFixpointDatatype("",2,3))]
        C = ClusterDatatype(elements).getEmptyValue()
        C.e1 = 5
        self.assertEqual(C['e1'], 5)
        C.e2
        C.e3

    def test_toBoolArray(self):
        elements = [("e1", FixpointDatatype("",4,4,True)),
                    ("e2", FixpointDatatype("",8,0,False)),
                    ("e3", ComplexFixpointDatatype("",2,3))]
        C = ClusterDatatype(elements)
        V = C.getEmptyValue()
        V.e1 = 1
        V.e2 = 128
        V.e3 = 1-1j
        boolarray = C.toBoolArray(V)
        expected = np.hstack([np.array([0,0,0,1,0,0,0,0]),
                              np.array([1,0,0,0,0,0,0,0]),
                              np.array([0,1,0,0,0,1,1,0,0,0])]).astype(np.uint8)
        nt.assert_array_equal(boolarray, expected)

    def test_fromBoolArray(self):
        elements = [("e1", FixpointDatatype("",4,4,True)),
                    ("e2", FixpointDatatype("",8,0,False)),
                    ("e3", ComplexFixpointDatatype("",2,3))]
        C = ClusterDatatype(elements)
        boolarray = np.hstack([np.array([0,0,0,1,0,0,0,0]),
                              np.array([1,0,0,0,0,0,0,0]),
                              np.array([0,1,0,0,0,1,1,0,0,0])]).astype(np.uint8)
        V = C.fromBoolArray(boolarray)
        self.assertEqual(V.e1, 1)
        self.assertEqual(V.e2, 128)
        self.assertEqual(V.e3, 1-1j)



if __name__ == '__main__':
    unittest.main()
