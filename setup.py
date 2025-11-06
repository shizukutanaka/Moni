#!/usr/bin/env python3
"""
Moni System Monitor - Setup script for PyPI distribution

This setup.py provides compatibility for older build systems.
Modern installations should use pyproject.toml with setuptools.build_meta.
"""

from setuptools import setup

# All configuration is in pyproject.toml
# This file exists for backward compatibility with:
# - pip install -e . (editable installs)
# - python setup.py develop
# - Legacy build tools

if __name__ == "__main__":
    setup(
        # Configuration is loaded from pyproject.toml
        # via setuptools.config.pyprojecttoml
    )
