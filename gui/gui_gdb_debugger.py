# gui/gui_gdb_debugger.py

import dearpygui.dearpygui as dpg
import os
from typing import Optional
from classes.project_data.project_data import ProjectData
from services.gdb_service import GDBService, GDBConnectionInfo

class GDBDebuggerState:
    """Holds the state of the GDB debugger connection"""
    def __init__(self):
        self.service: Optional[GDBService] = None
        self.is_connected = False
        self.current_emulator = ""
        self.current_host = "localhost"
        self.current_port = 3333

_debugger_state = GDBDebuggerState()

def show_gdb_debugger_window(sender, app_data, project_data: ProjectData):
    """Show the GDB debugger connection window"""
    global _debugger_state
    
    WINDOW_TAG = "gdb_debugger_window"
    
    if dpg.does_item_exist(WINDOW_TAG):
        dpg.show_item(WINDOW_TAG)
        return
    
    # Initialize service
    _debugger_state.service = GDBService(project_data)
    
    with dpg.window(
        label="GDB Debugger",
        tag=WINDOW_TAG,
        width=700,
        height=600,
        on_close=lambda: _on_window_close()
    ):
        # Header
        dpg.add_text("🛠 GDB Server Connection", color=(100, 150, 255))
        dpg.add_text("Connect to emulator GDB servers for debugging", 
                    color=(150, 150, 150))
        dpg.add_separator()
        dpg.add_spacer(height=10)
        
        # Connection Status
        with dpg.group(horizontal=True):
            dpg.add_text("Status:", color=(150, 150, 150))
            dpg.add_text("Not connected", 
                        tag=f"{WINDOW_TAG}_status",
                        color=(200, 100, 100))
        
        dpg.add_spacer(height=10)
        dpg.add_separator()
        dpg.add_spacer(height=10)
        
        # Connection Settings
        dpg.add_text("Connection Settings", color=(100, 150, 255))
        dpg.add_spacer(height=5)
        
        # Emulator Selection
        with dpg.group(horizontal=True):
            dpg.add_text("Emulator:")
            
            platform = project_data.GetCurrentBuildVersion().GetPlatform()
            emulators = _get_emulators_for_platform(platform)
            
            if not emulators:
                dpg.add_text("No GDB-compatible emulators for this platform", 
                           color=(200, 100, 100))
            else:
                dpg.add_combo(
                    items=emulators,
                    tag=f"{WINDOW_TAG}_emulator_combo",
                    default_value=emulators[0],
                    width=200,
                    callback=lambda s, d: _on_emulator_changed(d, project_data)
                )
                
                # Info button
                dpg.add_button(
                    label="ℹ️ Setup",
                    callback=lambda: _show_emulator_instructions(
                        dpg.get_value(f"{WINDOW_TAG}_emulator_combo")
                    )
                )
        
        dpg.add_spacer(height=5)
        
        # Host
        with dpg.group(horizontal=True):
            dpg.add_text("Host:")
            dpg.add_input_text(
                tag=f"{WINDOW_TAG}_host_input",
                default_value="localhost",
                width=200
            )
        
        dpg.add_spacer(height=5)
        
        # Port
        with dpg.group(horizontal=True):
            dpg.add_text("Port:")
            dpg.add_input_text(
                tag=f"{WINDOW_TAG}_port_input",
                default_value="3333",
                width=200,
                decimal=True
            )
            dpg.add_button(
                label="Test Connection",
                callback=lambda: _test_connection(project_data)
            )
        
        dpg.add_spacer(height=10)
        
        # Connection Buttons
        with dpg.group(horizontal=True):
            dpg.add_button(
                label="Connect",
                tag=f"{WINDOW_TAG}_connect_button",
                callback=lambda: _connect_to_gdb(project_data),
                width=150
            )
            dpg.add_button(
                label="Disconnect",
                tag=f"{WINDOW_TAG}_disconnect_button",
                callback=lambda: _disconnect_from_gdb(),
                width=150,
                enabled=False
            )
        
        dpg.add_spacer(height=10)
        dpg.add_separator()
        dpg.add_spacer(height=10)
        
        # VSCode Integration
        dpg.add_text("VSCode Debugging", color=(100, 150, 255))
        dpg.add_spacer(height=5)
        
        dpg.add_text("Generate VSCode configuration for debugging:", 
                    color=(150, 150, 150))
        dpg.add_spacer(height=5)
        
        with dpg.group(horizontal=True):
            dpg.add_button(
                label="📝 Generate launch.json",
                callback=lambda: _generate_vscode_config(project_data),
                width=200
            )
            dpg.add_text("Creates .vscode/launch.json", 
                        color=(150, 150, 150))
        
        dpg.add_spacer(height=10)
        dpg.add_separator()
        dpg.add_spacer(height=10)
        
        # Command-Line GDB
        dpg.add_text("Command-Line GDB", color=(100, 150, 255))
        dpg.add_spacer(height=5)
        
        dpg.add_text("Generate .gdbinit for command-line debugging:", 
                    color=(150, 150, 150))
        dpg.add_spacer(height=5)
        
        with dpg.group(horizontal=True):
            dpg.add_button(
                label="📝 Generate .gdbinit",
                callback=lambda: _generate_gdbinit(project_data),
                width=200
            )
            dpg.add_button(
                label="🚀 Launch GDB CLI",
                callback=lambda: _launch_gdb_cli(project_data),
                width=200
            )
        
        dpg.add_spacer(height=10)
        dpg.add_separator()
        dpg.add_spacer(height=10)
        
        # Instructions
        with dpg.child_window(tag=f"{WINDOW_TAG}_instructions", height=200):
            dpg.add_text("Getting Started:", color=(100, 150, 255))
            dpg.add_spacer(height=5)
            
            dpg.add_text("1. Enable GDB server in your emulator (click 'Setup' button)")
            dpg.add_text("2. Start your game in the emulator")
            dpg.add_text("3. Test the connection to verify GDB server is running")
            dpg.add_text("4. Click 'Connect' to establish connection")
            dpg.add_text("5. Generate VSCode config or .gdbinit file")
            dpg.add_text("6. Set breakpoints in VSCode and start debugging!")
            
            dpg.add_spacer(height=10)
            
            dpg.add_text("Debugging Tips:", color=(100, 150, 255))
            dpg.add_spacer(height=5)
            
            dpg.add_text("• Compile your mod first to generate symbols")
            dpg.add_text("• Use VSCode's debug panel to set breakpoints")
            dpg.add_text("• Memory addresses match your codecave/hook addresses")
            dpg.add_text("• Check emulator console for GDB server status")

