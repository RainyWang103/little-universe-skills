"""Integration tests for malformed inputs, exit codes, and distributable ZIPs."""
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

ROOT = Path(__file__).resolve().parents[1]
SHA = 'a' * 40


def module(filename, name):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'scripts' / filename)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


packager = module('package-skills.py', 'packager')


class ScriptTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'repo'
        shutil.copytree(ROOT / 'skills', self.root / 'skills')
        shutil.copytree(ROOT / '.github', self.root / '.github')
        shutil.copytree(ROOT / 'scripts', self.root / 'scripts', ignore=shutil.ignore_patterns('__pycache__'))
        for filename in ('README.md', '.gitignore'):
            shutil.copyfile(ROOT / filename, self.root / filename)
        self.skill = self.root / 'skills/travel-planner'

    def cli(self, script='validate-skills.py', *args):
        return subprocess.run([sys.executable, str(ROOT / 'scripts' / script),
                               '--root', str(self.root), *args], capture_output=True, text=True)

    def reject(self, message):
        result = self.cli()
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn(message, result.stderr)

    def edit_entry(self, before, after):
        path = self.skill / 'SKILL.md'
        path.write_text(path.read_text().replace(before, after))

    def test_valid_repository(self):
        result = self.cli()
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_missing_frontmatter(self):
        self.edit_entry('---', 'invalid')
        self.reject('frontmatter')

    def test_duplicate_key(self):
        self.edit_entry('name: travel-planner', 'name: travel-planner\nname: other')
        self.reject('duplicate YAML key')

    def test_extra_frontmatter_key(self):
        self.edit_entry('name: travel-planner', 'name: travel-planner\nversion: 1')
        self.reject('only name and description')

    def test_bad_name(self):
        self.edit_entry('name: travel-planner', 'name: Travel_Planner')
        self.reject('name must match')

    def test_empty_description(self):
        self.edit_entry('description:', 'description: #')
        self.reject('description must be nonempty')

    def test_missing_ui(self):
        (self.skill / 'agents/openai.yaml').unlink()
        self.reject('missing agents/openai.yaml')

    def test_invalid_ui(self):
        (self.skill / 'agents/openai.yaml').write_text('interface: []\n')
        self.reject('UI interface')

    def test_default_prompt_must_invoke_skill(self):
        path = self.skill / 'agents/openai.yaml'
        path.write_text(path.read_text().replace('$travel-planner', 'planner'))
        self.reject('invoke the Skill')

    def test_missing_reference(self):
        (self.skill / 'references/preferences.md').unlink()
        self.reject('broken reference')

    def test_reference_style_and_encoded_escape(self):
        path = self.skill / 'SKILL.md'
        path.write_text(path.read_text() + '\n[bad]: %2e%2e/README.md\n')
        self.reject('escapes Skill')

    def test_placeholder(self):
        (self.skill / 'references/preferences.md').write_text('TODO: write this\n')
        self.reject('placeholder')

    def test_symlink(self):
        (self.skill / 'references/leak.md').symlink_to(self.root / 'README.md')
        self.reject('symlinks')

    def test_all_skill_directories_checked(self):
        (self.root / 'skills/broken').mkdir()
        self.reject('missing SKILL.md')

    def test_no_skills(self):
        shutil.rmtree(self.root / 'skills/travel-planner')
        self.reject('no Skills')

    def test_malformed_workflow(self):
        (self.root / '.github/workflows/validate.yml').write_text('jobs: [\n')
        self.reject('validate.yml')

    def test_missing_workflow(self):
        (self.root / '.github/workflows/publish.yml').unlink()
        self.reject('missing repository file')

    def test_multiple_independent_packages_and_reproducibility(self):
        second = self.root / 'skills/second-planner'
        shutil.copytree(self.skill, second)
        for path in [second / 'SKILL.md', second / 'agents/openai.yaml']:
            path.write_text(path.read_text().replace('travel-planner', 'second-planner'))
        output = self.root / 'dist'
        first = packager.package(self.root, output, SHA)
        self.assertEqual(len(first['artifacts']), 2)
        for artifact in first['artifacts']:
            with zipfile.ZipFile(output / artifact['file']) as z:
                self.assertTrue(all(n.startswith(artifact['skill'] + '/') for n in z.namelist()))
                self.assertIn(artifact['skill'] + '/SKILL.md', z.namelist())
                for member in z.namelist():
                    self.assertEqual(z.read(member), (self.root / 'skills' / member).read_bytes())
                self.assertIsNone(z.testzip())
        second_build = packager.package(self.root, output, SHA)
        self.assertEqual(first, second_build)
        self.assertEqual(json.loads((output / f'build-{SHA}.json').read_text())['commit_sha'], SHA)

    def test_package_validation_failure_nonzero(self):
        (self.skill / 'SKILL.md').unlink()
        result = self.cli('package-skills.py', '--sha', SHA, '--output', str(self.root / 'dist'))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('missing SKILL.md', result.stderr)
        self.assertFalse(list((self.root / 'dist').glob('*.zip')))

    def test_invalid_sha_nonzero(self):
        result = self.cli('package-skills.py', '--sha', 'main', '--output', str(self.root / 'dist'))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('commit SHA', result.stderr)

    def test_size_limit(self):
        with patch.object(packager, 'MAX_BYTES', 10):
            with self.assertRaisesRegex(ValueError, 'exceeds 25 MB'):
                packager.package(self.root, self.root / 'dist', SHA)
        self.assertFalse(list((self.root / 'dist').glob('*.zip')))

    def test_compressed_size_limit(self):
        # ZIP header overhead forces this small package above its raw content size.
        for path in self.skill.rglob('*'):
            if path.is_file():
                path.unlink()
        (self.skill / 'SKILL.md').write_text('---\nname: travel-planner\ndescription: x\n---\nx\n')
        (self.skill / 'agents/openai.yaml').write_text(
            'interface:\n  display_name: x\n  short_description: x\n  default_prompt: $travel-planner\n')
        (self.skill / 'references/x.md').write_text('x')
        total = sum(p.stat().st_size for p in self.skill.rglob('*') if p.is_file())
        with patch.object(packager, 'MAX_BYTES', total):
            with self.assertRaisesRegex(ValueError, 'ZIP exceeds 25 MB'):
                packager.package(self.root, self.root / 'dist', SHA)

    def test_output_inside_skill_rejected(self):
        with self.assertRaisesRegex(ValueError, 'outside skills'):
            packager.package(self.root, self.skill / 'dist', SHA)


if __name__ == '__main__':
    unittest.main()
