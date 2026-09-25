# -*- mode: python ; coding: utf-8 -*-

import sys
import os
from PyInstaller.utils.hooks import collect_data_files

# --- Configuración del bloque de análisis ---
a = Analysis(
    ['server.py'],  # Tu script principal
    pathex=[],
    binaries=[],
    datas=[
        # Incluye la carpeta 'templates' y todo su contenido
        ('templates', 'templates'),
        # Si tuvieras una carpeta 'static', la incluirías aquí también
        # ('static', 'static'),
    ],
    hiddenimports=[
        # Dependencias que PyInstaller podría no detectar automáticamente
        'flask',
        'jinja2',
        'markupsafe',
        'werkzeug',
        'itsdangerous',
        'click',
        'qrcode',
        'PIL',          # Pillow
        'pkg_resources', # A veces necesario para paquetes con recursos
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    cipher=None,
)

# --- Configuración del ejecutable (PYZ) ---
pyz = PYZ(a.pure, a.zipped_data, cipher=None)

# --- Configuración del archivo EXE ---
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='wifi-file-transfer',  # Nombre del ejecutable (sin .exe)
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,         # Compresión UPX (reduce el tamaño)
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,     # Muestra la consola (útil para depuración)
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)