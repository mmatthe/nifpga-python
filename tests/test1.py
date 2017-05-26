import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

import nifpga

# B = nifpga.bitfile.Bitfile("USRP-datatypes-0008.lvbitx")
B = nifpga.bitfile.Bitfile("USRP-Bitfile_ReadWriteTypes-0001.lvbitx")
for k, v in B.registers.items():
    print k
    print v
