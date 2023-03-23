# Configuration file for the Sphinx documentation builder.
#
# This file only contains a selection of the most common options. For a full
# list see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html
from backend import __version__

from pallets_sphinx_themes import ProjectLink

# Project --------------------------------------------------------------

project = "Backend Server"
copyright = "2023, Sireto Technology"
author = "Bibishan Pandey"
release = __version__

# General --------------------------------------------------------------

extensions = [
    "sphinx.ext.napoleon",
    "sphinx.ext.autodoc",
    "sphinx.ext.intersphinx",
    "pallets_sphinx_themes",
    "myst_parser",
    "sphinx_material",
]

autodoc_typehints = "description"
intersphinx_mapping = {
    "python": ("https://docs.python.org/3/", None),
    "click": ("https://click.palletsprojects.com/en/8.1.x/", None),
}
napoleon_google_docstring = True
napoleon_numpy_docstring = False
napoleon_include_init_with_doc = False
napoleon_include_private_with_doc = True
napoleon_attr_annotations = True


templates_path = ["_templates"]
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

# HTML -----------------------------------------------------------------

html_theme = "sphinx_material"
# Material theme options (see theme.conf for more information)
html_theme_options = {
    # Set the name of the project to appear in the navigation.
    "nav_title": "Better Collected",
    # Set you GA account ID to enable tracking
    # "google_analytics_account": "UA-XXXXX",
    # Specify a base_url used to generate sitemap.xml. If not
    # specified, then no sitemap will be built.
    # "base_url": "https://project.github.io/project",
    "version_dropdown": True,
    "theme_color": "#3B82F6",
    "color_primary": "white",
    "color_accent": "#f43f5e",
    "html_minify": True,
    "css_minify": True,
    "logo_icon": "&#xe869",
    "repo_name": "Backend Server",
    # "repo_url": "https://github.com/project/project/",
    # Visible levels of the global TOC; -1 means unlimited
    "globaltoc_depth": 4,
    # If False, expand all TOC entries
    "globaltoc_collapse": True,
    # If True, show hidden TOC entries
    "globaltoc_includehidden": True,
}
html_context = {
    "project_links": [
        ProjectLink("Source Code", ""),
    ]
}
html_sidebars = {
    "**": ["logo-text.html", "globaltoc.html", "localtoc.html", "searchbox.html"]
}
singlehtml_sidebars = {"index": ["project.html", "localtoc.html"]}
html_title = f"Backend Server: Documentation ({__version__})"
html_show_sourcelink = False
html_static_path = ["_static"]
