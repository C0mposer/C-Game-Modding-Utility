# gui/gui_text_editors.py

import os
import subprocess
import json
from tkinter import messagebox
from classes.project_data.project_data import ProjectData


#! VSCode
def callback_open_vscode(sender, app_data, current_project_data: ProjectData):
    """Open project folder in VSCode and automatically generate tasks.json if it doesn't exist"""
    project_folder = current_project_data.GetProjectFolder()

    if not project_folder or not os.path.exists(project_folder):
        messagebox.showerror("Error", "Project folder not found")
        return

    # Check if tasks.json already exists
    vscode_folder = os.path.join(project_folder, ".vscode")
    tasks_file = os.path.join(vscode_folder, "tasks.json")

    # Only auto-generate if tasks.json doesn't exist
    if not os.path.exists(tasks_file):
        try:
            _generate_vscode_tasks_internal(current_project_data)
            print(f" Auto-generated VSCode tasks.json")
        except Exception as e:
            print(f" Warning: Could not auto-generate tasks: {e}")
    else:
        print(f" Using existing VSCode tasks.json (not overwriting)")

    try:
        # Try 'code' command (VSCode CLI)
        subprocess.Popen(['code', project_folder], shell=True)
        print(f" Opened VSCode: {project_folder}")
    except Exception as e:
        messagebox.showerror("Error",
            f"Could not open VSCode.\n\n"
            f"Make sure VSCode is installed and 'code' is in PATH.\n\n"
            f"Error: {str(e)}")


def callback_generate_vscode_tasks(sender, app_data, current_project_data: ProjectData):
    """Generate VSCode tasks.json with compile, build, and inject tasks"""
    try:
        _generate_vscode_tasks_internal(current_project_data)
        
        current_build = current_project_data.GetCurrentBuildVersion()
        platform = current_build.GetPlatform()
        emulators = _get_platform_emulators(platform)
        
        # messagebox.showinfo("Success", 
        #     f"VSCode tasks.json generated!\n\n"
        #     f"Platform: {platform}\n"
        #     f"Tasks Created:\n"
        #     f"  • Compile (interactive build selection)\n"
        #     f"  • Build ISO (interactive build selection)\n"
        #     f"  • Inject ({len(emulators)} emulator(s))\n"
        #     f"  • Clean\n\n"
        #     f"Press Ctrl+Shift+B in VSCode to run tasks")
    except Exception as e:
        messagebox.showerror("Error", f"Could not generate tasks.json:\n\n{str(e)}")


