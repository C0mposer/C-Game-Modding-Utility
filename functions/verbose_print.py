import sys

is_verbose = False

def set_verbose(verbose: bool):
    global is_verbose
    is_verbose = verbose

def verbose_print(string: str):
    global is_verbose

    if is_verbose:
        print(string)
    else:
        return

# Detect verbose mode from command line arguments
if '-verbose' in sys.argv or '--verbose' in sys.argv:
    is_verbose = True