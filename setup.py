from pathlib import Path
from setuptools import setup


def read(name):
    return open(Path(Path(__file__).parent, name)).read()


setup(
    name='pkgbuilder',
    version='0.0.0',
    packages=['pkgbuilder'],
    test_suite='test',
    entry_points={
        'console_scripts': [
            'pkgbuilder = pkgbuilder.__main__:main',
        ],
    },

    description='Library and CLI tool to build pacman packages',
    long_description=read('README.md'),
    long_description_content_type='text/markdown',
    url='https://github.com/jcrd/python-pkgbuilder',
    license='MIT',
    author='James Reed',
    author_email='jcrd@tuta.io',

    keywords='pacman makepkg AUR',
    classifiers=[
        'Development Status :: 2 - Pre-Alpha',
        'Topic :: System :: Archiving :: Packaging',
        'License :: OSI Approved :: MIT License',
    ],
)
