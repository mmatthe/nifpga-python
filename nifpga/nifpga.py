"""
NiFpga, a thin wrapper around the FPGA Interface C API

Copyright (c) 2015 National Instruments
"""
from .statuscheckedlibrary import (NamedArgtype,
                                   LibraryFunctionInfo,
                                   StatusCheckedLibrary,
                                   LibraryNotFoundError)
import ctypes
from enum import Enum  # Third-party enum34
from collections import namedtuple
import numpy as np



class DataType(Enum):
    """ DataType is an enumerator, with the intention of abstracting the
    association between datatypes and ctypes within the Python API.
    """
    Bool = 1
    I8 = 2
    U8 = 3
    I16 = 4
    U16 = 5
    I32 = 6
    U32 = 7
    I64 = 8
    U64 = 9
    Sgl = 10
    Dbl = 11

    def __str__(self):
        return self.name

    def _return_ctype(self):
        """ Returns the associated ctype of a given datatype. """
        _datatype_ctype = {
            DataType.Bool: ctypes.c_uint8,
            DataType.I8: ctypes.c_int8,
            DataType.U8: ctypes.c_uint8,
            DataType.I16: ctypes.c_int16,
            DataType.U16: ctypes.c_uint16,
            DataType.I32: ctypes.c_int32,
            DataType.U32: ctypes.c_uint32,
            DataType.I64: ctypes.c_int64,
            DataType.U64: ctypes.c_uint64,
            DataType.Sgl: ctypes.c_float,
            DataType.Dbl: ctypes.c_double,
        }
        return _datatype_ctype[self]

NUMBER_TO_TYPES = {
    '4001' : 'I8',
    '4002' : 'I16',
    '4003' : 'I32',
    '4004' : 'I64',
    '4005' : 'U8',
    '4006' : 'U16',
    '4007' : 'U32',
    '4008' : 'U64',
    '4021' : 'Bool',
    '405F' : 'FXP',
    '405E' : 'CFXP',
    }
TYPE_TO_NUMBER = dict((b,a) for (a,b) in NUMBER_TO_TYPES.items())
TYPE_TO_NUMBER["BOOLEAN"] = "4021"
TYPE_TO_BITS = {
    'I8' : 8,
    'I16' : 16,
    'I32' : 32,
    'I64' : 64,
    'U8' : 8,
    'U16' : 16,
    'U32' : 32,
    'U64' : 64,
    'BOOLEAN' : 1,
    }
# BoolArrayMappedDatatype = namedtuple("BoolArrayMappedDatatype", "name, num_bits")
class BoolArrayMappedDatatype(object):
    num_bits = None
    name = None

    def __init__(self, name, num_bits):
        self.num_bits = num_bits
        self.name = name

    def __str__(self):
        return "%s (%d bits)" % (self.name, self.num_bits)

    def _return_ctype(self):
        return ctypes.c_uint8 * self.num_bits

    def toBoolArray(self, data):
        raise NotImplementedError()

    def fromBoolArray(self, boolArray):
        raise NotImplementedError()

def _fixpointFromBoolArray(integer, fractional, signed, boolArray):
    num_bits = integer+fractional
    assert len(boolArray) == num_bits
    vals = 2**np.arange(num_bits, dtype=np.uint64)[::-1]
    value = (boolArray * vals).sum()
    if signed and boolArray[0]:
        value = value - 2**num_bits
    if fractional > 0:
        return float(value)  / 2**(fractional)
    else:
        return value  // 2**(fractional)

def _fixpointToBoolArray(integer, fractional, signed, value):
    if value < 0 and not signed:
        raise RuntimeError("Unsigned value cannot create negative number")
    num_bits = integer + fractional
    as_int = int(np.round(value * 2**fractional))
    bits = np.array([as_int & (1 << (b)) for b in range(num_bits)[::-1]])
    return (bits != 0).astype(np.uint8)


