"""
Settings management for Earth Engine authentication.
Stores settings persistently on C: drive (or user's AppData).
"""
import os
import json
import logging
from pathlib import Path

# Settings file location - use AppData\Local for user-specific settings
if os.name == 'nt':  # Windows
    SETTINGS_DIR = Path(os.environ.get('LOCALAPPDATA', os.path.expanduser('~'))) / 'GEE_Downloader'
else:
    SETTINGS_DIR = Path.home() / '.gee_downloader'

SETTINGS_FILE = SETTINGS_DIR / 'settings.json'

# Ensure settings directory exists
SETTINGS_DIR.mkdir(parents=True, exist_ok=True)


def load_settings():
    """Load settings from persistent storage."""
    if not SETTINGS_FILE.exists():
        return {}
    
    try:
        with open(SETTINGS_FILE, 'r') as f:
            settings = json.load(f)
        logging.info(f"Settings loaded from {SETTINGS_FILE}")
        return settings
    except Exception as e:
        logging.warning(f"Failed to load settings: {e}")
        return {}


def save_settings(service_account_key: str = None, project_id: str = None, 
                  bbox: str = None, start_date: str = None, end_date: str = None,
                  output_folder: str = None, max_tiles: str = None):
    """Save settings to persistent storage."""
    settings = load_settings()
    
    if service_account_key is not None:
        # Store absolute path
        if service_account_key and os.path.exists(service_account_key):
            settings['service_account_key'] = os.path.abspath(service_account_key)
        elif service_account_key == "":
            # Clear it if empty string
            settings.pop('service_account_key', None)
        else:
            settings['service_account_key'] = service_account_key
    
    if project_id is not None:
        if project_id:
            settings['project_id'] = project_id
        else:
            settings.pop('project_id', None)
    
    # Save application parameters
    if bbox is not None:
        if bbox:
            settings['bbox'] = bbox
        else:
            settings.pop('bbox', None)
    
    if start_date is not None:
        if start_date:
            settings['start_date'] = start_date
        else:
            settings.pop('start_date', None)
    
    if end_date is not None:
        if end_date:
            settings['end_date'] = end_date
        else:
            settings.pop('end_date', None)
    
    if output_folder is not None:
        if output_folder:
            settings['output_folder'] = os.path.abspath(output_folder) if output_folder else None
        else:
            settings.pop('output_folder', None)
    
    if max_tiles is not None:
        if max_tiles:
            settings['max_tiles'] = max_tiles
        else:
            settings.pop('max_tiles', None)
    
    try:
        with open(SETTINGS_FILE, 'w') as f:
            json.dump(settings, f, indent=2)
        logging.info(f"Settings saved to {SETTINGS_FILE}")
        return True
    except Exception as e:
        logging.error(f"Failed to save settings: {e}")
        return False


def get_service_account_key():
    """Get service account key path from settings."""
    settings = load_settings()
    key_path = settings.get('service_account_key')
    if key_path and os.path.exists(key_path):
        return key_path
    return None


def get_project_id():
    """Get project ID from settings."""
    settings = load_settings()
    return settings.get('project_id')


def clear_settings():
    """Clear all settings."""
    try:
        if SETTINGS_FILE.exists():
            SETTINGS_FILE.unlink()
        logging.info("Settings cleared")
        return True
    except Exception as e:
        logging.error(f"Failed to clear settings: {e}")
        return False

