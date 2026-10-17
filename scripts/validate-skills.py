#!/usr/bin/env python3
"""Validate every independent Skill and repository workflow; fail closed."""
import argparse
from pathlib import Path
import re
import sys
import tempfile
from urllib.parse import unquote, urlsplit

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from skill_sources import materialize


class UniqueLoader(yaml.SafeLoader):
    """Reject duplicate keys instead of silently accepting the last value."""


def unique_mapping(loader, node, deep=False):
    result = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in result:
            raise ValueError(f'duplicate YAML key: {key}')
        result[key] = loader.construct_object(value_node, deep=deep)
    return result


UniqueLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, unique_mapping)


def load_yaml(text):
    return yaml.load(text, Loader=UniqueLoader)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def validate_skill(skill):
    require(skill.is_dir() and not skill.is_symlink(), 'Skill must be a real directory')
    files = sorted(skill.rglob('*'))
    require(not any(p.is_symlink() for p in files), 'symlinks are forbidden in Skill packages')
    entry = skill / 'SKILL.md'
    require(entry.is_file(), 'missing SKILL.md')
    text = entry.read_text(encoding='utf-8')
    match = re.match(r'\A---\r?\n(.*?)\r?\n---(?:\r?\n|$)', text, re.S)
    require(match is not None, 'missing YAML frontmatter')
    metadata = load_yaml(match.group(1))
    require(isinstance(metadata, dict) and set(metadata) == {'name', 'description'},
            'frontmatter must contain only name and description')
    name = metadata['name']
    require(isinstance(name, str) and len(name) <= 64 and
            re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', name) and name == skill.name,
            'name must match directory, use lowercase hyphenated syntax, and be <=64 characters')
    description = metadata['description']
    require(isinstance(description, str) and 0 < len(description.strip()) <= 1024,
            'description must be nonempty text <=1024 characters')
    require('<' not in description and '>' not in description, 'description cannot contain angle brackets')
    require(text[match.end():].strip(), 'missing execution instructions')
    ui_file = skill / 'agents/openai.yaml'
    require(ui_file.is_file(), 'missing agents/openai.yaml')
    ui = load_yaml(ui_file.read_text(encoding='utf-8'))
    require(isinstance(ui, dict) and isinstance(ui.get('interface'), dict), 'missing UI interface')
    for field in ('display_name', 'short_description', 'default_prompt'):
        value = ui['interface'].get(field)
        require(isinstance(value, str) and value.strip(), f'missing UI {field}')
    require(f'${name}' in ui['interface']['default_prompt'], 'default_prompt must invoke the Skill')
    require((skill / 'references').is_dir() and any((skill / 'references').glob('*.md')),
            'missing reference documents')
    for path in files:
        if not path.is_file() or path.suffix not in {'.md', '.yaml', '.yml', '.py', '.txt', '.json'}:
            continue
        content = path.read_text(encoding='utf-8')
        require(content.strip(), f'empty file: {path.relative_to(skill)}')
        require(not re.search(r'\b(?:TODO|FIXME|TBD|PLACEHOLDER)\b|待补充|待填写', content, re.I),
                f'placeholder in {path.relative_to(skill)}')
        if path.suffix != '.md':
            continue
        # Inline links, images, reference-style links and autolinked relative paths.
        links = re.findall(r'!?\[[^\]]*\]\(\s*(<[^>]+>|[^\s)]+)', content)
        links += re.findall(r'^\s*\[[^\]]+\]:\s*(<[^>]+>|\S+)', content, re.M)
        for link in links:
            target = unquote(link.strip('<>'))
            parsed = urlsplit(target)
            if parsed.scheme in {'https', 'http', 'mailto'} or target.startswith('#'):
                continue
            require(not parsed.scheme and not parsed.netloc and not target.startswith('/'),
                    f'unsupported or absolute reference: {target}')
            if not parsed.path:
                continue
            resolved = (path.parent / parsed.path).resolve()
            require(resolved.is_relative_to(skill.resolve()), f'reference escapes Skill: {target}')
            require(resolved.is_file(), f'broken reference in {path.name}: {target}')
    return name


def validate_repository(root):
    for required in ('.github/workflows/validate.yml', '.github/workflows/publish.yml',
                     '.github/pull_request_template.md', 'scripts/validate-skills.py',
                     'scripts/package-skills.py', 'scripts/build-skills.py', 'scripts/skill_sources.py',
                     'README.md', '.gitignore'):
        require((root / required).is_file(), f'missing repository file: {required}')
    errors = []
    with tempfile.TemporaryDirectory() as tmp:
        stage = Path(tmp)
        entries = materialize(root, stage)
        for platform, name in entries:
            try:
                skill = stage / platform / name
                validate_skill(skill)
                if platform == 'gpt':
                    entry = (skill / 'SKILL.md').read_text()
                    require('references/platform-runtime.md' in entry, 'missing GPT runtime reference')
                    for path in skill.rglob('*.md'):
                        content = path.read_text()
                        require('/home/box/agent-data/' not in content, 'foreign runtime path in GPT package')
            except (ValueError, OSError, yaml.YAMLError) as exc:
                errors.append(f'{platform}/{name}: {exc}')
    for workflow in sorted((root / '.github/workflows').glob('*.y*ml')):
        try:
            data = load_yaml(workflow.read_text(encoding='utf-8'))
            require(isinstance(data, dict) and isinstance(data.get('jobs'), dict) and data['jobs'],
                    'workflow must contain jobs')
            # PyYAML YAML 1.1 treats the GitHub key `on` as True.
            require('on' in data or True in data, 'workflow must contain triggers')
        except (ValueError, OSError, yaml.YAMLError) as exc:
            errors.append(f'{workflow.name}: {exc}')
    require(not errors, '\n'.join(errors))
    return entries


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    try:
        names = validate_repository(args.root.resolve())
    except (ValueError, OSError, yaml.YAMLError) as exc:
        print(f'Validation failed: {exc}', file=sys.stderr)
        return 1
    print('Validated: ' + ', '.join(f'{p}/{n}' for p, n in names))
    return 0


if __name__ == '__main__':
    sys.exit(main())
