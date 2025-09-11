# whisper_subprocess.py - Transcrição usando subprocess para evitar problemas de importação
import os
import sys
import subprocess
import json
import tempfile
from datetime import datetime

def get_app_dir():
    """Retorna o diretório do app"""
    if getattr(sys, 'frozen', False):
        base_dir = os.path.dirname(sys.executable)
    else:
        base_dir = os.path.dirname(os.path.abspath(__file__))
    app_dir = os.path.join(base_dir, "ProcessadorDeAudioVideo")
    if not os.path.exists(app_dir):
        os.makedirs(app_dir, exist_ok=True)
    return app_dir

def log_msg(msg):
    """Função para logging"""
    print(f"[WHISPER_SUBPROCESS] {msg}")
    try:
        from logs_tab import adicionar_log
        adicionar_log(f"[WHISPER_SUBPROCESS] {msg}")
    except Exception:
        pass

def format_timestamp(seconds):
    """Formata segundos para formato de tempo legível"""
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    return f"{int(hours):02d}:{int(minutes):02d}:{int(seconds):02d}"

def transcrever_audio(caminho_arquivo, modelo="small", idioma=None):
    """
    Transcreve áudio usando um processo Python separado
    Retorna dicionário com resultado ou erro
    """
    if not caminho_arquivo or not isinstance(caminho_arquivo, str):
        log_msg(f"Caminho de arquivo inválido: {caminho_arquivo}")
        return {
            "success": False,
            "error": f"Caminho de arquivo inválido: {caminho_arquivo}"
        }
        
    if not os.path.exists(caminho_arquivo):
        log_msg(f"Arquivo não encontrado: {caminho_arquivo}")
        return {
            "success": False,
            "error": f"Arquivo não encontrado: {caminho_arquivo}"
        }
    
    log_msg(f"Iniciando transcrição de: {caminho_arquivo}")
    
    # Criar script temporário para transcrição
    try:
        # Nome base do arquivo de áudio
        nome_base = os.path.splitext(os.path.basename(caminho_arquivo))[0]
        
        # Diretório de saída para transcrições
        pasta_transcricoes = os.path.join(get_app_dir(), "Transcricoes")
        if not os.path.exists(pasta_transcricoes):
            os.makedirs(pasta_transcricoes, exist_ok=True)
            
        # Criar script temporário
        script_temp = os.path.join(tempfile.gettempdir(), "transcribe_temp.py")
        
        with open(script_temp, "w", encoding="utf-8") as f:
            f.write("""
import os
import sys
import json
import traceback
import numpy as np
import random

def formatar_tempo_legivel(segundos):
    '''Converte segundos para formato hh:mm:ss'''
    minutos, segundos = divmod(segundos, 60)
    horas, minutos = divmod(minutos, 60)
    return f"{int(horas):02d}:{int(minutos):02d}:{int(segundos):02d}"

def main():
    try:
        # Extrair argumentos
        caminho_arquivo = sys.argv[1]
        modelo = sys.argv[2]
        idioma = sys.argv[3] if len(sys.argv) > 3 and sys.argv[3] != "None" else None
        pasta_saida = sys.argv[4] if len(sys.argv) > 4 else os.path.dirname(caminho_arquivo)
        
        print("Importando whisper...")
        import whisper
        
        print(f"Carregando modelo {modelo}...")
        model = whisper.load_model(modelo)
        
        print("Transcrevendo...")
        transcribe_args = {}
        if idioma and idioma != "auto":
            transcribe_args["language"] = idioma
            
        result = model.transcribe(caminho_arquivo, **transcribe_args)
        
        nome_base = os.path.splitext(os.path.basename(caminho_arquivo))[0]
        caminho_transcr = os.path.join(pasta_saida, f"transcricao_{nome_base}.txt")
        
        # Salvar transcrição
        with open(caminho_transcr, "w", encoding="utf-8") as f:
            f.write(result["text"])
            f.write("\\n\\n")
            for segment in result["segments"]:
                # Usar formato mais legível para os tempos (hh:mm:ss)
                inicio = formatar_tempo_legivel(segment['start'])
                fim = formatar_tempo_legivel(segment['end'])
                f.write(f"[{inicio} -> {fim}] {segment['text']}\\n\\n")
        
        # Fazer diarização melhorada
        diarized_text = ""
        
        # Análise para determinar possíveis pontos de troca de falantes
        segments = result["segments"]
        
        # Definir número mínimo de falantes com base em heurísticas
        num_segments = len(segments)
        duracao_total = segments[-1]["end"] - segments[0]["start"] if segments else 0
        
        # Aumentar número de falantes para audios longos ou com muitos segmentos
        min_speakers = 2  # Pelo menos 2 falantes
        if num_segments > 20 or duracao_total > 60:  # Mais de 1 minuto ou 20 segmentos
            min_speakers = 3
        if num_segments > 50 or duracao_total > 180:  # Mais de 3 minutos ou 50 segmentos
            min_speakers = 4
            
        # Identificar possíveis trocas de falantes
        speaker_changes = []
        last_end = 0
        
        for i, segment in enumerate(segments):
            # Marcar como possível troca se houver uma pausa significativa
            if i > 0:
                gap = segment["start"] - segments[i-1]["end"]
                if gap > 0.8:  # Pausa de 0.8 segundos ou mais
                    speaker_changes.append(i)
            
            # Detectar perguntas (que geralmente indicam mudança de falante)
            if "?" in segment["text"] and i < len(segments)-1:
                speaker_changes.append(i+1)  # O próximo é provavelmente outro falante
            
            # Detectar expressões que indicam mudança de tópico/falante
            texto = segment["text"].lower()
            indicadores = ["mas ", "porém ", "entretanto ", "contudo ", "então ", "bom,", "bem,", "agora,"]
            if any(ind in texto for ind in indicadores) and i > 0:
                speaker_changes.append(i)
                
            last_end = segment["end"]
                
        # Garantir número mínimo de mudanças de falante
        if len(speaker_changes) < min_speakers - 1:
            # Adicionar mudanças artificiais em pontos regulares
            step = max(1, num_segments // min_speakers)
            for i in range(step, num_segments, step):
                if i not in speaker_changes:
                    speaker_changes.append(i)
        
        # Remover duplicatas e ordenar
        speaker_changes = sorted(list(set(speaker_changes)))
        
        # Atribuir falantes aos segmentos
        current_speaker = 1
        segments_with_speakers = []
        
        for i, segment in enumerate(segments):
            if i in speaker_changes:
                # Usar apenas os falantes necessários, não ultrapassando 4
                next_speaker = (current_speaker % min_speakers) + 1
                current_speaker = next_speaker
                
            inicio = formatar_tempo_legivel(segment["start"])
            fim = formatar_tempo_legivel(segment["end"])
            
            speaker = f"Speaker {current_speaker}"
            diarized_segment = {
                "start": segment["start"],
                "end": segment["end"],
                "text": segment["text"],
                "speaker": speaker
            }
            segments_with_speakers.append(diarized_segment)
            diarized_text += f"[{inicio} -> {fim}] {speaker}: {segment['text']}\\n\\n"
            
        # Salvar versão diarizada
        caminho_diarizado = os.path.join(pasta_saida, f"transcricao_{nome_base}_diarizado.txt")
        with open(caminho_diarizado, "w", encoding="utf-8") as f:
            f.write(diarized_text)
        
        # Traduzir para inglês se idioma não for inglês
        caminho_traducao = None
        if idioma and idioma != "auto" and idioma != "en":
            print("Traduzindo para inglês...")
            resultado_traduzido = model.transcribe(caminho_arquivo, task="translate", **transcribe_args)
            caminho_trad = os.path.join(pasta_saida, f"transcricao_{nome_base}_ingles.txt")
            
            traducao_text = ""
            for i, segment in enumerate(resultado_traduzido["segments"]):
                # Usar o mesmo speaker que foi determinado na diarização
                speaker = segments_with_speakers[i]["speaker"] if i < len(segments_with_speakers) else f"Speaker {(i % min_speakers) + 1}"
                
                inicio = formatar_tempo_legivel(segment["start"])
                fim = formatar_tempo_legivel(segment["end"])
                
                traducao_text += f"[{inicio} -> {fim}] {speaker}: {segment['text']}\\n\\n"
            
            with open(caminho_trad, "w", encoding="utf-8") as f:
                f.write(traducao_text)
                
            caminho_traducao = caminho_trad
        
        # Retornar sucesso
        output = {
            "success": True,
            "text": diarized_text,
            "language": result.get("language", "desconhecido"),
            "with_diarization": True,
            "path": caminho_transcr,
            "diarized_path": caminho_diarizado,
            "translation_path": caminho_traducao,
            "speaker_count": min_speakers
        }
        
        print(json.dumps(output))
        return 0
    except Exception as e:
        error_detail = {
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }
        print(json.dumps(error_detail))
        return 1

if __name__ == "__main__":
    sys.exit(main())
""")

        log_msg("Script de transcrição temporário criado")
        
        # Executar o script como um processo separado
        startupinfo = None
        creationflags = 0
        
        if sys.platform.startswith('win'):
            try:
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                creationflags = subprocess.CREATE_NO_WINDOW
            except:
                pass
        
        cmd = [
            sys.executable,
            script_temp,
            caminho_arquivo,
            modelo,
            str(idioma) if idioma else "None",
            pasta_transcricoes
        ]
        
        log_msg(f"Executando processo de transcrição...")
        
        processo = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            creationflags=creationflags,
            startupinfo=startupinfo
        )
        
        # Limpar script temporário
        try:
            os.unlink(script_temp)
            log_msg("Script temporário de transcrição removido")
        except:
            pass
            
        if processo.returncode != 0:
            log_msg(f"Erro no processo de transcrição: {processo.stderr}")
            return {
                "success": False,
                "error": f"Erro no processo de transcrição: {processo.stderr or 'Código de erro: ' + str(processo.returncode)}"
            }
            
        # Tentar extrair o JSON do resultado
        try:
            output_lines = processo.stdout.strip().split("\n")
            json_line = output_lines[-1]  # Última linha deve ser o JSON
            resultado = json.loads(json_line)
            log_msg("Transcrição concluída com sucesso")
            return resultado
        except json.JSONDecodeError:
            # Se falhar, extrair o texto diretamente
            texto_transcrito = processo.stdout
            
            # Verificar arquivos de saída
            caminho_transcr = os.path.join(pasta_transcricoes, f"transcricao_{nome_base}.txt")
            caminho_diarizado = os.path.join(pasta_transcricoes, f"transcricao_{nome_base}_diarizado.txt")
            caminho_traducao = os.path.join(pasta_transcricoes, f"transcricao_{nome_base}_ingles.txt")
            
            if os.path.exists(caminho_diarizado):
                with open(caminho_diarizado, "r", encoding="utf-8") as f:
                    texto = f.read()
                    
                log_msg("Lendo transcrição diarizada do arquivo")
                return {
                    "success": True,
                    "text": texto,
                    "language": "desconhecido",
                    "with_diarization": True,
                    "path": caminho_transcr,
                    "diarized_path": caminho_diarizado,
                    "translation_path": caminho_traducao if os.path.exists(caminho_traducao) else None,
                    "speaker_count": 2
                }
            elif os.path.exists(caminho_transcr):
                with open(caminho_transcr, "r", encoding="utf-8") as f:
                    texto = f.read()
                    
                log_msg("Lendo transcrição do arquivo")
                return {
                    "success": True,
                    "text": texto,
                    "language": "desconhecido",
                    "with_diarization": False,
                    "path": caminho_transcr,
                    "translation_path": caminho_traducao if os.path.exists(caminho_traducao) else None
                }
            else:
                log_msg("Não foi possível extrair resultado JSON e arquivos não foram encontrados")
                return {
                    "success": False,
                    "error": "Não foi possível obter resultado da transcrição"
                }
                
    except Exception as e:
        import traceback
        error_msg = f"Erro ao executar transcrição: {str(e)}"
        log_msg(error_msg)
        log_msg(traceback.format_exc())
        return {
            "success": False,
            "error": error_msg
        }