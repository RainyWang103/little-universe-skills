"""Cross-platform assembly must preserve boundaries and be usable without the repo."""
import importlib.util
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from skill_sources import assembled_files, materialize

spec = importlib.util.spec_from_file_location('platform_packager', ROOT / 'scripts/package-skills.py')
packager = importlib.util.module_from_spec(spec)
spec.loader.exec_module(packager)


class PlatformTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'repo'
        shutil.copytree(ROOT, self.root, ignore=shutil.ignore_patterns('.git', 'build', 'dist', '__pycache__'))

    def test_shared_change_reaches_both_platforms(self):
        path = self.root / 'shared/travel-planner/references/preferences.md'
        path.write_text(path.read_text() + '\nShared revision.\n')
        for platform in ('gpt', 'grok'):
            self.assertIn(b'Shared revision.', assembled_files(self.root, platform, 'travel-planner')['references/preferences.md'])

    def test_platform_rule_does_not_leak(self):
        for platform in ('gpt', 'grok'):
            payload = assembled_files(self.root, platform, 'safety-charter')
            self.assertEqual('references/platform-runtime.md' in payload, platform == 'gpt')
            self.assertEqual(b'/home/box/agent-data/' in payload['SKILL.md'], platform == 'grok')

    def test_undeclared_override_rejected(self):
        path = self.root / 'platforms/gpt/travel-planner/references/preferences.md'
        path.write_text('Accidental duplicate')
        with self.assertRaisesRegex(ValueError, 'undeclared'):
            assembled_files(self.root, 'gpt', 'travel-planner')

    def test_shared_symlink_rejected(self):
        path = self.root / 'shared/travel-planner/references/leak.md'
        path.symlink_to(self.root / 'README.md')
        with self.assertRaisesRegex(ValueError, 'symlinks'):
            assembled_files(self.root, 'gpt', 'travel-planner')

    def test_sets_must_match(self):
        shutil.rmtree(self.root / 'platforms/grok/travel-planner')
        with self.assertRaisesRegex(ValueError, 'sets differ'):
            materialize(self.root, self.root / 'build')

    def test_build_wont_overwrite(self):
        target = self.root / 'build'
        target.mkdir()
        (target / 'important.txt').write_text('keep')
        with self.assertRaisesRegex(ValueError, 'must be empty'):
            materialize(self.root, target)
        self.assertEqual((target / 'important.txt').read_text(), 'keep')

    def test_gpt_only_build(self):
        target = self.root / 'build'
        entries = materialize(self.root, target, 'gpt')
        self.assertEqual(len(entries), 5)
        self.assertFalse((target / 'grok').exists())

    def test_ten_archives_are_independent(self):
        target = self.root / 'dist'
        manifest = packager.package(self.root, target, 'b' * 40)
        self.assertEqual(len(manifest['artifacts']), 10)
        for a in manifest['artifacts']:
            with tempfile.TemporaryDirectory() as tmp:
                with zipfile.ZipFile(target / a['file']) as z:
                    z.extractall(tmp)
                skill = Path(tmp) / a['skill']
                self.assertEqual(packager.validator.validate_skill(skill), a['skill'])
                expected = assembled_files(self.root, a['platform'], a['skill'])
                actual = {p.relative_to(skill).as_posix(): p.read_bytes() for p in skill.rglob('*') if p.is_file()}
                self.assertEqual(actual, expected)


if __name__ == '__main__':
    unittest.main()
