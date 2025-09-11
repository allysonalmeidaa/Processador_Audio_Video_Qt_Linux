import os
import sys
import shutil
import platform
from PyQt6.QtWidgets import QMessageBox
from logs_tab import adicionar_log
from yt_dlp_import import get_yt_dlp
from platform_utils import get_platform_config

def get_app_dir():
    if getattr(sys, 'frozen', False):
        base_dir = os.path.dirname(sys.executable)
    else:
        base_dir = os.path.dirname(os.path.abspath(__file__))
    app_dir = os.path.join(base_dir, "ProcessadorDeAudioVideo")
    if not os.path.exists(app_dir):
        os.makedirs(app_dir, exist_ok=True)
    return app_dir

def garantir_ffmpeg(window_parent=None, log_callback=None):
    """
    Garante que o FFmpeg esteja disponível. Multiplataforma.
    """
    config = get_platform_config()
    ffmpeg_bin = config['ffmpeg_bin']
    sistema = platform.system()
    
    if sistema == "Windows":
        ffmpeg_bin = "ffmpeg.exe"
    else:  
        ffmpeg_bin = "ffmpeg"

    pasta_app = get_app_dir()
    ffmpeg_path = os.path.join(pasta_app, ffmpeg_bin)

    # 1. Verifica se já existe na pasta do app
    if os.path.exists(ffmpeg_path):
        adicionar_log(f"FFmpeg encontrado na pasta do app: {ffmpeg_path}")
        return ffmpeg_path

    # 2. Verifica no PATH do sistema
    ffmpeg_global = shutil.which(ffmpeg_bin)
    if ffmpeg_global:
        adicionar_log(f"FFmpeg encontrado no PATH do sistema: {ffmpeg_global}")
        return ffmpeg_global

    # 3. Tentar baixar apenas no Windows
    if sistema == "Windows":
        try:
            import requests
            import zipfile
            msg = "Baixando FFmpeg para Windows..."
            if log_callback:
                log_callback(msg)
            adicionar_log(msg)
            
            url = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
            zip_path = os.path.join(pasta_app, "ffmpeg.zip")
            
            # Download
            r = requests.get(url, stream=True)
            r.raise_for_status()
            
            with open(zip_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            
            # Extração
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                for member in zip_ref.namelist():
                    if member.endswith(ffmpeg_bin):
                        # Extrair mantendo a estrutura de diretórios
                        extracted_path = zip_ref.extract(member, pasta_app)
                        # Mover para a pasta principal do app
                        final_path = os.path.join(pasta_app, os.path.basename(extracted_path))
                        if extracted_path != final_path:
                            if os.path.exists(final_path):
                                os.remove(final_path)
                            shutil.move(extracted_path, final_path)
                        break
            
            # Limpar
            os.remove(zip_path)
            
            if os.path.exists(ffmpeg_path):
                adicionar_log(f"FFmpeg baixado e instalado com sucesso em: {ffmpeg_path}")
                return ffmpeg_path
            
        except Exception as e:
            adicionar_log(f"Falha ao baixar FFmpeg: {e}")

    # 4. Se não conseguir, avisa usuário
    msg = (f"FFmpeg não encontrado.\n\n"
           f"Para {sistema}, instale o FFmpeg:\n"
           f"- Windows: Baixe de https://www.gyan.dev/ffmpeg/builds/ e coloque em: {pasta_app}\n"
           f"- Linux: Execute 'sudo apt install ffmpeg' ou equivalente")
    
    adicionar_log(msg)
    try:
        if window_parent is not None:
            QMessageBox.critical(window_parent, "Erro FFmpeg", msg)
        else:
            print(msg)
    except Exception:
        print(msg)
    return None