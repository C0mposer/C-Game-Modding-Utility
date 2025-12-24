from functions.helper_funcs import *
from functions.print_wrapper import *

# Injection type constants
INJECTION_TYPE_EXISTING_FILE = "existing_file"
INJECTION_TYPE_NEW_FILE = "new_file"
INJECTION_TYPE_MEMORY_ONLY = "memory_only"

# Base Class for Codecave, Hook, and BinaryPatch
class InjectionTarget:
    def __init__(self):
        self.name: str = None
        self.code_files: list[str] = []
        self.memory_address: str = None

        self.size: str = "0" # Optional
        self.injection_file: str = None
        self.injection_file_address: str = None
        self.injection_file_address_offset_from_memory_address = None
        self.auto_calculate_injection_file_address = False

        self.injection_type: str = INJECTION_TYPE_EXISTING_FILE  # Default to existing behavior
        self.enabled: bool = True  # Whether this target is enabled (for compilation/injection)
        
    def GetName(self):
        return self.name
    def SetName(self, name: str):
        safe_name = SanitizeNameNoSpaces(name)
        self.name = safe_name
        
    def GetMemoryAddress(self):
        return self.memory_address
    def SetMemoryAddress(self, mem_address: str):
        self.memory_address = mem_address
    def GetMemoryAddressAsInt(self):
        return int(self.memory_address, base=16)
    def SetMemoryAddressAsInt(self, mem_address: int):
        self.memory_address = str(mem_address)
        
    def GetSize(self):
        return self.size
    def SetSize(self, size):
        self.size = size
    def GetSizeAsInt(self):
        return int(self.size, base=16)
        
    # Make specific methods for Codecave, Hook, and BinaryPatch
    def GetCodeFilesPaths(self):
        return self.code_files
    def GetCodeFilesPathsAsString(self):
        files_string: str = "\""
        for file in self.code_files:
            files_string += file + " "
        files_string += "\" "
        return files_string
    def GetCodeFilesNames(self):
        code_files_no_path = list()
        for file in self.code_files:
            code_files_no_path.append(GetFileNameFromPath(file))
        return code_files_no_path
    
    def AddCodeFile(self, file_path: str):
        self.code_files.append(file_path)
    def PopCodeFile(self):
        file_removed = self.code_files.pop()
        print_dark_grey(f"Removed {file_removed} from code files")
    
    def GetInjectionFile(self):
        return self.injection_file
    def SetInjectionFile(self, file_path: str):
        self.injection_file = file_path
        
    def GetInjectionFileAddress(self):
        return self.injection_file_address
    def SetInjectionFileAddress(self, address: str):
        self.injection_file_address = address
        
    def GetAutoCalculateInjectionFileAddress(self):
        return self.auto_calculate_injection_file_address
    def SetAutoCalculateInjectionFileAddress(self, value: bool):
        self.auto_calculate_injection_file_address = value
    
    # Injection type methods
    def GetInjectionType(self) -> str:
        return self.injection_type

    def SetInjectionType(self, injection_type: str):
        # Clamp to known values so old/corrupt projects don’t break things
        valid = {
            INJECTION_TYPE_EXISTING_FILE,
            INJECTION_TYPE_NEW_FILE,
            INJECTION_TYPE_MEMORY_ONLY,
        }
        if injection_type not in valid:
            injection_type = INJECTION_TYPE_EXISTING_FILE
        self.injection_type = injection_type

    def IsNewFile(self) -> bool:
        return self.injection_type == INJECTION_TYPE_NEW_FILE

    def IsMemoryOnly(self) -> bool:
        return self.injection_type == INJECTION_TYPE_MEMORY_ONLY

    # Enabled state methods
    def IsEnabled(self) -> bool:
        return self.enabled

    def SetEnabled(self, enabled: bool):
        self.enabled = enabled