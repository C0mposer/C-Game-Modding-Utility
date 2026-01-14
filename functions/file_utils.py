
def get_file_extension(file_path: str) -> str:
    return file_path.split(".")[-1]


def get_filename_from_path(file_path: str) -> str:
    s = file_path.split("/")[-1]
    return s.split("\\")[-1]


# Backward compatibility aliases (PascalCase)
GetFileExtension = get_file_extension
GetFileNameFromPath = get_filename_from_path
