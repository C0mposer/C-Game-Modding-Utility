import sys

def is_pyinstaller():
    return hasattr(sys, 'frozen') and getattr(sys, 'frozen') == 'windows_exe' or hasattr(sys, '_MEIPASS')