def _generate_vscode_tasks_internal(current_project_data: ProjectData):
    """Internal function to generate tasks.json"""
    project_folder = current_project_data.GetProjectFolder()
    current_build = current_project_data.GetCurrentBuildVersion()
    platform = current_build.GetPlatform()
    
    if not project_folder or not os.path.exists(project_folder):
        raise ValueError("Project folder not found")
    
    # Create .vscode folder if it doesn't exist
    vscode_folder = os.path.join(project_folder, ".vscode")
    os.makedirs(vscode_folder, exist_ok=True)
    
    # Get tool directory (parent of projects folder)
    tool_dir = os.path.abspath(os.path.dirname(os.path.dirname(project_folder)))
    
    # Get absolute path to modtool.py
    #modtool_path = os.path.abspath(os.path.join(tool_dir, "modtool.py"))
    modtool_path = os.path.abspath(os.path.join(tool_dir, "mod_utility.exe"))
    
    # Verify CLI tool exists
    if not os.path.exists(modtool_path):
        raise FileNotFoundError(f"CLI tool not found at: {modtool_path}")
    
    # Get project name (not full path)
    project_name = os.path.basename(project_folder)
    
    # Get emulators for platform
    emulators = _get_platform_emulators(platform)
    
    # Build tasks
    tasks = {
        "version": "2.0.0",
        "tasks": []
    }
    
    # Compile task (interactive build selection)
    tasks["tasks"].append({
        "label": "Compile",
        "type": "shell",
        "command": "./mod_utility.exe",
        "args": [
            "compile",
            project_name
        ],
        "options": {
            "cwd": "${workspaceFolder}..\\..\\..\\"
        },
        "group": {
            "kind": "build",
            "isDefault": True
        },
        "presentation": {
            "reveal": "always",
            "panel": "new"
        },
        "problemMatcher": "$gcc"
    })
    
    # Build ISO task
    tasks["tasks"].append({
        "label": "Build ISO",
        "type": "shell",
        "command": "./mod_utility.exe",
        "args": [
            "build",
            project_name
        ],
        "options": {
            "cwd": "${workspaceFolder}..\\..\\..\\"
        },
        "group": "build",
        "presentation": {
            "reveal": "always",
            "panel": "new"
        },
        "problemMatcher": []
    })
    
    # Inject tasks (one per emulator)
    for emulator in emulators:
        tasks["tasks"].append({
            "label": f"Inject into {emulator}",
            "type": "shell",
            "command": "./mod_utility.exe",
            "args": [
                "inject",
                project_name,
                emulator
            ],
            "options": {
                "cwd": "${workspaceFolder}..\\..\\..\\"
            },
            "group": "test",
            "presentation": {
                "reveal": "always",
                "panel": "new"
            },
            "problemMatcher": []
        })
    
    # Clean task
    tasks["tasks"].append({
        "label": "Clean",
        "type": "shell",
        "command": "./mod_utility.exe",
        "args": [
            "clean",
            project_name
        ],
        "options": {
            "cwd": "${workspaceFolder}..\\..\\..\\"
        },
        "group": "build",
        "presentation": {
            "reveal": "always",
            "panel": "new"
        },
        "problemMatcher": []
    })
    
    # Write tasks.json
    tasks_file = os.path.join(vscode_folder, "tasks.json")
    with open(tasks_file, 'w') as f:
        json.dump(tasks, f, indent=4)
    
    print(f" Generated VSCode tasks.json")



#! Sublime
def callback_open_sublime(sender, app_data, current_project_data: ProjectData):
    """Open project folder in Sublime Text with auto-generated project file if it doesn't exist"""
    project_folder = current_project_data.GetProjectFolder()

    if not project_folder or not os.path.exists(project_folder):
        messagebox.showerror("Error", "Project folder not found")
        return

    # Check if Sublime project file already exists
    project_name = current_project_data.GetProjectName()
    sublime_folder = os.path.join(project_folder, ".sublime")
    sublime_project_file = os.path.join(sublime_folder, f"{project_name}.sublime-project")

    # Only auto-generate if project file doesn't exist
    if not os.path.exists(sublime_project_file):
        try:
            _generate_sublime_project_file(current_project_data)
            print(f" Auto-generated Sublime project file")
        except Exception as e:
            print(f" Warning: Could not auto-generate Sublime project file: {e}")
    else:
        print(f" Using existing Sublime project file (not overwriting)")

    # Try common Sublime Text installation paths
    sublime_paths = [
        r"C:\Program Files\Sublime Text\subl.exe",
        r"C:\Program Files\Sublime Text 3\subl.exe",
        r"C:\Program Files\Sublime Text 4\subl.exe",
    ]
    
    for sublime_path in sublime_paths:
        if os.path.exists(sublime_path):
            try:
                # Open the project file
                subprocess.Popen([sublime_path, sublime_project_file])
                print(f" Opened Sublime Text: {sublime_project_file}")
                return
            except Exception as e:
                print(f"Failed to open with {sublime_path}: {e}")
                continue
    
    # If none found, show error
    messagebox.showerror("Error", 
        f"Could not find Sublime Text.\n\n"
        f"Expected at:\n"
        f"  C:\\Program Files\\Sublime Text\\subl.exe\n\n"
        f"Please install Sublime Text or update the path.")


