# yt_dlp_wrapper.py - Wrapper para yt-dlp com tratamento de erros
import os
import sys
import subprocess
from logs_tab import adicionar_log

def baixar_video_youtube(url, pasta_saida):
    """
    Função segura para baixar vídeos do YouTube usando subprocess
    ao invés de importar diretamente o módulo yt-dlp
    """
    try:
        adicionar_log(f"Tentando baixar vídeo do YouTube: {url}")
        
        # Garante que a pasta de saída existe
        if not os.path.exists(pasta_saida):
            os.makedirs(pasta_saida, exist_ok=True)
            
        # Define o nome do arquivo de saída
        output_template = os.path.join(pasta_saida, "video_%(title)s.%(ext)s")
        
        # Configura comando para executar yt-dlp como processo separado
        comando = [
            sys.executable, "-m", "yt_dlp",
            "-f", "bestvideo[ext=mp4]+bestaudio[ext=m4a]/mp4",
            "--merge-output-format", "mp4",
            "-o", output_template,
            "--no-playlist",
            url
        ]
        
        # Executa o comando como processo separado
        startupinfo = None
        creationflags = 0
        
        if sys.platform.startswith('win'):
            import subprocess
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            creationflags = subprocess.CREATE_NO_WINDOW
        
        adicionar_log("Executando yt-dlp como processo externo...")
        processo = subprocess.run(
            comando,
            capture_output=True,
            text=True,
            creationflags=creationflags,
            startupinfo=startupinfo
        )
        
        # Verifica se o processo terminou com sucesso
        if processo.returncode != 0:
            adicionar_log(f"Erro ao baixar vídeo: {processo.stderr}")
            return None, None
            
        # Procura pelo nome do arquivo no output
        output = processo.stdout
        titulo = None
        arquivo_final = None
        
        for linha in output.splitlines():
            if "[download]" in linha and "Destination" in linha:
                arquivo_final = linha.split("Destination: ")[1].strip()
            if "[download]" in linha and "has already been downloaded" in linha:
                arquivo_final = linha.split("[download] ")[1].split(" has already")[0]
            if "[Merger]" in linha and "Merging formats into" in linha:
                arquivo_final = linha.split("Merging formats into ")[1].strip('"')
                
        if arquivo_final and os.path.exists(arquivo_final):
            titulo = os.path.splitext(os.path.basename(arquivo_final))[0]
            titulo = titulo.replace("video_", "")
            adicionar_log(f"Download concluído: {arquivo_final}")
            return arquivo_final, titulo
            
        # Busca qualquer arquivo MP4 ou WebM criado recentemente na pasta
        import glob
        import time
        
        arquivos = glob.glob(os.path.join(pasta_saida, "video_*.mp4")) + \
                  glob.glob(os.path.join(pasta_saida, "video_*.webm")) + \
                  glob.glob(os.path.join(pasta_saida, "video_*.mkv"))
        
        if arquivos:
            # Ordena por data de modificação (mais recente primeiro)
            arquivos.sort(key=os.path.getmtime, reverse=True)
            arquivo_final = arquivos[0]
            titulo = os.path.splitext(os.path.basename(arquivo_final))[0]
            titulo = titulo.replace("video_", "")
            adicionar_log(f"Arquivo encontrado após download: {arquivo_final}")
            return arquivo_final, titulo
            
        adicionar_log("Falha ao encontrar arquivo após download")
        return None, None
        
    except Exception as e:
        adicionar_log(f"Erro ao baixar vídeo do YouTube: {str(e)}")
        import traceback
        adicionar_log(traceback.format_exc())
        return None, None