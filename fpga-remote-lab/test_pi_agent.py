import os
os.environ.setdefault('AGENT_TOKEN', 'unit-test-only')
import unittest
from pi_agent import request_packet, extract_frames


class ProtocolTests(unittest.TestCase):
    def test_request_layout(self):
        packet=request_packet(switches=3,buttons=8,reset=True,a=0x12345678,b=9)
        self.assertEqual(len(packet),12)
        self.assertEqual(packet[:7],bytes.fromhex('a5830178563412'))
        checksum=0
        for byte in packet:checksum^=byte
        self.assertEqual(checksum,0)

    def test_noise_fragment_and_checksum(self):
        valid=bytearray([0x5a,8,0x78,0x56,0x34,0x12])
        checksum=0
        for byte in valid:checksum^=byte
        valid.append(checksum)
        buf=bytearray(b'noise')+valid[:3]
        self.assertEqual(extract_frames(buf),[])
        buf.extend(valid[3:])
        self.assertEqual(extract_frames(buf),[(8,0x12345678)])
        bad=valid.copy();bad[-1]^=1
        self.assertEqual(extract_frames(bad+valid),[(8,0x12345678)])
