import os
from typing import Optional, Tuple
from classes.project_data.project_data import ProjectData
from classes.injection_targets.code_cave import Codecave
from classes.injection_targets.hook import Hook
from services.pattern_service import PatternService
from functions.verbose_print import verbose_print

class TemplateResult:
    """Result of template application"""
    def __init__(self, success: bool, message: str = ""):
        self.success = success
        self.message = message
        self.codecaves_created = 0
        self.hooks_created = 0

class TemplateService:
    """Handles platform-specific project templates"""
    
    # PS1 Header Codecave (exists in ALL PS1 games)
    PS1_HEADER_CODECAVE = {
        'name': 'PS1_Header',
        'memory_address': '8000B0B8',
        'size': '800',
        'description': 'PS1 System Header (2KB free space available in all games)',
        'file_offset_from_ram': '800B0B8',  # For SCUS files, typically at 0x48
    }
    
    def __init__(self, project_data: ProjectData):
        self.project_data = project_data
    
    def apply_ps1_template(self) -> TemplateResult:
        """
        Apply complete PS1 template:
        1. Create header codecave
        2. Add main.c to codecave
        3. Find first auto-hook
        4. Set everything up for immediate compilation
        
        Returns TemplateResult with success status
        """
        result = TemplateResult(success=False)
        
        current_build = self.project_data.GetCurrentBuildVersion()
        platform = current_build.GetPlatform()
        
        if platform != "PS1":
            result.message = "Template only available for PS1 projects"
            return result
        
        print("\n" + "="*60)
        print("APPLYING PS1 PROJECT TEMPLATE")
        print("="*60)
        
        # Step 1: Create header codecave
        print("\n[1/3] Creating PS1 header codecave...")
        codecave_result = self._create_ps1_header_codecave()
        
        if not codecave_result:
            result.message = "Failed to create header codecave"
            return result
        
        result.codecaves_created = 1
        print("   Header codecave created (2KB @ 0x8000B0B8)")
        
        # Step 2: Auto-detect hook
        print("\n[2/3] Scanning for hooks...")
        hook_result = self._auto_detect_first_hook()
        
        if hook_result:
            result.hooks_created = 1
            print(f"   Hook created: {hook_result}")
        else:
            print("   No hooks auto-detected (you can add manually)")
        
        # Step 3: Verify setup
        print("\n[3/3] Verifying project setup...")
        if self._verify_ps1_setup():
            result.success = True
            result.message = (
                f"PS1 template applied successfully!\n\n"
                f"Ready to compile and run!"
            )
            print("   Project ready to compile!")
        else:
            result.success = False
            result.message = "Template applied but setup incomplete"
            print("   Setup verification failed")
        
        print("\n" + "="*60)
        print("TEMPLATE APPLICATION COMPLETE")
        print("="*60 + "\n")
        
        return result
    
    def create_ps1_header_codecave_only(self) -> bool:
        """
        Create just the PS1 header codecave (for the button in codecaves tab).
        Returns True on success.
        """
        current_build = self.project_data.GetCurrentBuildVersion()
        platform = current_build.GetPlatform()
        
        if platform != "PS1":
            print("Header codecave only available for PS1 projects")
            return False
        
        # Check if header codecave already exists
        existing_names = current_build.GetCodeCaveNames()
        if self.PS1_HEADER_CODECAVE['name'] in existing_names:
            print(f" Header codecave already exists: {self.PS1_HEADER_CODECAVE['name']}")
            return False
        
        return self._create_ps1_header_codecave()
    
    def _create_ps1_header_codecave(self) -> bool:
        """Create the PS1 header codecave with main.c and syscalls"""
        current_build = self.project_data.GetCurrentBuildVersion()
        project_folder = self.project_data.GetProjectFolder()

        # Create syscalls.s for PS1 printf syscall
        syscalls_s_path = os.path.join(project_folder, "asm", "syscalls.s")
        if not os.path.exists(syscalls_s_path):
            with open(syscalls_s_path, "w") as syscalls_file:
                syscalls_file.write(""".set noreorder
.align 2
.global printf_syscall
.type printf_syscall, @function
printf_syscall:
    li    $t2, 0xA0
    jr    $t2
    li    $t1, 0x3F
\n
""")

        # Create syscalls.h header
        syscalls_h_path = os.path.join(project_folder, "include", "syscalls.h")
        if not os.path.exists(syscalls_h_path):
            with open(syscalls_h_path, "w") as syscalls_h:
                syscalls_h.write("""#ifndef SYSCALLS_H
#define SYSCALLS_H

// PS1 BIOS Syscall - printf
// Uses syscall 0x3F (std_out_printf) via 0xA0 vector
int printf_syscall(const char* format, ...);

#endif // SYSCALLS_H
""")
            verbose_print(f"  Created: include/syscalls.h")

        # Only update main.c if it contains the default template code (hasn't been customized yet)
        main_c_path = os.path.join(project_folder, "src", "main.c")
        main_updated = False
        if os.path.exists(main_c_path):
            with open(main_c_path, "r") as f:
                current_content = f.read()

            # Check if main.c still has default content (user hasn't customized it)
            is_default = "// Your code here" in current_content or current_content.strip() == ""

            if is_default:
                with open(main_c_path, "w") as main_file:
                    main_file.write("""#include <types.h>
#include <symbols.h>
#include <syscalls.h>

void ModMain(void) {
    printf_syscall("Hello World!\\n");

    return;
}

""")
                main_updated = True
                verbose_print(f"  Updated: src/main.c")
            else:
                verbose_print(f"  Skipped: src/main.c (already customized)")

        # Create codecave object
        header_cave = Codecave()
        header_cave.SetName(self.PS1_HEADER_CODECAVE['name'])
        header_cave.SetMemoryAddress(self.PS1_HEADER_CODECAVE['memory_address'])
        header_cave.SetSize(self.PS1_HEADER_CODECAVE['size'])

        # Set injection file (main executable)
        main_exe = current_build.GetMainExecutable()
        if main_exe:
            header_cave.SetInjectionFile(main_exe)

            # Calculate file address
            file_offset = current_build.GetInjectionFileOffset(main_exe)
            if file_offset:
                try:
                    # Memory: 0x8000B0B8 → Remove 0x80 prefix → 0x00B0B8
                    mem_addr_int = int(self.PS1_HEADER_CODECAVE['memory_address'][2:], 16)
                    offset_int = int(file_offset, 16)
                    file_addr = 0x48

                    header_cave.SetInjectionFileAddress(f"{file_addr:X}")
                    header_cave.SetAutoCalculateInjectionFileAddress(False)

                    print(f"  File offset calculated: 0x{file_addr:X}")
                except ValueError:
                    print("   Could not calculate file offset")
                    header_cave.SetAutoCalculateInjectionFileAddress(False)

        # Add main.c to codecave only if it was updated with Hello World
        if main_updated and os.path.exists(main_c_path):
            header_cave.AddCodeFile(main_c_path)
            print(f"  Added to codecave: src/main.c")
        elif not main_updated:
            print(f"  Skipped adding main.c to codecave (user has custom code)")

        if os.path.exists(syscalls_s_path):
            header_cave.AddCodeFile(syscalls_s_path)
            print(f"  Added to codecave: asm/syscalls.s")

        # Add codecave to project
        current_build.AddCodeCave(header_cave)

        print(f"   Created: {self.PS1_HEADER_CODECAVE['name']}")
        return True
    
    def _auto_detect_first_hook(self) -> Optional[str]:
        """
        Auto-detect and create the first hook found.
        Returns hook name on success, None on failure.
        """
        current_build = self.project_data.GetCurrentBuildVersion()
        
        # Use pattern service to find hooks
        pattern_service = PatternService(self.project_data)
        matches = pattern_service.find_hook_patterns()
        
        if not matches:
            print("  No patterns found")
            return None
        
        # Use the first match
        first_match = matches[0]
        hook_name = "AutoHook_Main"
        
        # Create hook from pattern
        hook = pattern_service.create_hook_from_pattern(first_match, hook_name)
        
        # Set main executable as target
        main_exe = current_build.GetMainExecutable()
        if main_exe:
            hook.SetInjectionFile(main_exe)
        
        # Add to project
        current_build.AddHook(hook)
        
        print(f"  Found: {first_match.pattern_name}")
        print(f"  Memory: 0x{first_match.memory_address:X}")
        print(f"  File: 0x{first_match.file_offset:X}")
        
        return hook_name
    
    def _verify_ps1_setup(self) -> bool:
        """Verify that PS1 project has everything needed to compile"""
        current_build = self.project_data.GetCurrentBuildVersion()
        project_folder = self.project_data.GetProjectFolder()
        
        checks = []
        
        # Check 1: Main executable set
        has_main_exe = current_build.GetMainExecutable() is not None
        checks.append(("Main executable set", has_main_exe))
        
        # Check 2: At least one codecave
        has_codecave = len(current_build.GetEnabledCodeCaves()) > 0
        checks.append(("Codecave created", has_codecave))
        
        # Check 3: main.c exists
        main_c_exists = os.path.exists(os.path.join(project_folder, "src", "main.c"))
        checks.append(("main.c exists", main_c_exists))
        
        # Check 4: File offset set
        main_exe = current_build.GetMainExecutable()
        has_offset = False
        if main_exe:
            offset = current_build.GetInjectionFileOffset(main_exe)
            has_offset = offset and offset != ""
        checks.append(("File offset set", has_offset))
        
        # Print verification results
        for check_name, passed in checks:
            status = "" if passed else ""
            print(f"    {status} {check_name}")
        
        return all(passed for _, passed in checks)

    def setup_ps2_print_syscall(self) -> bool:
        """
        Create PS2 _print syscall files (syscalls.s and syscalls.h).
        Updates main.c to call _print("Hello World!\n").
        Returns True on success.
        """
        current_build = self.project_data.GetCurrentBuildVersion()
        platform = current_build.GetPlatform()
        project_folder = self.project_data.GetProjectFolder()

        if platform != "PS2":
            print("PS2 print syscall only available for PS2 projects")
            return False

        # Create syscalls.s for PS2 _print syscall
        syscalls_s_path = os.path.join(project_folder, "asm", "syscalls.s")
        if not os.path.exists(syscalls_s_path):
            with open(syscalls_s_path, "w") as syscalls_file:
                syscalls_file.write(""".set noreorder
.global _print
.type _print, @function
_print:
    li $v1, 0x75
    syscall
    jr $ra
    nop
\n
""")
            verbose_print(f"  Created: asm/syscalls.s")

        # Create syscalls.h header
        syscalls_h_path = os.path.join(project_folder, "include", "syscalls.h")
        if not os.path.exists(syscalls_h_path):
            with open(syscalls_h_path, "w") as syscalls_h:
                syscalls_h.write("""#ifndef SYSCALLS_H
#define SYSCALLS_H

// PS2 BIOS Syscall - _print
// Uses syscall 0x75
int _print(const char* format, ...);

#endif // SYSCALLS_H
""")
            verbose_print(f"  Created: include/syscalls.h")

        # Only update main.c if it contains the default template code (hasn't been customized yet)
        main_c_path = os.path.join(project_folder, "src", "main.c")
        if os.path.exists(main_c_path):
            with open(main_c_path, "r") as f:
                current_content = f.read()

            # Check if main.c still has default content (user hasn't customized it)
            is_default = "// Your code here" in current_content or current_content.strip() == ""

            if is_default:
                with open(main_c_path, "w") as main_file:
                    main_file.write("""#include <types.h>
#include <symbols.h>
#include <syscalls.h>

void ModMain(void) {
    _print("Hello World!\\n");

    return;
}

""")
                verbose_print(f"  Updated: src/main.c")
            else:
                verbose_print(f"  Skipped: src/main.c (already customized)")

        return True

    def setup_ps2_hook_with_return_value(self, original_function: str, return_type: str = "int") -> bool:
        """
        Create PS2 template for hooks that need to preserve return values.

        Args:
            original_function: Name of the original function (e.g., "sceSifSendCmd")
            return_type: Return type (e.g., "int")

        Returns:
            True if template was created, False if main.c already customized
        """
        project_folder = self.project_data.GetProjectFolder()
        main_c_path = os.path.join(project_folder, "src", "main.c")

        # Define the EXACT default PS2 template
        default_ps2_template = """#include <types.h>
#include <symbols.h>
#include <syscalls.h>

void ModMain(void) {
    _print("Hello World!\\n");

    return;
}

"""

        # Check if main.c matches the exact default template
        if os.path.exists(main_c_path):
            with open(main_c_path, 'r') as f:
                current_content = f.read()

            # Only proceed if it matches the EXACT default template
            if current_content != default_ps2_template:
                verbose_print(f"  Skipped: src/main.c (already customized or not default PS2 template)")
                return False

        # Create template with return value
        underscore_func = f"_{original_function}"

        template = f"""
#include <types.h>
#include <symbols.h>
#include <syscalls.h>

{return_type} {underscore_func}();

{return_type} ModMain(void) {{
    {return_type} ret = {underscore_func}(); // MUST keep as first line. This is the function that was replaced by the hook.

    // Your code here
    _print("Hello World!\n");

    return ret; // MUST keep as last line. This is the return value from the replaced function.
}}

"""

        with open(main_c_path, 'w') as f:
            f.write(template)

        verbose_print(f"  Updated: src/main.c (Return value template for {original_function})")
        return True

    def should_offer_template(self) -> Tuple[bool, str]:
        current_build = self.project_data.GetCurrentBuildVersion()
        platform = current_build.GetPlatform()
        
        # Only for PS1
        if platform != "PS1":
            return False, "Not a PS1 project"
        
        # Check if main executable is set (SCUS file)
        main_exe = current_build.GetMainExecutable()
        if not main_exe:
            return False, "No main executable set"
        
        # Check if it's a SCUS/SCES/SLUS/SLES file
        main_exe_upper = main_exe.upper()
        is_ps1_exe = any(main_exe_upper.startswith(prefix) for prefix in 
                        ["SCUS", "SCES", "SLUS", "SLES", "SCPS", "SLPS"])
        
        if not is_ps1_exe:
            return False, "Not a PS1 executable"
        
        # FIX: Check if THIS BUILD VERSION has codecaves
        # (not just if any build version has codecaves)
        has_codecaves = len(current_build.GetEnabledCodeCaves()) > 0
        if has_codecaves:
            return False, "Build version already has codecaves"
        
        # Check if file offset is set
        file_offset = current_build.GetInjectionFileOffset(main_exe)
        if not file_offset or file_offset == "":
            return False, "File offset not set yet"
        
        # NEW: Check if game folder is set (required for template)
        game_folder = current_build.GetGameFolder()
        if not game_folder or not os.path.exists(game_folder):
            return False, "Game folder not set yet"
        
        return True, "Ready for template"


