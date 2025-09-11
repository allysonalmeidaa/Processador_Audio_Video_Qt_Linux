#!/usr/bin/env python3
# Script auxiliar para transcrição de áudio em processo separado
import os
import sys
import argparse
import traceback

def main():
    # Parser de argumentos da linha de comando
    parser = argparse.ArgumentParser(description='Helper script for audio transcription')
    parser.add_argument('--file', type=str, required=True, help='Path to audio file')
    parser.add_argument('--model', type=str, default='small', help='Model size (tiny, base, small, medium, large)')
    parser.add_argument('--language', type=str, help='Language code (optional)')
    
    # Parse dos argumentos
    args = parser.parse_args()
    
    try:
        # Importamos o whisper aqui dentro do processo separado
        import whisper
        
        # Carregamos o modelo
        model = whisper.load_model(args.model)
        
        # Configuramos os parâmetros da transcrição
        transcribe_options = {}
        if args.language and args.language != "auto":
            transcribe_options["language"] = args.language
        
        # Fazemos a transcrição
        result = model.transcribe(args.file, **transcribe_options)
        
        # Retornamos o texto transcrito
        print(result["text"])
        return 0
        
    except Exception as e:
        print(f"ERRO: {str(e)}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        return 1

if __name__ == "__main__":
    sys.exit(main())