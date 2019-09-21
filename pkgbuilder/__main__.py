# This project is licensed under the MIT License.

import argparse
import os
import sys
import logging

from pkgbuilder.builder import Builder
from pkgbuilder.pkgbuild import Pkgbuild

log = logging.getLogger('pkgbuilder')
log.setLevel(logging.INFO)
log.addHandler(logging.StreamHandler(sys.stdout))


def die(e):
    msg = 'ERROR: {}: {}\n'
    sys.stderr.write(msg.format(*[v[1] for v in e.args[0].items()]))
    sys.exit(1)


def main():
    p = argparse.ArgumentParser()
    p.add_argument('names', nargs='*', default=[os.getcwd()],
                   help='package names')
    p.add_argument('-C', '--pacman-config', default='/etc/pacman.conf',
                   help='path to pacman config file')
    p.add_argument('-M', '--makepkg-config', default='/etc/makepkg.conf',
                   help='path to makepkg config file')
    p.add_argument('-b', '--builddir', default='/var/cache/pkgbuilder',
                   help='path to package build directory')
    p.add_argument('-r', '--chrootdir', default='/var/lib/pkgbuilder',
                   help='path to chroot directory')
    p.add_argument('-d', '--pkgbuilds', default='..',
                   help='path to directory of local PKGBUILDs')
    p.add_argument('-i', '--install', action='store_true',
                   help='install packages')
    p.add_argument('-B', '--rebuild', action='store_true',
                   help='build packages even if they exists')
    p.add_argument('-R', '--remove', action='store_true',
                   help='remove package build directories')
    p.add_argument('-a', '--aur', action='store_true',
                   help='search for packages in the AUR only')

    args = p.parse_args()

    for name in args.names:
        try:
            b = Builder(name, args.pacman_config, args.makepkg_config,
                        args.builddir, args.chrootdir, args.pkgbuilds,
                        args.aur and Pkgbuild.Source.Aur or None)
        except Pkgbuild.NoPkgbuildError as e:
            die(e)
        if args.remove:
            b.pkgbuild.remove()
            continue
        try:
            b.build(args.rebuild)
        except Pkgbuild.SourceNotFoundError as e:
            die(e)
        if args.install:
            b.install()


if __name__ == '__main__':
    main()
