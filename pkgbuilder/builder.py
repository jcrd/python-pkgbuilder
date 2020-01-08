# This project is licensed under the MIT License.

"""
.. module:: builder
   :synopsis: Builds packages and dependencies in chroots.

.. moduleauthor:: James Reed <jcrd@tuta.io>
"""

from pathlib import Path
from itertools import repeat
import json
import logging
import time

from .chroot import Chroot
from .pkgbuild import Pkgbuild, LocalDir, parse_restriction
from .repo import get_repo
from .utils import write_stdin, default_pacman_conf

log = logging.getLogger('pkgbuilder')


def pacman(args, confirm=False):
    """
    Run pacman with given arguments while bypassing prompts.

    :param args: A list of arguments to pacman
    :param confirm: Allow prompts if `True`, defaults to `False`
    """
    write_stdin(['sudo', 'pacman', *args], confirm and [] or repeat('y\n'))


class Manifest:
    """
    The build manifest records built packages and dependencies.

    :param pkgname: Name of package
    :param pkgbuilddir: Path to PKGBUILD directory
    """
    def __init__(self, pkgname, pkgbuilddir):
        self.pkgname = pkgname
        self.pkgbuilddir = pkgbuilddir
        self.filepath = Path(pkgbuilddir, 'build.json')
        self.reset()

    def exists(self):
        """
        Check if the manifest file exists.

        :return: `True` if exists, `False` otherwise
        """
        return self.filepath.exists()

    @property
    def all_packages(self):
        """
        A set of paths to all built packages (including all dependencies).

        :return: A set of paths to all built packages
        """
        return self.packages | self.depends | self.makedepends

    def verify(self, paths=set()):
        """
        Verify that the packages in the manifest exist.

        :param paths: A set of package paths to verify, defaults to runtime \
        packages
        :return: `True` if packages exist, `False` otherwise
        """
        for p in paths or self.runtime_packages:
            if not Path(p).exists():
                return False
        return True

    @property
    def build_depends(self):
        """
        A set of paths to build dependencies, i.e. `depends` and `makedepends`.

        :return: A set of paths to build dependencies
        """
        return self.depends | self.makedepends

    @property
    def runtime_packages(self):
        """
        A set of paths to built packages and runtime dependencies.

        :return: A set of paths to built packages and runtime dependencies
        """
        return self.packages | self.depends

    def save(self):
        """
        Save the manifest file.
        """
        d = {
            'name': self.pkgname,
            'timestamp': time.time(),
            'packages': list(self.packages),
            'depends': list(self.depends),
            'makedepends': list(self.makedepends),
        }
        with open(self.filepath, 'w') as f:
            json.dump(d, f)

    def load(self):
        """
        Load the manifest file and populate the manifest's packages and
        dependencies properties.

        :return: A dictionary with keys: name, timestamp, packages, depends, \
        makedepends
        """
        if not self.exists():
            return {}
        with open(self.filepath) as f:
            j = json.load(f)
            try:
                self.pkgname = j['name']
                self.packages = set(j['packages'])
                self.depends = set(j['depends'])
                self.makedepends = set(j['makedepends'])
            except KeyError as e:
                log.warning('Found malformed manifest: {}'.format(e))
                return {}

            return j

    def reset(self):
        """
        Remove all packages and dependencies from manifest.
        """
        self.packages = set()
        self.depends = set()
        self.makedepends = set()

    def install(self, reinstall=False, pacman_conf=None, sysroot=None,
                confirm=False):
        """
        Install the packages in the manifest.

        :param reinstall: Reinstall installed packages if `True`, defaults to \
        `False`
        :param pacman_conf: Path to pacman configuration file
        :param sysroot: An alternative system root \
        (see pacman's --sysroot flag)
        :param confirm: Prompt to install if `True`, defaults to `False`
        :raises CalledProcessError: Raised if the pacman command fails
        """
        args = ['-U']
        if not reinstall:
            args += ['--needed']
        if pacman_conf:
            args += ['--config', pacman_conf]
        if sysroot:
            args += ['--sysroot', sysroot]

        if self.depends:
            deps = args + ['--asdeps']
            for d in self.depends:
                deps.append(d)
            pacman(deps, confirm)
        for p in self.packages:
            args.append(p)
        pacman(args, confirm)

    def repo_add(self, repo, pacman_conf=default_pacman_conf):
        """
        Add packages described by manifest to a local repository.

        :param repo: Name of or path to repository
        :param pacman_conf: Path to pacman configuration file
        """
        get_repo(repo).add(self)


