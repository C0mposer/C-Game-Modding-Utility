import json
import os
from typing import List, Dict, Optional
from dataclasses import dataclass
import time

@dataclass
class RecentProject:
    path: str
    name: str
    platform: str
    timestamp: float

class RecentProjectsService:
    """Manages the list of recently opened projects"""

    MAX_RECENT = 10
    CONFIG_FILE = os.path.join(os.getcwd(), ".modtool", "recent_projects.json")

    @staticmethod
    def _ensure_config_dir():
        """Ensure config directory exists"""
        config_dir = os.path.dirname(RecentProjectsService.CONFIG_FILE)
        if not os.path.exists(config_dir):
            os.makedirs(config_dir, exist_ok=True)

    @staticmethod
    def add_recent_project(file_path: str, project_name: str, platform: str):
        """Add project to recent list (or move to top if already exists)"""
        projects = RecentProjectsService.get_recent_projects()

        # Normalize the path for comparison (absolute + case-normalized)
        normalized_path = os.path.normcase(os.path.abspath(file_path))

        # Remove if already in list (using normalized path comparison)
        projects = [p for p in projects if os.path.normcase(os.path.abspath(p.path)) != normalized_path]

        # Add to front (store the absolute path)
        projects.insert(0, RecentProject(
            path=os.path.abspath(file_path),
            name=project_name,
            platform=platform,
            timestamp=time.time()
        ))

        # Keep only MAX_RECENT
        projects = projects[:RecentProjectsService.MAX_RECENT]

        # Save
        RecentProjectsService._save_projects(projects)

    @staticmethod
    def get_recent_projects() -> List[RecentProject]:
        """Get list of recent projects, filtered to only existing files"""
        projects = RecentProjectsService._load_projects()

        # Filter out non-existent files
        valid_projects = [p for p in projects if os.path.exists(p.path)]

        # Deduplicate using normalized paths (keeps first occurrence)
        seen = set()
        deduped = []
        for p in valid_projects:
            normalized = os.path.normcase(os.path.abspath(p.path))
            if normalized not in seen:
                seen.add(normalized)
                # Update the path to be absolute if it was relative
                p.path = os.path.abspath(p.path)
                deduped.append(p)

        # Save if list changed (removed non-existent or duplicates)
        if len(deduped) != len(projects):
            RecentProjectsService._save_projects(deduped)

        return deduped

    @staticmethod
    def remove_recent_project(file_path: str):
        """Remove specific project from recent list"""
        projects = RecentProjectsService.get_recent_projects()
        normalized_path = os.path.normcase(os.path.abspath(file_path))
        projects = [p for p in projects if os.path.normcase(os.path.abspath(p.path)) != normalized_path]
        RecentProjectsService._save_projects(projects)

    @staticmethod
    def clear_recent_projects():
        """Clear all recent projects"""
        RecentProjectsService._save_projects([])

    @staticmethod
    def _load_projects() -> List[RecentProject]:
        """Load projects from JSON file"""
        if not os.path.exists(RecentProjectsService.CONFIG_FILE):
            return []

        try:
            with open(RecentProjectsService.CONFIG_FILE, 'r') as f:
                data = json.load(f)
                return [
                    RecentProject(**p) for p in data.get('recent_projects', [])
                ]
        except Exception as e:
            print(f"Error loading recent projects: {e}")
            return []

    @staticmethod
    def _save_projects(projects: List[RecentProject]):
        """Save projects to JSON file"""
        RecentProjectsService._ensure_config_dir()

        try:
            data = {
                'recent_projects': [
                    {
                        'path': p.path,
                        'name': p.name,
                        'platform': p.platform,
                        'timestamp': p.timestamp
                    }
                    for p in projects
                ]
            }

            with open(RecentProjectsService.CONFIG_FILE, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"Error saving recent projects: {e}")
