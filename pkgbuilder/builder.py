# This project is licensed under the MIT License.

"""
.. module:: builder
   :synopsis: Builds packages and dependencies in chroots.

.. moduleauthor:: James Reed <jcrd@tuta.io>
"""

from pathlib import Path
from subprocess import run
import json
import logging
import sys
import time

from .chroot import Chroot
from .pkgbuild import Pkgbuild

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

        :return: True if all packages exist, otherwise false
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
            return None
        with open(self.filepath) as f:
            j = json.load(f)
            try:
                self.packages = set(j['packages'])
                self.dependencies = set(j['dependencies'])
            except KeyError as e:
                sys.stderr.write('Found malformed manifest: {}'.format(e))

            return j

    def reset(self):
        """
        Remove all packages and dependencies from manifest.
        """
        self.packages = set()
        self.dependencies = set()

    def install(self, pacman_conf=None, sysroot=None):
        """
        Install the packages in the manifest.

        :param pacman_conf: Path to pacman configuration file
        :param sysroot: An alternative system root \
        (see pacman's --sysroot flag)
        """
        cmd = ['sudo', 'pacman', '-U']
        if pacman_conf:
            cmd += ['--config', pacman_conf]
        if sysroot:
            cmd += ['--sysroot', sysroot]
        if self.dependencies:
            deps = cmd + ['--asdeps']
            for d in self.dependencies:
                deps.append(d)
            run(deps, check=True)
        for p in self.packages:
            cmd.append(p)
        run(cmd, check=True)


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
    """
    def __init__(self,
                 name,
                 pacman_conf='/etc/pacman.conf',
                 makepkg_conf='/etc/makepkg.conf',
                 builddir='/var/cache/pkgbuilder',
                 chrootdir='/var/lib/pkgbuilder',
                 localdir=None,
                 source=None):
        self.name = name
        self.pacman_conf = pacman_conf
        self.makepkg_conf = makepkg_conf
        self.builddir = builddir
        self.chrootdir = chrootdir
        self.localdir = localdir
        self.source = source

        self.chroot = Chroot(pacman_conf, makepkg_conf, chrootdir)
        self.pkgbuild = Pkgbuild.new(name, builddir, localdir, source)

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
            self.packages |= set(self.pkgbuild.packagelist())
            return self.all_packages
        else:
            for line in stdout.splitlines():
                f = line.split(": ")
                if f[0] == 'error' and f[1] == 'target not found':
                    dep = f[2]
                    log.info('%s: Missing dependency: %s', self.name, dep)
                    b = Builder(dep, self.pacman_conf, self.makepkg_conf,
                                self.builddir, self.chrootdir, self.localdir)
                    self.dependencies |= b._build(rebuild)
            if self.dependencies:
                self._build(rebuild, iter + 1)

        return set()

    def build(self, rebuild=False):
        """
        Build the package.

        :param rebuild: Build packages even if they exist
        :return: A set of paths to all built packages
        """
        pkgs = self._build(rebuild=rebuild)
        self.save()
        return pkgs

    def install(self, sysroot=None):
        """
        Install built packages, building if necessary.

        :param sysroot: An alternative system root
        """
        self.build()
        super().install(self.pacman_conf, sysroot)
