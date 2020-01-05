import unittest

from pkgbuilder.builder import Builder
from pkgbuilder.pkgbuild import Pkgbuild, LocalDir, Restriction

from .common import test1_pkg, test1_dep1_pkg, localdir, chrootdir, pkgnames


def newBuilder(pkg='test1'):
    return Builder(pkg,
                   builddir='/tmp/pkgbuilder/cache',
                   chrootdir=chrootdir,
                   localdir=localdir,
                   source=Pkgbuild.Source.Local)


class TestMakeChroot(unittest.TestCase):
    def setUp(self):
        self.builder = newBuilder()

    def test_make_chroot(self):
        self.builder.chroot.make()
        self.assertTrue(self.builder.chroot.exists())

    def tearDown(self):
        self.builder.pkgbuild.remove()

class TestBuild(unittest.TestCase):
    def setUp(self):
        self.builder = newBuilder()
        self.builder.chroot.make()

    def test_build(self):
        self.assertTrue(self.builder._build())
        self.assertIn(test1_pkg, pkgnames(self.builder.packages))
        self.assertIn(test1_dep1_pkg, pkgnames(self.builder.dependencies))
        self.assertTrue(self.builder.verify())

    def tearDown(self):
        self.builder.pkgbuild.remove()


class TestSaveManifest(unittest.TestCase):
    def setUp(self):
        self.builder = newBuilder()
        self.builder._build()

    def test_save_manifest(self):
        self.assertTrue(self.builder.exists())

    def tearDown(self):
        self.builder.pkgbuild.remove()


class TestLoadManifest(unittest.TestCase):
    def setUp(self):
        self.builder = newBuilder()
        self.builder.build()

    def test_load_manifest(self):
        j = self.builder.load()
        self.assertIsNotNone(j)
        self.assertIn(test1_pkg, pkgnames(j['packages']))
        self.assertIn(test1_dep1_pkg, pkgnames(j['dependencies']))

    def tearDown(self):
        self.builder.pkgbuild.remove()


class TestFailingBuild(unittest.TestCase):
    def setUp(self):
        self.builder = newBuilder('test-fail')
        try:
            self.builder.build()
        except LocalDir.ProviderNotFoundError:
            pass

    def test_no_manifest(self):
        self.assertFalse(self.builder.exists())

    def tearDown(self):
        self.builder.pkgbuild.remove()


class TestDependencyRestriction(unittest.TestCase):
    def setUp(self):
        self.builder = newBuilder('test-dep-restriction')

    def test_dependency_restriction(self):
        self.assertTrue(self.builder.build())

    def tearDown(self):
        self.builder.pkgbuild.remove()

class TestDependencyRestrictionFailure(unittest.TestCase):
    def setUp(self):
        self.builder = newBuilder('test-dep-restriction-fail')

    def test_dependency_restriction_failure(self):
        try:
            self.builder.build()
            return False
        except LocalDir.ProviderNotFoundError as e:
            if Restriction('>', '2') in e.args[0]['version_restrictions']:
                return True

    def tearDown(self):
        self.builder.pkgbuild.remove()

if __name__ == '__main__':
    unittest.main()
