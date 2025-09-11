# safe_import.py - Versão segura para Windows e Linux
import importlib
import platform

def safe_import(name, globals=None, locals=None, fromlist=(), level=0):
    """
    Versão simplificada e segura de importação que funciona em ambas plataformas.
    """
    try:
        # Usar importlib diretamente é mais seguro
        return importlib.import_module(name)
    except Exception as e:
        print(f"Erro ao importar {name}: {e}")
        return None

# Não modifique o __import__ no Windows, apenas no Linux
if platform.system() == "Linux":
    try:
        import builtins
        if not hasattr(builtins, '__original_import__'):
            builtins.__original_import__ = builtins.__import__
            builtins.__import__ = safe_import
    except Exception as e:
        print(f"Não foi possível configurar safe_import no Linux: {e}")