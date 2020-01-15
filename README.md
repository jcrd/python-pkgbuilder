# python-pkgbuilder

python-pkgbuilder provides a library and command-line tool for building pacman
packages and their dependencies in chroots.

## Dependencies

* python
* [pacman](https://www.archlinux.org/packages/core/x86_64/pacman/)
* [devtools](https://www.archlinux.org/packages/extra/any/devtools/)

## Setup

Two directories are expected to exist before python-pkgbuilder is run:

* `/var/cache/pkgbuilder`
* `/var/lib/pkgbuilder`

They should be writable by the user running python-pkgbuilder.

This can be achieved by:

* creating the `pkgbuilder` group
* setting group ownership of the above directories to `pkgbuilder`
* setting the mode of the above directories to `0775`
* adding the user to the `pkgbuilder` group

## Command-line client

### Usage

```
usage: pkgbuilder [-h] [-C PACMAN_CONFIG] [-M MAKEPKG_CONFIG] [-b BUILDDIR]
                  [-c CHROOTDIR] [-d PKGBUILDS] [-i] [-I] [-r REPO] [-B] [-R]
                  [-a]
                  [name [name ...]]

positional arguments:
  name                  package name

optional arguments:
  -h, --help            show this help message and exit
  -C PACMAN_CONFIG, --pacman-config PACMAN_CONFIG
                        path to pacman config file
  -M MAKEPKG_CONFIG, --makepkg-config MAKEPKG_CONFIG
                        path to makepkg config file
  -b BUILDDIR, --builddir BUILDDIR
                        path to package build directory
  -c CHROOTDIR, --chrootdir CHROOTDIR
                        path to chroot directory
  -d PKGBUILDS, --pkgbuilds PKGBUILDS
                        path to directory of local PKGBUILDs
  -i, --install         install packages
  -I, --reinstall       reinstall packages
  -r REPO, --repo REPO  install package via local repo
  -B, --rebuild         build packages even if they exists (pass twice to
                        rebuild dependencies)
  -R, --remove          remove package build directories
  -a, --aur             search for packages in the AUR only
```

## Python module

Simplest example:
```python
from pkgbuilder.builder import Builder

b = Builder('aurutils')
b.build()
b.install()
```

See the [API documentation][1] for descriptions of all functions.

[1]: https://jcrd.github.io/python-pkgbuilder/

## License

This project is licensed under the MIT License (see [LICENSE](LICENSE)).
