# This project is licensed under the MIT License.

"""
.. module:: chroot
   :synopsis: A wrapper for mkarchroot and makechrootpkg.

.. moduleauthor:: James Reed <jcrd@tuta.io>
"""

from pathlib import Path
from shutil import copy2, rmtree
import logging
import re

from parse import compile

from .utils import CmdLogger, cwd

log = logging.getLogger('pkgbuilder.chroot')
cmdlog = CmdLogger(log)


class Mirrorlist:
    """
    A chroot's mirrorlist.

    :param chroot: The chroot
    """
    archive_url = 'https://archive.archlinux.org/repos'

    def __init__(self, chroot):
        self.chroot = chroot
        self.path = str(chroot.root) + '/etc/pacman.d/mirrorlist'
        self.mirrors = []

    def __str__(self):
        return '\n'.join(['Server = ' + m for m in self.mirrors])

    def read(self):
        """
        Read the mirrors from the mirrorlist file.

        :return: List of mirror URLs
        """
        p = compile('Server = {url}\n')
        with open(self.path) as f:
            for line in f:
                r = p.parse(line)
                if r:
                    self.mirrors.append(r.named['url'])
        return self.mirrors

    def write(self):
        """
        Write the list of mirrors to the mirrorlist file.

        :return: String of mirrorlist content
        """
        with open(self.path, 'w') as f:
            f.write(str(self))
        self.chroot.refresh()
        return str(self)

    def copy(self, path='/etc/pacman.d/mirrorlist'):
        """
        Copy the provided mirrorlist into the chroot and refresh pacman
        databases.

        :param path: Path to the mirrorlist
        """
        copy2(path, self.path)
        self.chroot.refresh()
        self.read()

    def set(self, mirror, write=True):
        """
        Set the given mirror as the chroot's only mirror and refresh pacman
        databases.

        :param mirror: The mirror URL
        :param write: Whether to write the changed mirrorlist to the chroot, \
        defaults to `True`
        """
        self.mirrors = [mirror]
        if write:
            self.write()

    def add(self, mirror, write=True):
        """
        Append the given mirror to the chroot's mirrorlist and refresh pacman
        databases.

        :param mirror: The mirror URL
        :param write: Whether to write the changed mirrorlist to the chroot, \
        defaults to `True`
        """
        self.mirrors.append(mirror)
        if write:
            self.write()

    def set_date(self, date, write=True):
        """
        Set the mirror to the Arch Linux Archive repository of the given date.

        :param date: A date object
        :param write: Whether to write the changed mirrorlist to the chroot, \
        defaults to `True`
        :return: The mirror URL
        """
        date_url = f'{date:/%Y/%m/%d}'
        mirror = Mirrorlist.archive_url + date_url + '/$repo/os/$arch'
        self.set(mirror, write)
        return mirror


class Chroot:
    """
    A mkarchroot-based chroot capable of building packages with makechrootpkg.

    :param working_dir: Path to chroot directory
    """
    def __init__(self, working_dir):
        self.working_dir = Path(working_dir)
        self.root = Path(working_dir, 'root')
        self.mirrorlist = Mirrorlist(self)

    def exists(self):
        """
        Check if the chroot exists.

        :return: `True` if exists, `False` otherwise
        """
        return self.root.exists()

    def make(self):
        """
        Make the chroot using mkarchroot.
        """
        if not self.working_dir.exists():
            self.working_dir.mkdir(parents=True)
        cmd = ['mkarchroot', str(self.root), 'base-devel', 'devtools']
        cmdlog.run(cmd)

    def pacman(self, flags):
        """
        Run pacman with the given flags in the chroot.

        :param flags: String containing flags for the pacman command
        """
        cmdlog.run(['arch-nspawn', str(self.root), 'pacman', flags])

    def refresh(self):
        """
        Refresh pacman databases.
        """
        self.pacman('-Syy')

    def update(self):
        """
        Update the chroot with `pacman -Syu`.
        """
        if not self.exists():
            self.make()
        else:
            self.pacman('-Syuu')

    def remove(self):
        """
        Remove the chroot.
        """
        if self.exists():
            rmtree(self.working_dir)

    def makepkg(self, pkgbuild, deps=[]):
        """
        Build a package in the chroot using makechrootpkg.

        :param pkgbuild: Pkgbuild to build
        :param deps: List of dependency package paths to install into chroot
        :return: makechrootpkg return code, stdout, and stderr
        """
        if not self.exists():
            self.make()
        pkgbuild.update()
        cmd = ['makechrootpkg', '-cr', str(self.working_dir)]
        for d in deps:
            cmd += ['-I', d]
        cmd += ['--', '-s']
        with cwd(pkgbuild.builddir):
            return cmdlog.run(cmd)
