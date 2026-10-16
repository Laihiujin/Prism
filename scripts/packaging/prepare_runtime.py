"""Stage a relocatable native conda runtime without modifying local account data."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile


def prepare(destination: Path):
    root = Path(__file__).resolve().parents[2]
    runtime = root / 'prismenv'
    python = runtime / ('python.exe' if os.name == 'nt' else 'bin/python')
    if not (runtime / 'conda-meta').is_dir():
        raise RuntimeError('Run micromamba provision.py before packaging')
    if destination.exists():
        raise RuntimeError('Runtime staging destination must be new')
    flags = {'creationflags': subprocess.CREATE_NO_WINDOW} if os.name == 'nt' else {}
    probe = subprocess.run([str(python), '-c', 'import conda_pack'], capture_output=True, **flags)
    if probe.returncode:
        subprocess.run([str(python), '-m', 'pip', 'install', 'conda-pack==0.9.2'], check=True, **flags)
    with tempfile.TemporaryDirectory(prefix='prism-conda-') as temp:
        archive = Path(temp) / 'runtime.tar'
        subprocess.run([str(python), '-c',
                        'import conda_pack,sys; conda_pack.pack(prefix=sys.argv[1], output=sys.argv[2], format="tar")',
                        str(runtime), str(archive)], check=True, **flags)
        destination.mkdir(parents=True)
        with tarfile.open(archive) as packed:
            packed.extractall(destination, filter='data')
    manifest = json.loads((runtime / 'prism-runtime.json').read_text(encoding='utf-8'))
    manifest.update(envDir='.', python='python.exe' if os.name == 'nt' else 'bin/python')
    (destination / 'prism-runtime.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('destination', type=Path)
    prepare(parser.parse_args().destination)
