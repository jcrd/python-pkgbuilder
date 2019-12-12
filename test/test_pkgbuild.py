from pathlib import Path
import os
import unittest

from pkgbuilder.pkgbuild import Pkgbuild, LocalDir, Restriction, \
    parse_restriction

from .common import test1_pkg, localdir, pkgnames


def newPkgbuild(pkg='test1'):
    return Pkgbuild.new(pkg,
                        builddir='/tmp/pkgbuilder/cache',
                        localdir=localdir,
                        source=Pkgbuild.Source.Local)

class TestLocalPkgbuild(unittest.TestCase):
    def setUp(self):
        self.pkgbuild = newPkgbuild()

    def test_packagelist(self):
        self.assertIn(test1_pkg, pkgnames(self.pkgbuild.packagelist))

    def test_srcinfo(self):
        srcinfo = self.pkgbuild.srcinfo
        file = Path(self.pkgbuild.builddir, '.SRCINFO')
        self.assertTrue(file.exists())
        self.assertEqual(srcinfo['pkgbase'], 'test1')
        self.assertEqual(srcinfo['depends'], ['test1-dep1'])

    def test_dependency_restrictions(self):
        self.assertFalse(self.pkgbuild.dependency_restrictions('test1-dep1'))

    def tearDown(self):
        self.pkgbuild.remove()


class TestNoPkgbuild(unittest.TestCase):
    def test_no_pkgbuild_error(self):
        try:
            newPkgbuild('test-nopkgbuild')
            return False
        except Pkgbuild.NoPkgbuildError:
            return True


class TestSourceNotFound(unittest.TestCase):
    def test_source_not_found_error(self):
        try:
            newPkgbuild('test-fail')
            return False
        except Pkgbuild.SourceNotFoundError:
            return True


class TestRestriction(unittest.TestCase):
    def test_parse_restriction(self):
        name, r = parse_restriction('test>=2')
        self.assertEqual(name, 'test')
        self.assertEqual(r, Restriction('>=', '2'))


class TestLocalDir(unittest.TestCase):
    def setUp(self):
        self.localdir = LocalDir(localdir, '/tmp/pkgbuilder/cache')
        self.localdir.update()

    def test_srcinfo_generation(self):
        with os.scandir('/tmp/pkgbuilder/cache/local') as dir:
            for entry in dir:
                srcinfo = Path(entry.path, '.SRCINFO')
                self.assertTrue(srcinfo.exists())

    def test_packages(self):
        pkg = LocalDir.Package('test1', '1')
        pkgbuild = newPkgbuild()
        self.assertIn(pkg, self.localdir.packages)
        self.assertTrue(self.localdir.packages[pkg], [pkgbuild])

    def test_provides(self):
        pkg = self.localdir.providers('test-provides-pkg1')
        self.assertTrue(pkg)
        self.assertEqual(pkg[0].name, 'test-provides')

    def test_provides_restricted(self):
        r = Restriction('>', '1')
        pkg = self.localdir.providers('test-provides-version2', [r])
        self.assertTrue(pkg)
        self.assertEqual(pkg[0].name, 'test-provides-version')

    def test_provider_not_found_error(self):
        r = Restriction('<', '2')
        try:
            self.localdir.providers('test-provides-version2', [r])
            return False
        except LocalDir.ProviderNotFoundError:
            return True


if __name__ == '__main__':
    unittest.main()
