"""Assemble self-contained skills from shared sources and explicit platform layers."""
import json
from pathlib import Path
import re

PLATFORMS = ('gpt', 'grok')
NAME = re.compile(r'[a-z0-9]+(?:-[a-z0-9]+)*')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def files(directory):
    if not directory.exists():
        return {}
    require(directory.is_dir() and not directory.is_symlink(), f'invalid source directory: {directory}')
    result = {}
    for path in sorted(directory.rglob('*')):
        require(not path.is_symlink(), f'symlinks are forbidden: {path}')
        if path.is_file():
            rel = path.relative_to(directory).as_posix()
            require('__pycache__' not in path.parts and path.suffix != '.pyc', f'generated source file: {path}')
            result[rel] = path.read_bytes()
    return result


def inventory(root):
    require((root / 'shared').is_dir() and not (root / 'shared').is_symlink(), 'missing or unsafe shared directory')
    require((root / 'platforms').is_dir() and not (root / 'platforms').is_symlink(), 'missing or unsafe platforms directory')
    names = None
    for platform in PLATFORMS:
        directory = root / 'platforms' / platform
        require(directory.is_dir() and not directory.is_symlink(), f'missing platform: {platform}')
        current = sorted(p.name for p in directory.iterdir() if p.is_dir() and p.name != '_common')
        require(current, f'no Skills for {platform}')
        for name in current:
            require(NAME.fullmatch(name), f'invalid skill directory: {name}')
        require(names is None or names == current, 'GPT and Grok skill sets differ')
        names = current
    for path in (root / 'shared').iterdir():
        require(path.is_dir() and path.name in names, f'unused shared source: {path}')
    return [(platform, name) for platform in PLATFORMS for name in names]


def assembled_files(root, platform, name):
    require(platform in PLATFORMS and NAME.fullmatch(name), 'invalid platform or skill')
    directory = root / 'platforms' / platform
    override_file = directory / 'overrides.json'
    overrides = json.loads(override_file.read_text()) if override_file.exists() else {}
    require(isinstance(overrides, dict), 'overrides must be an object')
    allowed = overrides.get(name, [])
    require(isinstance(allowed, list) and all(isinstance(p, str) for p in allowed), 'invalid override list')
    shared = files(root / 'shared' / name)
    common = files(directory / '_common')
    specific = files(directory / name)
    require(not (shared.keys() & common.keys()), 'common/shared file collision')
    result = {**shared, **common}
    collisions = set(result) & set(specific)
    require(collisions == set(allowed), f'{platform}/{name}: undeclared or stale overrides: {sorted(collisions ^ set(allowed))}')
    result.update(specific)
    require('SKILL.md' in result, f'{platform}/{name}: missing SKILL.md')
    return dict(sorted(result.items()))


def materialize(root, output, platform=None):
    """Write only into an empty directory, never overwrite installed or source files."""
    root, output = root.resolve(), output.resolve()
    for source in (root / 'shared', root / 'platforms'):
        require(not output.is_relative_to(source), 'output must be outside source directories')
    require(platform is None or platform in PLATFORMS, 'invalid platform')
    require(not output.exists() or (output.is_dir() and not any(output.iterdir())), 'output must be empty')
    entries = [(p, n) for p, n in inventory(root) if platform is None or p == platform]
    payloads = [(p, n, assembled_files(root, p, n)) for p, n in entries]
    for p, name, payload in payloads:
        for rel, content in payload.items():
            target = output / p / name / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)
    return entries
