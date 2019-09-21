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


class TestNoPkgbuild(unittest.TestCase):
    def test_no_pkgbuild_error(self):
        try:
            Pkgbuild.new('test-nopkgbuild',
                         builddir='/tmp/pkgbuilder/cache',
                         localdir=localdir,
                         source=Pkgbuild.Source.Local)
            return False
        except Pkgbuild.NoPkgbuildError:
            return True


class TestSourceNotFound(unittest.TestCase):
    def test_source_not_found_error(self):
        try:
            Pkgbuild.new('test-fail',
                         builddir='/tmp/pkgbuilder/cache',
                         localdir=localdir,
                         source=Pkgbuild.Source.Local)
            return False
        except Pkgbuild.SourceNotFoundError:
            return True
