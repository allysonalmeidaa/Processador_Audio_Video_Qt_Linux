# youtube_downloader.py - Função simples para baixar do YouTube
import os
import sys
import subprocess
import platform
from logs_tab import adicionar_log

def get_app_dir():
    # Diretório raiz do projeto
    if getattr(sys, 'frozen', False):
        base_dir = os.path.dirname(sys.executable)
    else:
        base_dir = os.path.dirname(os.path.abspath(__file__))
    app_dir = os.path.join(base_dir, "ProcessadorDeAudioVideo")
    if not os.path.exists(app_dir):
        os.makedirs(app_dir, exist_ok=True)
    return app_dir

def baixar_video_youtube(url, pasta_destino):
    """
    Baixa um vídeo do YouTube usando subprocess e yt-dlp
    Retorna (caminho_arquivo, nome_base) ou (None, None) em caso de erro
    """
    try:
        # Criar pasta destino se não existir
        if not os.path.exists(pasta_destino):
            os.makedirs(pasta_destino, exist_ok=True)
            adicionar_log(f"Criado diretório de destino: {pasta_destino}")
            
        # Verificar se yt-dlp está instalado usando subprocess
        try:
            # Configurações para subprocess
            startupinfo = None
            creationflags = 0
            if platform.system() == "Windows":
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                creationflags = subprocess.CREATE_NO_WINDOW
                
            # Tenta executar yt-dlp --version
            subprocess.run(
                ["yt-dlp", "--version"], 
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=creationflags,
                startupinfo=startupinfo
            )
        except (FileNotFoundError, subprocess.SubprocessError):
            adicionar_log("yt-dlp não encontrado no sistema")
            return None, None
            
        # Preparar nome de arquivo de saída
        output_template = os.path.join(pasta_destino, "video_%(title)s.%(ext)s")
        
        # Preparar comando
        cmd = [
            "yt-dlp",
            "--format", "bestvideo[ext=mp4]+bestaudio[ext=m4a]/mp4",
            "--merge-output-format", "mp4",
            "--no-playlist",
            "-o", output_template,
            url
        ]
        
        adicionar_log(f"Iniciando download do YouTube: {url}")
        
        # Executar comando
        processo = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            creationflags=creationflags,
            startupinfo=startupinfo
        )
        
        if processo.returncode != 0:
            adicionar_log(f"Erro ao baixar vídeo: {processo.stderr}")
            return None, None
            
        # Encontrar arquivo baixado
        arquivos = [f for f in os.listdir(pasta_destino) if f.startswith("video_") and f.endswith(".mp4")]
        if not arquivos:
            adicionar_log("Nenhum arquivo foi baixado")
            return None, None
            
        # Pegar o arquivo mais recente
        arquivos.sort(key=lambda x: os.path.getmtime(os.path.join(pasta_destino, x)), reverse=True)
        caminho_video = os.path.join(pasta_destino, arquivos[0])
        nome_base = os.path.splitext(os.path.basename(caminho_video))[0].replace("video_", "")
        
        adicionar_log(f"Download concluído: {caminho_video}")
        return caminho_video, nome_base
        
    except Exception as e:
        import traceback
        adicionar_log(f"Erro durante o download: {str(e)}")
        adicionar_log(traceback.format_exc())
        return None, None