def _generate_sublime_project_file(current_project_data: ProjectData):
    """Generate Sublime Text project file with build systems"""
    project_folder = current_project_data.GetProjectFolder()
    project_name = current_project_data.GetProjectName()
    current_build = current_project_data.GetCurrentBuildVersion()
    platform = current_build.GetPlatform()
    
    if not project_folder or not os.path.exists(project_folder):
        raise ValueError("Project folder not found")
    
    # Create .sublime folder if it doesn't exist
    sublime_folder = os.path.join(project_folder, ".sublime")
    os.makedirs(sublime_folder, exist_ok=True)
    
    # Get tool directory
    tool_dir = "${project_path}..\\..\\"
    
    # Get absolute path to modtool.py
    modtool_path = "mod_utility.exe"
    
    if not os.path.exists(modtool_path):
        raise FileNotFoundError(f"CLI tool not found at: {modtool_path}")
    
    # Get emulators for platform
    emulators = _get_platform_emulators(platform)
    
    # Build Sublime project structure
    sublime_project = {
        "folders": [
            {
                "path": "..",
                "folder_exclude_patterns": [".notepad++", ".vscode"],
            }
        ],
        "build_systems": []
    }
    
    # Add Compile build system
    sublime_project["build_systems"].append({
        "name": "Compile Mod",
        "working_dir": tool_dir,
        "shell_cmd": f'chcp 65001 >nul && "./..\\..\\{modtool_path}" --no-color compile "{project_name}"',
        "file_regex": r"^(.+):([0-9]+):([0-9]+): (.*)$",
        "encoding": "utf-8",
        "variants": [
            {
                "name": "Compile (Verbose)",
                "shell_cmd": f'chcp 65001 >nul && "{modtool_path}" --no-color --verbose compile "{project_name}"'
            }
        ]
    })
    
    # Add Build ISO build system
    sublime_project["build_systems"].append({
        "name": "Build ISO",
        "working_dir": tool_dir,
        "shell_cmd": f'chcp 65001 >nul && "{modtool_path}" --no-color build "{project_name}"',
        "encoding": "utf-8",
        "variants": [
            {
                "name": "Build ISO (Verbose)",
                "shell_cmd": f'chcp 65001 >nul && "{modtool_path}" --no-color --verbose build "{project_name}"'
            }
        ]
    })
    
    # Add Inject build systems (one per emulator)
    for emulator in emulators:
        sublime_project["build_systems"].append({
            "name": f"Inject into {emulator}",
            "working_dir": tool_dir,
            "shell_cmd": f'chcp 65001 >nul && "{modtool_path}" --no-color inject "{project_name}" "{emulator}"',
            "encoding": "utf-8"
        })
    
    # Add Clean build system
    sublime_project["build_systems"].append({
        "name": "Clean Build",
        "working_dir": tool_dir,
        "shell_cmd": f'chcp 65001 >nul && "{modtool_path}" --no-color clean "{project_name}"',
        "encoding": "utf-8"
    })
    
    # Add Info build system
    sublime_project["build_systems"].append({
        "name": "Project Info",
        "working_dir": tool_dir,
        "shell_cmd": f'chcp 65001 >nul && "{modtool_path}" --no-color info "{project_name}"',
        "encoding": "utf-8"
    })
    
    # Write project file to .sublime folder
    project_file_path = os.path.join(sublime_folder, f"{project_name}.sublime-project")
    with open(project_file_path, 'w') as f:
        json.dump(sublime_project, f, indent=4)
    
    print(f" Generated Sublime project file")


def callback_generate_sublime_project(sender, app_data, current_project_data: ProjectData):
    """Generate Sublime Text project file with build systems (menu callback)"""
    try:
        _generate_sublime_project_file(current_project_data)
        
        current_build = current_project_data.GetCurrentBuildVersion()
        platform = current_build.GetPlatform()
        emulators = _get_platform_emulators(platform)
        
        project_folder = current_project_data.GetProjectFolder()
        sublime_folder = os.path.join(project_folder, ".sublime")
        
        # messagebox.showinfo("Success", 
        #     f"Sublime Text project file generated!\n\n"
        #     f"Platform: {platform}\n"
        #     f"Build Systems Created:\n"
        #     f"  • Compile Mod\n"
        #     f"  • Build ISO\n"
        #     f"  • Inject ({len(emulators)} emulator(s))\n"
        #     f"  • Clean Build\n"
        #     f"  • Project Info\n\n"
        #     f"Location: {sublime_folder}\n\n")
    except Exception as e:
        messagebox.showerror("Error", f"Could not generate Sublime project file:\n\n{str(e)}")


