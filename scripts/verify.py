"""Run portable offline checks; does not run Pi setup, cameras or model inference."""
import ast
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
sources=list(ROOT.glob('*.py'))
for folder in ['scripts','tests','dashboard']:
    sources.extend((ROOT/folder).rglob('*.py'))
for path in sources: ast.parse(path.read_text(),filename=str(path))
print(f'Parsed {len(sources)} Python files.',flush=True)
for path in [ROOT/'setup_raspberry_pi.sh', ROOT/'fix_openblas.sh', *sorted((ROOT/'scripts').glob('*.sh'))]:
    subprocess.run(['bash', '-n', str(path)], check=True)
subprocess.run([sys.executable,'-m','unittest','discover','-s','tests','-v'],cwd=ROOT,check=True)
print('Offline checks passed. Physical Pi/recognition/fit checks remain pending.')
