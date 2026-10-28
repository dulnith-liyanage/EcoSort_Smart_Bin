"""Local route history and explicitly reviewed training examples."""
import base64
from datetime import datetime
import io
import json
from pathlib import Path
import sqlite3
import time
import uuid
import zipfile
from zoneinfo import ZoneInfo

LABELS = ('paper', 'plastic', 'metal', 'food')
REVIEW_LABELS = (*LABELS, 'unsupported', 'empty')
MAX_IMAGES = 500
MAX_IMAGE_BYTES = 64 * 1024 * 1024


class EventStore:
    def __init__(self, path):
        self.path = Path(path)
        self.images = self.path.parent / 'captures'
        self.images.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS events (id INTEGER PRIMARY KEY, at REAL NOT NULL, category TEXT NOT NULL, score REAL, mode TEXT NOT NULL, status TEXT NOT NULL)')
            columns = {r[1] for r in db.execute('PRAGMA table_info(events)')}
            for name, kind in [('capture_file','TEXT'), ('capture_at','REAL'), ('corrected_category','TEXT'), ('reviewed_at','REAL'), ('model','TEXT')]:
                if name not in columns:
                    db.execute(f'ALTER TABLE events ADD COLUMN {name} {kind}')

    def connect(self):
        return sqlite3.connect(self.path, timeout=5)

    def add(self, category, score, mode, status='command_completed', capture=None, model=None):
        if category not in LABELS:
            raise ValueError('Invalid category')
        filename = None
        captured_at = None
        if capture:
            try:
                from PIL import Image
                encoded = capture['jpeg']
                if not isinstance(encoded, str) or len(encoded) > 1500000:
                    raise ValueError('Oversized capture')
                raw = base64.b64decode(encoded, validate=True)
                with Image.open(io.BytesIO(raw)) as image:
                    if image.format != 'JPEG' or max(image.size) > 2048:
                        raise ValueError('Invalid capture')
                    image = image.convert('RGB')
                    image.thumbnail((1024, 1024))
                    filename = uuid.uuid4().hex + '.jpg'
                    image.save(self.images / filename, 'JPEG', quality=85)
                captured_at = float(capture['at'])
            except (ValueError, KeyError, TypeError, OSError):
                if filename:
                    (self.images / filename).unlink(missing_ok=True)
                filename = None  # A capture failure must not hide a completed route.
        with self.connect() as db:
            cursor = db.execute('INSERT INTO events (at,category,score,mode,status,capture_file,capture_at,model) VALUES (?,?,?,?,?,?,?,?)',
                                (time.time(),category,score,mode,status,filename,captured_at,model))
            event_id = cursor.lastrowid
        self.prune()
        return event_id

    @staticmethod
    def _row(row):
        event = dict(row)
        event.pop('capture_file', None)
        return event

    def rows(self, limit=250, mode=None, offset=0):
        with self.connect() as db:
            db.row_factory = sqlite3.Row
            query = 'SELECT *, capture_file IS NOT NULL AS has_image FROM events'
            args = []
            if mode is not None:
                query += ' WHERE mode=?'; args.append(mode)
            query += ' ORDER BY id DESC LIMIT ? OFFSET ?'; args.extend((limit,offset))
            return [self._row(row) for row in db.execute(query,args)]

    def get(self, event_id):
        with self.connect() as db:
            db.row_factory = sqlite3.Row
            row = db.execute('SELECT *, capture_file IS NOT NULL AS has_image FROM events WHERE id=?',(event_id,)).fetchone()
        if row is None:
            raise ValueError('Route not found')
        return self._row(row)

    def image_path(self, event_id):
        with self.connect() as db:
            row = db.execute('SELECT capture_file FROM events WHERE id=?',(event_id,)).fetchone()
        if row is None or not row[0]:
            return None
        filename = row[0]
        if len(filename) != 36 or not filename.endswith('.jpg') or any(c not in '0123456789abcdef' for c in filename[:-4]):
            return None
        path = self.images / filename
        return path if path.is_file() else None

    def review(self, event_id, category):
        if category not in REVIEW_LABELS:
            raise ValueError('Invalid review category')
        if self.image_path(event_id) is None:
            raise ValueError('No saved image is available to review for this route')
        with self.connect() as db:
            db.execute('UPDATE events SET corrected_category=?,reviewed_at=? WHERE id=?',
                       (category,time.time(),event_id))
        return self.get(event_id)

    def counts(self, mode):
        midnight = datetime.now(ZoneInfo('Asia/Colombo')).replace(hour=0,minute=0,second=0,microsecond=0).timestamp()
        with self.connect() as db:
            counts = dict(db.execute('SELECT category,COUNT(*) FROM events WHERE at>=? AND mode=? GROUP BY category',(midnight,mode)))
        return {key:counts.get(key,0) for key in LABELS}

    def summary(self, mode):
        midnight = datetime.now(ZoneInfo('Asia/Colombo')).replace(hour=0,minute=0,second=0,microsecond=0).timestamp()
        with self.connect() as db:
            counts = dict(db.execute('SELECT COALESCE(corrected_category,category),COUNT(*) FROM events WHERE at>=? AND mode=? GROUP BY COALESCE(corrected_category,category)',(midnight,mode)))
            reviewed = db.execute('SELECT COUNT(*) FROM events WHERE at>=? AND mode=? AND reviewed_at IS NOT NULL',(midnight,mode)).fetchone()[0]
        empty = counts.pop('empty',0)
        total = sum(counts.values())
        recyclable = sum(counts.get(key,0) for key in ('paper','plastic','metal'))
        food = counts.get('food',0)
        return {'total':total,'recyclable':recyclable,'food':food,'other':total-recyclable-food,
                'recyclable_percent':round(100*recyclable/total,1) if total else None,
                'non_recyclable_percent':round(100*food/total,1) if total else None,
                'other_percent':round(100*(total-recyclable-food)/total,1) if total else None,
                'reviewed':reviewed,'empty_excluded':empty}

    def prune(self):
        # Keep labels/history permanently; bound JPEG storage, pruning unreviewed first.
        with self.connect() as db:
            rows = list(db.execute('SELECT id,capture_file FROM events WHERE capture_file IS NOT NULL ORDER BY reviewed_at IS NOT NULL,at,id'))
            total = sum((self.images / name).stat().st_size for _,name in rows if (self.images/name).is_file())
            remaining = len(rows)
            for event_id,name in rows:
                path = self.images/name
                if remaining<=MAX_IMAGES and total<=MAX_IMAGE_BYTES and path.is_file():
                    continue
                if path.is_file():
                    total -= path.stat().st_size
                    path.unlink()
                db.execute('UPDATE events SET capture_file=NULL WHERE id=?',(event_id,))
                remaining -= 1

    def export_reviews(self):
        output = io.BytesIO()
        manifest = []
        with zipfile.ZipFile(output,'w',compression=zipfile.ZIP_DEFLATED) as archive:
            # Only hardware examples, with human labels and retained images, are exported.
            with self.connect() as db:
                db.row_factory = sqlite3.Row
                rows = list(db.execute('SELECT * FROM events WHERE mode=? AND reviewed_at IS NOT NULL AND capture_file IS NOT NULL ORDER BY id',('hardware',)))
            for row in rows:
                path = self.image_path(row['id'])
                if path is None:
                    continue
                name = f"images/{row['id']}.jpg"
                try:
                    archive.write(path,name)
                except OSError:
                    continue
                manifest.append({'event_id':row['id'],'image':name,'label':row['corrected_category'],
                                 'prediction':row['category'],'match_score':row['score'],
                                 'captured_at':row['capture_at'],'reviewed_at':row['reviewed_at'],'model':row['model']})
            archive.writestr('labels.json',json.dumps(manifest,indent=2))
            archive.writestr('README.txt','Human-reviewed EcoSort camera crops. No model has been trained by exporting.\nSplit by physical object/session before training; hold out a separate test set.\nLabels empty and unsupported are rejection examples, not one of the four bins.\nDo not publish images without checking their contents.\n')
        return output.getvalue()
