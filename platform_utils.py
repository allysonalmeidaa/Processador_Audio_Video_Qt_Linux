# platform_utils.py
import os
import sys
import platform

def is_windows():
    return platform.system() == "Windows"

def is_linux():
    return platform.system() == "Linux"

def get_platform_config():
    """Retorna configurações específicas da plataforma"""
    config = {
        'is_windows': is_windows(),
        'is_linux': is_linux(),
        'temp_dir': None,
        'ffmpeg_bin': None,
        'subprocess_flags': {}
    }
    
    if is_windows():
        import subprocess
        config['temp_dir'] = os.environ.get('TEMP', os.environ.get('TMP', 'C:\\Temp'))
        config['ffmpeg_bin'] = 'ffmpeg.exe'
        config['subprocess_flags'] = {
            'creationflags': subprocess.CREATE_NO_WINDOW,
            'startupinfo': subprocess.STARTUPINFO()
        }
    else:
        config['temp_dir'] = '/tmp'
        config['ffmpeg_bin'] = 'ffmpeg'
        config['subprocess_flags'] = {}
    
    return config

def safe_import(module_name):
    """Importação segura que funciona em ambas as plataformas"""
    try:
        import importlib
        return importlib.import_module(module_name)
    except ImportError:
        return None
    except Exception as e:
        print(f"Erro ao importar {module_name}: {e}")
        return None