# yt_dlp_import.py - Importação segura do yt-dlp
import importlib

def get_yt_dlp():
    """
    Função segura para importar yt-dlp em qualquer plataforma
    Retorna (yt_dlp_module, is_available)
    """
    try:
        # Importação direta e simples
        yt_dlp = importlib.import_module('yt_dlp')
        return yt_dlp, True
    except ImportError as e:
        print(f"yt-dlp não disponível: {e}")
        return None, False
    except Exception as e:
        print(f"Erro ao importar yt-dlp: {e}")
        return None, False