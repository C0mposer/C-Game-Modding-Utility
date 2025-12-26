"""
Messagebox wrapper that centers dialogs over DPG viewport
"""

import tkinter as tk
from tkinter import messagebox
import dearpygui.dearpygui as dpg


def _keep_on_top(window):
    """Keep window on top and focused"""
    try:
        if window.winfo_exists():
            window.lift()
            window.focus_force()
            window.after(100, lambda: _keep_on_top(window))
    except:
        pass


def _create_positioned_parent():
    """Create a tiny parent window at viewport center for messagebox positioning"""
    viewport_pos = dpg.get_viewport_pos()
    viewport_width = dpg.get_viewport_client_width()
    viewport_height = dpg.get_viewport_client_height()

    center_x = viewport_pos[0] + viewport_width // 2
    center_y = viewport_pos[1] + viewport_height // 2

    root = tk.Tk()
    root.overrideredirect(True)
    root.attributes('-topmost', True)
    root.geometry(f"1x1+{center_x}+{center_y}")
    root.configure(bg='white')

    root.update_idletasks()
    root.update()

    return root


def showinfo(title, message, parent=None):
    """Show info messagebox centered over DPG viewport"""
    if parent is None:
        root = _create_positioned_parent()
        result = messagebox.showinfo(title, message, parent=root)
        root.destroy()
        return result
    else:
        return messagebox.showinfo(title, message, parent=parent)


def showerror(title, message, parent=None):
    """Show error messagebox centered over DPG viewport"""
    if parent is None:
        root = _create_positioned_parent()
        result = messagebox.showerror(title, message, parent=root)
        root.destroy()
        return result
    else:
        return messagebox.showerror(title, message, parent=parent)


def showwarning(title, message, parent=None):
    """Show warning messagebox centered over DPG viewport"""
    if parent is None:
        root = _create_positioned_parent()
        result = messagebox.showwarning(title, message, parent=root)
        root.destroy()
        return result
    else:
        return messagebox.showwarning(title, message, parent=parent)


def askyesno(title, message, parent=None):
    """Show yes/no messagebox centered over DPG viewport"""
    if parent is None:
        root = _create_positioned_parent()
        result = messagebox.askyesno(title, message, parent=root)
        root.destroy()
        return result
    else:
        return messagebox.askyesno(title, message, parent=parent)


def askokcancel(title, message, parent=None):
    """Show ok/cancel messagebox centered over DPG viewport"""
    if parent is None:
        root = _create_positioned_parent()
        result = messagebox.askokcancel(title, message, parent=root)
        root.destroy()
        return result
    else:
        return messagebox.askokcancel(title, message, parent=parent)


def askyesnocancel(title, message, parent=None):
    """Show yes/no/cancel messagebox centered over DPG viewport"""
    if parent is None:
        root = _create_positioned_parent()
        result = messagebox.askyesnocancel(title, message, parent=root)
        root.destroy()
        return result
    else:
        return messagebox.askyesnocancel(title, message, parent=parent)


def askretrycancel(title, message, parent=None):
    """Show retry/cancel messagebox centered over DPG viewport"""
    if parent is None:
        root = _create_positioned_parent()
        result = messagebox.askretrycancel(title, message, parent=root)
        root.destroy()
        return result
    else:
        return messagebox.askretrycancel(title, message, parent=parent)
