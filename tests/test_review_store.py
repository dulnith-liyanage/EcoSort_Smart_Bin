"""Image/label integrity, migration, storage bounds and material estimates."""
import base64
import io
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
import zipfile
from PIL import Image
from dashboard.store import EventStore


def capture():
    raw=io.BytesIO(); Image.new('RGB',(40,30),'green').save(raw,'JPEG')
    return {'jpeg':base64.b64encode(raw.getvalue()).decode(),'at':1234567890.0}


class ReviewStoreTests(unittest.TestCase):
    def setUp(self):
        self.directory=tempfile.TemporaryDirectory();self.addCleanup(self.directory.cleanup)
        self.path=Path(self.directory.name)/'history.sqlite3'
        self.store=EventStore(self.path)

    def test_migration_preserves_legacy_route_without_inventing_a_photo(self):
        path=Path(self.directory.name)/'legacy.sqlite3'
        with sqlite3.connect(path) as db:
            db.execute('CREATE TABLE events (id INTEGER PRIMARY KEY,at REAL NOT NULL,category TEXT NOT NULL,score REAL,mode TEXT NOT NULL,status TEXT NOT NULL)')
            db.execute("INSERT INTO events VALUES(1,0,'metal',.7,'hardware','command_completed')")
        legacy=EventStore(path)
        self.assertEqual(legacy.get(1)['category'],'metal')
        self.assertFalse(legacy.get(1)['has_image'])
        self.assertIsNone(legacy.image_path(1))

    def test_review_is_persistent_preserves_route_and_does_not_expose_paths(self):
        event=self.store.add('plastic',.4,'hardware',capture=capture(),model='clip')
        self.assertTrue(self.store.image_path(event).is_file())
        self.store.review(event,'food')
        row=EventStore(self.path).get(event)
        self.assertEqual(row['category'],'plastic')
        self.assertEqual(row['corrected_category'],'food')
        self.assertNotIn('capture_file',row)
        self.assertEqual(self.store.counts('hardware')['plastic'],1)
        self.assertEqual(self.store.summary('hardware')['recyclable_percent'],0)
        self.assertEqual(self.store.summary('hardware')['non_recyclable_percent'],100)

    def test_zero_totals_empty_and_unsupported_are_honest(self):
        self.assertIsNone(self.store.summary('hardware')['recyclable_percent'])
        event=self.store.add('paper',.1,'hardware',capture=capture())
        self.store.review(event,'empty')
        self.assertEqual(self.store.summary('hardware')['total'],0)
        self.assertEqual(self.store.summary('hardware')['empty_excluded'],1)
        self.store.review(event,'unsupported')
        summary=self.store.summary('hardware')
        self.assertEqual(summary['other_percent'],100)
        self.assertEqual(summary['non_recyclable_percent'],0)

    def test_summary_uses_current_mode_and_today_only(self):
        for category in ('paper','plastic','metal','food'):
            self.store.add(category,.7,'hardware')
        self.store.add('food',.7,'demo')
        old=self.store.add('food',.7,'hardware')
        with self.store.connect() as db:db.execute('UPDATE events SET at=0 WHERE id=?',(old,))
        self.assertEqual(self.store.summary('hardware')['recyclable_percent'],75)
        self.assertEqual(len(self.store.rows(mode='demo')),1)

    def test_review_rejects_bad_labels_and_missing_photos(self):
        event=self.store.add('paper',.5,'hardware')
        for label in ('wrong','paper'):
            with self.assertRaises(ValueError):self.store.review(event,label)
        with self.assertRaises(ValueError):self.store.get(999)

    def test_bad_image_does_not_lose_route_record(self):
        for bad in [{'jpeg':'bad data','at':0},{'jpeg':'x'*1500001,'at':0}]:
            event=self.store.add('metal',.7,'hardware',capture=bad)
            self.assertFalse(self.store.get(event)['has_image'])
        self.assertEqual(len(self.store.rows()),2)

    def test_retention_prefers_reviewed_images_and_keeps_history(self):
        with patch('dashboard.store.MAX_IMAGES',2):
            a=self.store.add('paper',.8,'hardware',capture=capture())
            self.store.review(a,'paper')
            b=self.store.add('plastic',.8,'hardware',capture=capture())
            c=self.store.add('food',.8,'hardware',capture=capture())
        self.assertTrue(self.store.get(a)['has_image'])
        self.assertFalse(self.store.get(b)['has_image'])
        self.assertTrue(self.store.get(c)['has_image'])
        self.assertEqual(len(self.store.rows()),3)

    def test_retention_also_enforces_byte_limit(self):
        with patch('dashboard.store.MAX_IMAGE_BYTES',1):
            event=self.store.add('paper',.8,'hardware',capture=capture())
        self.assertFalse(self.store.get(event)['has_image'])
        self.assertEqual(list(self.store.images.iterdir()),[])

    def test_export_contains_only_reviewed_hardware_photos_and_correct_labels(self):
        a=self.store.add('plastic',.4,'hardware',capture=capture())
        self.store.review(a,'metal')
        self.store.add('food',.5,'hardware',capture=capture())
        demo=self.store.add('paper',.8,'demo',capture=capture());self.store.review(demo,'paper')
        with zipfile.ZipFile(io.BytesIO(self.store.export_reviews())) as archive:
            manifest=json.loads(archive.read('labels.json'))
            self.assertEqual(len(manifest),1)
            self.assertEqual(manifest[0]['label'],'metal')
            self.assertEqual(manifest[0]['prediction'],'plastic')
            Image.open(io.BytesIO(archive.read(manifest[0]['image']))).verify()
