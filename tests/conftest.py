"""Shared pytest fixtures."""

import platform

import pytest


@pytest.fixture
def is_macos() -> bool:
    """Whether the current host is macOS."""
    return platform.system() == 'Darwin'
