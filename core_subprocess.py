import os
import sys
import json
import traceback

def main():
    try:
        if len(sys.argv) < 4:
            raise ValueError("Uso: core_subprocess.py <caminho_arquivo> <modelo> <idioma|auto>")

        caminho_arquivo = sys.argv[1]
        modelo = sys.argv[2]
        idioma = sys.argv[3]
        if idioma == "None":
            idioma = None

        from Transcricao_core_V3 import transcrever_com_diarizacao

        texto = transcrever_com_diarizacao(
            caminho_arquivo,
            modelo_escolhido=modelo,
            idioma=idioma,
            progresso_callback=None,
            checar_cancelamento=None
        )

        out = {
            "success": True,
            "text": texto if isinstance(texto, str) else str(texto),
            "with_diarization": True,
            "segments": []  # placeholder
        }
        print(json.dumps(out, ensure_ascii=False))
        return 0

    except Exception as e:
        err = {
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }
        print(json.dumps(err, ensure_ascii=False))
        return 1

if __name__ == "__main__":
    sys.exit(main())