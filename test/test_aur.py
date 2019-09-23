from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from pkgbuilder.aur import GitRepo


class TestGitClone(unittest.TestCase):
    def setUp(self):
        self.url = 'https://aur.archlinux.org/aurutils-git.git'
        self.tmp = TemporaryDirectory()
        self.repopath = Path(self.tmp.name, 'repo')

    def test_git_clone(self):
        repo = GitRepo(self.repopath)
        repo.clone(self.url)
        self.assertTrue(repo.is_repo())

    def tearDown(self):
        self.tmp.cleanup()
