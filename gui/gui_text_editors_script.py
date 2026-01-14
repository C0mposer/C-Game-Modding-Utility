# gui/gui_text_editors.py

import os
import subprocess
import json
from classes.project_data.project_data import ProjectData


def _generate_vscode_tasks_internal_script(current_project_data: ProjectData):
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
    
    # Get absolute path to CLI.py
    modtool_path = os.path.abspath(os.path.join(tool_dir, "CLI.py"))
    
    # Verify CLI.py exists
    if not os.path.exists(modtool_path):
        raise FileNotFoundError(f"CLI.py not found at: {modtool_path}")
    
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
        "command": "python",
        "args": [
            modtool_path,
            "compile",
            project_name
        ],
        "options": {
            "cwd": tool_dir
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
        "command": "python",
        "args": [
            modtool_path,
            "build",
            project_name
        ],
        "options": {
            "cwd": tool_dir
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
            "command": "python",
            "args": [
                modtool_path,
                "inject",
                project_name,
                emulator
            ],
            "options": {
                "cwd": tool_dir
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
        "command": "python",
        "args": [
            modtool_path,
            "clean",
            project_name
        ],
        "options": {
            "cwd": tool_dir
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



def _generate_sublime_project_file_script(current_project_data: ProjectData):
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
    tool_dir = os.path.abspath(os.path.dirname(os.path.dirname(project_folder)))
    
    # Get absolute path to CLI.py
    modtool_path = os.path.abspath(os.path.join(tool_dir, "CLI.py"))
    
    if not os.path.exists(modtool_path):
        raise FileNotFoundError(f"CLI.py not found at: {modtool_path}")
    
    # Get emulators for platform
    emulators = _get_platform_emulators(platform)
    
    # Build Sublime project structure
    sublime_project = {
        "folders": [
            {
                "path": "..",
                "folder_exclude_patterns": [".notepad++", ".vscode", ".sublime", ".config/output"],
                "file_exclude_patterns": ["*.sublime-project", "*.sublime-workspace"]
            }
        ],
        "build_systems": []
    }
    
    # Add Compile build system
    sublime_project["build_systems"].append({
        "name": "Compile Mod",
        "working_dir": tool_dir,
        "shell_cmd": f'chcp 65001 >nul && python "{modtool_path}" --no-color compile "{project_name}"',
        "file_regex": r"^(.+):([0-9]+):([0-9]+): (.*)$",
        "encoding": "utf-8",
        "variants": [
            {
                "name": "Compile (Verbose)",
                "shell_cmd": f'chcp 65001 >nul && python "{modtool_path}" --no-color --verbose compile "{project_name}"'
            }
        ]
    })
    
    # Add Build ISO build system
    sublime_project["build_systems"].append({
        "name": "Build ISO",
        "working_dir": tool_dir,
        "shell_cmd": f'chcp 65001 >nul && python "{modtool_path}" --no-color build "{project_name}"',
        "encoding": "utf-8",
        "variants": [
            {
                "name": "Build ISO (Verbose)",
                "shell_cmd": f'chcp 65001 >nul && python "{modtool_path}" --no-color --verbose build "{project_name}"'
            }
        ]
    })
    
    # Add Inject build systems (one per emulator)
    for emulator in emulators:
        sublime_project["build_systems"].append({
            "name": f"Inject into {emulator}",
            "working_dir": tool_dir,
            "shell_cmd": f'chcp 65001 >nul && python "{modtool_path}" --no-color inject "{project_name}" "{emulator}"',
            "encoding": "utf-8"
        })
    
    # Add Clean build system
    sublime_project["build_systems"].append({
        "name": "Clean Build",
        "working_dir": tool_dir,
        "shell_cmd": f'chcp 65001 >nul && python "{modtool_path}" --no-color clean "{project_name}"',
        "encoding": "utf-8"
    })
    
    # Add Info build system
    sublime_project["build_systems"].append({
        "name": "Project Info",
        "working_dir": tool_dir,
        "shell_cmd": f'chcp 65001 >nul && python "{modtool_path}" --no-color info "{project_name}"',
        "encoding": "utf-8"
    })
    
    # Write project file to .sublime folder
    project_file_path = os.path.join(sublime_folder, f"{project_name}.sublime-project")
    with open(project_file_path, 'w') as f:
        json.dump(sublime_project, f, indent=4)
    
    print(f" Generated Sublime project file")

def _generate_notepadpp_batch_files_script(current_project_data: ProjectData):
    project_folder = current_project_data.GetProjectFolder()
    project_name = current_project_data.GetProjectName()
    current_build = current_project_data.GetCurrentBuildVersion()
    platform = current_build.GetPlatform()
    
    if not project_folder or not os.path.exists(project_folder):
        raise ValueError("Project folder not found")
    
    # Get tool directory
    tool_dir = os.path.abspath(os.path.dirname(os.path.dirname(project_folder)))
    
    # Get absolute path to CLI.py
    modtool_path = os.path.abspath(os.path.join(tool_dir, "CLI.py"))
    
    if not os.path.exists(modtool_path):
        raise FileNotFoundError(f"CLI.py not found at: {modtool_path}")
    
    # Create batch files directory
    batch_dir = os.path.join(project_folder, ".notepad++")
    os.makedirs(batch_dir, exist_ok=True)
    
    # Get emulators for platform
    emulators = _get_platform_emulators(platform)
    
    # Compile batch file
    compile_bat = os.path.join(batch_dir, "compile.bat")
    with open(compile_bat, 'w') as f:
        f.write(f'@echo off\n')
        f.write(f'cd /d "{tool_dir}"\n')
        f.write(f'py "{modtool_path}" --no-color compile "{project_name}"\n')
        f.write(f'pause\n')
    
    # Compile verbose batch file
    compile_verbose_bat = os.path.join(batch_dir, "compile_verbose.bat")
    with open(compile_verbose_bat, 'w') as f:
        f.write(f'@echo off\n')
        f.write(f'cd /d "{tool_dir}"\n')
        f.write(f'py "{modtool_path}" --no-color --verbose compile "{project_name}"\n')
        f.write(f'pause\n')
    
    # Build ISO batch file
    build_bat = os.path.join(batch_dir, "build_iso.bat")
    with open(build_bat, 'w') as f:
        f.write(f'@echo off\n')
        f.write(f'cd /d "{tool_dir}"\n')
        f.write(f'py "{modtool_path}" --no-color build "{project_name}"\n')
        f.write(f'pause\n')
    
    # Build ISO batch file
    build_verbose_bat = os.path.join(batch_dir, "build_iso_verbose.bat")
    with open(build_verbose_bat, 'w') as f:
        f.write(f'@echo off\n')
        f.write(f'cd /d "{tool_dir}"\n')
        f.write(f'py "{modtool_path}" --no-color --verbose build "{project_name}"\n')
        f.write(f'pause\n')
    
    # Inject batch files
    for emulator in emulators:
        # Emulator name for filename
        safe_name = emulator.replace(' ', '_').replace('.', '_').lower()
        inject_bat = os.path.join(batch_dir, f"inject_{safe_name}.bat")
        
        with open(inject_bat, 'w') as f:
            f.write(f'@echo off\n')
            f.write(f'cd /d "{tool_dir}"\n')
            f.write(f'py "{modtool_path}" --no-color inject "{project_name}" "{emulator}"\n')
            f.write(f'pause\n')
    
    # Clean batch file
    clean_bat = os.path.join(batch_dir, "clean.bat")
    with open(clean_bat, 'w') as f:
        f.write(f'@echo off\n')
        f.write(f'cd /d "{tool_dir}"\n')
        f.write(f'py "{modtool_path}" --no-color clean "{project_name}"\n')
        f.write(f'pause\n')
    
    # Project info batch file
    info_bat = os.path.join(batch_dir, "project_info.bat")
    with open(info_bat, 'w') as f:
        f.write(f'@echo off\n')
        f.write(f'cd /d "{tool_dir}"\n')
        f.write(f'py "{modtool_path}" --no-color info "{project_name}"\n')
        f.write(f'pause\n')



def _get_platform_emulators(platform: str) -> list:
    emulator_map = {
        "PS1": ["DuckStation", "PCSX-Redux", "BizHawk", "Mednafen 1.29", "Mednafen 1.31"],
        "PS2": ["PCSX2"],
        "Gamecube": ["Dolphin"],
        "Wii": ["Dolphin"],
        "N64": ["Project64"]
    }
    
    return emulator_map.get(platform, [])