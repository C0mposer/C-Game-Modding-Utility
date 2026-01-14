from functions.file_utils import get_file_extension


def is_valid_code_file(file_path: str) -> bool:
    file_extension = get_file_extension(file_path)
    return file_extension in ("c", "cpp", "asm", "s")


def is_valid_asm_file(file_path: str) -> bool:
    file_extension = get_file_extension(file_path)
    return file_extension in ("s", "asm")


# Backward compatibility aliases (PascalCase)
IsAValidCodeFile = is_valid_code_file
IsAValidASMFile = is_valid_asm_file
