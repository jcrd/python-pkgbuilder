# This project is licensed under the MIT License.

"""
.. module:: repo
   :synopsis: An interface to local pacman package databases.

.. moduleauthor:: James Reed <jcrd@tuta.io>
"""

from glob import iglob
from pathlib import Path
from shutil import copy2
from subprocess import run

from parse import search

from .utils import default_pacman_conf


def get_repo(name_or_path, pacman_conf=default_pacman_conf):
    """
    Get a LocalRepo object from a repository name or path.

    :param name_or_path: Name or path to directory of local repository
    :param pacman_conf: Path to pacman configuration file
    :return: A LocalRepo object
    """
    if Path(name_or_path).is_absolute():
        return LocalRepo(name_or_path)
    else:
        return RepoConf(pacman_conf).get_repo(name_or_path)


class RepoConf:
    """
    A wrapper for the repositories defined in pacman's configuration file.

    :param pacman_conf: Path to pacman configuration file
    """
    class RepoNotFoundError(Exception):
        """
        An exception raised when a repository cannot be found by name.
        """
        pass

    class RepoNotLocalError(Exception):
        """
        An exception raised when a repository exists but is not local.
        """
        pass

    def __init__(self, pacman_conf=default_pacman_conf):
        self.pacman_conf = pacman_conf

    def get_repo(self, name):
        """
        Get a LocalRepo object by name as defined in pacman's configuration \
        file.

        :param name: The repository name
        :return: A LocalRepo object
        """
        err = {'name': name, 'pacman_conf': self.pacman_conf}

        try:
            r = run(['pacman-conf', '-r', name], capture_output=True, \
                    text=True, check=True)
        except CalledProcessError:
            err['message'] = 'Repository {} not found'.format(name)
            raise RepoConf.RepoNotFoundError(err)

        s = search('Server = file://{path}\n', r.stdout)
        if not s:
            err['message'] = 'Repository {} is not local'.format(name)
            raise RepoConf.RepoNotLocalError(err)

        return LocalRepo(s.named['path'], name)


class LocalRepo:
    """
    A wrapper for a local pacman repository.

    :param path: A path to the directory containing the repository database
    :param name: The name of the repository, defaults to the name of the last \
    directory in the path
    """
    class DatabaseNotFoundError(Exception):
        """
        An exception raised when a database file is not found in the given \
        repository path.
        """
        pass

    def __init__(self, path, name=None):
        self.path = Path(path)
        self.name = name or self.path.name
        self.db = self._find_db()

    def _find_db(self):
        """
        Find the database file in a repository directory.

        :return: The database filename
        """
        def error():
            err = {'message': \
                   'Database for {} repository not found'.format(self.name),
                   'name': self.name,
                   'path': self.path}
            raise LocalRepo.DatabaseNotFoundError(err)

        if not self.path.exists():
            error()

        pattern = str(Path(self.path, '{}.db.tar*'.format(self.name)))

        try:
            for f in iglob(pattern):
                if not f.endswith('.old'):
                    return f
        except StopIteration:
            pass

        error()

    def _repo_cmd(self, cmd, args):
        return run(['repo-{}'.format(cmd), str(self.db), *args]).returncode == 0

    def add(self, manifest):
        """
        Add a built package to the repository.

        :param manifest: A Manifest object describing the built package
        :return: `True` if the `repo-add` command succeeded, `False` otherwise
        """
        if not manifest.exists():
            return False
        for pkg in manifest.runtime_packages:
            copy2(Path(manifest.pkgbuilddir, pkg), self.path)
        return self._repo_cmd('add', manifest.runtime_packages)
