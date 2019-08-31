import unittest

from pkgbuilder.pkgbuild import Pkgbuild

from .common import test1_pkg, localdir, pkgnames


class TestLocalPkgbuild(unittest.TestCase):
    def setUp(self):
        self.pkgbuild = Pkgbuild.new('test1',
                                     builddir='/tmp/pkgbuilder/cache',
                                     localdir=localdir,
                                     source=Pkgbuild.Source.Local)

    def test_packagelist(self):
        pkgs = self.pkgbuild.packagelist()
        self.assertIn(test1_pkg, pkgnames(pkgs))

    def tearDown(self):
        self.pkgbuild.remove()
