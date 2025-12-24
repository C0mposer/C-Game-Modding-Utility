from functions.helper_funcs import *
from functions.print_wrapper import *
from classes.injection_targets.injection_target import *

class BinaryPatch(InjectionTarget):
    def __init__(self):
        super().__init__()
    
    def AddBinaryFile(self, file_path: str):
        self.code_files.append(file_path)
            
    def RemoveLatestBinaryFile(self):
        removed_file = self.files.pop()
        print_dark_grey(f"Removed file: {removed_file} from binary patch {self.name}")
        