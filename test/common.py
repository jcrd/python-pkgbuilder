from pathlib import Path

test1_pkg = 'test1-1-1-any.pkg.tar.xz'
test1_dep1_pkg = 'test1-dep1-1-1-any.pkg.tar.xz'
test1_makedep1_pkg = 'test1-makedep1-1-1-any.pkg.tar.xz'

localdir = str(Path(__file__).parent) + '/pkgbuilds'
chrootdir = '/var/lib/pkgbuilder'


def pkgnames(pkgs):
    return [str(Path(p).name) for p in pkgs]
