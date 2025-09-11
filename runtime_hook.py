# runtime_hook.py - Configurações de runtime para o executável
import os
import sys
import warnings
import platform

# Silenciar warnings
warnings.filterwarnings("ignore")

# Configurar paths para recursos
if getattr(sys, 'frozen', False):
    # Modo executável
    base_dir = getattr(sys, '_MEIPASS', os.path.dirname(sys.executable))
else:
    # Modo desenvolvimento
    base_dir = os.path.dirname(os.path.abspath(__file__))

# Configuração específica para cada plataforma
if platform.system() == "Linux":
    # Adicionar paths para bibliotecas apenas no Linux
    sys.path.insert(0, base_dir)
    sys.path.insert(0, os.path.join(base_dir, 'whisper'))
    sys.path.insert(0, os.path.join(base_dir, 'resemblyzer'))

    # Configurar environment variables
    os.environ['CUDA_VISIBLE_DEVICES'] = ''
    os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'
    os.environ['PYTHONWARNINGS'] = 'ignore'

    # Configurar para usar CPU apenas
    try:
        import torch
        torch.set_num_threads(1)
    except ImportError:
        pass
elif platform.system() == "Windows":
    # Configurações específicas para Windows
    sys.path.insert(0, base_dir)
    # Não tenta modificar o __import__ no Windows
    os.environ['PYTHONWARNINGS'] = 'ignore'