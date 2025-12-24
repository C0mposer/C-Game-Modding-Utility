class MultiPatchASM:
    """Represents a multi-patch ASM file that generates hooks dynamically"""
    def __init__(self):
        self.name: str = ""
        self.file_path: str = ""  # Path to .s/.asm file
    
    def SetName(self, name: str):
        self.name = name
    
    def GetName(self) -> str:
        return self.name
    
    def SetFilePath(self, path: str):
        self.file_path = path
    
    def GetFilePath(self) -> str:
        return self.file_path