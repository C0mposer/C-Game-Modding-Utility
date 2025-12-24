# gui/gui_debugger.py

"""
C Debugger GUI Window

Interactive debugger for C code with:
- Source code viewer with syntax highlighting
- Breakpoint management (click to set/remove)
- Variable inspection (locals, parameters, globals)
- Register viewer
- Step over/into/out functionality
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import os
import threading
from typing import Optional, List, Dict

from classes.debugger.debugger_backend import DebuggerBackend, DebuggerState
from classes.debugger.breakpoint import Breakpoint
from classes.project_data.project_data import ProjectData
from services.dwarf_parser_service import DWARFParser, SourceLine, Variable, FunctionInfo


class DebuggerWindow:
    """C Debugger GUI Window"""

    def __init__(self, parent, project_data: ProjectData):
        """
        Initialize the debugger window.

        Args:
            parent: Parent tkinter window
            project_data: Project data
        """
        self.parent = parent
        self.project_data = project_data

        # Create debugger backend
        self.debugger = DebuggerBackend(project_data)

        # State
        self.current_source_file: Optional[str] = None
        self.source_files: List[str] = []
        self.line_to_breakpoint: Dict[int, Breakpoint] = {}  # line_num -> Breakpoint
        self.current_function: Optional[FunctionInfo] = None
        self.initialized: bool = False  # Track if debugger backend is initialized
        self.polling: bool = False  # Track if polling loop is running
        self.polling_interval: int = 100  # Poll every 100ms

        # Create window
        self.window = tk.Toplevel(parent)
        self.window.title("C Debugger")
        self.window.geometry("1200x800")

        # Build UI
        self._build_ui()

        # Don't initialize debugger here - it blocks the GUI thread
        # Instead, it will be initialized in show() after window is visible

    def _build_ui(self):
        """Build the GUI layout"""
        # Main container
        main_frame = ttk.Frame(self.window)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Top toolbar
        self._build_toolbar(main_frame)

        # Middle paned window (source code + bottom panels)
        paned = ttk.PanedWindow(main_frame, orient=tk.VERTICAL)
        paned.pack(fill=tk.BOTH, expand=True, pady=(5, 0))

        # Source code viewer
        self._build_source_viewer(paned)

        # Bottom paned window (variables + registers)
        bottom_paned = ttk.PanedWindow(paned, orient=tk.HORIZONTAL)
        paned.add(bottom_paned, weight=1)

        # Variables panel
        self._build_variables_panel(bottom_paned)

        # Registers panel
        self._build_registers_panel(bottom_paned)

        # Status bar
        self._build_status_bar(main_frame)

    def _build_toolbar(self, parent):
        """Build the top toolbar with control buttons"""
        toolbar = ttk.Frame(parent)
        toolbar.pack(fill=tk.X, pady=(0, 5))

        # File selection
        ttk.Label(toolbar, text="Source File:").pack(side=tk.LEFT, padx=(0, 5))

        self.file_combo = ttk.Combobox(toolbar, state="readonly", width=40)
        self.file_combo.pack(side=tk.LEFT, padx=(0, 10))
        self.file_combo.bind("<<ComboboxSelected>>", self._on_file_selected)

        # Control buttons
        self.continue_btn = ttk.Button(toolbar, text="Continue", command=self._on_continue, state=tk.DISABLED)
        self.continue_btn.pack(side=tk.LEFT, padx=2)

        self.step_over_btn = ttk.Button(toolbar, text="Step Over", command=self._on_step_over, state=tk.DISABLED)
        self.step_over_btn.pack(side=tk.LEFT, padx=2)

        self.step_into_btn = ttk.Button(toolbar, text="Step Into", command=self._on_step_into, state=tk.DISABLED)
        self.step_into_btn.pack(side=tk.LEFT, padx=2)

        self.step_out_btn = ttk.Button(toolbar, text="Step Out", command=self._on_step_out, state=tk.DISABLED)
        self.step_out_btn.pack(side=tk.LEFT, padx=2)

        # Separator
        ttk.Separator(toolbar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=10)

        # Debug mode toggle
        self.debug_mode_var = tk.BooleanVar(value=self.project_data.GetCurrentBuildVersion().IsDebugMode())
        debug_mode_check = ttk.Checkbutton(
            toolbar,
            text="Debug Mode (-O0)",
            variable=self.debug_mode_var,
            command=self._on_debug_mode_toggle
        )
        debug_mode_check.pack(side=tk.LEFT, padx=5)

    def _build_source_viewer(self, parent):
        """Build the source code viewer with line numbers and breakpoints"""
        source_frame = ttk.Frame(parent)
        parent.add(source_frame, weight=3)

        # Create text widget with line numbers
        text_frame = ttk.Frame(source_frame)
        text_frame.pack(fill=tk.BOTH, expand=True)

        # Line numbers (with breakpoint indicators)
        self.line_numbers = tk.Text(
            text_frame,
            width=6,
            padx=5,
            takefocus=0,
            border=0,
            background='#f0f0f0',
            state=tk.DISABLED,
            wrap=tk.NONE
        )
        self.line_numbers.pack(side=tk.LEFT, fill=tk.Y)

        # Bind click event to line numbers for breakpoint toggle
        self.line_numbers.bind("<Button-1>", self._on_line_number_click)

        # Source code
        self.source_text = tk.Text(
            text_frame,
            wrap=tk.NONE,
            font=('Consolas', 10),
            undo=True
        )
        self.source_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Scrollbars
        v_scroll = ttk.Scrollbar(text_frame, orient=tk.VERTICAL, command=self._on_scroll)
        v_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        h_scroll = ttk.Scrollbar(source_frame, orient=tk.HORIZONTAL, command=self.source_text.xview)
        h_scroll.pack(side=tk.BOTTOM, fill=tk.X)

        self.source_text.config(yscrollcommand=self._update_scroll)
        self.line_numbers.config(yscrollcommand=v_scroll.set)
        self.source_text.config(xscrollcommand=h_scroll.set)

        # Configure tags for syntax highlighting and breakpoints
        self.source_text.tag_config("breakpoint_line", background="#ffe0e0")
        self.source_text.tag_config("current_line", background="#e0ffe0")
        self.source_text.tag_config("keyword", foreground="#0000ff")
        self.source_text.tag_config("string", foreground="#008000")
        self.source_text.tag_config("comment", foreground="#808080", font=('Consolas', 10, 'italic'))

    def _build_variables_panel(self, parent):
        """Build the variables inspection panel"""
        var_frame = ttk.LabelFrame(parent, text="Variables", padding=5)
        parent.add(var_frame, weight=1)

        # Create notebook for different variable categories
        var_notebook = ttk.Notebook(var_frame)
        var_notebook.pack(fill=tk.BOTH, expand=True)

        # Parameters tab
        params_frame = ttk.Frame(var_notebook)
        var_notebook.add(params_frame, text="Parameters")

        self.params_tree = ttk.Treeview(
            params_frame,
            columns=('value', 'type', 'location'),
            show='tree headings',
            height=6
        )
        self.params_tree.heading('#0', text='Name')
        self.params_tree.heading('value', text='Value')
        self.params_tree.heading('type', text='Type')
        self.params_tree.heading('location', text='Location')

        self.params_tree.column('#0', width=120)
        self.params_tree.column('value', width=120)
        self.params_tree.column('type', width=120)
        self.params_tree.column('location', width=100)

        self.params_tree.pack(fill=tk.BOTH, expand=True)

        # Locals tab
        locals_frame = ttk.Frame(var_notebook)
        var_notebook.add(locals_frame, text="Locals")

        self.locals_tree = ttk.Treeview(
            locals_frame,
            columns=('value', 'type', 'location'),
            show='tree headings',
            height=6
        )
        self.locals_tree.heading('#0', text='Name')
        self.locals_tree.heading('value', text='Value')
        self.locals_tree.heading('type', text='Type')
        self.locals_tree.heading('location', text='Location')

        self.locals_tree.column('#0', width=120)
        self.locals_tree.column('value', width=120)
        self.locals_tree.column('type', width=120)
        self.locals_tree.column('location', width=100)

        self.locals_tree.pack(fill=tk.BOTH, expand=True)

        # Globals tab
        globals_frame = ttk.Frame(var_notebook)
        var_notebook.add(globals_frame, text="Globals")

        # Search box for globals
        search_frame = ttk.Frame(globals_frame)
        search_frame.pack(fill=tk.X, pady=(0, 5))
        ttk.Label(search_frame, text="Search:").pack(side=tk.LEFT, padx=(0, 5))
        self.global_search = ttk.Entry(search_frame)
        self.global_search.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.global_search.bind('<KeyRelease>', self._on_global_search)

        self.globals_tree = ttk.Treeview(
            globals_frame,
            columns=('value', 'type', 'address'),
            show='tree headings',
            height=6
        )
        self.globals_tree.heading('#0', text='Name')
        self.globals_tree.heading('value', text='Value')
        self.globals_tree.heading('type', text='Type')
        self.globals_tree.heading('address', text='Address')

        self.globals_tree.column('#0', width=120)
        self.globals_tree.column('value', width=120)
        self.globals_tree.column('type', width=120)
        self.globals_tree.column('address', width=100)

        self.globals_tree.pack(fill=tk.BOTH, expand=True)

    def _build_registers_panel(self, parent):
        """Build the CPU registers panel"""
        reg_frame = ttk.LabelFrame(parent, text="MIPS Registers", padding=5)
        parent.add(reg_frame, weight=1)

        # Create treeview for registers
        self.registers_tree = ttk.Treeview(
            reg_frame,
            columns=('value', 'description'),
            show='tree headings',
            height=15
        )
        self.registers_tree.heading('#0', text='Register')
        self.registers_tree.heading('value', text='Value')
        self.registers_tree.heading('description', text='Description')

        self.registers_tree.column('#0', width=80)
        self.registers_tree.column('value', width=100)
        self.registers_tree.column('description', width=150)

        self.registers_tree.pack(fill=tk.BOTH, expand=True)

        # Scrollbar
        reg_scroll = ttk.Scrollbar(reg_frame, orient=tk.VERTICAL, command=self.registers_tree.yview)
        reg_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.registers_tree.config(yscrollcommand=reg_scroll.set)

        # Populate with MIPS register names
        self._populate_registers()

    def _build_status_bar(self, parent):
        """Build the status bar at the bottom"""
        status_frame = ttk.Frame(parent, relief=tk.SUNKEN, borderwidth=1)
        status_frame.pack(fill=tk.X, side=tk.BOTTOM, pady=(5, 0))

        self.status_label = ttk.Label(status_frame, text="Initializing debugger...")
        self.status_label.pack(side=tk.LEFT, padx=5, pady=2)

    def _initialize_debugger(self):
        """Initialize the debugger backend in a background thread"""
        self._set_status("Initializing debugger...")

        # Run initialization in background thread to avoid freezing GUI
        thread = threading.Thread(target=self._initialize_debugger_thread, daemon=True)
        thread.start()

    def _initialize_debugger_thread(self):
        """Background thread that performs heavy initialization"""
        try:
            # Initialize backend (DWARF parsing happens here - can be slow)
            success, error = self.debugger.initialize()

            if not success:
                # Schedule error dialog on main thread
                self.window.after(0, lambda: messagebox.showerror(
                    "Debugger Error",
                    f"Failed to initialize debugger:\n\n{error}"
                ))
                self.window.after(0, lambda: self._set_status(f"Error: {error}"))
                return

            # Get source files from line program
            line_program = self.debugger.source_line_cache
            if line_program:
                # Filter to only .c files (not assembly)
                self.source_files = sorted([f for f in line_program.keys() if f.endswith('.c')])

                if self.source_files:
                    # Update GUI on main thread
                    def update_file_list():
                        self.file_combo['values'] = [os.path.basename(f) for f in self.source_files]
                        self.file_combo.current(0)
                        self._load_source_file(self.source_files[0])

                    self.window.after(0, update_file_list)

            # Inject debug codecave
            success, error = self.debugger.inject_debug_codecave()
            if success and "rebuild" in error.lower():
                # Debug codecave was added, but needs rebuild
                def show_rebuild_warning():
                    messagebox.showinfo(
                        "Debug Codecave Added",
                        f"{error}\n\nIMPORTANT: You must rebuild your project before debugging will work!\n\n"
                        "The debug infrastructure has been added to your project, but it needs to be "
                        "compiled into the game. Build your project, then run the game in the emulator."
                    )
                self.window.after(0, show_rebuild_warning)
            elif not success:
                # Schedule warning on main thread
                self.window.after(0, lambda: messagebox.showwarning(
                    "Debugger Warning",
                    f"Failed to inject debug codecave:\n\n{error}\n\nDebugging may not work correctly."
                ))

            # Mark as initialized and update status on main thread
            def finish_init():
                self.initialized = True
                self._set_status("Debugger ready. Set breakpoints and start debugging.")

            self.window.after(0, finish_init)

        except Exception as e:
            # Schedule error dialog on main thread
            import traceback
            traceback.print_exc()

            def show_error():
                messagebox.showerror(
                    "Debugger Error",
                    f"Unexpected error during initialization:\n\n{e}"
                )
                self._set_status(f"Error: {e}")
                self.initialized = False

            self.window.after(0, show_error)

    def _load_source_file(self, file_path: str):
        """
        Load a source file into the editor.

        Args:
            file_path: Absolute path to source file
        """
        if not os.path.exists(file_path):
            messagebox.showerror("File Error", f"Source file not found:\n{file_path}")
            return

        self.current_source_file = file_path

        try:
            with open(file_path, 'r') as f:
                content = f.read()

            # Clear existing content
            self.source_text.config(state=tk.NORMAL)
            self.source_text.delete('1.0', tk.END)

            # Insert content
            self.source_text.insert('1.0', content)

            # Apply basic syntax highlighting
            self._apply_syntax_highlighting()

            # Update line numbers
            self._update_line_numbers()

            # Disable editing
            self.source_text.config(state=tk.DISABLED)

            # Update status
            self._set_status(f"Loaded {os.path.basename(file_path)}")

        except Exception as e:
            messagebox.showerror("File Error", f"Failed to load source file:\n\n{e}")

    def _apply_syntax_highlighting(self):
        """Apply basic syntax highlighting to the source code"""
        # Simple keyword highlighting for C
        keywords = [
            'void', 'int', 'char', 'float', 'double', 'bool', 'short', 'long', 'unsigned', 'signed',
            'if', 'else', 'while', 'for', 'do', 'switch', 'case', 'break', 'continue', 'return',
            'struct', 'union', 'enum', 'typedef', 'sizeof', 'const', 'static', 'extern', 'volatile',
            'register', 'auto', 'goto', 'default'
        ]

        content = self.source_text.get('1.0', tk.END)

        # Highlight keywords
        for keyword in keywords:
            start = '1.0'
            while True:
                pos = self.source_text.search(f'\\m{keyword}\\M', start, tk.END, regexp=True)
                if not pos:
                    break
                end = f"{pos}+{len(keyword)}c"
                self.source_text.tag_add('keyword', pos, end)
                start = end

        # Highlight strings (simple - just double quotes)
        start = '1.0'
        while True:
            start_pos = self.source_text.search('"', start, tk.END)
            if not start_pos:
                break
            end_pos = self.source_text.search('"', f"{start_pos}+1c", tk.END)
            if not end_pos:
                break
            self.source_text.tag_add('string', start_pos, f"{end_pos}+1c")
            start = f"{end_pos}+1c"

        # Highlight comments (// and /* */)
        lines = content.split('\n')
        for i, line in enumerate(lines, 1):
            # Single-line comments
            if '//' in line:
                comment_start = line.index('//')
                self.source_text.tag_add('comment', f"{i}.{comment_start}", f"{i}.end")

    def _update_line_numbers(self):
        """Update the line numbers display"""
        self.line_numbers.config(state=tk.NORMAL)
        self.line_numbers.delete('1.0', tk.END)

        # Get number of lines
        line_count = int(self.source_text.index('end-1c').split('.')[0])

        # Generate line numbers
        line_nums = '\n'.join(str(i) for i in range(1, line_count + 1))
        self.line_numbers.insert('1.0', line_nums)

        # Highlight lines with breakpoints
        for line_num, bp in self.line_to_breakpoint.items():
            if bp.enabled:
                self.line_numbers.tag_add('breakpoint', f"{line_num}.0", f"{line_num}.end")

        self.line_numbers.config(state=tk.DISABLED)

    def _populate_registers(self):
        """Populate the register list with MIPS register names"""
        register_info = [
            ("$zero", "Always 0"),
            ("$at", "Assembler temporary"),
            ("$v0", "Return value 0"),
            ("$v1", "Return value 1"),
            ("$a0", "Argument 0"),
            ("$a1", "Argument 1"),
            ("$a2", "Argument 2"),
            ("$a3", "Argument 3"),
            ("$t0", "Temporary 0"),
            ("$t1", "Temporary 1"),
            ("$t2", "Temporary 2"),
            ("$t3", "Temporary 3"),
            ("$t4", "Temporary 4"),
            ("$t5", "Temporary 5"),
            ("$t6", "Temporary 6"),
            ("$t7", "Temporary 7"),
            ("$s0", "Saved 0"),
            ("$s1", "Saved 1"),
            ("$s2", "Saved 2"),
            ("$s3", "Saved 3"),
            ("$s4", "Saved 4"),
            ("$s5", "Saved 5"),
            ("$s6", "Saved 6"),
            ("$s7", "Saved 7"),
            ("$t8", "Temporary 8"),
            ("$t9", "Temporary 9"),
            ("$k0", "Kernel 0"),
            ("$k1", "Kernel 1"),
            ("$gp", "Global pointer"),
            ("$sp", "Stack pointer"),
            ("$fp", "Frame pointer"),
            ("$ra", "Return address"),
        ]

        for reg_name, description in register_info:
            self.registers_tree.insert('', tk.END, text=reg_name, values=("0x00000000", description))

    def _on_line_number_click(self, event):
        """Handle click on line numbers to toggle breakpoints"""
        # Get line number at click position
        index = self.line_numbers.index(f"@{event.x},{event.y}")
        line_num = int(index.split('.')[0])

        # Debug: print what line was clicked
        print(f"[Debugger] Clicked line number widget at index: {index}, extracted line: {line_num}")

        # Toggle breakpoint
        self._toggle_breakpoint(line_num)

    def _toggle_breakpoint(self, line_num: int):
        """
        Toggle a breakpoint at the specified line.

        Args:
            line_num: Line number (1-based)
        """
        if not self.current_source_file:
            return

        # Check if breakpoint already exists
        if line_num in self.line_to_breakpoint:
            # Remove breakpoint
            bp = self.line_to_breakpoint[line_num]
            success, error = self.debugger.remove_breakpoint(bp.bp_id)

            if success:
                del self.line_to_breakpoint[line_num]
                self.source_text.tag_remove('breakpoint_line', f"{line_num}.0", f"{line_num}.end")
                self._update_line_numbers()
                self._set_status(f"Removed breakpoint at line {line_num}")
            else:
                messagebox.showerror("Breakpoint Error", f"Failed to remove breakpoint:\n\n{error}")
        else:
            # Add breakpoint
            print(f"[Debugger] Adding breakpoint at {os.path.basename(self.current_source_file)}:{line_num}")
            bp, error = self.debugger.add_breakpoint(self.current_source_file, line_num)

            if bp:
                print(f"[Debugger] Breakpoint created: ID={bp.bp_id}, address=0x{bp.location.assembly_address:08X}")
                # Enable it immediately (this writes to emulator memory)
                success, error = self.debugger.enable_breakpoint(bp.bp_id)

                if success:
                    self.line_to_breakpoint[line_num] = bp
                    self.source_text.tag_add('breakpoint_line', f"{line_num}.0", f"{line_num}.end")
                    self._update_line_numbers()
                    self._set_status(f"Added breakpoint at line {line_num} (address: 0x{bp.location.assembly_address:08X})")
                    print(f"[Debugger] Breakpoint enabled and injected to emulator memory")
                else:
                    messagebox.showerror("Breakpoint Error", f"Failed to enable breakpoint:\n\n{error}")
                    print(f"[Debugger] Failed to enable breakpoint: {error}")
            else:
                print(f"[Debugger] Failed to create breakpoint: {error}")
                messagebox.showwarning("Breakpoint Warning", f"Cannot set breakpoint at line {line_num}:\n\n{error}")

    # Event handlers
    def _on_file_selected(self, event):
        """Handle file selection from combo box"""
        selected_idx = self.file_combo.current()
        if 0 <= selected_idx < len(self.source_files):
            self._load_source_file(self.source_files[selected_idx])

    def _on_continue(self):
        """Handle Continue button"""
        success, error = self.debugger.resume_execution()
        if success:
            self._set_status("Execution resumed")
            # Clear register/variable views
            self._clear_runtime_data()
        else:
            messagebox.showerror("Resume Error", f"Failed to resume:\n\n{error}")

    def _on_step_over(self):
        """Handle Step Over button"""
        self._set_status("Stepping over...")
        # TODO: Implement step over logic

    def _on_step_into(self):
        """Handle Step Into button"""
        self._set_status("Stepping into...")
        # TODO: Implement step into logic

    def _on_step_out(self):
        """Handle Step Out button"""
        self._set_status("Stepping out...")
        # TODO: Implement step out logic

    def _on_debug_mode_toggle(self):
        """Handle debug mode checkbox toggle"""
        enabled = self.debug_mode_var.get()
        self.project_data.GetCurrentBuildVersion().SetDebugMode(enabled)

        if enabled:
            self._set_status("Debug mode enabled (-O0). Recompile for best debugging experience.")
        else:
            self._set_status("Debug mode disabled. Using normal compiler flags.")

    def _on_global_search(self, event):
        """Handle global variable search"""
        search_text = self.global_search.get().lower()

        # TODO: Filter globals based on search text

    def _on_scroll(self, *args):
        """Handle scrolling of source code and line numbers together"""
        self.source_text.yview(*args)
        self.line_numbers.yview(*args)

    def _update_scroll(self, *args):
        """Update scrollbar and sync line numbers"""
        self.line_numbers.yview_moveto(args[0])
        # The scrollbar will be updated by the caller

    def _set_status(self, message: str):
        """Update the status bar"""
        self.status_label.config(text=message)

    def show(self):
        """Show the debugger window"""
        self.window.deiconify()
        self.window.lift()
        self.window.focus_force()

        # Initialize debugger after window is shown (non-blocking)
        # Use after() to defer initialization so window appears first
        # Only initialize once
        if not self.initialized:
            self.window.after(100, self._initialize_debugger)

        # Start polling loop if not already running
        if not self.polling:
            self.polling = True
            self._poll_breakpoints()

    def _poll_breakpoints(self):
        """Poll for breakpoint hits (runs periodically)"""
        if not self.polling or not self.initialized:
            return

        try:
            # Check if a breakpoint was hit
            bp = self.debugger.poll_breakpoint_hit()
            if bp:
                print(f"[Debugger] Breakpoint hit! ID={bp.bp_id}, line={bp.location.line_number}")
                self._on_breakpoint_hit(bp)

        except Exception as e:
            print(f"[Debugger] Polling error: {e}")

        # Schedule next poll
        if self.polling:
            self.window.after(self.polling_interval, self._poll_breakpoints)

    def _on_breakpoint_hit(self, bp: Breakpoint):
        """Handle when a breakpoint is hit"""
        # Update status
        self._set_status(f"Breakpoint hit at line {bp.location.line_number} (hits: {bp.hit_count})")

        # Read and display registers
        registers = self.debugger.get_register_values()
        self._update_registers(registers)

        # TODO: Read and display variables
        self._update_variables()

        # Flash the breakpoint line
        self.source_text.tag_configure('breakpoint_hit', background='#FFD700')
        self.source_text.tag_add('breakpoint_hit', f"{bp.location.line_number}.0", f"{bp.location.line_number}.end")

    def _update_registers(self, registers: dict):
        """Update the register tree view with values"""
        # Clear existing values
        for item in self.registers_tree.get_children():
            reg_name = self.registers_tree.item(item, 'text')
            if reg_name in registers:
                value = registers[reg_name]
                self.registers_tree.item(item, values=(f"0x{value:08X}", self.registers_tree.item(item, 'values')[1]))

    def _update_variables(self):
        """Update the variable tree views"""
        try:
            # Get all variable values from debugger
            variables = self.debugger.get_variable_values()

            if not variables:
                print("[Debugger GUI] No variables returned from debugger")
                return

            print(f"[Debugger GUI] Got {len(variables)} variables")

            # Clear existing entries
            for tree in [self.params_tree, self.locals_tree, self.globals_tree]:
                tree.delete(*tree.get_children())

            # Variables are returned as: name -> (type_name, value, location, is_parameter, is_global)
            for var_name, (type_name, value, location, is_parameter, is_global) in variables.items():
                # Format value as hex
                value_str = f"0x{value:08X}"

                # Determine which tree to add to based on flags
                if is_global:
                    tree = self.globals_tree
                elif is_parameter:
                    tree = self.params_tree
                else:
                    tree = self.locals_tree

                # Add to appropriate tree
                tree.insert('', 'end', text=var_name, values=(value_str, type_name, location))

            print(f"[Debugger GUI] Updated variable displays")

        except Exception as e:
            print(f"[Debugger GUI] Error updating variables: {e}")
            import traceback
            traceback.print_exc()

    def _clear_runtime_data(self):
        """Clear register and variable displays"""
        # Reset registers to zero
        for item in self.registers_tree.get_children():
            self.registers_tree.item(item, values=("0x00000000", self.registers_tree.item(item, 'values')[1]))

        # Clear variables
        for tree in [self.params_tree, self.locals_tree, self.globals_tree]:
            tree.delete(*tree.get_children())

        # Remove breakpoint hit highlighting
        self.source_text.tag_remove('breakpoint_hit', '1.0', tk.END)

    def close(self):
        """Close the debugger window"""
        # Stop polling
        self.polling = False

        # Shutdown debugger backend
        self.debugger.shutdown()

        # Destroy window
        self.window.destroy()
