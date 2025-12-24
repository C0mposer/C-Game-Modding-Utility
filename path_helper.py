"""
Path helper utilities for handling PyInstaller bundled executables.

This module provides a centralized way to get the application directory
that works correctly in both development (Python script) and production
(PyInstaller bundle) environments.
"""
import sys
import os


def get_application_directory() -> str:
    """
    Get the directory where the application is located.

    Works correctly for both development (Python script) and production (PyInstaller bundle).

    In development mode (running as Python script):
        Returns the directory containing the main script

    In production mode (running as PyInstaller bundle):
        Returns the directory containing the .exe file (NOT the temp AppData location)

    Returns:
        str: Absolute path to the application directory
    """
    if getattr(sys, 'frozen', False):
        # Running as PyInstaller bundle - use executable location
        # sys.argv[0] is the path to the .exe file
        return os.path.dirname(os.path.abspath(sys.argv[0]))
    else:
        # Running as Python script - use script location
        # __file__ is this module's path, so return its directory
        return os.path.dirname(os.path.abspath(__file__))
