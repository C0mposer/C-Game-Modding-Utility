# services/gdb_service.py

import socket
import subprocess
import os
import time
from typing import Optional, Dict, List, Tuple
from classes.project_data.project_data import ProjectData

class GDBConnectionInfo:
    """Information about a GDB server connection"""
    def __init__(self, emulator: str, host: str, port: int, platform: str):
        self.emulator = emulator
        self.host = host
        self.port = port
        self.platform = platform
        self.is_connected = False

class GDBResult:
    """Result of a GDB operation"""
    def __init__(self, success: bool, message: str = ""):
        self.success = success
        self.message = message

class GDBService:
    """Handles GDB server connections for debugging mods"""
    
    # Default GDB ports for each emulator
    DEFAULT_PORTS = {
        "DuckStation": 3333,
        "PCSX-Redux": 3333,
        "Dolphin": 5555,
        "Project64": 6666,
    }
    
    # GDB architectures for each platform
    ARCHITECTURES = {
        "PS1": "mips:3000",
        "PS2": "mips:5900",
        "Gamecube": "powerpc:750",
        "Wii": "powerpc:broadway",
        "N64": "mips:4000"
    }
    
    def __init__(self, project_data: ProjectData):
        self.project_data = project_data
        self.current_connection: Optional[GDBConnectionInfo] = None
        self.gdb_process: Optional[subprocess.Popen] = None
    
    def get_default_port(self, emulator: str) -> int:
        """Get the default GDB port for an emulator"""
        return self.DEFAULT_PORTS.get(emulator, 3333)
    
    def test_connection(self, host: str, port: int) -> GDBResult:
        """Test if a GDB server is reachable"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)
            result = sock.connect_ex((host, port))
            sock.close()
            
            if result == 0:
                return GDBResult(True, f"GDB server found at {host}:{port}")
            else:
                return GDBResult(False, f"No GDB server at {host}:{port}")
        except Exception as e:
            return GDBResult(False, f"Connection error: {str(e)}")
    
    def connect(self, emulator: str, host: str, port: int) -> GDBResult:
        """Connect to a GDB server"""
        try:
            # Test connection first
            test_result = self.test_connection(host, port)
            if not test_result.success:
                return test_result
            
            # Store connection info
            platform = self.project_data.GetCurrentBuildVersion().GetPlatform()
            self.current_connection = GDBConnectionInfo(emulator, host, port, platform)
            self.current_connection.is_connected = True
            
            print(f"Connected to {emulator} GDB server at {host}:{port}")
            return GDBResult(True, f"Connected to {emulator}")
            
        except Exception as e:
            return GDBResult(False, f"Connection failed: {str(e)}")
    
    def disconnect(self) -> GDBResult:
        """Disconnect from current GDB server"""
        if not self.current_connection:
            return GDBResult(False, "Not connected")
        
        try:
            if self.gdb_process:
                self.gdb_process.terminate()
                self.gdb_process = None
            
            emulator = self.current_connection.emulator
            self.current_connection = None
            
            return GDBResult(True, f"Disconnected from {emulator}")
        except Exception as e:
            return GDBResult(False, f"Disconnect error: {str(e)}")
    
    def get_connection_status(self) -> Tuple[bool, str]:
        """Get current connection status"""
        if not self.current_connection:
            return False, "Not connected"
        
        # Test if still connected
        test = self.test_connection(
            self.current_connection.host,
            self.current_connection.port
        )
        
        if not test.success:
            self.current_connection = None
            return False, "Connection lost"
        
        return True, f"Connected to {self.current_connection.emulator}"
    
    def generate_vscode_launch_config(self) -> Optional[Dict]:
        """
        Generate VSCode launch.json configuration for debugging.
        Returns a dict that can be written to .vscode/launch.json
        """
        if not self.current_connection:
            return None
        
        platform = self.current_connection.platform
        project_folder = self.project_data.GetProjectFolder()
        
        # Get symbol file path
        symbol_file = "${workspaceFolder}/.config/output/object_files/MyMod.elf"
        
        # Get architecture
        arch = self.ARCHITECTURES.get(platform, "mips:3000")
        
        # Get gdb-multiarch path
        gdb_path = self._get_gdb_path()
        
        config = {
            "version": "0.2.0",
            "configurations": [
                {
                    "name": f"Debug {platform} Mod ({self.current_connection.emulator})",
                    "type": "cppdbg",
                    "request": "launch",
                    "program": symbol_file,
                    "args": [],
                    "stopAtEntry": True,
                    "cwd": "${workspaceFolder}",
                    "environment": [],
                    "externalConsole": False,
                    "MIMode": "gdb",
                    "miDebuggerPath": gdb_path,
                    "miDebuggerServerAddress": f"{self.current_connection.host}:{self.current_connection.port}",
                    "setupCommands": [
                        {
                            "text": f"set architecture {arch}"
                        },
                        {
                            "text": "set remote Z-packet on"
                        },
                        {
                            "text": "set breakpoint auto-hw off"
                        },
                        {
                            "text": "set breakpoint always-inserted on"
                        },
                        {
                            "text": "set pagination off"
                        },
                        {
                            "text": "set complaints 0"
                        }
                    ],
                    "logging": {
                        "engineLogging": True,
                        "trace": True,
                        "traceResponse": True
                    }
                }
            ]
        }
        
        return config
    
    def _get_gdb_path(self) -> str:
        """Get the gdb-multiarch executable path"""
        tool_dir = os.getcwd()
        gdb_path = os.path.join(tool_dir, "prereq", "gdb", "gdb-multiarch.exe")
        return gdb_path
    
    def _get_symbol_file_path(self) -> str:
        """Get the path to the compiled ELF with symbols"""
        project_folder = self.project_data.GetProjectFolder()
        return os.path.join(project_folder, ".config", "output", "object_files", "MyMod.elf")
    
    def generate_gdbinit(self) -> GDBResult:
        """
        Generate a .gdbinit file for command-line GDB debugging.
        This file contains initialization commands for GDB.
        """
        if not self.current_connection:
            return GDBResult(False, "Not connected to GDB server")
        
        try:
            project_folder = self.project_data.GetProjectFolder()
            gdbinit_path = os.path.join(project_folder, ".gdbinit")
            
            platform = self.current_connection.platform
            arch = self.ARCHITECTURES.get(platform, "mips:3000")
            symbol_file = self._get_symbol_file_path()
            
            # Normalize path for GDB (use forward slashes)
            symbol_file = symbol_file.replace('\\', '/')
            
            with open(gdbinit_path, 'w') as f:
                f.write(f"# .gdbinit for {self.current_connection.emulator} remote debugging\n\n")
                f.write(f"# Suppress pagination\n")
                f.write(f"set pagination off\n")
                f.write(f"set confirm off\n\n")
                f.write(f"# Set architecture for {platform}\n")
                f.write(f"set architecture {arch}\n\n")
                f.write(f"# Enable remote breakpoint packets (critical for emulator GDB servers)\n")
                f.write(f"set remote Z-packet on\n")
                f.write(f"set breakpoint auto-hw off\n")
                f.write(f"set breakpoint always-inserted on\n\n")
                f.write(f"# Suppress the Windows ABI warning\n")
                f.write(f"set complaints 0\n\n")
                f.write(f"# Optional: Enable debug output (comment out if too verbose)\n")
                f.write(f"# set debug remote 1\n\n")
                f.write(f"# Load symbols from your mod\n")
                f.write(f"file {symbol_file}\n\n")
                f.write(f"# Connect to {self.current_connection.emulator} GDB server\n")
                f.write(f"target remote {self.current_connection.host}:{self.current_connection.port}\n\n")
                f.write(f"# Optional: Set some initial breakpoints\n")
                f.write(f"# break ModMain\n")
                f.write(f"# break main\n\n")
                f.write(f"echo \\n=== Connected to {self.current_connection.emulator} ===\\n\n")
                f.write(f"echo GDB is ready. Use 'break', 'continue', 'step', etc.\\n\\n\n")
            
            print(f"Generated .gdbinit: {gdbinit_path}")
            return GDBResult(True, f".gdbinit created at project root")
            
        except Exception as e:
            return GDBResult(False, f"Failed to create .gdbinit: {str(e)}")
    
    def get_emulator_instructions(self, emulator: str) -> str:
        """Get platform-specific instructions for enabling GDB server"""
        instructions = {
            "DuckStation": (
                "To enable GDB server in DuckStation:\n\n"
                "1. Settings → Advanced\n"
                "2. Enable 'Debug Device'\n"
                "3. Set Debug Port to 3333\n"
                "4. Restart DuckStation\n"
                "5. Load your game\n\n"
                "GDB will be available at localhost:3333"
            ),
            "PCSX-Redux": (
                "PCSX-Redux has GDB server built-in:\n\n"
                "1. Configuration -> Emulation -> Enable GDB Server\n"
                "2. Default port is 3333\n\n"
                "3. Install C/C++ VSCode Extension"
                "GDB will be available at localhost:3333"
            ),
            "Dolphin": (
                "To enable GDB server in Dolphin:\n\n"
                "1. Config → Interface\n"
                "2. Enable 'Show Debugging UI'\n"
                "3. Restart Dolphin\n"
                "4. View → Debugger\n"
                "5. Code tab → Start debugging (F5)\n\n"
                "GDB will be available at localhost:5555"
            ),
            "Project64": (
                "Project64 GDB support:\n\n"
                "1. Enable GDB stub in settings\n"
                "2. Default port is 6666\n\n"
                "Note: GDB support may vary by Project64 version"
            )
        }
        
        return instructions.get(emulator, "GDB instructions not available for this emulator.")
    
    def launch_gdb_cli(self) -> GDBResult:
        """
        Launch command-line GDB connected to the server.
        Uses gdb-multiarch for all platforms.
        """
        if not self.current_connection:
            return GDBResult(False, "Not connected to GDB server")
        
        try:
            gdb_path = self._get_gdb_path()
            
            if not os.path.exists(gdb_path):
                return GDBResult(False, f"GDB not found: {gdb_path}")
            
            project_folder = self.project_data.GetProjectFolder()
            
            # Generate .gdbinit first
            self.generate_gdbinit()
            
            # Launch GDB
            self.gdb_process = subprocess.Popen(
                [gdb_path],
                cwd=project_folder,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            
            print(f"Launched GDB CLI: {gdb_path}")
            return GDBResult(True, "GDB CLI launched in new window")
            
        except Exception as e:
            return GDBResult(False, f"Failed to launch GDB: {str(e)}")