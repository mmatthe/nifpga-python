import sys
import os
import time
import numpy as np




sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from nifpga import Session

def assertEquality(a, b, tol):
    d = np.sum(abs(a - b))
    if d > tol:
        raise AssertionError("Values differ: %s vs %s" % (a, b))


def test_incluster(session):
    in_cluster = session.registers['in_custer']
    out_cluster = session.registers['out_clustercopy']
    V_in = in_cluster.getEmptyValue()
    V_in['e1_I8.8'] = 1.5
    V_in['e2_I-3.15'] = 0.00000535
    V_in['e3_C4.4'] = 1+0.3125j
    V_in['e4_bool'] = True
    V_in['e5_I32'] = 31+256

    in_cluster.write(V_in)
    time.sleep(0.05)
    V_out = out_cluster.read()
    for k in V_in.keys():
        if k == '__types__': continue
        assertEquality(V_in[k], V_out[k], 0.001)
    assertEquality(session.registers['out_e1I9.8'].read(), 2.5, 0.001)
    assertEquality(session.registers['out_e2U-7.30'].read(), 0.00000535**2, 0.0001)
    # assertEquality(session.registers['out_e3C9.8'].read(),(1+0.3j) * (2+0.5j), 0.0001)
    assertEquality(session.registers['out_e4bool'].read(),True,0)
    assertEquality(session.registers['out_e5I32'].read(),  30+256, 0)

    print " === Success for Cluster in! === "


def test_fixpoint_IO(session):
    session.registers['in_I1.15'].write(0.003)
    session.registers['in_U2.3'].write(1.125)
    session.registers['in_C3.3'].write(0.5-0.25j)
    session.registers['in_a4I8'].write([1,2,3,4])

    time.sleep(0.05)
    c_exp = (0.5-0.25j) * (1+2j)
    assertEquality(session.registers['out_I3.15'].read(), 1.003, 0.0001)
    assertEquality(session.registers['out_U3.3'].read(), 0.125, 0.0001)
    assertEquality(session.registers['out_I7.6real'].read(), np.real(c_exp), 0.0001)
    assertEquality(session.registers['out_I7.6imag'].read(), np.imag(c_exp), 0.0001)
    assertEquality(session.registers['out_C7.6'].read(), c_exp, 0.0001)
    assertEquality(np.array(session.registers['out_a4I8'].read()), np.array([1, 4, 9, 16]), 0)

    print " === Success for fixpoint IO test! ==="

def test_clusterout(session):
    session.registers['in_e1I8.8'].write(5.80078125)
    session.registers['in_e2I-3.15'].write(-0.00001)
    session.registers['in_e3C4.4'].write(0.8125+0.1875j)
    session.registers['in_e4Bool'].write(False)
    session.registers['in_e5I32'].write(100)

    time.sleep(0.05)
    V_out = session.registers['out_cluster'].read()
    assertEquality(V_out['e1_I8.8'], 6.80078125, 0.0001)
    assertEquality(V_out['e2_I-3.15'], 0.00001**2, 0.00000001)
    assertEquality(V_out['e3_C4.4'], (0.8125+0.1875j)+(0.5+2j), 0.00001)
    assertEquality(V_out['e4_bool'], False, 0)
    assertEquality(V_out['e5_I32'], -100, 0)

    print " === Success for Cluster out! === "

with Session("USRP-Bitfile_ReadWriteTypes-0001.lvbitx", "RIO0") as session:
    session.download()
    session.run()

    print "Detected registers:"
    print "\n".join(session.registers.keys())
    print "=" * 80

    print "Detected FIFOs:"
    print "\n".join(session.fifos.keys())
    print "=" * 80

    test_incluster(session)
    test_fixpoint_IO(session)
    test_clusterout(session)
