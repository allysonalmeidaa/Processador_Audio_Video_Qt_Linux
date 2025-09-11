# whisper_import.py - Importação segura para o whisper
import importlib
import platform
import os
import sys

def import_whisper_safely():
    """
    Importa o módulo whisper de forma segura em qualquer plataforma
    Retorna (whisper_module, error_message)
    """
    try:
        # Importação direta sem manipulações
        whisper = importlib.import_module('whisper')
        return whisper, None
    except ImportError as e:
        return None, f"Whisper não instalado. Execute: pip install openai-whisper"
    except Exception as e:
        return None, f"Erro ao carregar whisper: {str(e)}"

def load_whisper_model(model_name):
    """
    Carrega um modelo whisper de forma segura
    Retorna (model, error_message)
    """
    whisper, error = import_whisper_safely()
    if error:
        return None, error
    
    try:
        model = whisper.load_model(model_name)
        return model, None
    except Exception as e:
        return None, f"Erro ao carregar modelo {model_name}: {str(e)}"