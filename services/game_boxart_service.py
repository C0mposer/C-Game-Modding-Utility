import os
import requests
from typing import Optional
from classes.project_data.project_data import ProjectData
from functions.verbose_print import verbose_print
from services.game_metadata_service import GameMetadataService


class GameBoxartService:
    @staticmethod
    def get_boxart_path(project_data: ProjectData) -> str:
        project_folder = project_data.GetProjectFolder()
        config_folder = os.path.join(project_folder, '.config')

        # Ensure .config folder exists
        os.makedirs(config_folder, exist_ok=True)

        return os.path.join(config_folder, 'game.jpg')

    @staticmethod
    def download_boxart(project_data: ProjectData) -> bool:
        boxart_path = GameBoxartService.get_boxart_path(project_data)

        # If box art already exists, don't download again
        if os.path.exists(boxart_path):
            verbose_print(f" Box art already exists: {boxart_path}")
            return True

        current_build = project_data.GetCurrentBuildVersion()
        platform = current_build.GetPlatform()

        game_identifier = None
        url = None
        
        
        # Shoutout the lovely people who have painstakingly uploaded every game cover with consistent formatting :)
        if platform == "PS1":
            game_identifier = GameMetadataService.get_ps1_game_id(current_build)
            if game_identifier:
                url = f'https://raw.githubusercontent.com/xlenore/psx-covers/main/covers/default/{game_identifier}.jpg'
                print(f"  PS1 Game ID: {game_identifier}")

        elif platform == "PS2":
            game_identifier = GameMetadataService.get_ps2_game_id(current_build)
            if game_identifier:
                url = f'https://raw.githubusercontent.com/xlenore/ps2-covers/main/covers/default/{game_identifier}.jpg'

        elif platform == "Gamecube":
            game_identifier = GameMetadataService.get_gamecube_game_id(current_build)
            if game_identifier:
                url = f'https://ia601900.us.archive.org/20/items/coversdb-gc/{game_identifier}.png'

        elif platform == "Wii":
            game_identifier = GameMetadataService.get_wii_game_id(current_build)
            if game_identifier:
                url = f'https://ia803209.us.archive.org/15/items/coversdb-wii/{game_identifier}.png'

        if not url:
            print(f"Could not determine game identifier for {platform}. ID: {game_identifier}")
            return False

        try:
            verbose_print(f"Downloading box art from: {url}")
            response = requests.get(url, timeout=10)

            if response.status_code == 200:
                with open(boxart_path, 'wb') as f:
                    f.write(response.content)
                verbose_print(f"Box art downloaded successfully")
                return True
            else:
                verbose_print(f"Box art not found (HTTP {response.status_code})")
                return False

        except Exception as e:
            verbose_print(f"Failed to download box art: {e}")
            return False

    @staticmethod
    def has_boxart(project_data: ProjectData) -> bool:
        boxart_path = GameBoxartService.get_boxart_path(project_data)
        return os.path.exists(boxart_path)