#! Notepad++
def callback_open_notepadpp(sender, app_data, current_project_data: ProjectData):
    """Open project folder in Notepad++ as a workspace with auto-generated batch files if they don't exist"""
    project_folder = current_project_data.GetProjectFolder()

    if not project_folder or not os.path.exists(project_folder):
        messagebox.showerror("Error", "Project folder not found")
        return

    # Check if batch files directory already exists with files
    batch_dir = os.path.join(project_folder, ".notepad++")
    compile_bat = os.path.join(batch_dir, "compile.bat")

    # Only auto-generate if batch files don't exist (check for compile.bat as indicator)
    if not os.path.exists(compile_bat):
        try:
            _generate_notepadpp_batch_files(current_project_data)
            print(f" Auto-generated Notepad++ batch files")
        except Exception as e:
            print(f" Warning: Could not auto-generate batch files: {e}")
    else:
        print(f" Using existing Notepad++ batch files (not overwriting)")

    # Try common Notepad++ installation paths
    npp_paths = [
        r"C:\Program Files\Notepad++\notepad++.exe",
        r"C:\Program Files (x86)\Notepad++\notepad++.exe",
    ]
    
    for npp_path in npp_paths:
        if os.path.exists(npp_path):
            try:
                # Open Notepad++ with folder as workspace
                # -openFoldersAsWorkspace: Opens the folder as a workspace with file browser
                subprocess.Popen([npp_path, '-openFoldersAsWorkspace', project_folder])
                print(f" Opened Notepad++ workspace: {project_folder}")
                return
            except Exception as e:
                print(f"Failed to open with {npp_path}: {e}")
                continue
    
    # If none found, show error
    messagebox.showerror("Error", 
        f"Could not find Notepad++.\n\n"
        f"Expected at:\n"
        f"  C:\\Program Files\\Notepad++\\notepad++.exe\n"
        f"  or\n"
        f"  C:\\Program Files (x86)\\Notepad++\\notepad++.exe\n\n"
        f"Please install Notepad++.")


