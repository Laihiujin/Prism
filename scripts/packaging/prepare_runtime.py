"""Stage a relocatable native conda runtime without modifying local account data."""
import argparse
import ast
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile


def prune_unchanged_windows_records(destination: Path):
    """Avoid reopening loaded Python binaries when conda-pack has no change to make.

    This also supports environments whose conda package download cache was cleaned.
    Real entrypoint/shebang replacements are retained.
    """
    from conda_pack.prefixes import replace_prefix
    script = destination / 'Scripts/conda-unpack-script.py'
    source = script.read_text(encoding='utf-8')
    records = next(node.value for node in ast.parse(source).body if isinstance(node, ast.Assign)
                   and any(isinstance(target, ast.Name) and target.id == '_prefix_records' for target in node.targets))
    filtered = []
    for name, placeholder, mode in ast.literal_eval(records):
        file = destination / name
        if mode == 'binary':
            data = file.read_bytes()
            if replace_prefix(data, mode, placeholder, '__PRISM_FUTURE_PREFIX__') == data:
                continue
        filtered.append((name, placeholder, mode))
    lines = source.splitlines(keepends=True)
    start = sum(map(len, lines[:records.lineno - 1])) + records.col_offset
    end = sum(map(len, lines[:records.end_lineno - 1])) + records.end_col_offset
    script.write_text(source[:start] + repr(filtered) + source[end:], encoding='utf-8')


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
    if os.name == 'nt':
        prune_unchanged_windows_records(destination)
    manifest = json.loads((runtime / 'prism-runtime.json').read_text(encoding='utf-8'))
    manifest.update(envDir='.', python='python.exe' if os.name == 'nt' else 'bin/python')
    (destination / 'prism-runtime.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('destination', type=Path)
    prepare(parser.parse_args().destination)
