# This project is licensed under the MIT License.

"""
.. module:: utils
   :synopsis: pkgbuilder utilities.

.. moduleauthor:: James Reed <jcrd@tuta.io>
"""

from asyncio.subprocess import PIPE
from contextlib import contextmanager
from filecmp import dircmp
from pathlib import Path
from shutil import copy2, copytree, rmtree
import asyncio
import os
import subprocess


class CmdLogger:
    """
    A command runner capable of capturing and logging output.

    :param log: The logger
    """
    def __init__(self, log):
        self.log = log

    @asyncio.coroutine
    def _read_and_log(self, stream):
        """
        Read from a stream, capturing and logging each line.

        :param stream: The stream to read
        :return: The captured lines
        """
        lines = []
        while True:
            line = yield from stream.readline()
            if not line:
                break
            line = line.decode('utf-8')
            lines.append(line)
            self.log.info(line.rstrip())
        return ''.join(lines)

    @asyncio.coroutine
    def _run_and_log(self, cmd):
        """
        A coroutine to run a command, capturing and logging its output.

        :param cmd: The command to run
        :return: The command's exit code, a list of stdout lines, and a list of
        stderr lines
        """
        p = yield from asyncio.create_subprocess_exec(*cmd,
                                                      stdout=PIPE, stderr=PIPE)
        try:
            stdout, stderr = yield from asyncio.gather(
                self._read_and_log(p.stdout), self._read_and_log(p.stderr))
        except Exception:
            p.kill()
            raise
        finally:
            r = yield from p.wait()

        return r, stdout, stderr

    def run(self, cmd):
        """
        Run a command, capturing and logging its output.

        :param cmd: The command to run
        :return: The command's exit code, a list of stdout lines, and a list \
        of stderr lines
        """
        loop = asyncio.get_event_loop()
        return loop.run_until_complete(self._run_and_log(cmd))


@contextmanager
def cwd(path):
    """
    A context manager for changing the working directory.

    :param path: The new working directory
    """
    oldcwd = os.getcwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(oldcwd)


def write_stdin(cmd, iter):
    """
    Write strings produced by an iterable to a subprocess's standard input.

    :param cmd: The subprocess command
    :param iter: The iterable
    :raises CalledProcessError: Raised if the subprocess fails
    """
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)

    def wait():
        r = p.wait()
        if r != 0:
            raise subprocess.CalledProcessError(r, cmd)

    for i in iter:
        try:
            p.stdin.write(i.encode())
        except BrokenPipeError:
            wait()
            return

    p.stdin.close()
    wait()


def synctree(a, b):
    """
    Synchronize the contents of b with those found in a.

    :param a: The seed directory
    :param b: The destination directory
    """
    def sync(cmp):
        for name in cmp.left_only + cmp.diff_files:
            a_path = str(Path(cmp.left, name))
            b_path = str(Path(cmp.right, name))
            try:
                copytree(a_path, b_path)
            except NotADirectoryError:
                copy2(a_path, b_path)

        for name in cmp.right_only:
            path = str(Path(cmp.right, name))
            try:
                rmtree(path)
            except NotADirectoryError:
                os.remove(path)

    if not Path(b).exists():
        copytree(a, b)
        return

    cmp = dircmp(a, b)

    for c in [cmp] + list(cmp.subdirs.values()):
        sync(c)
