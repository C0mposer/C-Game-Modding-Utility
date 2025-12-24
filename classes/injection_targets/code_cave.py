from functions.helper_funcs import *
from functions.print_wrapper import *
from classes.injection_targets.injection_target import *
from functions.verbose_print import verbose_print

class Codecave(InjectionTarget):
    def __init__(self):
        super().__init__()
    
    def AddCFile(self, file_path: str):
        if IsAValidCodeFile(file_path):
            self.code_files.append(file_path)
        else:
            print_error("Not a valid C or C++ file")
            verbose_print(file_path)

    def RemoveLatestCFile(self):
        removed_file = self.code_files.pop()
        print_dark_grey(f"Removed file: {removed_file} from codecave {self.name}")
        
    def ClearCFiles(self):
        self.code_files.clear()
        print("Cleared all code files from codecave")