class Builder(Manifest):
    """
    A package builder.

    :param name: Name of the package to build
    :param pacman_conf: Path to pacman configuration file
    :param makepkg_conf: Path to makepkg configuration file
    :param builddir: Path to package build directory
    :param chrootdir: Path to chroot directory
    :param localdir: Path to directory of local PKGBUILDs
    :param source: PKGBUILD source - one of Pkgbuild.Source.Local or \
    Pkgbuild.Source.Aur
    :raises SourceNotFoundError: Raised when no source can be found for \
    name or its dependencies
    :raises NoPkgbuildError: Raised when a local directory exists but \
    does not contain a PKGBUILD file
    """
    def __init__(self,
                 name,
                 pacman_conf=default_pacman_conf,
                 makepkg_conf='/etc/makepkg.conf',
                 builddir='/var/cache/pkgbuilder',
                 chrootdir='/var/lib/pkgbuilder',
                 localdir=None,
                 source=None,
                 restrictions=[]):
        self.name = name
        self.pacman_conf = pacman_conf
        self.makepkg_conf = makepkg_conf
        self.builddir = builddir
        self.chrootdir = chrootdir
        self.source = source

        self.chroot = Chroot(chrootdir)

        if isinstance(localdir, LocalDir):
            self.localdir = localdir
            self.pkgbuild = localdir.providers(name, restrictions)[0]
        else:
            self.localdir = LocalDir(localdir, builddir, makepkg_conf)
            self.localdir.update()
            self.pkgbuild = Pkgbuild.new(name, builddir, localdir, source,
                                         makepkg_conf)

        super().__init__(name, self.pkgbuild.builddir)

    def _build(self, rebuild=False, iter=1):
        """
        Recursively build a package. If the initial build fails, build missing
        dependencies before retrying.

        :param rebuild: Build packages even if they exist
        :param iter: The iteration number
        :return: A set of paths to built runtime packages
        """
        if iter == 1:
            if rebuild:
                log.info('%s: Rebuilding...', self.name)
            else:
                if self.load() and self.verify():
                    log.info('%s: Already built', self.name)
                    return self.runtime_packages
                else:
                    self.reset()

        log.info('%s: Building... [pass %d]', self.name, iter)
        r, stdout, stderr = self.chroot.makepkg(self.pkgbuild,
                                                self.build_depends)

        if r == 0:
            self.packages |= set(self.pkgbuild.packagelist)
            if self.verify():
                self.save()
                return self.runtime_packages
        elif iter == 1:
            for line in stdout.splitlines():
                f = line.split(": ")
                if f[0] == 'error' and f[1] == 'target not found':
                    dep, _ = parse_restriction(f[2])
                    type = self.pkgbuild.dependency_type(dep)
                    log.info('%s: Missing %s: %s', self.name, type, dep)
                    rs = self.pkgbuild.dependency_restrictions(dep)
                    b = Builder(dep, self.pacman_conf, self.makepkg_conf,
                                self.builddir, self.chrootdir, self.localdir,
                                restrictions=rs)
                    b._build(rebuild)
                    if type == 'depends':
                        self.depends |= set(b.packages)
                    if type == 'makedepends':
                        self.makedepends |= set(b.packages)
            if self.build_depends:
                return self._build(rebuild, iter + 1)

        return set()

    def build(self, rebuild=False):
        """
        Build the package.

        :param rebuild: Build packages even if they exist
        :return: A list of paths to all built packages
        """
        return list(self._build(rebuild))

    def install(self, reinstall=False, sysroot=None, repo=None, confirm=False):
        """
        Install built packages, building if necessary.

        :param reinstall: Reinstall installed packages if `True`, defaults to \
        `False`
        :param sysroot: An alternative system root
        :param repo: Name or path to directory of local repository
        :param confirm: Prompt to install if `True`, defaults to `False`
        :return: A list of paths to all built packages
        """
        if not self.runtime_packages:
            self.build()
        if repo:
            self.repo_add(repo, self.pacman_conf)
            pacman(['-Sy', self.name], confirm)
        else:
            super().install(reinstall, self.pacman_conf, sysroot, confirm)
        return self.runtime_packages
