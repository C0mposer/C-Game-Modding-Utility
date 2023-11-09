
class BaseIGPatch():
    def __init__(self):
        self.in_game_address = "0x00000000"
        self.disk_address = "0x00000000"
        self.disk_offset = "0x0"
        self.files = ""
        
    def __init__(self, name, in_game_address, disk_address, disk_offset, files):
        self.name = name
        self.in_game_address =in_game_address
        self.disk_address = disk_address
        self.disk_offset = disk_offset
        self.files = files
        
    def get_in_game_address_int(self):
        return int(self.in_game_address, base=16)
    
    def get_disk_address_int(self):
        return int(self.disk_address, base=16)

    def get_files_no_ext(self):
        files_no_ext = []
        for file in self.files:
            files_no_ext = file.split(".")[0]   # Splitting off extension
        return files_no_ext
    
    def get_files_obj_ext(self):
        files_obj_ext = []
        for file in self.files:
            files_obj_ext = file.split(".")[0] + ".o"   # Splitting off extension
        return files_obj_ext

class Codecave(BaseIGPatch):
    def __init__(self):
        self.name = "Codecave"
        super.__init__()
        
    def __init__(self, name, in_game_address, disk_address, disk_offset, c_files):
        super.__init__(name, in_game_address, disk_address, disk_offset, c_files)
        
class Hook(BaseIGPatch):
    def __init__(self):
        self.name = "Hook"
        super.__init__()
        
    def __init__(self, name, in_game_address, disk_address, disk_offset, asm_files):
        super.__init__(name, in_game_address, disk_address, disk_offset, asm_files)
        
        
class UserBinaryPatch(BaseIGPatch):
    def __init__(self):
        self.name = "Patch"
        super.__init__()
        
    def __init__(self, name, in_game_address, disk_address, disk_offset, patch_files):
        super.__init__(name, in_game_address, disk_address, disk_offset, patch_files)
