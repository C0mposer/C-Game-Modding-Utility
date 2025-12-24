import pefile
from functions.verbose_print import verbose_print

def find_export_rva(exe_path: str, export_name: str) -> int:
    """
    Find the RVA of an exported symbol by parsing the PE export table.
    This works for data exports like EEmem.
    """
    try:
        pe = pefile.PE(exe_path, fast_load=True)
        if pe.OPTIONAL_HEADER.DATA_DIRECTORY[pefile.DIRECTORY_ENTRY["IMAGE_DIRECTORY_ENTRY_EXPORT"]].Size != 0:
            pe.parse_data_directories(directories=[pefile.DIRECTORY_ENTRY["IMAGE_DIRECTORY_ENTRY_EXPORT"]])


        # Check if the PE has exports
        if not hasattr(pe, 'DIRECTORY_ENTRY_EXPORT'):
            verbose_print("No export table found in executable.")
            return 0

        # Search through all exports
        for export in pe.DIRECTORY_ENTRY_EXPORT.symbols:
            if export.name and export.name.decode('utf-8') == export_name:
                verbose_print(f"Found '{export_name}' in export table at RVA: 0x{export.address:X}")
                return export.address

        verbose_print(f"Export '{export_name}' not found in export table.")
        return 0

    except Exception as e:
        verbose_print(f"Error parsing PE file: {e}")
        return 0