def _generate_notepadpp_batch_files(current_project_data: ProjectData):
    """Generate batch files for Notepad++ (can be run directly or via NppExec)"""
    project_folder = current_project_data.GetProjectFolder()
    project_name = current_project_data.GetProjectName()
    current_build = current_project_data.GetCurrentBuildVersion()
    platform = current_build.GetPlatform()
    
    if not project_folder or not os.path.exists(project_folder):
        raise ValueError("Project folder not found")
    
    # Get tool directory
    tool_dir = "..\\..\\..\\"
    
    # Get absolute path to modtool.py
    modtool_path = "mod_utility.exe"
    
    if not os.path.exists(modtool_path):
        raise FileNotFoundError(f"CLI tool not found at: {modtool_path}")
    
    # Create batch files directory
    batch_dir = os.path.join(project_folder, ".notepad++")
    os.makedirs(batch_dir, exist_ok=True)
    
    # Get emulators for platform
    emulators = _get_platform_emulators(platform)
    
    # === 1. Compile batch file ===
    compile_bat = os.path.join(batch_dir, "compile.bat")
    with open(compile_bat, 'w') as f:
        f.write(f'@echo off\n')
        f.write(f'cd "{tool_dir}"\n')
        f.write(f'{modtool_path} --no-color compile "{project_name}"\n')
        f.write(f'pause\n')
    
    # === 2. Compile verbose batch file ===
    compile_verbose_bat = os.path.join(batch_dir, "compile_verbose.bat")
    with open(compile_verbose_bat, 'w') as f:
        f.write(f'@echo off\n')
        f.write(f'cd "{tool_dir}"\n')
        f.write(f'{modtool_path} --no-color --verbose compile "{project_name}"\n')
        f.write(f'pause\n')
    
    # === 3. Build ISO batch file ===
    build_bat = os.path.join(batch_dir, "build_iso.bat")
    with open(build_bat, 'w') as f:
        f.write(f'@echo off\n')
        f.write(f'cd "{tool_dir}"\n')
        f.write(f'{modtool_path} --no-color build "{project_name}"\n')
        f.write(f'pause\n')
    
    # === 4. Build ISO verbose batch file ===
    build_verbose_bat = os.path.join(batch_dir, "build_iso_verbose.bat")
    with open(build_verbose_bat, 'w') as f:
        f.write(f'@echo off\n')
        f.write(f'cd "{tool_dir}"\n')
        f.write(f'{modtool_path} --no-color --verbose build "{project_name}"\n')
        f.write(f'pause\n')
    
    # === 5. Inject batch files (one per emulator) ===
    for emulator in emulators:
        # Sanitize emulator name for filename
        safe_name = emulator.replace(' ', '_').replace('.', '_').lower()
        inject_bat = os.path.join(batch_dir, f"inject_{safe_name}.bat")
        
        with open(inject_bat, 'w') as f:
            f.write(f'@echo off\n')
            f.write(f'cd "{tool_dir}"\n')
            f.write(f'{modtool_path} --no-color inject "{project_name}" "{emulator}"\n')
            f.write(f'pause\n')
    
    # === 6. Clean batch file ===
    clean_bat = os.path.join(batch_dir, "clean.bat")
    with open(clean_bat, 'w') as f:
        f.write(f'@echo off\n')
        f.write(f'cd "{tool_dir}"\n')
        f.write(f'{modtool_path} --no-color clean "{project_name}"\n')
        f.write(f'pause\n')
    
    # === 7. Project info batch file ===
    info_bat = os.path.join(batch_dir, "project_info.bat")
    with open(info_bat, 'w') as f:
        f.write(f'@echo off\n')
        f.write(f'cd "{tool_dir}"\n')
        f.write(f'{modtool_path} --no-color info "{project_name}"\n')
        f.write(f'pause\n')
    
    # === 8. Create README ===
    readme_path = os.path.join(batch_dir, "README.txt")
    with open(readme_path, 'w') as f:
        f.write(f"Notepad++ Batch Files for {project_name}\n")
        f.write(f"=" * 60 + "\n\n")
        f.write(f"These batch files can be run directly by double-clicking,\n")
        f.write(f"Platform: {platform}\n")
        f.write(f"Emulators: {', '.join(emulators)}\n\n")
        f.write(f"Available commands:\n")
        f.write(f"  compile.bat          - Compile project\n")
        f.write(f"  compile_verbose.bat  - Compile with verbose output\n")
        f.write(f"  build_iso.bat        - Build ISO\n")
        f.write(f"  build_iso_verbose.bat - Build ISO with verbose output\n")
        for emulator in emulators:
            safe_name = emulator.replace(' ', '_').replace('.', '_').lower()
            f.write(f"  inject_{safe_name}.bat - Inject into {emulator}\n")
        f.write(f"  clean.bat            - Clean build artifacts\n")
        f.write(f"  project_info.bat     - Show project information\n\n")
    print(f" Generated Notepad++ batch files")
    print(f"  Platform: {platform}")
    print(f"  Batch files: {7 + len(emulators)} total")
    print(f"  Location: {batch_dir}")


def callback_generate_notepadpp_batch_files(sender, app_data, current_project_data: ProjectData):
    """Generate Notepad++ batch files (menu callback)"""
    try:
        _generate_notepadpp_batch_files(current_project_data)
        
        current_build = current_project_data.GetCurrentBuildVersion()
        platform = current_build.GetPlatform()
        emulators = _get_platform_emulators(platform)
        
        project_folder = current_project_data.GetProjectFolder()
        batch_dir = os.path.join(project_folder, ".notepad++")
        
        # messagebox.showinfo("Success", 
        #     f"Notepad++ batch files generated!\n\n"
        #     f"Platform: {platform}\n"
        #     f"Batch Files Created: {7 + len(emulators)}\n"
        #     f"  • compile.bat\n"
        #     f"  • compile_verbose.bat\n"
        #     f"  • build_iso.bat\n"
        #     f"  • build_iso_verbose.bat\n"
        #     f"  • inject_*.bat ({len(emulators)} emulator(s))\n"
        #     f"  • clean.bat\n"
        #     f"  • project_info.bat\n\n"
        #     f"Location: {batch_dir}\n\n"
        #     f"Double-click any .bat file to run it!\n"
        #     f"Or use with NppExec plugin (F6 in Notepad++)")
    except Exception as e:
        messagebox.showerror("Error", f"Could not generate batch files:\n\n{str(e)}")


