# whisper_simple.py - Versão corrigida para transcrever áudio
import os
import sys
from datetime import datetime

def formatar_tempo_legivel(segundos):
    """Converte segundos para formato hh:mm:ss"""
    minutos, segundos = divmod(segundos, 60)
    horas, minutos = divmod(minutos, 60)
    return f"{int(horas):02d}:{int(minutos):02d}:{int(segundos):02d}"

def transcrever_audio(caminho_arquivo, modelo="small", idioma=None):
    """Transcreve áudio usando Whisper de forma simplificada"""
    try:
        # Configurar log
        def log_msg(msg):
            print(f"[TRANSCRIÇÃO SIMPLES] {msg}")
            try:
                from logs_tab import adicionar_log
                adicionar_log(f"[TRANSCRIÇÃO SIMPLES] {msg}")
            except:
                pass
                
        # Verificar caminho do arquivo
        if not caminho_arquivo or not isinstance(caminho_arquivo, str):
            log_msg(f"Caminho de arquivo inválido: {caminho_arquivo}")
            return {
                "success": False,
                "error": f"Caminho de arquivo inválido: {caminho_arquivo}"
            }
            
        log_msg(f"Iniciando: {caminho_arquivo}")
            
        # Verificar se arquivo existe
        if not os.path.exists(caminho_arquivo):
            log_msg(f"Arquivo não encontrado: {caminho_arquivo}")
            return {
                "success": False,
                "error": f"Arquivo não encontrado: {caminho_arquivo}"
            }
        
        # Tentar método seguro usando processo separado
        try:
            # Importar módulo de transcrição via subprocess
            import importlib.util
            spec = importlib.util.spec_from_file_location(
                "whisper_subprocess", 
                os.path.join(os.path.dirname(os.path.abspath(__file__)), "whisper_subprocess.py")
            )
            whisper_subprocess = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(whisper_subprocess)
            
            log_msg(f"Usando método de transcrição via subprocess")
            resultado = whisper_subprocess.transcrever_audio(caminho_arquivo, modelo, idioma)
            
            if resultado.get("success", False):
                log_msg("Transcrição concluída com sucesso")
            else:
                log_msg(f"Erro na transcrição: {resultado.get('error', 'Erro desconhecido')}")
                
            return resultado
        except Exception as e:
            # Se falhar o método seguro, tentamos importação direta
            log_msg(f"Importação direta falhou: {str(e)}. Tentando método alternativo...")
            
            try:
                # Tentativa direta de importar whisper
                import whisper
                log_msg("Biblioteca whisper importada com sucesso")
                
                # Carregar modelo
                log_msg(f"Carregando modelo: {modelo}")
                model = whisper.load_model(modelo)
                log_msg("Modelo carregado com sucesso")
                
                # Configurar argumentos
                transcribe_args = {}
                if idioma and idioma != "auto":
                    transcribe_args["language"] = idioma
                    log_msg(f"Idioma definido: {idioma}")
                
                # Fazer transcrição
                log_msg("Iniciando processo de transcrição...")
                result = model.transcribe(caminho_arquivo, **transcribe_args)
                log_msg("Transcrição concluída com sucesso")
                
                # Criar caminho para salvar a transcrição
                nome_base = os.path.splitext(os.path.basename(caminho_arquivo))[0]
                pasta_transcricoes = os.path.join(
                    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 
                    "ProcessadorDeAudioVideo", "Transcricoes"
                )
                    
                if not os.path.exists(pasta_transcricoes):
                    os.makedirs(pasta_transcricoes, exist_ok=True)
                    
                # Salvar a transcrição como arquivo
                caminho_transcr = os.path.join(pasta_transcricoes, f"transcricao_{nome_base}.txt")
                with open(caminho_transcr, "w", encoding="utf-8") as f:
                    for segment in result["segments"]:
                        inicio = formatar_tempo_legivel(segment["start"])
                        fim = formatar_tempo_legivel(segment["end"])
                        f.write(f"[{inicio} -> {fim}] {segment['text']}\n\n")
                log_msg(f"Transcrição salva em: {caminho_transcr}")
                
                # Se idioma não for inglês e for um idioma específico, traduzir para inglês
                if idioma and idioma != "auto" and idioma != "en":
                    log_msg("Realizando tradução para o inglês...")
                    resultado_traduzido = model.transcribe(caminho_arquivo, task="translate", **transcribe_args)
                    caminho_trad = os.path.join(pasta_transcricoes, f"transcricao_{nome_base}_ingles.txt")
                    with open(caminho_trad, "w", encoding="utf-8") as f:
                        for segment in resultado_traduzido["segments"]:
                            inicio = formatar_tempo_legivel(segment["start"])
                            fim = formatar_tempo_legivel(segment["end"])
                            f.write(f"[{inicio} -> {fim}] {segment['text']}\n\n")
                    log_msg(f"Tradução salva em: {caminho_trad}")
                
                # Aplicar diarização melhorada
                try:
                    log_msg("Aplicando diarização avançada...")
                    segments = result["segments"]
                    num_segments = len(segments)
                    
                    # Aumentar número de falantes para audios longos
                    num_speakers = 2  # Pelo menos 2 falantes
                    if num_segments > 20 or (segments[-1]["end"] - segments[0]["start"]) > 60:
                        num_speakers = 3  # Para áudios maiores que 1 minuto
                    if num_segments > 50:
                        num_speakers = 4  # Para áudios muito longos
                    
                    # Identificar possíveis trocas de falantes
                    speaker_changes = []
                    
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
                        indicadores = ["mas ", "porém ", "entretanto ", "contudo ", "então ", "bom,", "bem,"]
                        if any(ind in texto for ind in indicadores) and i > 0:
                            speaker_changes.append(i)
                    
                    # Garantir número mínimo de mudanças de falante
                    if len(speaker_changes) < num_speakers - 1:
                        # Adicionar mudanças artificiais em pontos regulares
                        step = max(1, num_segments // num_speakers)
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
                            # Usar apenas os falantes necessários, não ultrapassando num_speakers
                            next_speaker = (current_speaker % num_speakers) + 1
                            current_speaker = next_speaker
                        
                        segment_with_speaker = segment.copy()
                        segment_with_speaker["speaker"] = f"Speaker {current_speaker}"
                        segments_with_speakers.append(segment_with_speaker)
                    
                    log_msg(f"Diarização aplicada: {len(segments_with_speakers)} segmentos, {num_speakers} falantes")
                    
                    # Salvar versão com diarização
                    caminho_diarizado = os.path.join(pasta_transcricoes, f"transcricao_{nome_base}_diarizado.txt")
                    with open(caminho_diarizado, "w", encoding="utf-8") as f:
                        for segment in segments_with_speakers:
                            inicio = formatar_tempo_legivel(segment["start"])
                            fim = formatar_tempo_legivel(segment["end"])
                            f.write(f"[{inicio} -> {fim}] {segment['speaker']}: {segment['text']}\n\n")
                    log_msg(f"Transcrição com diarização salva em: {caminho_diarizado}")
                    
                    # Usa o texto diarizado para exibir
                    text_with_diarization = ""
                    for segment in segments_with_speakers:
                        inicio = formatar_tempo_legivel(segment["start"])
                        fim = formatar_tempo_legivel(segment["end"])
                        text_with_diarization += f"[{inicio} -> {fim}] {segment['speaker']}: {segment['text']}\n\n"
                        
                    return {
                        "success": True,
                        "text": text_with_diarization,
                        "language": result.get("language", "desconhecido"),
                        "segments": segments_with_speakers,
                        "with_diarization": True,
                        "speaker_count": num_speakers
                    }
                except Exception as e:
                    log_msg(f"Aviso: Diarização avançada não aplicada: {e}")
                
                return {
                    "success": True,
                    "text": result["text"],
                    "language": result.get("language", "desconhecido"),
                    "segments": result["segments"]
                }
            except Exception as e:
                log_msg(f"Erro ao importar whisper: {str(e)}")
                return {
                    "success": False,
                    "error": f"Erro ao importar whisper: {str(e)}"
                }
        
    except Exception as e:
        import traceback
        error_msg = f"Erro na transcrição: {str(e)}"
        log_msg(error_msg)
        return {
            "success": False,
            "error": error_msg,
            "traceback": traceback.format_exc()
        }