# Configuration file for the Sphinx documentation builder.

# -- Path setup --------------------------------------------------------------

import os
import sys
sys.path.insert(0, os.path.abspath('..'))

# -- Project information -----------------------------------------------------

project = 'pkgbuilder'
copyright = '2019, James Reed'
author = 'James Reed'

# -- General configuration ---------------------------------------------------

extensions = [
    'sphinx.ext.autodoc',
]

# -- Options for HTML output -------------------------------------------------

html_theme = 'alabaster'
