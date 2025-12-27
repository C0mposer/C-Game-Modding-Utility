import dearpygui.dearpygui as dpg
from typing import Optional
from classes.project_data.project_data import ProjectData
from services.memory_watch_service import MemoryWatchService, WatchEntry, DataType
from services.symbol_map_parser_service import SymbolParserService
from services.emulator_service import EmulatorService
from services.emulator_connection_manager import get_emulator_manager
from functions.verbose_print import verbose_print
import os
import threading

# Add this to gui_memory_watch.py at the module level

# Global memory watch service instance
_global_memory_watch_service = None

def get_memory_watch_service():
    return _global_memory_watch_service

def set_memory_watch_service(service):
    global _global_memory_watch_service
    _global_memory_watch_service = service

# Store reference to current window instance (if any)
_memory_watch_window_instance = None

# Module-level callback for emulator scans (called even when window isn't open)
def _on_emulators_scanned_module_callback(available: list):
    """Update Memory Watch UI when emulators are scanned from other windows"""
    verbose_print(f"[MemoryWatch Module] _on_emulators_scanned called with: {available}")

    # Update instance state if it exists
    if _memory_watch_window_instance:
        _memory_watch_window_instance.available_emulators = available
        # Ensure emu_service is set (needed for connection)
        if not _memory_watch_window_instance.emu_service:
            _memory_watch_window_instance.emu_service = EmulatorService(_memory_watch_window_instance.project_data)

    def update_ui():
        if dpg.does_item_exist("emulator_combo"):
            if available:
                dpg.configure_item("emulator_combo", items=available)
                if dpg.get_value("emulator_combo") in ["Scan for emulators...", "No emulators found"]:
                    dpg.set_value("emulator_combo", available[0])
                dpg.configure_item("connect_button", enabled=True)
            else:
                dpg.configure_item("emulator_combo", items=["No emulators found"])
                dpg.set_value("emulator_combo", "No emulators found")
                dpg.configure_item("connect_button", enabled=False)

    # Schedule on main thread
    try:
        dpg.split_frame()
        update_ui()
    except:
        update_ui()

def register_memory_watch_callback(manager):
    """Register the module-level callback with the manager"""
    manager.register_scan_callback(_on_emulators_scanned_module_callback)

