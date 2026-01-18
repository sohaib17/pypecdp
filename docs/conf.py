# Configuration file for the Sphinx documentation builder.
import os
import sys
import tomllib
from pathlib import Path

# Add source to path
sys.path.insert(0, os.path.abspath("../src"))

# Read version from pyproject.toml
pyproject_path = Path(__file__).parent.parent / "pyproject.toml"
with open(pyproject_path, "rb") as f:
    pyproject_data = tomllib.load(f)
    version = pyproject_data["project"]["version"]

# Project information
project = "pypecdp"
copyright = "2026, sohaib17"
author = "sohaib17"
release = version

# General configuration
extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",
    "sphinx.ext.viewcode",
    "sphinx.ext.intersphinx",
]

templates_path = ["_templates"]
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

# Suppress duplicate object warnings (common with class attributes)
suppress_warnings = ["app.add_directive"]

# Autodoc settings
autodoc_default_options = {
    "members": True,
    "undoc-members": True,
    "show-inheritance": True,
}
autodoc_typehints = "description"
autodoc_member_order = "bysource"


# Exclude CDP modules (third-party auto-generated)
def skip_cdp_modules(app, what, name, obj, skip, options):
    if "pypecdp.cdp" in str(getattr(obj, "__module__", "")):
        return True
    return skip


def setup(app):
    app.connect("autodoc-skip-member", skip_cdp_modules)


# Napoleon settings (for Google/NumPy style docstrings)
napoleon_google_docstring = True
napoleon_numpy_docstring = False
napoleon_include_init_with_doc = True

# Intersphinx mapping
intersphinx_mapping = {
    "python": ("https://docs.python.org/3", None),
}

# HTML output options
html_theme = "sphinx_rtd_theme"
html_static_path = []
html_theme_options = {
    "collapse_navigation": False,
    "sticky_navigation": True,
    "navigation_depth": 4,
    "includehidden": True,
    "titles_only": False,
}

# GitHub link
html_context = {
    "display_github": True,
    "github_user": "sohaib17",
    "github_repo": "pypecdp",
    "github_version": "main",
    "conf_py_path": "/docs/",
}

# Add GitHub link to sidebar
html_logo = None
html_favicon = None
