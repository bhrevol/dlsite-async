"""Sphinx configuration."""

project = "DLsite Async"
author = "byeonhyeok"
copyright = "2022, byeonhyeok"
extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",
    "sphinx_click",
    "myst_parser",
]
autodoc_typehints = "description"
html_theme = "furo"
