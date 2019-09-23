# This project is licensed under the MIT License.

"""
.. module:: aur
   :synopsis: A wrapper for the AUR RPC interface.

.. moduleauthor:: James Reed <jcrd@tuta.io>
"""

import json
import logging
import tarfile
import urllib.request

log = logging.getLogger('pkgbuilder.aur')


class AurPackage:
    """
    A package found on the AUR that can be downloaded.

    :param info: Package info
    :param url: URL to the AUR interface
    """
    def __init__(self, info, url):
        self.info = info
        self.url = url
        self.name = info['Name']
        self.urlpath = url + info['URLPath']

    def download(self, dest):
        """
        Download and extract package snapshot to given destination.

        :param dest: Extraction destination
        """
        with urllib.request.urlopen(self.urlpath) as r:
            with tarfile.open(fileobj=r, mode='r:gz') as t:
                log.info('%s: Downloading AUR snapshot to %s...',
                         self.name, dest)
                prefix = self.name + '/'
                members = []
                for m in t.getmembers():
                    if m.name.startswith(prefix):
                        m.name = m.name[len(prefix):]
                        members.append(m)
                t.extractall(dest, members)


class Aur:
    """
    Wrapper around the AUR RPC interface with caching for package info.
    See https://aur.archlinux.org/rpc.php.

    :param url: URL providing the RPC interface, defaults to \
    https://aur.archlinux.org
    """
    def __init__(self, url='https://aur.archlinux.org'):
        self.url = url
        self.rpc = url + '/rpc/?v=5&type=info'
        self.cache = {}

    def infos(self, *names):
        """
        Get info about AUR packages.

        :param names: Positional arguments specifying package names
        :return: A dictionary mapping names to info
        """
        res = {}
        args = ''

        for name in names:
            if name in self.cache:
                res[name] = self.cache[name]
            else:
                args += '&arg[]={}'.format(name)

        if not args:
            return res

        with urllib.request.urlopen(self.rpc + args) as r:
            s = r.read().decode('utf-8')
            for pkg in json.loads(s)['results']:
                name = pkg['Name']
                self.cache[name] = pkg
                res[name] = pkg

        return res

    def info(self, name):
        """
        Get info about an AUR package.

        :param name: Name of the AUR package
        :return: Package info or None if name is not found
        """
        try:
            return self.infos(name)[name]
        except KeyError:
            return None

    def get_package(self, name):
        """
        Get an AurPackage that can be downloaded.

        :param name: Name of the AUR package
        :return: an AurPackage or None if name is not found
        """
        i = self.info(name)
        if i:
            return AurPackage(i, self.url)
