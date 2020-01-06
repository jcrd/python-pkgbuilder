# This project is licensed under the MIT License.

"""
.. module:: pkgbuild
   :synopsis: Represent local or AUR-based PKGBUILDs.

.. moduleauthor:: James Reed <jcrd@tuta.io>
"""

from collections import namedtuple
from enum import Flag, auto
from pathlib import Path
from shutil import rmtree
from subprocess import run
import logging
import os

from srcinfo.parse import parse_srcinfo
from parse import parse

from .aur import Aur, GitRepo
from .utils import synctree

log = logging.getLogger('pkgbuilder.pkgbuild')

Restriction = namedtuple('Restriction', ['compare', 'version'])


def parse_restriction(pkg):
    """
    Parse package name and version Restriction string.

    :return: A tuple of the package name and a version Restriction tuple
    """
    for c in ['>=', '<=', '>', '<', '=']:
        p = parse('{name}' + c + '{version}', pkg)
        if p:
            return (p.named['name'], Restriction(c, p.named['version']))

    return (pkg, None)


class LocalDir:
    """
    A directory containing local PKGBUILDs.

    :param path: Path to directory
    :param builddir: Path to package build directory
    :param makepkg_conf: Path to makepkg configuration file
    """
    class ProviderNotFoundError(Exception):
        """
        An exception raised when no provider is found for the package name.
        """
        pass

    Package = namedtuple('Package', ['name', 'version'])

    def __init__(self, path, builddir, makepkg_conf=None):
        self.path = path
        self.builddir = builddir
        self.makepkg_conf = makepkg_conf
        self.check_update = True
        self.packages = {}

    def update(self, force=False):
        """
        Parse PKGBUILDs in the directory.

        :param force: Force checking for updates
        :return: A dictionary mapping Package tuples to lists of Pkgbuild \
        objects
        """
        if not self.path:
            return {}
        if not (self.check_update or force):
            return self.packages

        def add_package(pkg, pkgbuild):
            if pkg in self.packages:
                self.packages[pkg].append(pkgbuild)
            else:
                self.packages[pkg] = [pkgbuild]

        with os.scandir(self.path) as dir:
            for entry in dir:
                if not entry.is_dir():
                    continue
                try:
                    pkgbuild = Pkgbuild.new(entry.name, self.builddir,
                                            self.path, Pkgbuild.Source.Local,
                                            self.makepkg_conf)
                except Pkgbuild.NoPkgbuildError:
                    continue
                srcinfo = pkgbuild.srcinfo
                if 'provides' in srcinfo:
                    for p in srcinfo['provides']:
                        s = p.split('=')
                        if len(s) < 2:
                            s.append(srcinfo['pkgver'])
                        add_package(LocalDir.Package(*s), pkgbuild)
                else:
                    add_package(LocalDir.Package(srcinfo['pkgbase'],
                                                 srcinfo['pkgver']),
                                pkgbuild)

        self.check_update = False
        return self.packages

    def providers(self, name, restrictions=[]):
        """
        Get providers for a package with version Restrictions.

        :param name: Package name
        :param restrictions: A list of version Restrictions
        :raises ProviderNotFoundError: Raised when no provider can be found \
        for name
        :return: A list of Pkgbuild objects providing the package
        """
        def restrict_version(v, restrictions):
            for r in restrictions:
                if (r.compare == '>' and not v > r.version) \
                or (r.compare == '<' and not v < r.version) \
                or (r.compare == '=' and not v == r.version) \
                or (r.compare == '>=' and not v >= r.version) \
                or (r.compare == '<=' and not v <= r.version):
                    return False

            return True

        err = {'message': 'Provider for {} not found'.format(name),
               'source': Pkgbuild.Source.Local,
               'version_restrictions': restrictions}

        if not self.packages or not self.path:
            raise LocalDir.ProviderNotFoundError(err)
        for pkg, pkgbuilds in self.packages.items():
            if pkg.name == name \
                    and restrict_version(pkg.version, restrictions):
                return pkgbuilds
        raise LocalDir.ProviderNotFoundError(err)


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

    class ParseSrcinfoError(Exception):
        """
        An exception raised when parsing a PKGBUILD's srcinfo fails.
        """
        pass

    class Source(Flag):
        """
        Flags for local or AUR sources.
        """
        Local = auto()
        Aur = auto()

    @classmethod
    def new(cls, name, builddir, localdir=None, source=None, makepkg_conf=None):
        """
        Create a new LocalPkgbuild or AurPkgbuild.

        :param name: Package name
        :param builddir: Path to package build directory
        :param localdir: Path to directory of local PKGBUILDs
        :param source: PKGBUILD source - one of Pkgbuild.Source.Local or \
        Pkgbuild.Source.Aur
        :param makepkg_conf: Path to makepkg configuration file
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
            return LocalPkgbuild(name, builddir, dir, makepkg_conf)
        elif source == cls.Source.Local:
            err['source'] = cls.Source.Local
            raise cls.SourceNotFoundError(err)
        else:
            aurpkg = Pkgbuild.aur.get_package(name)
            if aurpkg:
                return AurPkgbuild(name, builddir, aurpkg, makepkg_conf)
            else:
                err['source'] = cls.Source.Aur
                raise cls.SourceNotFoundError(err)

    def __init__(self, name, buildpath, sourcedir, makepkg_conf=None):
        self.name = name
        self.buildpath = Path(buildpath, sourcedir)
        self.makepkg_conf = makepkg_conf
        self.builddir = Path(self.buildpath, self.name)
        self.pkgbuildpath = Path(self.builddir, 'PKGBUILD')
        self.check_update = True
        self._packagelist = []
        self._srcinfo = {}
        self._depends = {}
        self._makedepends = {}

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
        if self._update():
            log.info('%s: PKGBUILD [%s -> %s]', self.name, self.uri,
                     self.builddir)
        self.check_update = False

    @property
    def packagelist(self):
        """
        Get a list of paths to packages this PKGBUILD will produce when built.

        :return: A list of paths to packages
        :raises CalledProcessError: Raised if the makepkg command fails
        """
        if self._packagelist:
            return self._packagelist
        self.update()
        cmd = ['makepkg', '--packagelist']
        if self.makepkg_conf:
            cmd += ['--config', self.makepkg_conf]
        r = run(cmd, cwd=self.builddir, capture_output=True, text=True,
                check=True)
        self._packagelist = r.stdout.splitlines()
        return self._packagelist

    @property
    def srcinfo(self):
        """
        Get a srcinfo dictionary corresponding to makepkg --printsrcinfo output.

        :return: The srcinfo dictionary
        :raises CalledProcessError: Raised if the makepkg command fails
        :raises ParseSrcinfoError: Raised if parsing the srcinfo fails
        """
        if self._srcinfo:
            return self._srcinfo

        self.update()
        file = Path(self.builddir, '.SRCINFO')

        mtime = os.path.getmtime
        if file.exists() and not mtime(self.pkgbuildpath) > mtime(file):
            with open(file) as f:
                info = f.read()
        else:
            cmd = ['makepkg', '--printsrcinfo']
            if self.makepkg_conf:
                cmd += ['--config', self.makepkg_conf]
            log.info('%s: Generating .SRCINFO... [%s]', self.name,
                     self.builddir)
            r = run(cmd, cwd=self.builddir, capture_output=True, text=True,
                    check=True)
            info = r.stdout
            with open(file, 'w') as f:
                f.write(info)

        srcinfo, errors = parse_srcinfo(info)

        if errors:
            err = {'message': 'Failed to parse PKGBUILD srcinfo',
                   'errors': errors}
            raise ParseSrcinfoError(err)

        self._srcinfo = srcinfo
        return self._srcinfo

    def _get_depends(self, type):
        """
        Get a given type of package dependencies with Restrictions.

        :param type: One of `depends` or `makedepends`
        :return: A dictionary mapping package names to a list of Restriction \
        objects.
        """
        srcinfo_deps = []
        deps = {}

        try:
            srcinfo_deps += self.srcinfo[type]
        except KeyError:
            pass

        for pkg in srcinfo_deps:
            name, r = parse_restriction(pkg)
            if r:
                if name in deps:
                    if r not in deps[name]:
                        deps[name].append(r)
                else:
                    deps[name] = [r]
            else:
                deps[pkg] = []

        return deps

    @property
    def depends(self):
        """
        Get package dependencies and Restrictions.

        :return: A dictionary mapping package names to a list of Restriction \
        objects.
        """
        if not self._depends:
            self._depends = self._get_depends('depends')

        return self._depends

    @property
    def makedepends(self):
        """
        Get package build dependencies and Restrictions.

        :return: A dictionary mapping package names to a list of Restriction \
        objects.
        """
        if not self._makedepends:
            self._makedepends = self._get_depends('makedepends')

        return self._makedepends

    def dependency_type(self, name):
        """
        Get type of dependency.

        :param name: The package name
        :return: One of `depends` or `makedepends`
        """
        if name in self.depends:
            return 'depends'
        if name in self.makedepends:
            return 'makedepends'

    def dependency_restrictions(self, name):
        """
        Get dependency Restrictions for a package by name.

        :param name: The package name
        :return: A list of Restriction objects
        """
        if name in self.depends:
            return self.depends[name]
        if name in self.makedepends:
            return self.makedepends[name]

        return []


class LocalPkgbuild(Pkgbuild):
    """
    A locally sourced PKGBUILD.

    :param name: Package name
    :param buildpath: Path to build directory
    :param localdir: Path to the directory containing PKGBUILD
    :param makepkg_conf: Path to makepkg configuration file
    """
    def __init__(self, name, buildpath, localdir, makepkg_conf=None):
        super().__init__(name, buildpath, 'local', makepkg_conf)
        self.uri = localdir.as_uri()
        self.localdir = localdir

    def _update(self):
        """
        Synchronize the local PKGBUILD directory with the build directory.

        :return: `True` if the builddir was updated, `False` otherwise
        """
        return synctree(self.localdir, self.builddir)


class AurPkgbuild(Pkgbuild):
    """
    An AUR-based PKGBUILD.

    :param name: Package name
    :param buildpath: Path to build directory
    :param aurpkg: AurPackage for the given package name
    :param makepkg_conf: Path to makepkg configuration file
    """
    def __init__(self, name, buildpath, aurpkg, makepkg_conf=None):
        super().__init__(name, buildpath, 'aur', makepkg_conf)
        self.uri = aurpkg.giturl
        self.aurpkg = aurpkg

    def _update(self):
        """
        Clone the AUR package's git repository to the build directory or update
        it via git pull.

        :return: `True` if the builddir was updated, `False` otherwise
        """
        if self.builddir.exists():
            repo = GitRepo(self.builddir)
            if repo.is_repo():
                if repo.up_to_date():
                    return False
                repo.pull()
            else:
                self.remove()
                self.aurpkg.git_clone(self.builddir)
        else:
            self.aurpkg.git_clone(self.builddir)

        return True
