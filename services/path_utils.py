import os
from typing import Optional, List

class PathUtils:
    """Utilities for converting between absolute and relative paths for project portability"""

    @staticmethod
    def make_relative_if_in_project(absolute_path: Optional[str], project_folder: str) -> Optional[str]:
        """
        Convert absolute path to relative if it's within the project folder.
        Returns relative path starting with './' if in project, otherwise returns absolute path unchanged.

        Args:
            absolute_path: The absolute path to convert
            project_folder: The project root folder

        Returns:
            Relative path (starting with './') if in project folder, otherwise absolute path
        """
        if not absolute_path or not project_folder:
            return absolute_path

        try:
            # Normalize paths for comparison
            abs_path_normalized = os.path.normpath(os.path.abspath(absolute_path))
            project_normalized = os.path.normpath(os.path.abspath(project_folder))

            # Check if the file is within the project directory
            if abs_path_normalized.startswith(project_normalized + os.sep):
                # Get relative path from project root
                rel_path = os.path.relpath(abs_path_normalized, project_normalized)
                # Convert to forward slashes and add ./ prefix for clarity
                rel_path = './' + rel_path.replace('\\', '/')
                return rel_path
            else:
                # File is outside project, keep absolute path
                return absolute_path

        except (ValueError, OSError):
            # If any error occurs, return the original path
            return absolute_path

    @staticmethod
    def make_absolute_if_relative(path: Optional[str], project_folder: str) -> Optional[str]:
        """
        Convert relative path to absolute if it starts with './'.
        Returns absolute path if relative, otherwise returns path unchanged.

        Args:
            path: The path to convert (may be relative or absolute)
            project_folder: The project root folder

        Returns:
            Absolute path if input was relative, otherwise original path
        """
        if not path or not project_folder:
            return path

        try:
            # Check if path is already absolute
            if os.path.isabs(path):
                return path

            # Normalize path separators
            path_normalized = path.replace('/', os.sep).replace('\\', os.sep)
            project_folder_normalized = os.path.normpath(project_folder)
            project_folder_basename = os.path.basename(project_folder_normalized)

            # Check if path is relative (starts with ./ or .\)
            if path.startswith('./') or path.startswith('.\\'):
                # Remove the ./ prefix
                rel_path = path_normalized[2:]
                # Join with project folder to get absolute path
                abs_path = os.path.normpath(os.path.join(project_folder_normalized, rel_path))
                return abs_path

            # Check if path contains the project folder as part of it (e.g., "projects\ps2aht\src\main.c")
            # This handles old-style paths that included the project folder in the relative path
            if os.sep + project_folder_basename + os.sep in path_normalized or \
               path_normalized.startswith(project_folder_basename + os.sep):
                # Find where the project folder name starts in the path
                if path_normalized.startswith(project_folder_basename + os.sep):
                    # Strip the project folder part from the beginning
                    rel_path = path_normalized[len(project_folder_basename) + 1:]
                else:
                    # Find and strip everything up to and including the project folder name
                    idx = path_normalized.find(os.sep + project_folder_basename + os.sep)
                    rel_path = path_normalized[idx + len(os.sep + project_folder_basename + os.sep):]

                # Join with project folder to get absolute path
                abs_path = os.path.normpath(os.path.join(project_folder_normalized, rel_path))
                return abs_path
            else:
                # Path is relative and doesn't contain project folder - join directly
                abs_path = os.path.normpath(os.path.join(project_folder_normalized, path_normalized))
                return abs_path

        except (ValueError, OSError):
            # If any error occurs, return the original path
            return path

    @staticmethod
    def convert_paths_to_relative(paths: List[str], project_folder: str) -> List[str]:
        """
        Convert a list of absolute paths to relative paths if they're in the project folder.

        Args:
            paths: List of absolute paths
            project_folder: The project root folder

        Returns:
            List with paths converted to relative where applicable
        """
        return [PathUtils.make_relative_if_in_project(p, project_folder) for p in paths]

    @staticmethod
    def convert_paths_to_absolute(paths: List[str], project_folder: str) -> List[str]:
        """
        Convert a list of relative paths to absolute paths.

        Args:
            paths: List of paths (may be relative or absolute)
            project_folder: The project root folder

        Returns:
            List with relative paths converted to absolute
        """
        return [PathUtils.make_absolute_if_relative(p, project_folder) for p in paths]
