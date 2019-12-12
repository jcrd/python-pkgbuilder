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
from .utils import write_stdin

log = logging.getLogger('pkgbuilder')


class Manifest:
    """
    The build manifest records built packages and dependencies.

    :param pkgbuilddir: Path to PKGBUILD directory
    """
    def __init__(self, pkgbuilddir):
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
        A set of paths to all built packages (including dependencies).

        :return: A set of paths to all built packages
        """
        return self.packages | self.dependencies

    def verify(self):
        """
        Verify that the packages in the manifest exist.

        :return: `True` if all packages exist, `False` otherwise
        """
        for p in self.all_packages:
            if not Path(p).exists():
                return False
        return True

    def save(self):
        """
        Save the manifest file.
        """
        d = {
            'timestamp': time.time(),
            'packages': list(self.packages),
            'dependencies': list(self.dependencies),
        }
        with open(self.filepath, 'w') as f:
            json.dump(d, f)

    def load(self):
        """
        Load the manifest file and populate the manifest's packages and
        dependencies properties.

        :return: A dictionary with keys: timestamp, packages, dependencies
        """
        if not self.exists():
            return {}
        with open(self.filepath) as f:
            j = json.load(f)
            try:
                self.packages = set(j['packages'])
                self.dependencies = set(j['dependencies'])
            except KeyError as e:
                log.warning('Found malformed manifest: {}'.format(e))
                return {}

            return j

    def reset(self):
        """
        Remove all packages and dependencies from manifest.
        """
        self.packages = set()
        self.dependencies = set()

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
        cmd = ['sudo', 'pacman', '-U']
        if not reinstall:
            cmd += ['--needed']
        if pacman_conf:
            cmd += ['--config', pacman_conf]
        if sysroot:
            cmd += ['--sysroot', sysroot]

        def install(cmd):
            write_stdin(cmd, confirm and [] or repeat('y\n'))

        if self.dependencies:
            deps = cmd + ['--asdeps']
            for d in self.dependencies:
                deps.append(d)
            install(deps)
        for p in self.packages:
            cmd.append(p)
        install(cmd)


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
                 pacman_conf='/etc/pacman.conf',
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

        super().__init__(self.pkgbuild.builddir)

    def _build(self, rebuild=False, iter=1):
        """
        Recursively build a package. If the initial build fails, build missing
        dependencies before retrying.

        :param rebuild: Build packages even if they exist
        :param iter: The iteration number
        :return: A set of paths to all built packages
        """
        if iter == 1:
            if rebuild:
                log.info('%s: Rebuilding...', self.name)
            else:
                if self.load() and self.verify():
                    log.info('%s: Already built', self.name)
                    return self.all_packages
                else:
                    self.reset()

        log.info('%s: Building... [pass %d]', self.name, iter)
        r, stdout, stderr = self.chroot.makepkg(self.pkgbuild,
                                                self.dependencies)

        if r == 0:
            self.packages |= set(self.pkgbuild.packagelist)
            if self.verify():
                self.save()
                return self.all_packages
        elif iter == 1:
            for line in stdout.splitlines():
                f = line.split(": ")
                if f[0] == 'error' and f[1] == 'target not found':
                    dep, _ = parse_restriction(f[2])
                    log.info('%s: Missing dependency: %s', self.name, dep)
                    rs = self.pkgbuild.dependency_restrictions(dep)
                    b = Builder(dep, self.pacman_conf, self.makepkg_conf,
                                self.builddir, self.chrootdir, self.localdir,
                                restrictions=rs)
                    self.dependencies |= b._build(rebuild)
            if self.dependencies:
                return self._build(rebuild, iter + 1)

        return set()

    def build(self, rebuild=False):
        """
        Build the package.

        :param rebuild: Build packages even if they exist
        :return: A list of paths to all built packages
        """
        return list(self._build(rebuild=rebuild))

    def install(self, reinstall=False, sysroot=None, confirm=False):
        """
        Install built packages, building if necessary.

        :param reinstall: Reinstall installed packages if `True`, defaults to \
        `False`
        :param sysroot: An alternative system root
        :param confirm: Prompt to install if `True`, defaults to `False`
        :return: A list of paths to all built packages
        """
        if not self.all_packages:
            self.build()
        super().install(reinstall, self.pacman_conf, sysroot, confirm)
        return self.all_packages
