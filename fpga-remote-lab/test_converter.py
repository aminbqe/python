import io
import unittest
from zipfile import ZipFile
from fastapi.testclient import TestClient
from converter import inspect, generate
from server import app

ADDER = '''module full_adder(input wire a,b,cin, output wire sum,cout);
assign sum=a^b^cin; assign cout=(a&b)|(a&cin)|(b&cin); endmodule'''
MAPPING = {'a': 'switches:0', 'b': 'switches:1', 'cin': 'switches:2',
           'sum': 'leds:0', 'cout': 'leds:1'}


class ConverterTests(unittest.TestCase):
    def test_ansi_and_inherited_widths(self):
        ports = inspect('module demo(input wire [7:4] a,b, output reg q); endmodule')[0]['ports']
        self.assertEqual([p['width'] for p in ports], [4,4,1])
        self.assertEqual(ports[1]['lsb'], 4)

    def test_nonansi(self):
        ports = inspect('module demo(a,b,q); input [3:0] a,b; output q; endmodule')[0]['ports']
        self.assertEqual([p['name'] for p in ports], ['a','b','q'])
        self.assertEqual(ports[1]['width'],4)

    def test_archive_preserves_source_and_mapping(self):
        archive = generate(ADDER, 'full_adder', MAPPING)
        with ZipFile(io.BytesIO(archive)) as z:
            self.assertEqual(z.read('design.v').decode(), ADDER)
            wrapper = z.read('user_logic.v').decode()
            self.assertIn('.a(switches[0:0])', wrapper)
            self.assertIn('port_4[0], port_3[0]', wrapper)
            self.assertIn('lab_bridge.v', z.namelist())
            self.assertIn('lab.ucf', z.namelist())

    def test_overlap_rejected(self):
        with self.assertRaisesRegex(ValueError, 'مشترک'):
            generate(ADDER,'full_adder',{**MAPPING,'cout':'leds:0'})

    def test_unsupported_and_invalid(self):
        for code in ['module x(input [N:0] a); endmodule',
                     'module x(inout a); endmodule',
                     'module x #(parameter N=4)(input a); endmodule',
                     '`include "file.v"\nmodule x(input a); endmodule',
                     'module x(input [0:3] a); endmodule']:
            with self.assertRaises(ValueError): inspect(code)
        with self.assertRaises(ValueError):
            generate(ADDER,'full_adder',{**MAPPING,'a':'switches:4'})
        with self.assertRaises(ValueError):
            generate(ADDER,'full_adder',{})

    def test_api(self):
        with TestClient(app) as client:
            self.assertEqual(client.post('/api/verilog/inspect', json={'source':ADDER}).status_code,200)
            response=client.post('/api/verilog/convert',json={'source':ADDER,'top':'full_adder','mapping':MAPPING})
            self.assertEqual(response.status_code,200)
            self.assertEqual(response.headers['content-type'],'application/zip')
            files=client.post('/api/verilog/files',json={'source':ADDER,'top':'full_adder','mapping':MAPPING})
            self.assertEqual(files.status_code,200)
            contents={f['name']:f['content'] for f in files.json()['files']}
            self.assertEqual(contents['design.v'],ADDER)
            self.assertIn('NET "clk"',contents['lab.ucf'])
            self.assertIn('module user_logic',contents['user_logic.v'])
            prepared=client.post('/api/verilog/prepare-download',json={'source':ADDER,'top':'full_adder','mapping':MAPPING})
            self.assertEqual(prepared.status_code,200)
            download=client.get(prepared.json()['url'])
            self.assertEqual(download.status_code,200)
            head=client.head(prepared.json()['url'])
            self.assertEqual(head.status_code,200)
            self.assertEqual(int(head.headers['content-length']),len(download.content))
            self.assertEqual(head.content,b'')
            with ZipFile(io.BytesIO(download.content)) as z:
                self.assertIsNone(z.testzip())
                self.assertEqual(z.read('design.v').decode(),ADDER)
            self.assertEqual(client.get('/api/verilog/download/invalid').status_code,404)
            self.assertEqual(client.post('/api/verilog/inspect', json={'source':'bad'}).status_code,400)


if __name__ == '__main__': unittest.main()