class MemoryWatchWindow:
    """Memory Watch window for real-time RAM monitoring"""
    
    def __init__(self, project_data: ProjectData):
        global _memory_watch_window_instance

        self.project_data = project_data
        self.watch_service = MemoryWatchService()
        self.symbol_parser: Optional[SymbolParserService] = None
        self.window_tag = "memory_watch_window"
        self.is_watching = False

        # UI state
        self.manual_watches: list = []  # List of (entry, row_tags)
        self.symbol_watches: list = []  # List of (symbol, entry, row_tags)
        self.all_symbols: list = []  # Store all symbols for filtering
        self.current_filter: str = "all"  # Current filter: "all", "game", or "mod"

        # Loading modals
        self.loading_modal_tag = "memory_watch_loading_modal"
        self.scanning_modal_tag = "memory_watch_scanning_modal"

        # Available emulators
        self.available_emulators = []
        self.emu_service = None

        # Initialize centralized manager
        self.manager = get_emulator_manager()
        self.manager.set_project_data(project_data)

        # Store instance reference for module-level callback
        _memory_watch_window_instance = self

        # Module-level callback is already registered at project init
        # Also register instance callback for additional updates
        self.manager.register_scan_callback(self._on_emulators_scanned)

        # Create window
        self._create_window()

        # Set up callbacks
        self.watch_service.on_update = self._on_watch_update
        self.watch_service.on_error = self._on_watch_error

        # Check if there's an existing connection to restore
        self._restore_connection_state()
    
    def _create_window(self):
        """Create the memory watch window"""
        if dpg.does_item_exist(self.window_tag):
            dpg.show_item(self.window_tag)
            return
        
        if not dpg.does_item_exist("rgb_edit_theme"):
            with dpg.theme(tag="rgb_edit_theme"):
                with dpg.theme_component(dpg.mvButton):
                    dpg.add_theme_color(dpg.mvThemeCol_Button, (255, 20, 50, 255))
                    dpg.add_theme_color(dpg.mvThemeCol_ButtonHovered, (150, 10, 30, 255))
                    dpg.add_theme_color(dpg.mvThemeCol_ButtonActive, (110, 5, 10 , 255))
        
        
        window_width = 1000
        window_height = 706
        viewport_width = 1024
        viewport_height = 768
        pos_x = (viewport_width - window_width) // 2 - 8
        pos_y = (viewport_height - window_height) // 2 - 12
        with dpg.window(
            label="Memory Watch",
            tag=self.window_tag,
            width=window_width,
            height=window_height,
            pos=[pos_x, pos_y],
            on_close=self._on_window_close
        ):
            # Status bar
            with dpg.group(horizontal=True):
                dpg.add_text("Status:")
                dpg.add_text("Not connected", tag="watch_status_text", color=(255, 100, 100))
                dpg.add_spacer(width=20)
                
                # Emulator selection
                dpg.add_text("Emulator:")
                dpg.add_combo(
                    tag="emulator_combo",
                    items=["Scan for emulators..."],
                    default_value="Scan for emulators...",
                    width=200,
                    callback=self._on_emulator_selected
                )
                
                dpg.add_button(label="Scan", tag="scan_button", callback=self._scan_emulators, width=60)
                dpg.add_button(label="Connect", tag="connect_button", callback=self._connect_to_emulator, enabled=False, width=80)
                dpg.add_button(label="Stop Watching", tag="stop_watch_button", callback=self._stop_watching, enabled=False, show=False)
            
            dpg.add_separator()
            
            # Tab bar
            with dpg.tab_bar():
                # Manual Watch Tab
                with dpg.tab(label="Manual Watch"):
                    self._create_manual_tab()
                
                # Symbols Tab
                with dpg.tab(label="Symbols"):
                    self._create_symbols_tab()
        
        # Create loading modal
        self._create_loading_modal()
        
        # Create scanning modal
        self._create_scanning_modal()
    
    def _create_loading_modal(self):
        """Create loading modal dialog"""
        with dpg.window(
            label="Connecting to Emulator",
            tag=self.loading_modal_tag,
            modal=True,
            show=False,
            width=300,
            height=120,
            pos=[400, 300],
            no_resize=True,
            no_move=True,
            no_collapse=True
        ):
            dpg.add_text("Connecting to emulator and starting watch...", wrap=280)
            dpg.add_spacer(height=10)
            dpg.add_loading_indicator(style=0, radius=2.0)
    
    def _create_scanning_modal(self):
        """Create scanning modal dialog"""
        with dpg.window(
            label="Scanning for Emulators",
            tag=self.scanning_modal_tag,
            modal=True,
            show=False,
            width=300,
            height=120,
            pos=[400, 300],
            no_resize=True,
            no_move=True,
            no_collapse=True
        ):
            dpg.add_text("Scanning for running emulators...", wrap=280)
            dpg.add_spacer(height=10)
            dpg.add_loading_indicator(style=0, radius=2.0)
    
    def _show_scanning_modal(self):
        """Show the scanning modal"""
        dpg.show_item(self.scanning_modal_tag)
    
    def _create_manual_tab(self):
        """Create the manual watch tab"""
        dpg.add_text("Add Memory Address:")
        
        with dpg.group(horizontal=True):
            dpg.add_text("Address: 0x")
            dpg.add_input_text(
                tag="manual_address_input",
                hexadecimal=True,
                width=150,
                hint="80123456"
            )
            
            dpg.add_text("  Type:")
            dpg.add_combo(
                tag="manual_type_combo",
                items=["u8 (byte)", "s8 (signed byte)", "u16 (short)", "s16 (signed short)",
                       "u32 (int)", "s32 (signed int)", "float", "rgb (color)", "rgba (color+alpha)",
                       "bgr (color BGR)", "bgra (color BGRA)"],
                default_value="u32 (int)",
                width=150
            )
            
            dpg.add_text("  Name:")
            dpg.add_input_text(
                tag="manual_name_input",
                width=150,
                hint="Optional"
            )
            
            dpg.add_button(label="Add Watch", callback=self._add_manual_watch)
        
        dpg.add_separator()
        dpg.add_spacer(height=10)
        
        # Watch list header
        with dpg.table(header_row=False, borders_innerH=False, borders_outerH=False,
                      borders_innerV=False, borders_outerV=False):
            dpg.add_table_column(width_fixed=True, init_width_or_weight=150)
            dpg.add_table_column(width_fixed=True, init_width_or_weight=100)
            dpg.add_table_column(width_fixed=True, init_width_or_weight=100)
            dpg.add_table_column(width_fixed=True, init_width_or_weight=120)
            dpg.add_table_column(width_fixed=True, init_width_or_weight=120)
            dpg.add_table_column(width_fixed=True, init_width_or_weight=200)
            
            with dpg.table_row():
                dpg.add_text("Name")
                dpg.add_text("Address")
                dpg.add_text("Type")
                dpg.add_text("Value (Dec)")
                dpg.add_text("Value (Hex)")
                dpg.add_text("Actions")
        
        dpg.add_separator()
        
        # Scrollable watch list
        with dpg.child_window(tag="manual_watch_list", height=-1, border=True):
            pass
    
    def _create_symbols_tab(self):
        """Create the symbols tab"""
        with dpg.group(horizontal=True):
            dpg.add_button(label="Load Symbols from Map", callback=self._load_symbols)
            dpg.add_text("", tag="symbols_status_text")
        
        dpg.add_separator()
        dpg.add_spacer(height=10)
        
        # Filter
        with dpg.group(horizontal=True):
            dpg.add_text("Filter:")
            dpg.add_input_text(
                tag="symbol_filter_input",
                width=300,
                hint="Search symbols...",
                callback=self._filter_symbols
            )
            dpg.add_button(label="Watch All Visible", callback=self._watch_all_symbols)
        
        dpg.add_separator()

        # Symbol type filter buttons
        with dpg.group(horizontal=True):
            dpg.add_text("Filter:")
            dpg.add_button(
                label="All Symbols",
                tag="filter_all_symbols",
                callback=lambda: self._filter_symbols_by_type("all")
            )
            dpg.add_button(
                label="Game Symbols",
                tag="filter_game_symbols",
                callback=lambda: self._filter_symbols_by_type("game")
            )
            dpg.add_button(
                label="Mod Symbols",
                tag="filter_mod_symbols",
                callback=lambda: self._filter_symbols_by_type("mod")
            )

        dpg.add_separator()

        # Symbol list header
        with dpg.table(header_row=False, borders_innerH=False, borders_outerH=False,
                      borders_innerV=False, borders_outerV=False):
            dpg.add_table_column(width_fixed=True, init_width_or_weight=110)  # Symbol Type
            dpg.add_table_column(width_fixed=True, init_width_or_weight=180)  # Symbol Name
            dpg.add_table_column(width_fixed=True, init_width_or_weight=100)  # Address
            dpg.add_table_column(width_fixed=True, init_width_or_weight=30)   # Size
            dpg.add_table_column(width_fixed=True, init_width_or_weight=80)   # Type
            dpg.add_table_column(width_fixed=True, init_width_or_weight=100)  # Value (Dec)
            dpg.add_table_column(width_fixed=True, init_width_or_weight=100)  # Value (Hex)
            dpg.add_table_column(width_fixed=True, init_width_or_weight=280)  # Actions

            with dpg.table_row():
                dpg.add_text("Symbol Type")
                dpg.add_text("Symbol Name")
                dpg.add_text("Address")
                dpg.add_text("S")
                dpg.add_text("Type")
                dpg.add_text("Value (Dec)")
                dpg.add_text("Value (Hex)")
                dpg.add_text("Actions")

        dpg.add_separator()
        
        # Scrollable symbol list
        with dpg.child_window(tag="symbol_watch_list", height=-1, border=True):
            pass
    
    def _scan_emulators(self):
        """Scan for available emulators using centralized manager"""
        dpg.show_item(self.scanning_modal_tag)

        def scan_thread():
            # Use manager's scan (will notify all registered callbacks)
            self.available_emulators = self.manager.scan_emulators()
            self.emu_service = EmulatorService(self.project_data)

            # Update UI on main thread
            def update_combo():
                dpg.hide_item(self.scanning_modal_tag)

                if not self.available_emulators:
                    from gui import gui_messagebox as messagebox
                    messagebox.showwarning(
                        "No Emulators",
                        "No compatible emulators detected.\n\n"
                        "Make sure an emulator is running with a game loaded."
                    )
                    dpg.configure_item("emulator_combo", items=["No emulators found"])
                    dpg.set_value("emulator_combo", "No emulators found")
                    dpg.configure_item("connect_button", enabled=False)
                else:
                    dpg.configure_item("emulator_combo", items=self.available_emulators)
                    dpg.set_value("emulator_combo", self.available_emulators[0])
                    dpg.configure_item("connect_button", enabled=True)
                    verbose_print(f"Found {len(self.available_emulators)} emulators: {self.available_emulators}")

            # Schedule on main thread using a simple approach
            import time
            time.sleep(0.1)  # Small delay to ensure scanning modal shows

            # Update directly (should work since we're just setting values)
            try:
                update_combo()
            except:
                # If direct call fails, try again in a moment
                threading.Timer(0.1, update_combo).start()

        thread = threading.Thread(target=scan_thread, daemon=True)
        thread.start()

    def _on_emulators_scanned(self, available: list):
        """Callback when emulators are scanned by manager (from other windows)"""
        verbose_print(f"[MemoryWatch] _on_emulators_scanned called with: {available}")

        # Update our local state
        self.available_emulators = available

        # Ensure emu_service is set (needed for connection)
        if not self.emu_service:
            self.emu_service = EmulatorService(self.project_data)

        # Update UI if window exists (must happen on main thread)
        def update_ui():
            if dpg.does_item_exist("emulator_combo"):
                if available:
                    dpg.configure_item("emulator_combo", items=available)
                    if dpg.get_value("emulator_combo") in ["Scan for emulators...", "No emulators found"]:
                        dpg.set_value("emulator_combo", available[0])
                    dpg.configure_item("connect_button", enabled=True)
                else:
                    dpg.configure_item("emulator_combo", items=["No emulators found"])
                    dpg.set_value("emulator_combo", "No emulators found")
                    dpg.configure_item("connect_button", enabled=False)

        # Schedule on main thread
        try:
            dpg.split_frame()
            update_ui()
        except:
            # If split_frame fails, call directly (already on main thread)
            update_ui()

    def _restore_connection_state(self):
        """Restore connection state if manager has an active connection"""
        connection = self.manager.get_current_connection()
        if connection and dpg.does_item_exist("emulator_combo"):
            # Update combo with cached emulators
            if self.manager.available_emulators:
                self.available_emulators = self.manager.available_emulators
                self.emu_service = EmulatorService(self.project_data)  # Initialize service for connections
                dpg.configure_item("emulator_combo", items=self.available_emulators)
                dpg.set_value("emulator_combo", connection.emulator_name)
                dpg.configure_item("connect_button", enabled=True)
                verbose_print(f"[MemoryWatch] Restored connection to {connection.emulator_name}")
        elif self.manager.available_emulators and dpg.does_item_exist("emulator_combo"):
            # Use cached scan results from manager (scanned from another window)
            self.available_emulators = self.manager.available_emulators
            self.emu_service = EmulatorService(self.project_data)  # Initialize service for connections
            dpg.configure_item("emulator_combo", items=self.available_emulators)
            dpg.set_value("emulator_combo", self.available_emulators[0])
            dpg.configure_item("connect_button", enabled=True)
            verbose_print(f"[MemoryWatch] Restored {len(self.available_emulators)} emulators from cache")
    
    def _on_emulator_selected(self):
        """Called when emulator is selected from combo"""
        selected = dpg.get_value("emulator_combo")
        if selected and selected != "Scan for emulators..." and selected != "No emulators found":
            dpg.configure_item("connect_button", enabled=True)
        else:
            dpg.configure_item("connect_button", enabled=False)
    
    def _connect_to_emulator(self):
        """Connect to the selected emulator"""
        selected = dpg.get_value("emulator_combo")
        if not selected or selected == "Scan for emulators..." or selected == "No emulators found":
            return
        
        if not self.emu_service:
            from gui import gui_messagebox as messagebox
            messagebox.showerror("Error", "Please scan for emulators first")
            return
        
        dpg.show_item(self.loading_modal_tag)
        
        def connect_thread():
            from gui import gui_messagebox as messagebox
            
            # Try to connect
            success = self.watch_service.set_emulator_connection(self.emu_service, selected)
            
            def update_ui():
                dpg.hide_item(self.loading_modal_tag)
                
                if success:
                    # Start watching automatically
                    self.watch_service.start()
                    self.is_watching = True
                    
                    dpg.set_value("watch_status_text", f"Watching {selected}")
                    dpg.configure_item("watch_status_text", color=(100, 255, 100))
                    dpg.configure_item("scan_button", enabled=False)
                    dpg.configure_item("connect_button", enabled=False)
                    dpg.configure_item("emulator_combo", enabled=False)
                    dpg.show_item("stop_watch_button")
                    dpg.configure_item("stop_watch_button", enabled=True)
                    
                    #messagebox.showinfo("Connected", f"Connected to {selected} and started watching!")
                else:
                    messagebox.showerror(
                        "Connection Failed",
                        f"Could not connect to {selected}.\n\n"
                        "Make sure a game is loaded in the emulator."
                    )
            
            try:
                update_ui()
            except:
                threading.Timer(0.1, update_ui).start()
        
        thread = threading.Thread(target=connect_thread, daemon=True)
        thread.start()
    
    def _stop_watching(self):
        """Stop watching memory"""
        self.watch_service.stop()
        self.is_watching = False
        dpg.set_value("watch_status_text", "Stopped")
        dpg.configure_item("watch_status_text", color=(255, 255, 100))
        dpg.hide_item("stop_watch_button")
        dpg.configure_item("scan_button", enabled=True)
        dpg.configure_item("emulator_combo", enabled=True)
        
        # Re-enable connect button if we have emulators
        if self.available_emulators:
            dpg.configure_item("connect_button", enabled=True)
    
    def _add_manual_watch(self):
        """Add a manual watch entry"""
        address_str = dpg.get_value("manual_address_input")
        type_str = dpg.get_value("manual_type_combo")
        name = dpg.get_value("manual_name_input")
        
        if not address_str:
            return
        
        try:
            # Parse address
            if not address_str.startswith("0x"):
                address_str = "0x" + address_str
            address = int(address_str, 16)
            
            # Parse data type
            type_map = {
                "u8 (byte)": DataType.BYTE_UNSIGNED,
                "s8 (signed byte)": DataType.BYTE_SIGNED,
                "u16 (short)": DataType.SHORT_UNSIGNED,
                "s16 (signed short)": DataType.SHORT_SIGNED,
                "u32 (int)": DataType.INT_UNSIGNED,
                "s32 (signed int)": DataType.INT_SIGNED,
                "float": DataType.FLOAT,
                "rgb (color)": DataType.RGB,
                "rgba (color+alpha)": DataType.RGBA,
                "bgr (color BGR)": DataType.BGR,
                "bgra (color BGRA)": DataType.BGRA,
            }
            data_type = type_map.get(type_str, DataType.INT_UNSIGNED)
            
            # Add to watch service
            entry = self.watch_service.add_watch(address, data_type, name)
            
            # Add to GUI
            self._add_manual_watch_row(entry)
            
            # Clear inputs
            dpg.set_value("manual_address_input", "")
            dpg.set_value("manual_name_input", "")
            
        except ValueError:
            from gui import gui_messagebox as messagebox
            messagebox.showerror("Invalid Input", f"Invalid address: {address_str}")
    
    def _add_manual_watch_row(self, entry: WatchEntry):
        """Add a row to the manual watch list"""
        row_tag = f"manual_row_{id(entry)}"
        
        # Create table for this row
        with dpg.table(parent="manual_watch_list", tag=row_tag,
                    header_row=False, borders_innerH=False, borders_outerH=False,
                    borders_innerV=False, borders_outerV=False):
            dpg.add_table_column(width_fixed=True, init_width_or_weight=150)
            dpg.add_table_column(width_fixed=True, init_width_or_weight=100)
            dpg.add_table_column(width_fixed=True, init_width_or_weight=100)
            dpg.add_table_column(width_fixed=True, init_width_or_weight=120)
            dpg.add_table_column(width_fixed=True, init_width_or_weight=120)
            dpg.add_table_column(width_fixed=True, init_width_or_weight=200)
            
            name_tag = f"{row_tag}_name"
            addr_tag = f"{row_tag}_addr"
            type_tag = f"{row_tag}_type"
            dec_tag = f"{row_tag}_dec"
            hex_tag = f"{row_tag}_hex"
            color_swatch_tag = f"{row_tag}_color_swatch"
            
            with dpg.table_row():
                dpg.add_text(entry.name, tag=name_tag)
                dpg.add_text(f"0x{entry.address:X}", tag=addr_tag)
                
                # Type dropdown for switching
                dpg.add_combo(
                    tag=type_tag,
                    items=["u8", "s8", "u16", "s16", "u32", "s32", "rgb", "rgba", "bgr", "bgra"],
                    default_value=entry.data_type.value,
                    width=80,
                    callback=lambda s, a, u: self._change_watch_type(entry, a)
                )
                
                # Value displays with color swatch for color types
                with dpg.group(horizontal=True):
                    if entry.data_type.is_color:
                        # Add color swatch for color types
                        dpg.add_color_button(
                            tag=color_swatch_tag,
                            default_value=(0, 0, 0, 255),
                            width=20,
                            height=20,
                            no_alpha=not entry.data_type.has_alpha,
                            no_drag_drop=True
                        )
                    dpg.add_text("---", tag=dec_tag)

                dpg.add_text("---", tag=hex_tag)

                # Actions group
                with dpg.group(horizontal=True):
                    # Only add +/- buttons for non-color types
                    if not entry.data_type.is_color:
                        dpg.add_button(
                            label="-",
                            tag=f"{row_tag}_dec_btn",
                            callback=lambda: self._modify_value(entry, -1),
                            width=25
                        )
                        dpg.add_button(
                            label="+",
                            tag=f"{row_tag}_inc_btn",
                            callback=lambda: self._modify_value(entry, 1),
                            width=25
                        )
                    
                    # Edit button - color it differently for color types
                    if entry.data_type.is_color:
                        dpg.add_button(
                            label="Edit",
                            tag=f"{row_tag}_edit_btn",
                            callback=lambda: self._edit_value_dialog(entry),
                            width=50
                        )
                        dpg.bind_item_theme(f"{row_tag}_edit_btn", "rgb_edit_theme")
                    else:
                        dpg.add_button(
                            label="Edit",
                            tag=f"{row_tag}_edit_btn",
                            callback=lambda: self._edit_value_dialog(entry),
                            width=50
                        )
                    
                    dpg.add_button(
                        label="Remove",
                        callback=lambda: self._remove_manual_watch(entry, row_tag),
                        width=60
                    )
        
        self.manual_watches.append((entry, {
            'row': row_tag,
            'type': type_tag,
            'dec': dec_tag,
            'hex': hex_tag,
            'color_swatch': color_swatch_tag
        }))
        
        # If it's a color type and we're connected, do an immediate read
        if entry.data_type.is_color and self.watch_service.main_ram_address:
            self._immediate_read_value(entry)

    def _remove_manual_watch(self, entry: WatchEntry, row_tag: str):
        """Remove a manual watch"""
        self.watch_service.remove_watch(entry)
        dpg.delete_item(row_tag)
        self.manual_watches = [(e, tags) for e, tags in self.manual_watches if e != entry]
    
    def _change_watch_type(self, entry: WatchEntry, new_type_str: str):
        """Change the data type of a watch entry"""
        type_map = {
            "u8": DataType.BYTE_UNSIGNED,
            "s8": DataType.BYTE_SIGNED,
            "u16": DataType.SHORT_UNSIGNED,
            "s16": DataType.SHORT_SIGNED,
            "u32": DataType.INT_UNSIGNED,
            "s32": DataType.INT_SIGNED,
            "float": DataType.FLOAT,
            "rgb": DataType.RGB,
            "rgba": DataType.RGBA,
            "bgr": DataType.BGR,
            "bgra": DataType.BGRA,
        }
        old_type = entry.data_type
        new_type = type_map.get(new_type_str, DataType.INT_UNSIGNED)

        # Check if we need to rebuild (switching to/from color types, or changing alpha support)
        needs_rebuild = (old_type.is_color != new_type.is_color) or (old_type.has_alpha != new_type.has_alpha)
        
        entry.data_type = new_type
        verbose_print(f"Changed {entry.name} type to {new_type_str}")
        
        # If switching to/from color types or changing alpha support, rebuild the row
        if needs_rebuild:
            # Find and rebuild this row in manual watches
            for e, tags in self.manual_watches:
                if e == entry:
                    row_tag = tags['row']
                    self._remove_manual_watch(entry, row_tag)
                    # Re-add to watch service
                    entry = self.watch_service.add_watch(entry.address, entry.data_type, entry.name)
                    self._add_manual_watch_row(entry)
                    return

            # Find and rebuild in symbol watches
            for i, (symbol, e, tags) in enumerate(self.symbol_watches):
                if e == entry:
                    row_tag = tags['row']

                    # Remove existing buttons
                    if dpg.does_item_exist(f"{row_tag}_dec_btn"):
                        dpg.delete_item(f"{row_tag}_dec_btn")
                    if dpg.does_item_exist(f"{row_tag}_inc_btn"):
                        dpg.delete_item(f"{row_tag}_inc_btn")
                    if dpg.does_item_exist(f"{row_tag}_edit_btn"):
                        dpg.delete_item(f"{row_tag}_edit_btn")

                    # Handle color swatch in dec column
                    dec_group_tag = tags.get('dec_group')
                    if dpg.does_item_exist(dec_group_tag):
                        # Clear the group and rebuild
                        dpg.delete_item(dec_group_tag, children_only=True)

                        if new_type.is_color:
                            # Add color swatch
                            color_swatch_tag = f"{row_tag}_color_swatch"
                            dpg.add_color_button(
                                tag=color_swatch_tag,
                                default_value=(0, 0, 0, 255),
                                width=20,
                                height=20,
                                no_alpha=not new_type.has_alpha,
                                no_drag_drop=True,
                                parent=dec_group_tag
                            )
                            tags['color_swatch'] = color_swatch_tag

                        # Re-add the text
                        dpg.add_text("???", tag=tags['dec'], parent=dec_group_tag)
                    
                    # Re-add buttons based on type
                    if not new_type.is_color:
                        # Add +/- buttons for non-color types
                        def make_dec_callback(e):
                            return lambda: self._modify_value(e, -1)
                        dpg.add_button(
                            label="-",
                            tag=f"{row_tag}_dec_btn",
                            callback=make_dec_callback(entry),
                            width=25,
                            parent=tags['actions_group'],
                            before=tags['watch_btn']
                        )

                        def make_inc_callback(e):
                            return lambda: self._modify_value(e, 1)
                        dpg.add_button(
                            label="+",
                            tag=f"{row_tag}_inc_btn",
                            callback=make_inc_callback(entry),
                            width=25,
                            parent=tags['actions_group'],
                            before=tags['watch_btn']
                        )

                    # Always add Edit button
                    def make_edit_callback(e):
                        return lambda: self._edit_value_dialog(e)
                    dpg.add_button(
                        label="Edit",
                        tag=f"{row_tag}_edit_btn",
                        callback=make_edit_callback(entry),
                        width=50,
                        parent=tags['actions_group'],
                        before=tags['watch_btn']
                    )

                    # Color Edit button for color types
                    if new_type.is_color:
                        dpg.bind_item_theme(f"{row_tag}_edit_btn", "rgb_edit_theme")
                    
                    return
                
    def _rebuild_symbol_actions(self, symbol, entry, tags, row_tag):
        """Rebuild action buttons for a symbol watch"""
        # Clear all existing action buttons
        if dpg.does_item_exist(f"{row_tag}_dec"):
            dpg.delete_item(f"{row_tag}_dec")
        if dpg.does_item_exist(f"{row_tag}_inc"):
            dpg.delete_item(f"{row_tag}_inc")
        if dpg.does_item_exist(f"{row_tag}_edit"):
            dpg.delete_item(f"{row_tag}_edit")
        if dpg.does_item_exist(tags.get('color_swatch', '')):
            dpg.delete_item(tags['color_swatch'])
        
        # Add color swatch for color types in the dec value column
        if entry.data_type.is_color:
            # The dec_tag already exists as a text widget, we need to recreate the group
            # Delete the existing dec text and recreate with color swatch
            if dpg.does_item_exist(tags['dec']):
                parent = dpg.get_item_parent(tags['dec'])
                dpg.delete_item(tags['dec'])

                # Create new group with color swatch
                with dpg.group(horizontal=True, parent=parent):
                    color_swatch_tag = f"{row_tag}_color_swatch"
                    dpg.add_color_button(
                        tag=color_swatch_tag,
                        default_value=(0, 0, 0, 255),
                        width=20,
                        height=20,
                        no_alpha=not entry.data_type.has_alpha,
                        no_picker=True,
                        no_tooltip=True
                    )
                    dpg.add_text("???", tag=tags['dec'])
                    tags['color_swatch'] = color_swatch_tag
        else:
            # For non-color types, ensure dec is just text
            if dpg.does_item_exist(tags['dec']):
                parent = dpg.get_item_parent(tags['dec'])
                dpg.delete_item(tags['dec'])
                dpg.add_text("???", tag=tags['dec'], parent=parent)

        # Add +/- and Edit buttons (not for color types)
        if not entry.data_type.is_color:
            def make_dec_callback(e):
                return lambda: self._modify_value(e, -1)
            dpg.add_button(
                label="-",
                tag=f"{row_tag}_dec",
                callback=make_dec_callback(entry),
                width=25,
                parent=tags['actions_group'],
                before=tags['watch_btn']
            )
            
            def make_inc_callback(e):
                return lambda: self._modify_value(e, 1)
            dpg.add_button(
                label="+",
                tag=f"{row_tag}_inc",
                callback=make_inc_callback(entry),
                width=25,
                parent=tags['actions_group'],
                before=tags['watch_btn']
            )
        
        # Always add Edit button
        def make_edit_callback(e):
            return lambda: self._edit_value_dialog(e)
        dpg.add_button(
            label="Edit",
            tag=f"{row_tag}_edit",
            callback=make_edit_callback(entry),
            width=50,
            parent=tags['actions_group'],
            before=tags['watch_btn']
        )
    
    def _immediate_read_value(self, entry: WatchEntry):
        if not self.watch_service.main_ram_address:
            return

        # Reuse the same handle logic the watch loop uses
        handle = self.watch_service._ensure_process_handle()
        if not handle:
            return

        if entry.data_type.is_color:
            color = self.watch_service._read_color_value(handle, entry.address, entry.data_type)
            if color is not None:
                if entry.data_type.has_alpha:
                    # RGBA/BGRA -> (r, g, b, a)
                    entry.update_rgba_value(*color)
                else:
                    # RGB/BGR -> (r, g, b)
                    entry.update_rgb_value(*color)
            else:
                verbose_print(f"Warning: Failed to read color value for {entry.name}")
        else:
            value = self.watch_service._read_value(handle, entry.address, entry.data_type)
            if value is not None:
                entry.update_value(value)
            else:
                verbose_print(f"Warning: Failed to read value for {entry.name}")

        # Update UI immediately
        self._update_entry_ui(entry)

    
    
    def _update_entry_ui(self, entry: WatchEntry):
        """Update UI for a single entry (used for immediate feedback)"""
        dec_val = entry.format_value()
        hex_val = entry.format_hex()
        
        # Check if it's in manual watches
        for e, tags in self.manual_watches:
            if e == entry:
                dpg.set_value(tags['dec'], dec_val)
                dpg.set_value(tags['hex'], hex_val)
                dpg.configure_item(tags['dec'], color=(100, 255, 100))  # Green for instant update
                dpg.configure_item(tags['hex'], color=(100, 255, 100))
                
                # Update color swatch for color types
                if entry.data_type.is_color:
                    if dpg.does_item_exist(tags.get('color_swatch', '')):
                        if entry.data_type.has_alpha and entry.rgba_value is not None:
                            r, g, b, a = entry.rgba_value
                            dpg.configure_item(tags['color_swatch'], default_value=(r, g, b, a))
                        elif entry.rgb_value is not None:
                            r, g, b = entry.rgb_value
                            dpg.configure_item(tags['color_swatch'], default_value=(r, g, b, 255))
                return
        
        # Check if it's in symbol watches
        for symbol, e, tags in self.symbol_watches:
            if e == entry:
                dpg.set_value(tags['dec'], dec_val)
                dpg.set_value(tags['hex'], hex_val)
                dpg.configure_item(tags['dec'], color=(100, 255, 100))  # Green for instant update
                dpg.configure_item(tags['hex'], color=(100, 255, 100))
                
                # Update color swatch for color types
                if entry.data_type.is_color:
                    if dpg.does_item_exist(tags.get('color_swatch', '')):
                        if entry.data_type.has_alpha and entry.rgba_value is not None:
                            r, g, b, a = entry.rgba_value
                            dpg.configure_item(tags['color_swatch'], default_value=(r, g, b, a))
                        elif entry.rgb_value is not None:
                            r, g, b = entry.rgb_value
                            dpg.configure_item(tags['color_swatch'], default_value=(r, g, b, 255))
                return
    
    
    def _modify_value(self, entry: WatchEntry, delta: int):
        """Increment or decrement value by delta"""
        if entry.current_value is None:
            return
        
        # Handle float type specially
        if entry.data_type == DataType.FLOAT:
            import struct
            try:
                # Convert stored int to float
                float_val = struct.unpack('f', entry.current_value.to_bytes(4, byteorder='little'))[0]
                # Add delta (convert to float delta)
                new_float = float_val + float(delta)
                # Write back
                success = self.watch_service.write_float_value(entry.address, new_float)
                if success:
                    self._immediate_read_value(entry)
                else:
                    from gui import gui_messagebox as messagebox
                    messagebox.showerror("Write Failed", "Could not write float value to memory")
            except Exception as e:
                from gui import gui_messagebox as messagebox
                messagebox.showerror("Error", f"Failed to modify float: {e}")
            return
        
        # Get current value as signed if needed
        current = entry.current_value
        if entry.data_type.is_signed:
            max_val = 2 ** (entry.data_type.size * 8)
            if current >= max_val // 2:
                current = current - max_val
        
        new_value = current + delta
        
        # Write to memory
        success = self.watch_service.write_value(entry.address, new_value, entry.data_type)
        if success:
            # Immediately read back and update the UI for instant feedback
            self._immediate_read_value(entry)
        else:
            from gui import gui_messagebox as messagebox
            messagebox.showerror("Write Failed", "Could not write value to memory")
    
    def _edit_value_dialog(self, entry: WatchEntry):
        dialog_tag = f"edit_dialog_{id(entry)}"

        if dpg.does_item_exist(dialog_tag):
            # For color dialogs, refresh the underlying memory value before showing
            if entry.data_type.is_color:
                self._immediate_read_value(entry)

                picker_tag = f"{dialog_tag}_color_picker"
                if dpg.does_item_exist(picker_tag):
                    # Push the freshly-read value into the picker (0.0-1.0 normalized)
                    if entry.data_type.has_alpha and entry.rgba_value is not None:
                        r, g, b, a = entry.rgba_value
                        dpg.set_value(picker_tag, (r / 255.0, g / 255.0, b / 255.0, a / 255.0))
                    elif entry.rgb_value is not None:
                        r, g, b = entry.rgb_value
                        dpg.set_value(picker_tag, (r / 255.0, g / 255.0, b / 255.0, 1.0))
                else:
                    # Dialog exists but isn't a color dialog anymore (type changed) - rebuild it.
                    dpg.delete_item(dialog_tag)

                if dpg.does_item_exist(dialog_tag):
                    dpg.show_item(dialog_tag)
                    return
            else:
                dpg.show_item(dialog_tag)
                return

        # Special handling for color types - show color picker
        if entry.data_type.is_color:
            # Read current value from memory first to ensure we have the latest value
            self._immediate_read_value(entry)
            self._edit_color_dialog(entry, dialog_tag)
            return
        
        def save_value():
            value_str = dpg.get_value(f"{dialog_tag}_input")
            try:
                # Handle float type
                if entry.data_type == DataType.FLOAT:
                    new_value = float(value_str)
                    success = self.watch_service.write_float_value(entry.address, new_value)
                else:
                    # Parse value (supports hex with 0x prefix)
                    if value_str.startswith("0x"):
                        new_value = int(value_str, 16)
                    else:
                        new_value = int(value_str)
                    
                    # Write to memory
                    success = self.watch_service.write_value(entry.address, new_value, entry.data_type)
                
                if success:
                    # Immediately read back and update the UI for instant feedback
                    self._immediate_read_value(entry)
                    dpg.delete_item(dialog_tag)
                else:
                    from gui import gui_messagebox as messagebox
                    messagebox.showerror("Write Failed", "Could not write value to memory")
            except ValueError:
                from gui import gui_messagebox as messagebox
                messagebox.showerror("Invalid Value", "Please enter a valid number")
        
        # Get default value for input field
        if entry.data_type == DataType.FLOAT:
            default_value = entry.format_value() if entry.current_value is not None else "0.0"
            hint_text = "Enter decimal number (e.g., 3.14159)"
        else:
            default_value = entry.format_value() if entry.current_value is not None else "0"
            hint_text = "Enter decimal or 0xHEX"
        
        with dpg.window(
            label=f"Edit Value: {entry.name}",
            tag=dialog_tag,
            modal=True,
            width=350,
            height=180,
            pos=[400, 300]
        ):
            dpg.add_text(f"Address: 0x{entry.address:X}")
            dpg.add_text(f"Type: {entry.data_type.value}")
            dpg.add_spacer(height=10)
            
            dpg.add_text("New Value:")
            dpg.add_input_text(
                tag=f"{dialog_tag}_input",
                width=320,
                hint=hint_text,
                default_value=default_value,
                decimal=(entry.data_type == DataType.FLOAT)
            )
            
            dpg.add_spacer(height=10)
            with dpg.group(horizontal=True):
                dpg.add_button(label="Save", callback=save_value, width=120)
                dpg.add_button(label="Cancel", callback=lambda: dpg.delete_item(dialog_tag), width=120)
    
    def _edit_color_dialog(self, entry: WatchEntry, dialog_tag: str):
        # Delete existing dialog if it exists
        if dpg.does_item_exist(dialog_tag):
            dpg.delete_item(dialog_tag)
        
        # Force an immediate read from memory to get fresh values
        if not self.watch_service.main_ram_address:
            print("Error: No emulator connection")
            return
        
        handle = self.watch_service._ensure_process_handle()
        if not handle:
            print("Error: Could not get process handle")
            return
        
        # Read the color value directly from memory right now
        color = self.watch_service._read_color_value(handle, entry.address, entry.data_type)
        if color is not None:
            if entry.data_type.has_alpha:
                entry.update_rgba_value(*color)
            else:
                entry.update_rgb_value(*color)
            verbose_print(f"Successfully read color from memory: {color}")
        else:
            print(f"Warning: Could not read color from memory for {entry.name}")
        
        # Get the color values in 0-255 range for DearPyGui
        if entry.data_type.has_alpha and entry.rgba_value is not None:
            r, g, b, a = entry.rgba_value
            initial_color = (r, g, b, a)
            verbose_print(f"Opening color picker with RGBA (0-255): {r}, {g}, {b}, {a}")
        elif entry.rgb_value is not None:
            r, g, b = entry.rgb_value
            initial_color = (r, g, b, 255)
            verbose_print(f"Opening color picker with RGB (0-255): {r}, {g}, {b}")
        else:
            # Fallback to white if we still couldn't read
            initial_color = (255, 255, 255, 255)
            verbose_print("Warning: Using default white color because read failed")

        def on_color_change(sender, app_data):
            """Called whenever the color picker changes - write immediately"""
            color = dpg.get_value(f"{dialog_tag}_color_picker")
            
            verbose_print(f"Color picker returned: {color}")

            # DearPyGui returns values in 0-255 range
            r = round(color[0])
            g = round(color[1])
            b = round(color[2])
            a = round(color[3]) if len(color) > 3 else 255

            # Clamp to valid range
            r = max(0, min(255, r))
            g = max(0, min(255, g))
            b = max(0, min(255, b))
            a = max(0, min(255, a))

            # Write to memory immediately
            self.watch_service.write_color_value(entry.address, entry.data_type, r, g, b, a)

            # Immediately read back and update the UI for instant feedback
            self._immediate_read_value(entry)

        def close_dialog():
            dpg.delete_item(dialog_tag)

        # Get type display string
        type_str = entry.data_type.value.upper()
        byte_count = entry.data_type.size

        with dpg.window(
            label=f"Edit Color: {entry.name}",
            tag=dialog_tag,
            modal=True,
            width=450,
            height=570,
            pos=[350, 100]
        ):
            dpg.add_text(f"Address: 0x{entry.address:X}")
            dpg.add_text(f"Type: {type_str} ({byte_count} bytes)")
            dpg.add_spacer(height=10)

            # Color picker with wheel - use 0-255 values, not normalized
            dpg.add_color_picker(
                tag=f"{dialog_tag}_color_picker",
                default_value=initial_color,
                no_alpha=not entry.data_type.has_alpha,
                display_rgb=True,  # Enable RGB display to see actual values
                display_hsv=True,
                display_hex=True,
                width=400,
                picker_mode=dpg.mvColorPicker_wheel,
                callback=on_color_change
            )

            dpg.add_spacer(height=10)
            dpg.add_button(label="Close", callback=close_dialog, width=150)
    
    def _load_symbols(self):
        """Load symbols from memory map"""
        project_folder = self.project_data.GetProjectFolder()
        map_path = os.path.join(project_folder, '.config', 'memory_map', 'MyMod.map')
        
        if not os.path.exists(map_path):
            from gui import gui_messagebox as messagebox
            messagebox.showerror(
                "Map File Not Found",
                "Memory map not found.\n\n"
                "Compile your project first to generate the map file."
            )
            return
        
        # Parse symbols
        self.symbol_parser = SymbolParserService(map_path)
        symbols = self.symbol_parser.parse()
        
        if not symbols:
            from gui import gui_messagebox as messagebox
            messagebox.showwarning(
                "No Symbols",
                "No symbols found in map file."
            )
            return
        
        # Store all symbols for filtering
        self.all_symbols = symbols
        dpg.set_value("symbols_status_text", f"Loaded {len(symbols)} symbols")

        # Populate symbol list with current filter
        self._populate_symbols()

    def _filter_symbols_by_type(self, filter_type: str):
        """Filter symbols by type (Game Symbol / Mod Symbol)"""
        self.current_filter = filter_type
        self._populate_symbols()

    def _populate_symbols(self):
        """Populate the symbol watch list based on current filter"""
        # Clear existing
        dpg.delete_item("symbol_watch_list", children_only=True)
        self.symbol_watches.clear()

        # Filter symbols based on current filter
        filtered_symbols = []
        for symbol in self.all_symbols:
            if self.current_filter == "all":
                filtered_symbols.append(symbol)
            elif self.current_filter == "game" and symbol.symbol_type == "Game Symbol":
                filtered_symbols.append(symbol)
            elif self.current_filter == "mod" and symbol.symbol_type == "Mod Symbol":
                filtered_symbols.append(symbol)

        # Add rows for filtered symbols
        for symbol in filtered_symbols:
            self._add_symbol_row(symbol)
    
    def _add_symbol_row(self, symbol):
        """Add a row for a symbol"""
        row_tag = f"symbol_row_{id(symbol)}"

        # Create table for this row
        with dpg.table(parent="symbol_watch_list", tag=row_tag,
                    header_row=False, borders_innerH=False, borders_outerH=False,
                    borders_innerV=False, borders_outerV=False):
            dpg.add_table_column(width_fixed=True, init_width_or_weight=110)  # Symbol Type
            dpg.add_table_column(width_fixed=True, init_width_or_weight=180)  # Symbol Name
            dpg.add_table_column(width_fixed=True, init_width_or_weight=100)  # Address
            dpg.add_table_column(width_fixed=True, init_width_or_weight=30)   # Size
            dpg.add_table_column(width_fixed=True, init_width_or_weight=80)   # Type
            dpg.add_table_column(width_fixed=True, init_width_or_weight=100)  # Value (Dec)
            dpg.add_table_column(width_fixed=True, init_width_or_weight=100)  # Value (Hex)
            dpg.add_table_column(width_fixed=True, init_width_or_weight=280)  # Actions

            symbol_type_tag = f"{row_tag}_symbol_type"
            name_tag = f"{row_tag}_name"
            addr_tag = f"{row_tag}_addr"
            size_tag = f"{row_tag}_size"
            type_tag = f"{row_tag}_type"
            dec_tag = f"{row_tag}_dec"
            hex_tag = f"{row_tag}_hex"
            watch_btn_tag = f"{row_tag}_watch_btn"
            actions_group_tag = f"{row_tag}_actions_group"
            color_swatch_tag = f"{row_tag}_color_swatch"
            dec_group_tag = f"{row_tag}_dec_group"

            with dpg.table_row():
                # Symbol Type with color coding
                symbol_type_text = symbol.symbol_type if hasattr(symbol, 'symbol_type') and symbol.symbol_type else "Unknown"
                symbol_type_color = (100, 200, 255) if symbol_type_text == "Game Symbol" else (255, 200, 100)
                dpg.add_text(symbol_type_text, tag=symbol_type_tag, color=symbol_type_color)

                dpg.add_text(symbol.name, tag=name_tag)
                dpg.add_text(f"0x{symbol.address:X}", tag=addr_tag)
                dpg.add_text(f"0x{symbol.size:X}", tag=size_tag)
                
                # Type dropdown (enabled, auto-watches on selection)
                dpg.add_combo(
                    tag=type_tag,
                    items=["u8", "s8", "u16", "s16", "u32", "s32", "float", "rgb", "rgba", "bgr", "bgra"],
                    default_value="u32",
                    width=70,
                    enabled=True,
                    callback=lambda s, a, u: self._on_symbol_type_changed(symbol, row_tag, a)
                )
                
                # Value column - wrap in group for potential color swatch
                with dpg.group(horizontal=True, tag=dec_group_tag):
                    dpg.add_text("---", tag=dec_tag)
                
                dpg.add_text("---", tag=hex_tag)
                
                # Actions group with buttons
                with dpg.group(horizontal=True, tag=actions_group_tag):
                    dpg.add_button(
                        label="Watch",
                        tag=watch_btn_tag,
                        callback=lambda: self._toggle_symbol_watch(symbol, row_tag),
                        width=70
                    )
            
            self.symbol_watches.append((symbol, None, {
                'row': row_tag,
                'type': type_tag,
                'dec': dec_tag,
                'dec_group': dec_group_tag,
                'hex': hex_tag,
                'watch_btn': watch_btn_tag,
                'actions_group': actions_group_tag,
                'color_swatch': color_swatch_tag
            }))
    
    def _toggle_symbol_watch(self, symbol, row_tag: str):
        """Toggle watching a symbol"""
        # Find entry in list
        for i, (sym, entry, tags) in enumerate(self.symbol_watches):
            if sym == symbol:
                if entry is None:
                    # Add watch
                    entry = self.watch_service.add_watch(
                        symbol.address,
                        DataType.INT_UNSIGNED,
                        symbol.name
                    )
                    self.symbol_watches[i] = (sym, entry, tags)
                    dpg.set_item_label(tags['watch_btn'], "Unwatch")
                    
                    # Update type combo to reflect u32
                    dpg.set_value(tags['type'], "u32")
                    
                    # Update type combo callback to change type (not re-watch)
                    def make_type_callback(e):
                        return lambda s, a, u: self._change_watch_type(e, a)
                    dpg.configure_item(tags['type'], callback=make_type_callback(entry))

                    # Add control buttons
                    self._add_symbol_control_buttons(entry, tags)
                    
                else:
                    # Remove watch
                    self.watch_service.remove_watch(entry)
                    self.symbol_watches[i] = (sym, None, tags)
                    dpg.set_item_label(tags['watch_btn'], "Watch")
                    # Keep type combo enabled so user can select type before re-watching
                    dpg.set_value(tags['dec'], "---")
                    dpg.set_value(tags['hex'], "---")
                    
                    # Reset type combo to u32
                    dpg.set_value(tags['type'], "u32")
                    
                    # Remove inc/dec/edit buttons
                    if dpg.does_item_exist(f"{row_tag}_dec_btn"):
                        dpg.delete_item(f"{row_tag}_dec_btn")
                    if dpg.does_item_exist(f"{row_tag}_inc_btn"):
                        dpg.delete_item(f"{row_tag}_inc_btn")
                    if dpg.does_item_exist(f"{row_tag}_edit_btn"):
                        dpg.delete_item(f"{row_tag}_edit_btn")
                    
                    # Remove color swatch if exists
                    if dpg.does_item_exist(tags.get('color_swatch', '')):
                        dpg.delete_item(tags['color_swatch'])
                break

    def _add_symbol_control_buttons(self, entry, tags):
        """Add +/-/Edit buttons for a symbol watch"""
        row_tag = tags['row']

        # Add inc/dec/edit buttons only if they don't exist
        if not dpg.does_item_exist(f"{row_tag}_dec_btn"):
            def make_dec_callback(e):
                return lambda: self._modify_value(e, -1)
            dpg.add_button(
                label="-",
                tag=f"{row_tag}_dec_btn",
                callback=make_dec_callback(entry),
                width=25,
                parent=tags['actions_group'],
                before=tags['watch_btn']
            )

        if not dpg.does_item_exist(f"{row_tag}_inc_btn"):
            def make_inc_callback(e):
                return lambda: self._modify_value(e, 1)
            dpg.add_button(
                label="+",
                tag=f"{row_tag}_inc_btn",
                callback=make_inc_callback(entry),
                width=25,
                parent=tags['actions_group'],
                before=tags['watch_btn']
            )

        if not dpg.does_item_exist(f"{row_tag}_edit_btn"):
            def make_edit_callback(e):
                return lambda: self._edit_value_dialog(e)
            dpg.add_button(
                label="Edit",
                tag=f"{row_tag}_edit_btn",
                callback=make_edit_callback(entry),
                width=50,
                parent=tags['actions_group'],
                before=tags['watch_btn']
            )
        # If it's a color type and we're connected, do an immediate read
        if entry.data_type.is_color and self.watch_service.main_ram_address:
            self._immediate_read_value(entry)

    def _on_symbol_type_changed(self, symbol, row_tag: str, new_type_str: str):
        """Handle type change in symbols tab - auto-starts watching if not already"""
        # Find the symbol watch entry
        for i, (sym, entry, tags) in enumerate(self.symbol_watches):
            if sym.address == symbol.address and tags['row'] == row_tag:
                if entry is None:
                    # Not being watched yet - start watching with the selected type
                    type_map = {
                        "u8": DataType.BYTE_UNSIGNED,
                        "s8": DataType.BYTE_SIGNED,
                        "u16": DataType.SHORT_UNSIGNED,
                        "s16": DataType.SHORT_SIGNED,
                        "u32": DataType.INT_UNSIGNED,
                        "s32": DataType.INT_SIGNED,
                        "float": DataType.FLOAT,
                        "rgb": DataType.RGB,
                        "rgba": DataType.RGBA,
                        "bgr": DataType.BGR,
                        "bgra": DataType.BGRA,
                    }
                    data_type = type_map.get(new_type_str, DataType.INT_UNSIGNED)

                    # Add watch
                    entry = self.watch_service.add_watch(symbol.address, data_type, symbol.name)
                    self.symbol_watches[i] = (symbol, entry, tags)
                    dpg.set_item_label(tags['watch_btn'], "Unwatch")

                    # Add control buttons
                    self._add_symbol_control_buttons(entry, tags)
                else:
                    # Already watching - just change the type
                    self._change_watch_type(entry, new_type_str)
                break

    def _change_symbol_watch_type(self, symbol, new_type_str: str):
        """Change the data type of a symbol watch (deprecated - kept for backward compatibility)"""
        # This is no longer used but kept in case of old callbacks
        pass
    
    def _watch_all_symbols(self):
        """Watch all visible symbols"""
        count = 0
        for i, (symbol, entry, tags) in enumerate(self.symbol_watches):
            if entry is None and dpg.is_item_shown(tags['row']):
                entry = self.watch_service.add_watch(
                    symbol.address,
                    DataType.INT_UNSIGNED,
                    symbol.name
                )
                self.symbol_watches[i] = (symbol, entry, tags)
                dpg.set_item_label(tags['watch_btn'], "Unwatch")
                
                # Enable type dropdown and set callback
                dpg.configure_item(tags['type'], enabled=True)
                # Use closure with default parameter to capture entry correctly
                def make_type_callback(e):
                    return lambda s, a, u: self._change_watch_type(e, a)
                dpg.configure_item(tags['type'], callback=make_type_callback(entry))
                
                # Add inc/dec/edit buttons only if they don't exist
                row_tag = tags['row']
                
                if not dpg.does_item_exist(f"{row_tag}_dec_btn"):
                    def make_dec_callback(e):
                        return lambda: self._modify_value(e, -1)
                    dpg.add_button(
                        label="-",
                        tag=f"{row_tag}_dec_btn",
                        callback=make_dec_callback(entry),
                        width=25,
                        parent=tags['actions_group'],
                        before=tags['watch_btn']
                    )
                
                if not dpg.does_item_exist(f"{row_tag}_inc_btn"):
                    def make_inc_callback(e):
                        return lambda: self._modify_value(e, 1)
                    dpg.add_button(
                        label="+",
                        tag=f"{row_tag}_inc_btn",
                        callback=make_inc_callback(entry),
                        width=25,
                        parent=tags['actions_group'],
                        before=tags['watch_btn']
                    )
                
                if not dpg.does_item_exist(f"{row_tag}_edit_btn"):
                    def make_edit_callback(e):
                        return lambda: self._edit_value_dialog(e)
                    dpg.add_button(
                        label="Edit",
                        tag=f"{row_tag}_edit_btn",
                        callback=make_edit_callback(entry),
                        width=50,
                        parent=tags['actions_group'],
                        before=tags['watch_btn']
                    )
                
                count += 1
        
        verbose_print(f"Added {count} symbol watches")
    
    def _filter_symbols(self):
        """Filter symbols by search text"""
        filter_text = dpg.get_value("symbol_filter_input").lower()
        
        for symbol, entry, tags in self.symbol_watches:
            if filter_text in symbol.name.lower():
                dpg.show_item(tags['row'])
            else:
                dpg.hide_item(tags['row'])
    
    def _on_watch_update(self, entries):
        """Called when watch values update"""
        # Update manual watches
        for entry, tags in self.manual_watches:
            dec_val = entry.format_value()
            hex_val = entry.format_hex()
            
            # Update text
            dpg.set_value(tags['dec'], dec_val)
            dpg.set_value(tags['hex'], hex_val)
            
            # Update color swatch for color types
            if entry.data_type.is_color:
                if dpg.does_item_exist(tags.get('color_swatch', '')):
                    if entry.data_type.has_alpha and entry.rgba_value is not None:
                        r, g, b, a = entry.rgba_value
                        dpg.configure_item(tags['color_swatch'], default_value=(r, g, b, a))
                    elif entry.rgb_value is not None:
                        r, g, b = entry.rgb_value
                        dpg.configure_item(tags['color_swatch'], default_value=(r, g, b, 255))
            
            # Highlight if changed
            if entry.has_changed:
                dpg.configure_item(tags['dec'], color=(255, 255, 100))
                dpg.configure_item(tags['hex'], color=(255, 255, 100))
            else:
                dpg.configure_item(tags['dec'], color=(255, 255, 255))
                dpg.configure_item(tags['hex'], color=(255, 255, 255))
        
        # Update symbol watches
        for symbol, entry, tags in self.symbol_watches:
            if entry is not None:
                dec_val = entry.format_value()
                hex_val = entry.format_hex()
                
                dpg.set_value(tags['dec'], dec_val)
                dpg.set_value(tags['hex'], hex_val)
                
                # Update color swatch for color types
                if entry.data_type.is_color:
                    if dpg.does_item_exist(tags.get('color_swatch', '')):
                        if entry.data_type.has_alpha and entry.rgba_value is not None:
                            r, g, b, a = entry.rgba_value
                            dpg.configure_item(tags['color_swatch'], default_value=(r, g, b, a))
                        elif entry.rgb_value is not None:
                            r, g, b = entry.rgb_value
                            dpg.configure_item(tags['color_swatch'], default_value=(r, g, b, 255))
                
                if entry.has_changed:
                    dpg.configure_item(tags['dec'], color=(255, 255, 100))
                    dpg.configure_item(tags['hex'], color=(255, 255, 100))
                else:
                    dpg.configure_item(tags['dec'], color=(255, 255, 255))
                    dpg.configure_item(tags['hex'], color=(255, 255, 255))
    
    def _on_watch_error(self, error_msg: str):
        """Called when watch encounters an error"""
        dpg.set_value("watch_status_text", f"Error: {error_msg}")
        dpg.configure_item("watch_status_text", color=(255, 100, 100))
    
    def _on_window_close(self):
        """Called when window is closed - just stop watching, don't reset connection"""
        # Stop watching but keep connection alive
        if self.is_watching:
            self.watch_service.stop()
            self.is_watching = False

        # DON'T unregister scan callback - keep receiving updates even when window is closed
        # The callback checks if window exists before updating UI

        verbose_print("Memory watch window closed (connection preserved)")
    
    def _reset_window_state(self):
        """Reset the entire window state - only called when switching projects"""
        # Stop watching service
        self.watch_service.stop()
        self.is_watching = False

        # Clear all watches from service
        self.watch_service.clear_watches()

        # Clear manual watches
        for entry, tags in self.manual_watches:
            if dpg.does_item_exist(tags['row']):
                dpg.delete_item(tags['row'])
        self.manual_watches.clear()

        # Clear symbol watches
        for symbol, entry, tags in self.symbol_watches:
            if dpg.does_item_exist(tags['row']):
                dpg.delete_item(tags['row'])
        self.symbol_watches.clear()

        # Reset symbol parser
        self.symbol_parser = None

        # Reset emulator selection
        self.available_emulators = []
        self.emu_service = None

        # Reset connection state in the watch service
        self.watch_service.reset_connection()

        # Delete the entire DearPyGui window so it gets recreated fresh with new project data
        if dpg.does_item_exist(self.window_tag):
            dpg.delete_item(self.window_tag)

        # Delete modals as well
        if dpg.does_item_exist(self.loading_modal_tag):
            dpg.delete_item(self.loading_modal_tag)

        if dpg.does_item_exist(self.scanning_modal_tag):
            dpg.delete_item(self.scanning_modal_tag)

        verbose_print("Memory watch window state fully reset")
    
    
    def show(self):
        """Show the window"""
        if dpg.does_item_exist(self.window_tag):
            dpg.show_item(self.window_tag)
        else:
            self._create_window()


# Global instance
_memory_watch_window: Optional[MemoryWatchWindow] = None
_last_project_data: Optional[ProjectData] = None


def get_memory_watch_service():
    """Get the global memory watch service instance"""
    global _memory_watch_window
    if _memory_watch_window:
        return _memory_watch_window.watch_service
    return None


def reset_memory_watch_for_project_change():
    """Reset memory watch when project changes or closes"""
    global _memory_watch_window, _last_project_data
    
    if _memory_watch_window is not None:
        verbose_print("Resetting memory watch for project change")
        _memory_watch_window._reset_window_state()
        _memory_watch_window = None
    
    _last_project_data = None


def show_memory_watch_window(project_data: ProjectData):
    """Show memory watch window"""
    global _memory_watch_window, _last_project_data
    
    # If project changed, fully reset
    if _memory_watch_window is not None and _last_project_data is not project_data:
        verbose_print("Project changed, fully resetting memory watch")
        _memory_watch_window._reset_window_state()
        _memory_watch_window = None
    
    # Create new instance if needed
    if _memory_watch_window is None:
        _memory_watch_window = MemoryWatchWindow(project_data)
    else:
        # Window already exists, just show it
        _memory_watch_window.show()
    
    _last_project_data = project_data