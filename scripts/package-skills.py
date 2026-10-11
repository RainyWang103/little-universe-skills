#!/usr/bin/env python3
"""Build verified per-Skill ZIPs, identified by a full Git commit SHA."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import sys
import tempfile
import zipfile

spec = importlib.util.spec_from_file_location('validate_skills', Path(__file__).with_name('validate-skills.py'))
validator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(validator)
MAX_BYTES = 25_000_000


def package(root, output, sha):
    validator.require(bool(re.fullmatch(r'[0-9a-f]{40}', sha)), 'commit SHA must be 40 lowercase hex characters')
    names = validator.validate_repository(root)
    output = output.resolve()
    validator.require(not output.is_relative_to((root / 'skills').resolve()), 'output must be outside skills')
    output.mkdir(parents=True, exist_ok=True)
    artifacts = []
    # Stage all packages before publishing any files, so a failed Skill leaves no partial build.
    with tempfile.TemporaryDirectory(dir=output) as staging:
        stage = Path(staging)
        for name in names:
            skill = root / 'skills' / name
            files = sorted(p for p in skill.rglob('*') if p.is_file())
            validator.require(sum(p.stat().st_size for p in files) <= MAX_BYTES,
                              f'{name}: uncompressed package exceeds 25 MB')
            filename = f'{name}-{sha}.zip'
            archive = stage / filename
            expected = {f'{name}/{p.relative_to(skill).as_posix()}': p.read_bytes() for p in files}
            with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_DEFLATED) as z:
                for member, content in expected.items():
                    info = zipfile.ZipInfo(member, date_time=(1980, 1, 1, 0, 0, 0))
                    info.compress_type = zipfile.ZIP_DEFLATED
                    info.external_attr = 0o100644 << 16
                    z.writestr(info, content)
            validator.require(archive.stat().st_size <= MAX_BYTES, f'{name}: ZIP exceeds 25 MB')
            with zipfile.ZipFile(archive) as z:
                validator.require(z.testzip() is None, f'{name}: corrupt ZIP')
                validator.require(set(z.namelist()) == set(expected) and len(z.namelist()) == len(expected),
                                  f'{name}: wrong ZIP structure')
                validator.require(f'{name}/SKILL.md' in z.namelist(), f'{name}: missing ZIP entrypoint')
                for member, content in expected.items():
                    validator.require(z.read(member) == content, f'{name}: ZIP content mismatch')
            artifacts.append({'skill': name, 'file': filename, 'bytes': archive.stat().st_size,
                              'sha256': hashlib.sha256(archive.read_bytes()).hexdigest(),
                              'members': sorted(expected)})
        manifest = {'commit_sha': sha, 'max_package_bytes': MAX_BYTES, 'artifacts': artifacts,
                    'deployment': 'download-only; no ChatGPT installation performed'}
        manifest_name = f'build-{sha}.json'
        (stage / manifest_name).write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
        for filename in [a['file'] for a in artifacts] + [manifest_name]:
            (stage / filename).replace(output / filename)
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--output', type=Path, default=Path('dist'))
    parser.add_argument('--sha', required=True)
    args = parser.parse_args()
    try:
        manifest = package(args.root.resolve(), args.output, args.sha)
    except (ValueError, OSError, validator.yaml.YAMLError, zipfile.BadZipFile) as exc:
        print(f'Packaging failed: {exc}', file=sys.stderr)
        return 1
    for artifact in manifest['artifacts']:
        print(f"Built {artifact['file']} ({artifact['bytes']} bytes)")
    return 0


if __name__ == '__main__':
    sys.exit(main())
