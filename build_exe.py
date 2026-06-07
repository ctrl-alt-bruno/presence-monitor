#!/usr/bin/env python3
"""
Script para gerar o executável distribuível do Presence Monitor.

Uso:
    python build_exe.py

Requisitos:
    pip install pyinstaller
"""
import shutil
import subprocess
import sys
from pathlib import Path


def main():
    repo_root = Path(__file__).parent
    
    # Verificar se PyInstaller está instalado
    try:
        import PyInstaller
    except ImportError:
        print("[ERRO] PyInstaller não encontrado.")
        print("Instale com: pip install pyinstaller")
        sys.exit(1)
    
    print("[...] Limpando builds anteriores...")
    for d in ["build", "dist"]:
        if (repo_root / d).exists():
            shutil.rmtree(repo_root / d)
    spec_file = repo_root / "presence_monitor.spec"
    if spec_file.exists():
        spec_file.unlink()
    
    print("[...] Gerando executável com PyInstaller...")
    
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--name=PresenceMonitor",
        "--windowed",
        "--onefile",
        "--add-data", f"{repo_root}/face_detector.tflite:.",
        "--add-data", f"{repo_root}/bg_reference.npy:.",
        "--collect-all=mediapipe",
        "--collect-all=cv2",
        "--collect-all=pystray",
        "--hidden-import=pystray",
        "--icon=NONE",
        str(repo_root / "presence_monitor.py"),
    ]
    
    result = subprocess.run(cmd, cwd=repo_root)
    
    if result.returncode != 0:
        print("[ERRO] Falha ao gerar EXE.")
        sys.exit(1)
    
    exe_path = repo_root / "dist" / "PresenceMonitor.exe"
    if exe_path.exists():
        print(f"[OK] Executável criado com sucesso!")
        print(f"[OK] Localização: {exe_path}")
        print(f"[OK] Tamanho: {exe_path.stat().st_size / 1024 / 1024:.1f} MB")
        print("\n[INFO] Para distribuir:")
        print(f"  1. Use o arquivo: dist/PresenceMonitor.exe")
        print("  2. Crie um instalador (veja INSTALL.md)")
    else:
        print("[ERRO] EXE não foi criado.")
        sys.exit(1)


if __name__ == "__main__":
    main()
