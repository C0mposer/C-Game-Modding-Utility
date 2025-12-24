from functions.helper_funcs import *
from functions.print_wrapper import *
from classes.injection_targets.injection_target import *

class Hook(InjectionTarget):
    def __init__(self):
        super().__init__()
        self.is_temporary: bool = False  # Mark as temporary (auto-generated)
    
    
    def AddASMFile(self, file_path: str):
        if IsAValidASMFile(file_path):
            self.files.append(file_path)
        else:
            print_error("Not a valid .s or .asm file")
            
    def RemoveLatestASMFile(self):
        removed_file = self.files.pop()
        print_dark_grey(f"Removed file: {removed_file} from hook {self.name}")
        
    def SetTemporary(self, is_temp: bool):
        self.is_temporary = is_temp
    
    def IsTemporary(self) -> bool:
        return self.is_temporary
        