class FixpointDatatype(BoolArrayMappedDatatype):
    def __init__(self, name, integer, fractional, signed):
        super(FixpointDatatype, self).__init__(name, integer+fractional)
        self._integer = integer
        self._fractional = fractional
        self._signed = signed

    def __str__(self):
        if self._signed:
            return "I%d.%d (%d bits)" % (self._integer, self._fractional, self.num_bits)
        else:
            return "U%d.%d (%d bits)" % (self._integer, self._fractional, self.num_bits)

    def getEmptyValue(self):
        return 0

    def toBoolArray(self, data):
        return _fixpointToBoolArray(self._integer, self._fractional, self._signed, data)

    def fromBoolArray(self, boolArray):
        return _fixpointFromBoolArray(self._integer, self._fractional, self._signed, boolArray)


class ComplexFixpointDatatype(BoolArrayMappedDatatype):
    def __init__(self, name, integer, fractional):
        super(ComplexFixpointDatatype, self).__init__(name, 2*(integer+fractional))
        self._integer = integer
        self._fractional = fractional

    def __str__(self):
        return "C%d.%d (%d bits)" % (self._integer, self._fractional, self.num_bits)

    def getEmptyValue(self):
        return 0+0j

    def toBoolArray(self, data):
        bits_real = _fixpointToBoolArray(self._integer, self._fractional, True, np.real(data))
        bits_imag = _fixpointToBoolArray(self._integer, self._fractional, True, np.imag(data))
        both = np.hstack([bits_real, bits_imag])
        return both

    def fromBoolArray(self, boolarray):
        half = self.num_bits // 2
        real = _fixpointFromBoolArray(self._integer, self._fractional, True, boolarray[:half])
        imag = _fixpointFromBoolArray(self._integer, self._fractional, True, boolarray[half:])
        return real + 1j*imag

class dotdict(dict):
    """dot.notation access to dictionary attributes"""
    __getattr__ = dict.get
    __setattr__ = dict.__setitem__
    __delattr__ = dict.__delitem__


class ClusterDatatype(BoolArrayMappedDatatype):
    def __init__(self, elements):
        self._elements = elements
        self.num_bits = sum(e[1].num_bits for e in elements)

    def __str__(self):
        return ("Cluster (%d bits)\n" % self.num_bits) + "\t\t".join("%10s : %s\n" % (n, t) for (n, t) in self._elements)

    def getEmptyValue(self):
        result = dotdict()
        result['__types__'] = dotdict()
        for name, typ in self._elements:
            result[name] = typ.getEmptyValue()
            result['__types__'][name] = str(typ)
        return result

    def toBoolArray(self, value):
        input_fields = set(value.keys()) - set(["__types__"])
        expected_fields = set([e[0] for e in self._elements])
        if input_fields != expected_fields:
            raise RuntimeError("Mismatching fields of cluster!\n\tGiven: %s\n\tExpected: %s" % (str(input_fields), str(expected_fields)))

        parts = [typ.toBoolArray(value[name]) for name, typ in self._elements]
        result = np.hstack(parts)
        assert len(result) == self.num_bits
        return result

    def fromBoolArray(self, boolarray):
        assert len(boolarray) == self.num_bits
        index = 0
        result = self.getEmptyValue()
        for name, typ in self._elements:
            part = boolarray[index:(index+typ.num_bits)]
            index = index + typ.num_bits
            result[name] = typ.fromBoolArray(part)
        return result


def _parseFixpoint(t, flattened):
    try:
        assert flattened[:4] == TYPE_TO_NUMBER[t]
    except KeyError:
        raise RuntimeError("type %s not supported" % t)

    signed = int(flattened[20:24])
    fullStr = flattened[8:12]
    full = int(fullStr, 16)
    frontStr = flattened[16:20]
    front = int(frontStr, 16)
    if front > 2**15-1:
        front = front - 2**16
    if signed:
        name = "I%d.%d" % (front, full-front)
    else:
        name = "U%d.%d" % (front, full-front)

    if t == 'FXP':
        return FixpointDatatype(name=name, integer=front, fractional=full-front, signed=signed)
    elif t == 'CFXP':
        return ComplexFixpointDatatype(name=name, integer=front, fractional=full-front)
    else:
        raise RuntimeError("Unknown fixpoint type: %s" % t)


def parseFlattenedFixpoint(typeholder, flattened):
    typeStr = TYPE_TO_NUMBER[typeholder]
    pos = flattened.find(typeStr)
    assert pos > 0
    flattened = flattened[pos:]
    return _parseFixpoint(typeholder, flattened)

