# python-pkgbuilder

python-pkgbuilder provides a library and command-line tool for building pacman
packages and their dependencies in chroots.

## Dependencies

* python
* [pacman](https://www.archlinux.org/packages/core/x86_64/pacman/)
* [devtools](https://www.archlinux.org/packages/extra/any/devtools/)

## Command-line client

### Usage

```
usage: pkgbuilder [-h] [-C PACMAN_CONFIG] [-M MAKEPKG_CONFIG] [-b BUILDDIR]
                  [-r CHROOTDIR] [-d PKGBUILDS] [-i] [-B] [-R] [-a]
                  [names [names ...]]

positional arguments:
  names                 package names

optional arguments:
  -h, --help            show this help message and exit
  -C PACMAN_CONFIG, --pacman-config PACMAN_CONFIG
                        path to pacman config file
  -M MAKEPKG_CONFIG, --makepkg-config MAKEPKG_CONFIG
                        path to makepkg config file
  -b BUILDDIR, --builddir BUILDDIR
                        path to package build directory
  -r CHROOTDIR, --chrootdir CHROOTDIR
                        path to chroot directory
  -d PKGBUILDS, --pkgbuilds PKGBUILDS
                        path to directory of local PKGBUILDs
  -i, --install         install packages
  -B, --rebuild         build packages even if they exists
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