def _get_emulators_for_platform(platform: str) -> list:
    """Get list of GDB-compatible emulators for the platform"""
    emulator_map = {
        "PS1": ["DuckStation", "PCSX-Redux"],
        "Gamecube": ["Dolphin"],
        "Wii": ["Dolphin"],
        "N64": ["Project64"]
    }
    return emulator_map.get(platform, [])

def _on_emulator_changed(emulator_name: str, project_data: ProjectData):
    """Update port when emulator changes"""
    global _debugger_state
    
    WINDOW_TAG = "gdb_debugger_window"
    
    if _debugger_state.service:
        default_port = _debugger_state.service.get_default_port(emulator_name)
        dpg.set_value(f"{WINDOW_TAG}_port_input", str(default_port))

def _test_connection(project_data: ProjectData):
    """Test if GDB server is reachable"""
    global _debugger_state
    
    WINDOW_TAG = "gdb_debugger_window"
    
    host = dpg.get_value(f"{WINDOW_TAG}_host_input")
    port_str = dpg.get_value(f"{WINDOW_TAG}_port_input")
    
    try:
        port = int(port_str)
    except ValueError:
        _show_message("Invalid Port", "Port must be a number")
        return
    
    if not _debugger_state.service:
        _debugger_state.service = GDBService(project_data)
    
    result = _debugger_state.service.test_connection(host, port)
    
    if result.success:
        _show_message("Connection Test", f"{result.message}")
    else:
        _show_message("Connection Test", f"{result.message}")

def _connect_to_gdb(project_data: ProjectData):
    """Connect to GDB server"""
    global _debugger_state
    
    WINDOW_TAG = "gdb_debugger_window"
    
    emulator = dpg.get_value(f"{WINDOW_TAG}_emulator_combo")
    host = dpg.get_value(f"{WINDOW_TAG}_host_input")
    port_str = dpg.get_value(f"{WINDOW_TAG}_port_input")
    
    try:
        port = int(port_str)
    except ValueError:
        _show_message("Invalid Port", "Port must be a number")
        return
    
    if not _debugger_state.service:
        _debugger_state.service = GDBService(project_data)
    
    result = _debugger_state.service.connect(emulator, host, port)
    
    if result.success:
        _debugger_state.is_connected = True
        _debugger_state.current_emulator = emulator
        _debugger_state.current_host = host
        _debugger_state.current_port = port
        
        # Update UI
        dpg.set_value(f"{WINDOW_TAG}_status", f"Connected to {emulator}")
        dpg.configure_item(f"{WINDOW_TAG}_status", color=(100, 200, 100))
        dpg.configure_item(f"{WINDOW_TAG}_connect_button", enabled=False)
        dpg.configure_item(f"{WINDOW_TAG}_disconnect_button", enabled=True)
        
        _show_message("Connected", f"{result.message}\n\nYou can now generate VSCode config or .gdbinit")
    else:
        _show_message("Connection Failed", f"{result.message}")

