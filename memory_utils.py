# memory_utils.py - CORRIGIDO
import gc
import sys
import importlib

def clear_memory():
    """Limpeza agressiva de memória para PyTorch"""
    try:
        gc.collect()
        
        # Importação condicional do torch
        try:
            import torch
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
                torch.cuda.synchronize()  # Corrigido
        except ImportError:
            pass  # Torch não disponível
        
        # Importação condicional do whisper
        try:
            whisper = importlib.import_module('whisper')
            if hasattr(whisper, '_models'):
                whisper._models.clear()
        except ImportError:
            pass  # Whisper não disponível
    except Exception as e:
        print(f"Erro ao limpar memória: {e}")