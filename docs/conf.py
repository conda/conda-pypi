# SPDX-License-Identifier: BSD-3-Clause
# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Path setup --------------------------------------------------------------

# If extensions (or modules to document with autodoc) are in another directory,
# add these directories to sys.path here. If the directory is relative to the
# documentation root, use os.path.abspath to make it absolute, like shown here.
#
import os
import sys

sys.path.insert(0, os.path.abspath(".."))


# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

project = html_title = "conda-pypi"
copyright = "2024, conda-pypi contributors"
author = "conda-pypi contributors"

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

# Add any Sphinx extension module names here, as strings. They can be
# extensions coming with Sphinx (named 'sphinx.ext.*') or your custom
# ones.
extensions = [
    "myst_parser",
    "sphinx.ext.autodoc",
    "sphinx.ext.autosummary",
    "sphinx.ext.graphviz",
    "sphinx.ext.ifconfig",
    "sphinx.ext.inheritance_diagram",
    "sphinx.ext.napoleon",
    "sphinx.ext.viewcode",
    "sphinx_copybutton",
    "sphinx_design",
    "sphinx_reredirects",
    "sphinx_sitemap",
    "sphinxarg.ext",
]

# Autodoc configuration
autodoc_mock_imports = []
autodoc_default_options = {
    "members": True,
    "undoc-members": True,
    "show-inheritance": True,
}

# Handle missing imports gracefully
autodoc_typehints = "description"

myst_heading_anchors = 3
myst_enable_extensions = [
    "amsmath",
    "colon_fence",
    "deflist",
    "dollarmath",
    "html_admonition",
    "html_image",
    "linkify",
    "replacements",
    "smartquotes",
    "substitution",
    "tasklist",
]


# Add any paths that contain templates here, relative to this directory.
templates_path = ["_templates"]
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

# List of patterns, relative to source directory, that match files and
# directories to ignore when looking for source files.
# This pattern also affects html_static_path and html_extra_path.
exclude_patterns = []


# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_theme = "conda_sphinx_theme"
html_static_path = ["_static"]

html_css_files = [
    "css/custom.css",
]

# Serving the robots.txt since we want to point to the sitemap.xml file
html_extra_path = ["robots.txt"]

html_theme_options = {
    "navigation_depth": -1,
    "use_edit_page_button": True,
    "navbar_center": ["navbar_center"],
}

html_context = {
    "github_user": "conda",
    "github_repo": "conda-pypi",
    "github_version": "main",
    "doc_path": "docs",
}

html_baseurl = "https://conda.github.io"

# We don't have a locale set, so we can safely ignore that for the sitemaps.
sitemap_locales = [None]
# We're hard-coding stable here since that's what we want Google to point to.
sitemap_url_scheme = "{link}"

# -- For sphinx_reredirects ------------------------------------------------

redirects = {}
