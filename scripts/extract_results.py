"""Restore recorded Phase 2C run details from the tracked compressed archive."""
from pathlib import Path
from zipfile import ZipFile

root=Path(__file__).resolve().parents[1]
archive=root/'data/phase2c-raw-details.zip'
with ZipFile(archive) as z:
    items=z.infolist()
    for entry in items:
        path=Path(entry.filename)
        if entry.is_dir() or path.is_absolute() or '..' in path.parts or path.parts[0]!='phase2c-final-pilot':
            raise ValueError('Unexpected archive entry: '+entry.filename)
        target=root/path
        target.parent.mkdir(parents=True,exist_ok=True)
        if target.exists():
            raise FileExistsError(f'Will not overwrite existing raw run: {target}')
        target.write_bytes(z.read(entry))
print(f'Restored {len(items)} recorded run files from {archive.name}')
