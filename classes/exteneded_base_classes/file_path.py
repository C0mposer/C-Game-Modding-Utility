class FilePathStr(str):
    def __init__(self):
        super.__init__()
    
    def GetFileExtension(self):
        return self.split(".")[-1]

    def GetFileNameFromPath(self):
        return self.split("/")[-1]

    def IsAValidCodeFile(self):
        file_extension = self.GetFileExtension()
        if file_extension == "c" or file_extension == "cpp":
            return True
        else:
            return False
    
    def IsAValidASMFile(self):
        file_extension = self.GetFileExtension()
        if file_extension == "s" or file_extension == "asm":
            return True
        else:
            return False
    
    