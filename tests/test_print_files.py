"""Independent binary STL checks using only Python's standard library."""
from collections import Counter
import json
from pathlib import Path
import struct
import unittest
import xml.etree.ElementTree as ET
import zipfile

ROOT=Path(__file__).resolve().parents[1]/'hardware/design/output'

class PrintFiles(unittest.TestCase):
    def test_saved_assemblies_contain_the_complete_mount(self):
        required = {'_01_cross_base','_02_motor_pedestal','_03_rim_shoe',
                    '_04_tray_adapter','MG996R_pan','MG996R_tilt',
                    'RB0051_pan_bracket','RB0051_tilt_bracket','Existing_tray'}
        for name, count in [('complete_assembly',30),('motor_assembly',16)]:
            with self.subTest(assembly=name):
                with zipfile.ZipFile(ROOT/(name+'.FCStd')) as archive:
                    document=ET.fromstring(archive.read('Document.xml'))
                features={o.attrib['name'] for o in document.findall('./Objects/Object')
                          if o.attrib.get('type')=='Part::Feature'}
                self.assertEqual(len(features),count)
                self.assertTrue(required.issubset(features),required-features)

    def test_every_print_has_closed_edges_and_positive_volume(self):
        report=json.loads((ROOT/'checks.json').read_text())
        paths=sorted((ROOT/'stl').glob('*.stl'))
        self.assertEqual(len(paths),9)
        for path in paths:
            with self.subTest(part=path.stem):
                data=path.read_bytes()
                count=struct.unpack_from('<I',data,80)[0]
                self.assertEqual(len(data),84+50*count)
                self.assertEqual(count,report[path.stem]['triangles'])
                edges=Counter()
                volume=0
                for i in range(count):
                    values=struct.unpack_from('<12fH',data,84+50*i)
                    a,b,c=[tuple(round(v,5) for v in values[j:j+3]) for j in [3,6,9]]
                    for p,q in [(a,b),(b,c),(c,a)]:edges[tuple(sorted((p,q)))]+=1
                    volume+=(a[0]*(b[1]*c[2]-b[2]*c[1])+a[1]*(b[2]*c[0]-b[0]*c[2])+a[2]*(b[0]*c[1]-b[1]*c[0]))/6
                self.assertTrue(all(n==2 for n in edges.values()))
                self.assertGreater(volume,0)

if __name__ == '__main__': unittest.main()
