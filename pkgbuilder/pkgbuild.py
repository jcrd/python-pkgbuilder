# This project is licensed under the MIT License.

"""
.. module:: pkgbuild
   :synopsis: Represent local or AUR-based PKGBUILDs.

.. moduleauthor:: James Reed <jcrd@tuta.io>
"""

from enum import Flag, auto
from pathlib import Path
from shutil import copytree, rmtree
from subprocess import run
import logging

from .aur import Aur

log = logging.getLogger('pkgbuilder.pkgbuild')


class Pkgbuild:
    """
    This class represents a local or AUR-based PKGBUILD. It creates the
    directory needed to build the package.
    """
    aur = Aur()

    class SourceNotFoundError(Exception):
        """
        An exception raised when no source is found for the package name.
        """
        pass

    class Source(Flag):
        """
        Flags for local or AUR sources.
        """
        Local = auto()
        Aur = auto()

    @classmethod
    def new(cls, name, builddir, localdir=None, source=None):
        """
        Create a new LocalPkgbuild or AurPkgbuild.

        :param name: Package name
        :param builddir: Path to package build directory
        :param localdir: Path to directory of local PKGBUILDs
        :param source: PKGBUILD source - one of Pkgbuild.Source.Local or \
        Pkgbuild.Source.Aur
        :raises SourceNotFoundError: Raised when no source can be found for \
        name
        :return: LocalPkgbuild or AurPkgbuild
        """
        dir = None
        try:
            path = Path(name).resolve(True)
            dir = path
            name = path.name
        except FileNotFoundError:
            if localdir:
                dir = Path(localdir, name).resolve()
        if dir and not dir.exists():
            dir = None

        err = {'message': 'Source for {} not found'.format(name)}

        if dir and source != cls.Source.Aur:
            return LocalPkgbuild(name, builddir, dir)
        elif source == cls.Source.Local:
            err['source'] = cls.Source.Local
            raise cls.SourceNotFoundError(err)
        else:
            aurpkg = Pkgbuild.aur.get_package(name)
            if aurpkg:
                return AurPkgbuild(name, builddir, aurpkg)
            else:
                err['source'] = cls.Source.Aur
                raise cls.SourceNotFoundError(err)

    def __init__(self, name, buildpath, sourcedir):
        self.name = name
        self.buildpath = Path(buildpath, sourcedir)
        self.builddir = Path(self.buildpath, self.name)
        self._packagelist = []

    def remove(self):
        """
        Remove build directory.
        """
        if not self.builddir.exists():
            return
        log.info('%s: Removing build dir... [%s]', self.name, self.builddir)
        rmtree(self.builddir)

    def update(self):
        """
        Update the build directory. An existing build directory will be
        removed.  Local sources are copied and AUR sources are downloaded to
        the build directory.
        """
        if not self.buildpath.exists():
            self.buildpath.mkdir(parents=True)
        elif self.builddir.exists():
            self.remove()

        self._prepare()
        log.info('%s: PKGBUILD [%s -> %s]', self.name, self.uri, self.builddir)

    def prepare(self):
        """
        Prepare to build the package, i.e. copy or download the PKGBUILD if
        the build directory doesn't already exist.
        """
        if not self.builddir.exists():
            self.update()

    def packagelist(self, makepkg_conf=None):
        """
        Get a list of paths to packages this PKGBUILD will produce when built.

        :param makepkg_conf: Path to makepkg configuration file
        :return: A list of paths to packages
        """
        if self._packagelist:
            return self._packagelist
        self.prepare()
        cmd = ['makepkg', '--packagelist']
        if makepkg_conf:
            cmd += ['--config', makepkg_conf]
        r = run(cmd, cwd=self.builddir, capture_output=True, text=True,
                check=True)
        self._packagelist = r.stdout.splitlines()
        return self._packagelist


class LocalPkgbuild(Pkgbuild):
    """
    A locally sourced PKGBUILD.

    :param name: Package name
    :param buildpath: Path to build directory
    :param localdir: Path to the directory containing PKGBUILD
    """
    def __init__(self, name, buildpath, localdir):
        super().__init__(name, buildpath, 'local')
        self.uri = localdir.as_uri()
        self.localdir = localdir

    def _prepare(self):
        """
        Copy the local PKGBUILD directory to the build directory.
        """
        copytree(self.localdir, self.builddir)


class AurPkgbuild(Pkgbuild):
    """
    An AUR-based PKGBUILD.

    :param name: Package name
    :param buildpath: Path to build directory
    :param aurpkg: AurPackage for the given package name
    """
    def __init__(self, name, buildpath, aurpkg):
        super().__init__(name, buildpath, 'aur')
        self.uri = aurpkg.urlpath
        self.aurpkg = aurpkg

    def _prepare(self):
        """
        Download the AUR-based PKGBUILD to the build directory.
        """
        self.aurpkg.download(self.builddir)