def _parseCluster(types, flattened):
    result = []
    for p, t in enumerate(types):
        try:
            typeStr = TYPE_TO_NUMBER[t]
        except KeyError:
            raise RuntimeError("Type %s not supported in cluster" % t)
        pos = flattened.find(typeStr)
        if pos == -1:
            raise RuntimeError("Could not find type %s at %dth position!" % (t, p))
        flattened = flattened[pos:]
        if t in ["FXP", "CFXP"]:
            result.append(_parseFixpoint(t, flattened))
        elif t.upper() == 'BOOLEAN':
            result.append(FixpointDatatype(name='Boolean', integer=1, fractional=0,signed=False))
        else:
            signed = t[0] == 'I'
            result.append(FixpointDatatype(name='t', integer=TYPE_TO_BITS[t], fractional=0, signed=signed))
        flattened = flattened[len(typeStr):]
    return result

def parseFlattenedCluster(reg_xml):
    flattened = reg_xml.find("FlattenedType").text
    typelist = reg_xml.find("Datatype").getchildren()[0].find("TypeList")
    types = []
    names = []
    for C in typelist.getchildren():
        type = C.tag.upper()
        types.append(type)
        name = C.find("Name").text
        names.append(name)
    typeDetails = _parseCluster(types, flattened)
    bitCount = sum(x.num_bits for x in typeDetails)
    bitCount_fromXML = int(reg_xml.find("SizeInBits").text)
    assert bitCount == bitCount_fromXML, "Bitcount %d not equal expected value %d for cluster %s" % (bitCount, bitCount_fromXML, reg_xml.find("Name").text)
    elements = list(zip(names, typeDetails))
    return ClusterDatatype(elements)





_SessionType = ctypes.c_uint32
_IrqContextType = ctypes.c_void_p

OPEN_ATTRIBUTE_NO_RUN = 1
RUN_ATTRIBUTE_WAIT_UNTIL_DONE = 1
CLOSE_ATTRIBUTE_NO_RESET_IF_LAST_SESSION = 1
INFINITE_TIMEOUT = 0xffffffff


