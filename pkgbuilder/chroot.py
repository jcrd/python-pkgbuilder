# This project is licensed under the MIT License.

"""
.. module:: chroot
   :synopsis: A wrapper for mkarchroot and makechrootpkg.

.. moduleauthor:: James Reed <jcrd@tuta.io>
"""

from pathlib import Path
from shutil import rmtree
import logging

from .utils import CmdLogger, cwd

log = logging.getLogger('pkgbuilder.chroot')
cmdlog = CmdLogger(log)


class Chroot:
    """
    A mkarchroot-based chroot capable of building packages with makechrootpkg.

    :param pacman_conf: Path to pacman configuration file
    :param makepkg_conf: Path to makepkg configuration file
    :param working_dir: Path to chroot directory
    """
    def __init__(self, pacman_conf, makepkg_conf, working_dir):
        self.pacman_conf = pacman_conf
        self.makepkg_conf = makepkg_conf
        self.working_dir = Path(working_dir)
        self.root = Path(working_dir, 'root')

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

    def update(self):
        """
        Update the chroot with `pacman -Syu`.
        """
        if not self.exists():
            self.make()
        else:
            cmd = ['arch-nspawn', str(self.root), 'pacman', '-Syu']
            cmdlog.run(cmd)

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
        pkgbuild.prepare()
        cmd = ['makechrootpkg', '-cr', str(self.working_dir)]
        for d in deps:
            cmd += ['-I', d]
        cmd += ['--', '-s']
        with cwd(pkgbuild.builddir):
            return cmdlog.run(cmd)
