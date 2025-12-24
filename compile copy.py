
from services.compilation_service import CompilationService, CompilationResult
from classes.mod_builder import ModBuilder
from classes.project_data.project_data import ProjectData

def Compile(current_project_data: ProjectData, mod_data: ModBuilder) -> bool:
    """
    Legacy compile function - redirects to new service.
    Returns True on success, False on failure.
    """
    service = CompilationService(current_project_data, mod_data, verbose=False, no_warnings=False)
    result = service.compile_project()
    return result.success

# Keep UpdateLinkerScript for now if other code depends on it
def UpdateLinkerScript(current_project_data: ProjectData, mod_data: ModBuilder):
    """Legacy linker script update - now handled by service"""
    service = CompilationService(current_project_data, mod_data, verbose=False, no_warnings=False)
    return service._update_linker_script()