class _NiFpga(StatusCheckedLibrary):
    """
    _NiFpga, a thin wrapper around the FPGA Interface C API

    Defines FPGA Interface C API types, and provides the _NiFpga class
    which loads C API symbols and allows them to be called, e.g.
    nifpga.Open(<args>) or nifpga["ReadU32](<args>). If any NiFpga function
    return status is non-zero, the appropriate exception derived from either
    WarningStatus or ErrorStatus is raised.

    While _NiFpga can be used directly, Session provides a higher-level and
    more convenient API that is better-suited for most users.
    """

    def __init__(self):
        library_function_infos = [
            LibraryFunctionInfo(
                pretty_name="Open",
                name_in_library="NiFpgaDll_Open",
                named_argtypes=[
                    NamedArgtype("bitfile path", ctypes.c_char_p),
                    NamedArgtype("signature", ctypes.c_char_p),
                    NamedArgtype("resource", ctypes.c_char_p),
                    NamedArgtype("attribute", ctypes.c_uint32),
                    NamedArgtype("session", ctypes.POINTER(_SessionType)),
                ]),
            LibraryFunctionInfo(
                pretty_name="Run",
                name_in_library="NiFpgaDll_Run",
                named_argtypes=[
                    NamedArgtype("session", _SessionType),
                    NamedArgtype("attribute", ctypes.c_uint32),
                ]),
            LibraryFunctionInfo(
                pretty_name="Close",
                name_in_library="NiFpgaDll_Close",
                named_argtypes=[
                    NamedArgtype("session", _SessionType),
                    NamedArgtype("attribute", ctypes.c_uint32),
                ]),
            LibraryFunctionInfo(
                pretty_name="OpenResource",
                name_in_library="NiFpgaDll_OpenResource",
                named_argtypes=[
                    NamedArgtype("parentSession", _SessionType),
                    NamedArgtype("parentIndex", ctypes.c_uint32),
                    NamedArgtype("globalIndex", ctypes.c_uint32),
                    NamedArgtype("childSession", ctypes.POINTER(_SessionType)),
                ]),
            LibraryFunctionInfo(
                pretty_name="AddResources",
                name_in_library="NiFpgaDll_AddResources",
                named_argtypes=[
                    NamedArgtype("session", _SessionType),
                    NamedArgtype("resourceNames", ctypes.POINTER(ctypes.c_char_p)),
                    NamedArgtype("resourceValues", ctypes.POINTER(ctypes.c_uint32)),
                    NamedArgtype("externalRegisters", ctypes.POINTER(ctypes.c_uint32)),
                    NamedArgtype("numberOfResources", ctypes.c_size_t),
                ]),
            LibraryFunctionInfo(
                pretty_name="GetResourceIndex",
                name_in_library="NiFpgaDll_GetResourceIndex",
                named_argtypes=[
                    NamedArgtype("resourceName", ctypes.c_char_p),
                    NamedArgtype("resourceIndex", ctypes.POINTER(ctypes.c_uint32)),
                ]),
            LibraryFunctionInfo(
                pretty_name="ReleaseResourceIndex",
                name_in_library="NiFpgaDll_ReleaseResourceIndex",
                named_argtypes=[
                    NamedArgtype("resourceName", ctypes.c_char_p),
                ]),
            LibraryFunctionInfo(
                pretty_name="GetResourceName",
                name_in_library="NiFpgaDll_GetResourceName",
                named_argtypes=[
                    NamedArgtype("resourceIndex", ctypes.c_uint32),
                    NamedArgtype("resourceName", ctypes.POINTER(ctypes.c_char_p)),
                ]),
            LibraryFunctionInfo(
                pretty_name="Reset",
                name_in_library="NiFpgaDll_Reset",
                named_argtypes=[
                    NamedArgtype("session", _SessionType),
                ]),
            LibraryFunctionInfo(
                pretty_name="Abort",
                name_in_library="NiFpgaDll_Abort",
                named_argtypes=[
                    NamedArgtype("session", _SessionType),
                ]),
            LibraryFunctionInfo(
                pretty_name="Download",
                name_in_library="NiFpgaDll_Download",
                named_argtypes=[
                    NamedArgtype("session", _SessionType),
                ]),
            LibraryFunctionInfo(
                pretty_name="ReserveIrqContext",
                name_in_library="NiFpgaDll_ReserveIrqContext",
                named_argtypes=[
                    NamedArgtype("session", _SessionType),
                    NamedArgtype("context", ctypes.POINTER(_IrqContextType)),
                ]),
            LibraryFunctionInfo(
                pretty_name="UnreserveIrqContext",
                name_in_library="NiFpgaDll_UnreserveIrqContext",
                named_argtypes=[
                    NamedArgtype("session", _SessionType),
                    NamedArgtype("context", ctypes.POINTER(_IrqContextType)),
                ]),
            LibraryFunctionInfo(
                pretty_name="WaitOnIrqs",
                name_in_library="NiFpgaDll_WaitOnIrqs",
                named_argtypes=[
                    NamedArgtype("session", _SessionType),
                    NamedArgtype("context", ctypes.POINTER(_IrqContextType)),
                    NamedArgtype("irqs", ctypes.c_uint32),
                    NamedArgtype("timeout ms", ctypes.c_uint32),
                    NamedArgtype("irqs asserted", ctypes.POINTER(ctypes.c_uint32)),
                    NamedArgtype("timed out", ctypes.POINTER(DataType.Bool._return_ctype())),
                ]),
            LibraryFunctionInfo(
                pretty_name="AcknowledgeIrqs",
                name_in_library="NiFpgaDll_AcknowledgeIrqs",
                named_argtypes=[
                    NamedArgtype("session", _SessionType),
                    NamedArgtype("irqs", ctypes.c_uint32),
                ]),
            LibraryFunctionInfo(
                pretty_name="ConfigureFifo",
                name_in_library="NiFpgaDll_ConfigureFifo",
                named_argtypes=[
                    NamedArgtype("session", _SessionType),
                    NamedArgtype("fifo", ctypes.c_uint32),
                    NamedArgtype("depth", ctypes.c_size_t),
                ]),
            LibraryFunctionInfo(
                pretty_name="ConfigureFifo2",
                name_in_library="NiFpgaDll_ConfigureFifo2",
                named_argtypes=[
                    NamedArgtype("session", _SessionType),
                    NamedArgtype("fifo", ctypes.c_uint32),
                    NamedArgtype("requested depth", ctypes.c_size_t),
                    NamedArgtype("actual depth", ctypes.POINTER(ctypes.c_size_t))
                ]),
            LibraryFunctionInfo(
                pretty_name="StartFifo",
                name_in_library="NiFpgaDll_StartFifo",
                named_argtypes=[
                    NamedArgtype("session", _SessionType),
                    NamedArgtype("fifo", ctypes.c_uint32),
                ]),
            LibraryFunctionInfo(
                pretty_name="StopFifo",
                name_in_library="NiFpgaDll_StopFifo",
                named_argtypes=[
                    NamedArgtype("session", _SessionType),
                    NamedArgtype("fifo", ctypes.c_uint32),
                ]),
            LibraryFunctionInfo(
                pretty_name="ReleaseFifoElements",
                name_in_library="NiFpgaDll_ReleaseFifoElements",
                named_argtypes=[
                    NamedArgtype("session", _SessionType),
                    NamedArgtype("fifo", ctypes.c_uint32),
                    NamedArgtype("elements", ctypes.c_size_t),
                ]),
            LibraryFunctionInfo(
                pretty_name="GetPeerToPeerFifoEndpoint",
                name_in_library="NiFpgaDll_GetPeerToPeerFifoEndpoint",
                named_argtypes=[
                    NamedArgtype("session", _SessionType),
                    NamedArgtype("fifo", ctypes.c_uint32),
                    NamedArgtype("endpoint", ctypes.POINTER(ctypes.c_uint32)),
                ]),
            LibraryFunctionInfo(
                pretty_name="ClientFunctionCall",
                name_in_library="NiFpgaDll_ClientFunctionCall",
                named_argtypes=[
                    NamedArgtype("session", _SessionType),
                    NamedArgtype("group", ctypes.c_uint32),
                    NamedArgtype("functionId", ctypes.c_uint32),
                    NamedArgtype("inBuffer", ctypes.c_void_p),
                    NamedArgtype("inBufferSize", ctypes.c_size_t),
                    NamedArgtype("outBuffer", ctypes.c_void_p),
                    NamedArgtype("outBufferSize", ctypes.c_size_t),
                ])
        ]  # list of function_infos

        for datatype in DataType:
            type_ctype = datatype._return_ctype()
            library_function_infos.extend([
                LibraryFunctionInfo(
                    pretty_name="Read%s" % datatype,
                    name_in_library="NiFpgaDll_Read%s" % datatype,
                    named_argtypes=[
                        NamedArgtype("session", _SessionType),
                        NamedArgtype("indicator", ctypes.c_uint32),
                        NamedArgtype("value", ctypes.POINTER(type_ctype)),
                    ]),
                LibraryFunctionInfo(
                    pretty_name="Write%s" % datatype,
                    name_in_library="NiFpgaDll_Write%s" % datatype,
                    named_argtypes=[
                        NamedArgtype("session", _SessionType),
                        NamedArgtype("control", ctypes.c_uint32),
                        NamedArgtype("value", type_ctype),
                    ]),
                LibraryFunctionInfo(
                    pretty_name="ReadArray%s" % datatype,
                    name_in_library="NiFpgaDll_ReadArray%s" % datatype,
                    named_argtypes=[
                        NamedArgtype("session", _SessionType),
                        NamedArgtype("indicator", ctypes.c_uint32),
                        NamedArgtype("array", ctypes.POINTER(type_ctype)),
                        NamedArgtype("size", ctypes.c_size_t),
                    ]),
                LibraryFunctionInfo(
                    pretty_name="WriteArray%s" % datatype,
                    name_in_library="NiFpgaDll_WriteArray%s" % datatype,
                    named_argtypes=[
                        NamedArgtype("session", _SessionType),
                        NamedArgtype("control", ctypes.c_uint32),
                        NamedArgtype("array", ctypes.POINTER(type_ctype)),
                        NamedArgtype("size", ctypes.c_size_t),
                    ]),
                LibraryFunctionInfo(
                    pretty_name="ReadFifo%s" % datatype,
                    name_in_library="NiFpgaDll_ReadFifo%s" % datatype,
                    named_argtypes=[
                        NamedArgtype("session", _SessionType),
                        NamedArgtype("fifo", ctypes.c_uint32),
                        NamedArgtype("data", ctypes.POINTER(type_ctype)),
                        NamedArgtype("number of elements", ctypes.c_size_t),
                        NamedArgtype("timeout ms", ctypes.c_uint32),
                        NamedArgtype("elements remaining", ctypes.POINTER(ctypes.c_size_t)),
                    ]),
                LibraryFunctionInfo(
                    pretty_name="WriteFifo%s" % datatype,
                    name_in_library="NiFpgaDll_WriteFifo%s" % datatype,
                    named_argtypes=[
                        NamedArgtype("session", _SessionType),
                        NamedArgtype("fifo", ctypes.c_uint32),
                        NamedArgtype("data", ctypes.POINTER(type_ctype)),
                        NamedArgtype("number of elements", ctypes.c_size_t),
                        NamedArgtype("timeout ms", ctypes.c_uint32),
                        NamedArgtype("empty elements remaining", ctypes.POINTER(ctypes.c_size_t)),
                    ]),
                LibraryFunctionInfo(
                    pretty_name="AcquireFifoReadElements%s" % datatype,
                    name_in_library="NiFpgaDll_AcquireFifoReadElements%s" % datatype,
                    named_argtypes=[
                        NamedArgtype("session", _SessionType),
                        NamedArgtype("fifo", ctypes.c_uint32),
                        NamedArgtype("elements", ctypes.POINTER(ctypes.POINTER(type_ctype))),
                        NamedArgtype("elements requested ", ctypes.c_size_t),
                        NamedArgtype("timeout ms", ctypes.c_uint32),
                        NamedArgtype("elements acquired", ctypes.POINTER(ctypes.c_size_t)),
                        NamedArgtype("elements remaining", ctypes.POINTER(ctypes.c_size_t)),
                    ]),
                LibraryFunctionInfo(
                    pretty_name="AcquireFifoWriteElements%s" % datatype,
                    name_in_library="NiFpgaDll_AcquireFifoWriteElements%s" % datatype,
                    named_argtypes=[
                        NamedArgtype("session", _SessionType),
                        NamedArgtype("fifo", ctypes.c_uint32),
                        NamedArgtype("elements", ctypes.POINTER(ctypes.POINTER(type_ctype))),
                        NamedArgtype("elements requested ", ctypes.c_size_t),
                        NamedArgtype("timeout ms", ctypes.c_uint32),
                        NamedArgtype("elements acquired", ctypes.POINTER(ctypes.c_size_t)),
                        NamedArgtype("elements remaining", ctypes.POINTER(ctypes.c_size_t)),
                    ]),
            ])  # end of library_function_infos.extend() call
        try:
            super(_NiFpga, self).__init__(library_name="NiFpga",
                                          library_function_infos=library_function_infos)
        except LibraryNotFoundError as e:
            import platform
            system = platform.system().lower()
            if system == 'windows':
                raise LibraryNotFoundError(
                    "Unable to find NiFpga.dll on your system, "
                    "ensure you have installed the relevent RIO distribution for your device. "
                    "Search for your product here: http://www.ni.com/downloads/ni-drivers/ "
                    "Original Exception: " + str(e))
            if system == 'linux':
                raise LibraryNotFoundError(
                    "Unable to find libNiFpga.so on your system, "
                    "If you are on desktop linux, ensure you have installed the latest "
                    "RIO Linux distribution for your product, such as http://www.ni.com/download/ni-rio-15.0/5603/en/ "
                    "If you are on a Linux RT embedded target (cRIO, sbRIO, FlexRIO, Industrial Controller, etc) install NI-RIO to your target "
                    "though MAX following these instructions: https://www.ni.com/getting-started/set-up-hardware/compactrio/controller-software "
                    "Original Exception: " + str(e))
            if system == 'darwin':
                raise LibraryNotFoundError(
                    "Unable to find NiFpga.Framework on your system, "
                    "Sorry we don't yet support using RIO Devices on OSX, contact your sales person "
                    "for the latest information on OSX support. "
                    "Original Exception: " + str(e))
            raise