def _disconnect_from_gdb():
    """Disconnect from GDB server"""
    global _debugger_state
    
    WINDOW_TAG = "gdb_debugger_window"
    
    if not _debugger_state.service:
        return
    
    result = _debugger_state.service.disconnect()
    
    _debugger_state.is_connected = False
    _debugger_state.current_emulator = ""
    
    # Update UI
    dpg.set_value(f"{WINDOW_TAG}_status", "Not connected")
    dpg.configure_item(f"{WINDOW_TAG}_status", color=(200, 100, 100))
    dpg.configure_item(f"{WINDOW_TAG}_connect_button", enabled=True)
    dpg.configure_item(f"{WINDOW_TAG}_disconnect_button", enabled=False)
    
    if result.success:
        _show_message("Disconnected", f"{result.message}")

def _generate_vscode_config(project_data: ProjectData):
    """Generate VSCode launch.json"""
    global _debugger_state
    
    if not _debugger_state.service:
        _debugger_state.service = GDBService(project_data)
    
    if not _debugger_state.is_connected:
        _show_message("Not Connected", "Please connect to GDB server first")
        return
    
    config = _debugger_state.service.generate_vscode_launch_config()
    
    if not config:
        _show_message("Error", "Could not generate configuration")
        return
    
    # Write to .vscode/launch.json
    import json
    
    project_folder = project_data.GetProjectFolder()
    vscode_dir = os.path.join(project_folder, ".vscode")
    os.makedirs(vscode_dir, exist_ok=True)
    
    launch_json_path = os.path.join(vscode_dir, "launch.json")
    
    try:
        with open(launch_json_path, 'w') as f:
            json.dump(config, f, indent=4)
        
        _show_message("Success", 
            f"VSCode launch.json created!\n\n"
            f"Location: .vscode/launch.json\n\n"
            f"To debug:\n"
            f"1. Open project in VSCode\n"
            f"2. Go to Run & Debug (Ctrl+Shift+D)\n"
            f"3. Select '{config['configurations'][0]['name']}'\n"
            f"4. Set breakpoints in your code\n"
            f"5. Press F5 to start debugging")
    
    except Exception as e:
        _show_message("Error", f"Failed to write launch.json:\n{str(e)}")

def _generate_gdbinit(project_data: ProjectData):
    """Generate .gdbinit file"""
    global _debugger_state
    
    if not _debugger_state.service:
        _debugger_state.service = GDBService(project_data)
    
    if not _debugger_state.is_connected:
        _show_message("Not Connected", "Please connect to GDB server first")
        return
    
    result = _debugger_state.service.generate_gdbinit()
    
    if result.success:
        _show_message("Success",
            f"{result.message}\n\n"
            f"To debug:\n"
            f"1. Open terminal in project folder\n"
            f"2. Run: gdb-multiarch\n"
            f"3. GDB will auto-connect using .gdbinit\n"
            f"4. Set breakpoints: break ModMain\n"
            f"5. Continue: continue")
    else:
        _show_message("Error", f"Failed to generate .gdbinit:\n{result.message}")

def _launch_gdb_cli(project_data: ProjectData):
    """Launch command-line GDB"""
    global _debugger_state
    
    if not _debugger_state.service:
        _debugger_state.service = GDBService(project_data)
    
    if not _debugger_state.is_connected:
        _show_message("Not Connected", "Please connect to GDB server first")
        return
    
    result = _debugger_state.service.launch_gdb_cli()
    
    if result.success:
        _show_message("GDB Launched", 
            f"{result.message}\n\n"
            f"GDB CLI opened in new window.\n"
            f"Commands are loaded from .gdbinit")
    else:
        _show_message("Error", f"Failed to launch GDB:\n{result.message}")

def _show_emulator_instructions(emulator_name: str):
    """Show setup instructions for the emulator"""
    from tkinter import messagebox
    
    if not _debugger_state.service:
        return
    
    instructions = _debugger_state.service.get_emulator_instructions(emulator_name)
    messagebox.showinfo(f"Setup {emulator_name}", instructions)

def _show_message(title: str, message: str):
    """Show a message dialog"""
    from tkinter import messagebox
    messagebox.showinfo(title, message)

def _on_window_close():
    """Clean up when window closes"""
    global _debugger_state
    
    if _debugger_state.is_connected and _debugger_state.service:
        _debugger_state.service.disconnect()
    
    _debugger_state.is_connected = False