# ==================== GUI Integration ====================

def callback_add_ps1_header_codecave(sender, app_data, current_project_data: ProjectData):
    """
    Callback for "Add PS1 Header Codecave" button in codecaves tab.
    Only visible for PS1 projects.
    """
    from tkinter import messagebox
    
    template_service = TemplateService(current_project_data)
    
    # Verify platform
    platform = current_project_data.GetCurrentBuildVersion().GetPlatform()
    if platform != "PS1":
        messagebox.showerror("Error", "PS1 header codecave only available for PS1 projects")
        return
    
    # Check if already exists
    existing_names = current_project_data.GetCurrentBuildVersion().GetCodeCaveNames()
    if TemplateService.PS1_HEADER_CODECAVE['name'] in existing_names:
        messagebox.showinfo("Already Exists", 
            "PS1 header codecave already exists in this project.\n\n"
            "Check the codecaves list above.")
        return
    
    # Create the codecave
    success = template_service.create_ps1_header_codecave_only()
    
    if success:
        # Update GUI
        from gui.gui_c_injection import UpdateCodecavesListbox, ReloadGuiCodecaveData
        UpdateCodecavesListbox(current_project_data)
        
        # Select the newly created codecave
        import dearpygui.dearpygui as dpg
        dpg.set_value("codecaves_listbox", TemplateService.PS1_HEADER_CODECAVE['name'])
        
        # Trigger selection callback to load details
        from gui.gui_c_injection import callback_codecave_selected
        callback_codecave_selected(
            "codecaves_listbox",
            TemplateService.PS1_HEADER_CODECAVE['name'],
            current_project_data
        )
        
        # Trigger auto-save
        from gui.gui_main_project import trigger_auto_save
        trigger_auto_save()
        
        messagebox.showinfo("Success",
            "PS1 Template Created!\n\n"
            "You can now compile your project!")
    else:
        messagebox.showerror("Failed", 
            "Could not create PS1 header codecave.\n\n"
            "Check console output for details.")


