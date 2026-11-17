"""Build the portable source ZIP without logs, temporary files or bytecode."""
from pathlib import Path
import zipfile

ROOT=Path(__file__).resolve().parent
output=ROOT.parent/'Nand-Asset-Studio.zip'
with zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED) as bundle:
    for path in sorted(ROOT.rglob('*')):
        if not path.is_file() or '__pycache__' in path.parts or path.suffix in ('.log','.pyc'):
            continue
        bundle.write(path,'NandStudio/'+path.relative_to(ROOT).as_posix())
with zipfile.ZipFile(output) as bundle:
    assert bundle.testzip() is None
    assert 'NandStudio/app.py' in bundle.namelist()
    assert len([n for n in bundle.namelist() if n.startswith('NandStudio/vendor/os/') and n.endswith('.vm')])==8
print(output)
