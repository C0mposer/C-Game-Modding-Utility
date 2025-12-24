import os
from typing import List, Dict, Optional, Tuple
from classes.project_data.project_data import ProjectData

class SizeAnalysisResult:
    """Represents size analysis for a single injection target"""
    def __init__(self, name: str, used_bytes: int, allocated_bytes: int, injection_type: str):
        self.name = name
        self.used_bytes = used_bytes
        self.allocated_bytes = allocated_bytes
        self.injection_type = injection_type  # "codecave", "hook", "binary_patch"
        
    @property
    def percentage_used(self) -> float:
        """Calculate percentage of space used"""
        if self.allocated_bytes == 0:
            return 0.0
        return (self.used_bytes / self.allocated_bytes) * 100.0
    
    @property
    def remaining_bytes(self) -> int:
        """Calculate remaining free space"""
        return self.allocated_bytes - self.used_bytes
    
    @property
    def is_overflow(self) -> bool:
        """Check if code exceeds allocated space"""
        return self.used_bytes > self.allocated_bytes
    
    @property
    def warning_level(self) -> str:
        """Get warning level: safe, warning, critical, overflow"""
        if self.is_overflow:
            return "overflow"
        elif self.percentage_used >= 90:
            return "critical"
        elif self.percentage_used >= 75:
            return "warning"
        else:
            return "safe"


class SizeAnalyzerService:
    """Analyzes compiled code sizes and compares to allocated space"""
    
    def __init__(self, project_data: ProjectData):
        self.project_data = project_data
    
    def analyze_all(self) -> List[SizeAnalysisResult]:
        """
        Analyze all codecaves, hooks, and binary patches.
        Returns list of analysis results.
        """
        results = []
        
        current_build = self.project_data.GetCurrentBuildVersion()
        project_folder = self.project_data.GetProjectFolder()
        bin_dir = os.path.join(project_folder, '.config', 'output', 'bin_files')
        
        # Check if bin directory exists
        if not os.path.exists(bin_dir):
            return results  # No compiled binaries yet
        
        # Analyze codecaves
        for codecave in current_build.GetEnabledCodeCaves():
            result = self._analyze_injection_target(codecave, bin_dir, "codecave")
            if result:
                results.append(result)
        
        # Analyze hooks
        for hook in current_build.GetEnabledHooks():
            result = self._analyze_injection_target(hook, bin_dir, "hook")
            if result:
                results.append(result)
        
        # Analyze binary patches
        for patch in current_build.GetEnabledBinaryPatches():
            result = self._analyze_injection_target(patch, bin_dir, "binary_patch")
            if result:
                results.append(result)
        
        return results
    
    def _analyze_injection_target(self, target, bin_dir: str, injection_type: str) -> Optional[SizeAnalysisResult]:
        """Analyze a single injection target"""
        name = target.GetName()
        
        # Get allocated size
        size_str = target.GetSize()
        if not size_str or size_str == '0' or size_str == '0x0' or size_str.lower() == 'none':
            return None  # Don't analyze if user didn't set a size
        
        try:
            allocated_bytes = int(size_str, 16)
        except ValueError:
            return None  # Invalid size format
        
        # Get actual binary size
        bin_file = os.path.join(bin_dir, f"{name}.bin")
        if not os.path.exists(bin_file):
            return None  # Binary not compiled yet
        
        used_bytes = os.path.getsize(bin_file)
        
        return SizeAnalysisResult(name, used_bytes, allocated_bytes, injection_type)
    
    def get_summary(self) -> Dict[str, any]:
        """Get overall summary statistics"""
        results = self.analyze_all()
        
        if not results:
            return {
                'total_count': 0,
                'total_used': 0,
                'total_allocated': 0,
                'overflow_count': 0,
                'warning_count': 0,
                'critical_count': 0
            }
        
        total_used = sum(r.used_bytes for r in results)
        total_allocated = sum(r.allocated_bytes for r in results)
        overflow_count = sum(1 for r in results if r.is_overflow)
        warning_count = sum(1 for r in results if r.warning_level == "warning")
        critical_count = sum(1 for r in results if r.warning_level == "critical")
        
        return {
            'total_count': len(results),
            'total_used': total_used,
            'total_allocated': total_allocated,
            'overflow_count': overflow_count,
            'warning_count': warning_count,
            'critical_count': critical_count,
            'percentage_used': (total_used / total_allocated * 100.0) if total_allocated > 0 else 0.0
        }