def _get_platform_emulators(platform: str) -> list:
    """Get list of supported emulators for a platform"""
    emulator_map = {
        "PS1": ["DuckStation", "PCSX-Redux", "BizHawk", "Mednafen 1.29", "Mednafen 1.31"],
        "PS2": ["PCSX2"],
        "Gamecube": ["Dolphin"],
        "Wii": ["Dolphin"],
        "N64": ["Project64"]
    }
    
    return emulator_map.get(platform, [])


#! Zed
def callback_open_zed(sender, app_data, current_project_data: ProjectData):
    """Open project folder in Zed and automatically generate tasks.json if it doesn't exist"""
    project_folder = current_project_data.GetProjectFolder()

    if not project_folder or not os.path.exists(project_folder):
        messagebox.showerror("Error", "Project folder not found")
        return

    # Check if tasks.json already exists
    zed_folder = os.path.join(project_folder, ".vscode")
    tasks_file = os.path.join(zed_folder, "tasks.json")

    # Only auto-generate if tasks.json doesn't exist
    if not os.path.exists(tasks_file):
        try:
            _generate_zed_tasks_internal(current_project_data)
            print(f" Auto-generated Zed tasks.json")
        except Exception as e:
            print(f" Warning: Could not auto-generate tasks: {e}")
    else:
        print(f" Using existing Zed tasks.json (not overwriting)")

    try:
        # Try 'zed' command (Zed CLI)
        subprocess.Popen(['zed', project_folder], shell=True)
        print(f" Opened Zed: {project_folder}")
    except Exception as e:
        messagebox.showerror("Error",
            f"Could not open Zed.\n\n"
            f"Make sure Zed is installed and 'zed' is in PATH.\n\n"
            f"Error: {str(e)}")


def callback_generate_zed_tasks(sender, app_data, current_project_data: ProjectData):
    """Generate Zed tasks.json with compile, build, and inject tasks"""
    try:
        _generate_zed_tasks_internal(current_project_data)
        
        current_build = current_project_data.GetCurrentBuildVersion()
        platform = current_build.GetPlatform()
        emulators = _get_platform_emulators(platform)
        
        # messagebox.showinfo("Success", 
        #     f"Zed tasks.json generated!\n\n"
        #     f"Platform: {platform}\n"
        #     f"Tasks Created:\n"
        #     f"  • Compile (interactive build selection)\n"
        #     f"  • Build ISO (interactive build selection)\n"
        #     f"  • Inject ({len(emulators)} emulator(s))\n"
        #     f"  • Clean\n\n"
        #     f"Use command palette to run tasks")
    except Exception as e:
        messagebox.showerror("Error", f"Could not generate tasks.json:\n\n{str(e)}")


def _generate_zed_tasks_internal(current_project_data: ProjectData):
    _generate_vscode_tasks_internal(current_project_data) # Same format
    


#! Changes the functions for when im testing VS built release
#TODO The most hacky thing you've ever seen in your entire life :)    
from functions.check_pyinstaller import *
test = None
if is_pyinstaller():
    _generate_vscode_tasks_internal = _generate_vscode_tasks_internal
    test = "Build"
else:
    from gui.gui_text_editors_script import _generate_vscode_tasks_internal_script, _generate_sublime_project_file_script, _generate_notepadpp_batch_files_script
    _generate_vscode_tasks_internal = _generate_vscode_tasks_internal_script
    _generate_sublime_project_file = _generate_vscode_tasks_internal_script
    _generate_notepadpp_batch_files = _generate_notepadpp_batch_files_script
    test = "Script"
    
    
print(test)