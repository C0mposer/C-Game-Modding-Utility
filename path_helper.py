import sys
import os


def get_application_directory() -> str:
    if getattr(sys, 'frozen', False):
        # Running as PyInstaller use executable location
        return os.path.dirname(os.path.abspath(sys.argv[0]))
    else:
        # Running as Python script use script location
        return os.path.dirname(os.path.abspath(__file__))
