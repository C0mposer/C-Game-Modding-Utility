# gui/gui_startup_window.py - UPDATED VERSION

import dearpygui.dearpygui as dpg
from tkinter import filedialog
from gui import gui_messagebox as messagebox
import os

from gui.gui_project_wizard import show_project_wizard  # NEW: Import wizard
from gui.gui_prereq_prompt import check_and_prompt_prereqs
from dpg.widget_themes import *
from services.project_serializer import ProjectSerializer
from path_helper import get_application_directory


# Helper Functions (defined first so they can be called by InitMainWindow)
def _populate_recent_projects():
    """Populate recent projects list"""
    from services.recent_projects_service import RecentProjectsService

    # Clear existing
    if dpg.does_item_exist("recent_projects_group"):
        dpg.delete_item("recent_projects_group", children_only=True)

    recent_projects = RecentProjectsService.get_recent_projects()

    if not recent_projects:
        dpg.add_text("  (No recent projects)", color=(128, 128, 128), parent="recent_projects_group")
        return

    for project in recent_projects:
        with dpg.group(horizontal=True, parent="recent_projects_group"):
            # Platform badge
            platform_color = {
                'PS1': (255, 61, 225),
                'PS2': (150, 100, 255),
                'Gamecube': (100, 200, 255),
                'Wii': (53, 255, 97),
                'N64': (255, 150, 100)
            }.get(project.platform, (150, 150, 150))

            # Project name as clickable button
            dpg.add_button(
                label=project.name,
                callback=_load_recent_project,
                user_data=project.path,
                width=300
            )
            
            # Move the X because of GC being 1 less character than the rest 
            if (project.platform == "Gamecube"):
                dpg.add_text(f"[GC] ", color=platform_color)
            else:
                dpg.add_text(f"[{project.platform}]", color=platform_color)

            # # Show truncated path
            # truncated_path = project.path if len(project.path) < 50 else "..." + project.path[-47:]
            # dpg.add_text(truncated_path, color=(128, 128, 128))

            # Remove button
            dpg.add_button(
                label="X",
                callback=_remove_recent_project,
                user_data=project.path,
                width=30
            )


def _load_recent_project(t, a, project_path):
    """Load a recent project"""
    #print(f"Test f{project_path}")
    from gui.gui_main_project import InitMainProjectWindowWithData

    project_data = ProjectSerializer.load_project(project_path, show_loading=True)
    if project_data:
        # Check prerequisites for this project's platform
        tool_dir = get_application_directory()
        platform = project_data.GetCurrentBuildVersion().GetPlatform()

        if not check_and_prompt_prereqs(tool_dir, platform, None):
            # User cancelled download - don't open project
            return

        dpg.delete_item("startup_window")
        InitMainProjectWindowWithData(project_data)
    else:
        # If load failed, refresh the recent projects list (file might be gone)
        _populate_recent_projects()


def _remove_recent_project(sender, app_data, project_path):
    """Remove project from recent list"""
    from services.recent_projects_service import RecentProjectsService
    RecentProjectsService.remove_recent_project(project_path)
    _populate_recent_projects()  # Refresh display


def InitMainWindow():
    """Main startup window - now launches wizard instead of simple name input"""
    dpg.delete_item("startup_window")

    with dpg.window(label="startup_window", tag="startup_window", no_move=True, no_resize=True):
        dpg.add_text("C & C++ Game Modding Utility")
        dpg.add_separator()
        dpg.add_spacer(height=10)

        # NEW: Single button to launch wizard
        dpg.add_button(
            label="Create New Project",
            callback=create_new_project_callback,
            height=50,
            width=300
        )
        SetLastItemsTheme(my_widget_themes.GetMyThemes()[0])

        dpg.add_spacer(height=5)
        dpg.add_text("  Step-by-step guided setup", color=(150, 150, 150))

        dpg.add_separator()
        dpg.add_spacer(height=10)

        dpg.add_button(
            label="Load Existing Project",
            height=50,
            width=300,
            callback=load_project_callback
        )
        SetLastItemsTheme("big_button_theme")

        dpg.add_separator()
        dpg.add_spacer(height=10)

        # Recent projects section
        dpg.add_text("Recent Projects:")
        with dpg.group(tag="recent_projects_group"):
            _populate_recent_projects()


# Callbacks
def create_new_project_callback():
    """NEW: Launch the project wizard instead of simple name input"""
    show_project_wizard()  # Launch the new wizard!

def load_project_callback():
    """Load an existing project from a .modproj file"""
    file_path = filedialog.askopenfilename(
        title="Load Project",
        filetypes=[("Mod Project Files", "*.modproj"), ("All Files", "*.*")],
        initialdir="projects"
    )

    if not file_path:
        return  # User cancelled

    # Load the project with loading indicator (handled internally)
    project_data = ProjectSerializer.load_project(file_path, show_loading=True)

    if project_data is None:
        messagebox.showerror("Load Failed", "Failed to load project file. The file may be corrupted.")
        return

    # Check prerequisites for this project's platform
    tool_dir = get_application_directory()
    platform = project_data.GetCurrentBuildVersion().GetPlatform()

    if not check_and_prompt_prereqs(tool_dir, platform, None):
        # User cancelled download - don't open project
        return

    # Import here to avoid circular imports
    from gui.gui_main_project import InitMainProjectWindowWithData

    # Open the project in the main window
    dpg.delete_item("startup_window")
    InitMainProjectWindowWithData(project_data)
