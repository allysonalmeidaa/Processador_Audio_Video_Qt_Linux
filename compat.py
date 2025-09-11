# compat.py - Funções de compatibilidade multiplataforma
import os
import sys
import platform
import subprocess

def is_windows():
    return platform.system() == "Windows"

def is_linux():
    return platform.system() == "Linux"

def get_subprocess_config():
    """Retorna a configuração adequada para subprocess em cada plataforma"""
    kwargs = {}
    if is_windows():
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        kwargs['creationflags'] = subprocess.CREATE_NO_WINDOW
        kwargs['startupinfo'] = startupinfo
    return kwargs

def run_subprocess(cmd, **extra_kwargs):
    """Executa um comando de forma compatível entre plataformas"""
    kwargs = get_subprocess_config()
    kwargs.update(extra_kwargs)
    return subprocess.run(cmd, **kwargs)

def get_app_dir():
    """Retorna o diretório do aplicativo de forma consistente"""
    if getattr(sys, 'frozen', False):
        base_dir = os.path.dirname(sys.executable)
    else:
        base_dir = os.path.dirname(os.path.abspath(__file__))
    app_dir = os.path.join(base_dir, "ProcessadorDeAudioVideo")
    if not os.path.exists(app_dir):
        os.makedirs(app_dir, exist_ok=True)
    return app_dir