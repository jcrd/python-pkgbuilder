# This project is licensed under the MIT License.

"""
.. module:: pkgbuild
   :synopsis: Represent local or AUR-based PKGBUILDs.

.. moduleauthor:: James Reed <jcrd@tuta.io>
"""

from enum import Flag, auto
from pathlib import Path
from shutil import rmtree
from subprocess import run
import logging

from .aur import Aur, GitRepo
from .utils import synctree

log = logging.getLogger('pkgbuilder.pkgbuild')


class Pkgbuild:
    """
    This class represents a local or AUR-based PKGBUILD. It creates the
    directory needed to build the package.
    """
    aur = Aur()

    class NoPkgbuildError(Exception):
        """
        An exception raised when a local directory exists but does not \
        contain a PKGBUILD file.
        """
        pass

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
        :raises NoPkgbuildError: Raised when a local directory exists but \
        does not contain a PKGBUILD file
        :return: LocalPkgbuild or AurPkgbuild
        """
        err = {'message': 'Directory does not contain a PKGBUILD file'}
        dir = None
        try:
            path = Path(name).resolve(True)
            dir = path
            name = path.name
        except FileNotFoundError:
            if localdir:
                dir = Path(localdir, name).resolve()
        if dir:
            if dir.exists():
                if not Path(dir, 'PKGBUILD').exists():
                    err['directory'] = str(dir)
                    raise cls.NoPkgbuildError(err)
            else:
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
        self.check_update = True
        self._packagelist = []

    def remove(self):
        """
        Remove build directory.
        """
        if not self.builddir.exists():
            return
        log.info('%s: Removing build dir... [%s]', self.name, self.builddir)
        rmtree(self.builddir)
        self.check_update = True

    def update(self, force=False):
        """
        Update the build directory. Local sources are synchronized and AUR
        sources are updated via git pull.

        :param force: Force checking for updates
        """
        if not (self.check_update or force):
            return
        if not self.buildpath.exists():
            self.buildpath.mkdir(parents=True)
        self._update()
        self.check_update = False
        log.info('%s: PKGBUILD [%s -> %s]', self.name, self.uri, self.builddir)

    def packagelist(self, makepkg_conf=None):
        """
        Get a list of paths to packages this PKGBUILD will produce when built.

        :param makepkg_conf: Path to makepkg configuration file
        :return: A list of paths to packages
        :raises CalledProcessError: Raised if the makepkg command fails
        """
        if self._packagelist:
            return self._packagelist
        self.update()
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

    def _update(self):
        """
        Synchronize the local PKGBUILD directory with the build directory.
        """
        synctree(self.localdir, self.builddir)


class AurPkgbuild(Pkgbuild):
    """
    An AUR-based PKGBUILD.

    :param name: Package name
    :param buildpath: Path to build directory
    :param aurpkg: AurPackage for the given package name
    """
    def __init__(self, name, buildpath, aurpkg):
        super().__init__(name, buildpath, 'aur')
        self.uri = aurpkg.giturl
        self.aurpkg = aurpkg

    def _update(self):
        """
        Clone the AUR package's git repository to the build directory or update
        it via git pull.
        """
        if self.builddir.exists():
            repo = GitRepo(self.builddir)
            if repo.is_repo():
                repo.pull()
            else:
                self.remove()
                self.aurpkg.git_clone(self.builddir)
        else:
            self.aurpkg.git_clone(self.builddir)
