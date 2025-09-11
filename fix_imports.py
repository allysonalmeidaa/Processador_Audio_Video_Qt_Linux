# fix_imports.py
import sys

def restore_original_import():
    """Restaura a função __import__ original do Python"""
    try:
        import platform
        if platform.system() != "Linux":
            print("restore_original_import só deve ser executado no Linux.")
            return False

        import builtins
        # Recarrega o módulo builtins para restaurar a importação original
        if 'builtins' in sys.modules:
            del sys.modules['builtins']
        
        # Recarrega o módulo
        import builtins as _builtins
        builtins.__import__ = _builtins.__import__
        
        # Remove qualquer vestígio de safe_import
        if 'safe_import' in sys.modules:
            del sys.modules['safe_import']
            
        print("Função __import__ restaurada com sucesso")
        return True
        
    except Exception as e:
        print(f"Erro ao restaurar __import__: {e}")
        return False


restore_original_import()