# whisper_wrapper.py - Versão atualizada para gerar corretamente as traduções

import os
import sys
import subprocess
import json
import traceback

def get_app_dir():
    """Retorna o diretório do app, considerando empacotamento."""
    if getattr(sys, 'frozen', False):
        base_dir = os.path.dirname(sys.executable)
    else:
        base_dir = os.path.dirname(os.path.abspath(__file__))
    app_dir = os.path.join(base_dir, "ProcessadorDeAudioVideo")
    if not os.path.exists(app_dir):
        os.makedirs(app_dir, exist_ok=True)
    return app_dir

def log_message(msg):
    """Log de mensagens"""
    print(f"[WHISPER_SUBPROCESS] {msg}")
    try:
        from logs_tab import adicionar_log
        adicionar_log(f"[WHISPER_SUBPROCESS] {msg}")
    except:
        pass

def transcrever_audio_processo_separado(caminho_arquivo, modelo="small", idioma=None):
    """
    Transcreve áudio usando um processo Python separado para evitar
    problemas de carregamento do Whisper/PyTorch.
    """
    if not caminho_arquivo or not os.path.exists(caminho_arquivo):
        return {
            "success": False,
            "error": f"Arquivo não encontrado: {caminho_arquivo}"
        }
        
    # Criar um script temporário para executar a transcrição
    pasta_app = get_app_dir()
    script_temp = os.path.join(pasta_app, "transcribe_temp.py")
    
    # Criar o script com o código necessário para transcrever
    with open(script_temp, "w", encoding="utf-8") as f:
        f.write("""
import os
import sys
import json
import time

def main():
    try:
        # Obter argumentos
        caminho_arquivo = sys.argv[1]
        modelo = sys.argv[2]
        idioma = sys.argv[3] if len(sys.argv) > 3 and sys.argv[3] != "None" else None
        
        # Importar whisper
        print("[SCRIPT] Importando whisper...")
        import whisper
        print("[SCRIPT] Whisper importado com sucesso")
        
        # Carregar modelo
        print(f"[SCRIPT] Carregando modelo {modelo}...")
        modelo_carregado = whisper.load_model(modelo)
        print("[SCRIPT] Modelo carregado com sucesso")
        
        # Configurar opções
        transcribe_args = {}
        if idioma and idioma != "auto":
            transcribe_args["language"] = idioma
            print(f"[SCRIPT] Idioma definido: {idioma}")
            
        # Transcrever
        print("[SCRIPT] Iniciando transcrição...")
        resultado = modelo_carregado.transcribe(caminho_arquivo, **transcribe_args)
        print("[SCRIPT] Transcrição concluída")
        
        # Preparar diretórios
        nome_base = os.path.splitext(os.path.basename(caminho_arquivo))[0]
        pasta_transcricoes = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                          "ProcessadorDeAudioVideo", "Transcricoes")
        
        if not os.path.exists(pasta_transcricoes):
            os.makedirs(pasta_transcricoes, exist_ok=True)
            
        # Salvar transcrição
        caminho_transcr = os.path.join(pasta_transcricoes, f"transcricao_{nome_base}.txt")
        with open(caminho_transcr, "w", encoding="utf-8") as f:
            for segment in resultado["segments"]:
                f.write(f"[{{segment['start']:.2f}} -> {{segment['end']:.2f}}] {{segment['text']}}\\n\\n")
        print(f"[SCRIPT] Transcrição salva: {caminho_transcr}")

        # Realizar diarização simples
        try:
            print("[SCRIPT] Realizando diarização simples...")
            segments_with_speakers = aplicar_diarizacao_simples(resultado["segments"])
            
            # Salvar versão com diarização
            caminho_diarizado = os.path.join(pasta_transcricoes, f"transcricao_{nome_base}_diarizado.txt")
            with open(caminho_diarizado, "w", encoding="utf-8") as f:
                for segment in segments_with_speakers:
                    f.write(f"[{{segment['start']:.2f}} -> {{segment['end']:.2f}}] {{segment['speaker']}}: {{segment['text']}}\\n\\n")
            print(f"[SCRIPT] Transcrição com diarização salva: {caminho_diarizado}")
            
            # Construir texto com diarização para exibição
            text_with_diarization = ""
            for segment in segments_with_speakers:
                text_with_diarization += f"[{{segment['start']:.2f}} -> {{segment['end']:.2f}}] {{segment['speaker']}}: {{segment['text']}}\\n\\n"
                
        except Exception as e:
            print(f"[SCRIPT] Erro na diarização: {e}")
            segments_with_speakers = None
            text_with_diarization = resultado["text"]
        
        # Se idioma não é inglês, traduzir para inglês
        caminho_trad = None
        if idioma and idioma != "auto" and idioma != "en":
            try:
                print("[SCRIPT] Iniciando tradução para inglês...")
                # Explicitamente definir task="translate"
                traducao_args = transcribe_args.copy()
                resultado_traduzido = modelo_carregado.transcribe(
                    caminho_arquivo, 
                    task="translate",
                    **traducao_args
                )
                
                caminho_trad = os.path.join(pasta_transcricoes, f"transcricao_{nome_base}_ingles.txt")
                with open(caminho_trad, "w", encoding="utf-8") as f:
                    for segment in resultado_traduzido["segments"]:
                        f.write(f"[{{segment['start']:.2f}} -> {{segment['end']:.2f}}] {{segment['text']}}\\n\\n")
                print(f"[SCRIPT] Tradução salva: {caminho_trad}")
            except Exception as e:
                print(f"[SCRIPT] Erro na tradução: {e}")
        
        # Retornar resultado
        resultado_final = {{
            "success": True,
            "text": text_with_diarization if segments_with_speakers else resultado["text"],
            "language": resultado.get("language", "desconhecido"),
            "tem_diarizacao": segments_with_speakers is not None,
            "tem_traducao": caminho_trad is not None
        }}
        print(json.dumps(resultado_final))
        return 0
        
    except Exception as e:
        import traceback
        print(json.dumps({{
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }}))
        return 1

def aplicar_diarizacao_simples(segments):
    \"\"\"Aplica diarização básica baseada em análise de segmentos\"\"\"
    # Inicializa a análise
    segments_with_speakers = []
    current_speaker = 0
    speaker_count = 2  # Começamos com ao menos 2 falantes
    last_time = 0
    
    # Analisa cada segmento
    for i, segment in enumerate(segments):
        start, end = segment["start"], segment["end"]
        text = segment["text"].strip()
        
        # Verifica pausas longas (possível troca de falante)
        if i > 0:
            pause_duration = start - last_time
            if pause_duration > 1.5:  # Pausa significativa
                current_speaker = (current_speaker + 1) % speaker_count
        
        # Analisa conteúdo do texto para detectar possível novo falante
        if i > 0 and text.startswith(("Mas", "Porém", "Entretanto", "No entanto", "Contudo", "?", "Discordo")):
            current_speaker = (current_speaker + 1) % speaker_count
        
        # Se o texto contém perguntas e respostas, aumenta número de falantes
        if "?" in text and i < len(segments) - 1 and not segments[i+1]["text"].strip().startswith("?"):
            speaker_count = max(speaker_count, 3)
        
        # Adiciona marcação de speaker
        segment_with_speaker = segment.copy()
        segment_with_speaker["speaker"] = f"Speaker {current_speaker + 1}"
        segments_with_speakers.append(segment_with_speaker)
        
        # Atualiza last_time para o próximo cálculo
        last_time = end
    
    return segments_with_speakers

if __name__ == "__main__":
    sys.exit(main())
""")
    
    # Executar o script como um processo separado
    try:
        # Configuração para subprocess (evitar janela no Windows)
        startupinfo = None
        creationflags = 0
        
        if sys.platform.startswith('win'):
            try:
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                creationflags = subprocess.CREATE_NO_WINDOW
            except:
                pass
        
        # Log
        log_message(f"Iniciando transcrição de: {caminho_arquivo}")
        log_message("Script de transcrição temporário criado")
        
        # Comando para executar script
        cmd = [
            sys.executable,
            script_temp,
            caminho_arquivo,
            modelo,
            str(idioma) if idioma else "None"
        ]
        
        # Executar o processo
        log_message("Executando processo de transcrição...")
        processo = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            creationflags=creationflags,
            startupinfo=startupinfo
        )
        
        # Processar a saída
        if processo.returncode == 0:
            try:
                # Capturar a última linha como JSON
                output_lines = processo.stdout.strip().split('\n')
                json_lines = [line for line in output_lines if line.startswith('{')]
                
                if json_lines:
                    resultado = json.loads(json_lines[-1])
                    log_message("Transcrição concluída com sucesso")
                    return resultado
                else:
                    log_message("Formato de saída inválido do processo")
                    return {
                        "success": True,
                        "text": processo.stdout,
                        "language": "desconhecido"
                    }
            except json.JSONDecodeError as e:
                log_message(f"Erro ao decodificar JSON: {e}")
                return {
                    "success": True,
                    "text": processo.stdout,
                    "language": "desconhecido"
                }
        else:
            log_message(f"Erro no processo de transcrição: {processo.stderr}")
            return {
                "success": False,
                "error": f"Erro na transcrição: {processo.stderr or processo.stdout}"
            }
        
    except Exception as e:
        error_message = f"Erro ao executar processo de transcrição: {str(e)}"
        log_message(error_message)
        return {
            "success": False,
            "error": error_message,
            "traceback": traceback.format_exc()
        }
    finally:
        # Limpar o script temporário
        try:
            if os.path.exists(script_temp):
                os.remove(script_temp)
        except:
            pass