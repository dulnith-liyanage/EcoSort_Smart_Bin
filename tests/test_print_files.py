"""Independent binary STL checks using only Python's standard library."""
from collections import Counter
import json
from pathlib import Path
import struct
import unittest

ROOT=Path(__file__).resolve().parents[1]/'hardware/design/output'

class PrintFiles(unittest.TestCase):
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
