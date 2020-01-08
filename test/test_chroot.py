from datetime import date
import unittest

from pkgbuilder.chroot import Chroot, Mirrorlist

from .common import chrootdir


class TestMirrorlistDate(unittest.TestCase):
    def setUp(self):
        self.mirrorlist = Mirrorlist(Chroot(chrootdir))

    def test_set_date(self):
        self.mirrorlist.set_date(date(2019, 9, 26), False)
        self.assertEqual(self.mirrorlist.mirrors[0],
                         Mirrorlist.archive_url + '/2019/09/26/$repo/os/$arch')


class TestMirrorlistStr(unittest.TestCase):
    def setUp(self):
        self.mirrorlist = Mirrorlist(Chroot(chrootdir))
        self.mirrorlist.mirrors = ['line1', 'line2']

    def test_save(self):
        self.assertEqual(str(self.mirrorlist),
                         'Server = line1\nServer = line2')