def callback_apply_ps1_template(sender, app_data, current_project_data: ProjectData):
    """
    Callback for "Apply PS1 Template" prompt.
    Shows after extracting PS1 game for new projects.
    """
    from tkinter import messagebox
    from gui.gui_loading_indicator import LoadingIndicator
    
    # Show loading indicator
    LoadingIndicator.show("Applying PS1 template...")
    
    def apply_async():
        try:
            template_service = TemplateService(current_project_data)
            result = template_service.apply_ps1_template()
            
            # Update UI on main thread
            def update_ui():
                LoadingIndicator.hide()
                
                if result.success:
                    # Update codecaves listbox
                    from gui.gui_c_injection import UpdateCodecavesListbox
                    UpdateCodecavesListbox(current_project_data)
                    
                    # Update hooks listbox
                    from gui.gui_asm_injection import UpdateHooksListbox
                    UpdateHooksListbox(current_project_data)
                    
                    # Show tabs
                    import dearpygui.dearpygui as dpg
                    dpg.configure_item("Game Files To Inject Into", show=True)
                    dpg.configure_item("Modifications", show=True)
                    
                    # Trigger auto-save
                    from gui.gui_main_project import trigger_auto_save
                    trigger_auto_save()
                    
                    # Show success message
                    #messagebox.showinfo("Template Applied", result.message)
                else:
                    messagebox.showerror("Template Failed", result.message)
            
            import dearpygui.dearpygui as dpg
            dpg.split_frame()
            update_ui()
            
        except Exception as e:
            LoadingIndicator.hide()
            import traceback
            messagebox.showerror("Error", 
                f"Failed to apply template:\n\n{str(e)}\n\n{traceback.format_exc()}")
    
    import threading
    thread = threading.Thread(target=apply_async, daemon=True)
    thread.start()


def show_ps1_template_prompt(current_project_data: ProjectData):
    """
    Show modal dialog asking if user wants to apply PS1 template.
    Only shown when conditions are met.
    """
    import dearpygui.dearpygui as dpg
    from tkinter import messagebox
    
    template_service = TemplateService(current_project_data)
    should_offer, reason = template_service.should_offer_template()
    
    if not should_offer:
        print(f"Not offering PS1 template: {reason}")
        return
    
    # Show prompt
    response = messagebox.askyesno(
        "Apply PS1 Template?",
        "Would you like to apply the PS1 project template?\n\n"
        "Recommended for new PS1 projects!"
    )
    
    if response:
        callback_apply_ps1_template(None, None, current_project_data)