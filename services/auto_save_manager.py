import threading
import time
from typing import Optional
from classes.project_data.project_data import ProjectData
from services.project_serializer import ProjectSerializer
from functions.verbose_print import verbose_print

class AutoSaveManager:
    """
    Manages automatic saving of project data.
    Saves immediately when changes are detected, with optional debouncing.
    """
    
    def __init__(self, project_data: ProjectData, debounce_seconds: float = 0.3):
        self.project_data = project_data
        self.debounce_seconds = debounce_seconds
        self.is_running = False
        self.save_pending = False
        self.last_save_time = 0
        self.save_thread: Optional[threading.Thread] = None
        self.lock = threading.Lock()
    
    def start(self):
        """Start the auto-save manager"""
        self.is_running = True
        verbose_print(" Auto-save enabled (saves after changes)")
    
    def stop(self):
        """Stop and perform final save"""
        self.is_running = False
        if self.save_pending:
            self.save_now()
        print(" Auto-save stopped")
    
    def mark_dirty(self, immediate: bool = False):
        """
        Mark project as having unsaved changes.
        
        Args:
            immediate: If True, save immediately without debouncing.
                      Use for button clicks, selections, etc.
                      If False, use debounce (good for text input).
        """
        if not self.is_running:
            return
        
        if immediate:
            # Save right now (but in background thread to not block UI)
            if self.save_thread is None or not self.save_thread.is_alive():
                self.save_thread = threading.Thread(target=self.save_now, daemon=True)
                self.save_thread.start()
        else:
            # Debounced save
            with self.lock:
                self.save_pending = True
                
                # If no save thread is running, start one
                if self.save_thread is None or not self.save_thread.is_alive():
                    self.save_thread = threading.Thread(target=self._debounced_save, daemon=True)
                    self.save_thread.start()
    
    def save_now(self):
        """Immediately save the project (blocking)"""
        if self.project_data:
            success = ProjectSerializer.save_project(self.project_data)
            if success:
                self.save_pending = False
                self.last_save_time = time.time()
                print(" Project auto-saved")
            return success
        return False
    
    def _debounced_save(self):
        """
        Wait for debounce period, then save if still dirty.
        This prevents rapid successive saves when user makes multiple quick changes.
        """
        time.sleep(self.debounce_seconds)
        
        with self.lock:
            if self.save_pending and self.is_running:
                self.save_now()