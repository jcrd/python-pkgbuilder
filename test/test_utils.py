from pathlib import Path
from shutil import copytree
from tempfile import TemporaryDirectory
import os
import unittest

from pkgbuilder.utils import synctree


class TestSynctree(unittest.TestCase):
    def setUp(self):
        self.seed = TemporaryDirectory()
        self.tmp = TemporaryDirectory()
        self.dest = Path(self.tmp.name, 'synctree')
        self.dir = Path(self.seed.name, 'dir')
        os.mkdir(self.dir)

        def echo(contents, *args):
            with open(Path(self.seed.name, *args), 'w') as f:
                f.write(contents)

        echo('before', 'file1')
        echo('before', 'file2')
        echo('before', 'file3')
        echo('before', self.dir, 'file1')
        echo('before', self.dir, 'file2')
        echo('before', self.dir, 'file3')

        copytree(self.seed.name, self.dest)

        echo('after', 'file1')
        echo('after', self.dir, 'file1')
        echo('new', 'file4')
        echo('new', self.dir, 'file4')

    def test_synctree(self):
        synctree(self.seed.name, self.dest)

        with open(Path(self.dest, 'file1')) as f:
            content = list(f)
            self.assertEqual(content[0], 'after')
        with open(Path(self.dest, self.dir, 'file1')) as f:
            content = list(f)
            self.assertEqual(content[0], 'after')
        self.assertTrue(Path(self.dest, 'file4').exists())
        self.assertTrue(Path(self.dest, self.dir, 'file4').exists())

    def tearDown(self):
        self.seed.cleanup()
        self.tmp.cleanup()
