#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
usb_detector.py - Módulo de Gestão de Mídia Removível e Heartbeat USB
Identifica automaticamente unidades USB montadas no Windows, Linux e macOS.
Monitora em segundo plano a presença física da unidade: se o usuário desconectar
o pendrive do computador, aciona o WIPE EMERGENCIAL DE RAM instantaneamente!
"""

import os
import sys
import time
import threading
from typing import List, Dict, Optional, Callable
from memory_security import emergency_panic_wipe


class USBDetector:
    """Localizador e monitor de unidades USB portáteis."""

    @staticmethod
    def get_removable_drives() -> List[Dict[str, str]]:
        """
        Retorna uma lista de dispositivos removíveis (pendrives USB) montados.
        Formato de retorno: [{'path': 'E:\\', 'name': 'KINGSTON (E:)', 'type': 'USB'}]
        """
        drives = []

        if sys.platform == 'win32':
            import ctypes
            kernel32 = ctypes.windll.kernel32
            bitmask = kernel32.GetLogicalDrives()
            for letter_idx in range(26):
                if bitmask & (1 << letter_idx):
                    letter = chr(65 + letter_idx) + ":\\"
                    # DRIVE_REMOVABLE = 2
                    drive_type = kernel32.GetDriveTypeW(letter)
                    if drive_type == 2:
                        # Obtém o rótulo do volume
                        vol_name_buf = ctypes.create_unicode_buffer(1024)
                        kernel32.GetVolumeInformationW(
                            letter, vol_name_buf, ctypes.sizeof(vol_name_buf),
                            None, None, None, None, 0
                        )
                        label = vol_name_buf.value or "Pendrive USB"
                        drives.append({
                            'path': letter,
                            'name': f"{label} ({letter})",
                            'type': 'USB Removível'
                        })

        elif sys.platform.startswith('linux'):
            # Procura em /media, /run/media e pontos vfat/exfat no /proc/mounts
            username = os.getenv('USER') or os.getenv('LOGNAME') or ''
            search_paths = [
                f"/media/{username}",
                f"/run/media/{username}",
                "/media",
                "/mnt"
            ]
            for base in search_paths:
                if os.path.exists(base):
                    try:
                        for entry in os.listdir(base):
                            full_p = os.path.join(base, entry)
                            if os.path.ismount(full_p) or os.path.isdir(full_p):
                                drives.append({
                                    'path': full_p,
                                    'name': f"Pendrive ({entry})",
                                    'type': 'USB Removível'
                                })
                    except Exception:
                        pass

        elif sys.platform == 'darwin':
            # macOS: /Volumes/* excluindo Macintosh HD
            volumes_dir = "/Volumes"
            if os.path.exists(volumes_dir):
                for vol in os.listdir(volumes_dir):
                    if vol not in ("Macintosh HD", "Recovery"):
                        full_p = os.path.join(volumes_dir, vol)
                        if os.path.ismount(full_p):
                            drives.append({
                                'path': full_p,
                                'name': f"USB ({vol})",
                                'type': 'USB Removível'
                            })

        # Se nenhum pendrive físico for detectado (ou em testes de bancada), inclui o diretório atual
        current_dir = os.path.abspath(os.path.dirname(__file__))
        drives.append({
            'path': current_dir,
            'name': f"Diretório Local Portátil ({current_dir})",
            'type': 'Pasta do Script'
        })

        return drives


class USBHeartbeatMonitor:
    """
    Thread sentinela de segurança: testa a cada 1.5s se a unidade USB
    ainda está fisicamente conectada à máquina. Se desconectada, zera a RAM!
    """

    def __init__(self, usb_root_path: str, on_disconnect_callback: Optional[Callable] = None):
        self.usb_root_path = usb_root_path
        self.on_disconnect_callback = on_disconnect_callback
        self._running = False
        self._thread: Optional[threading.Thread] = None

    def start(self):
        self._running = True
        self._thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False

    def _monitor_loop(self):
        while self._running:
            time.sleep(1.5)
            # Verifica se o caminho base do USB ainda existe no sistema de arquivos do SO
            if not os.path.exists(self.usb_root_path):
                # ALERTA MÁXIMO: PENDRIVE FOI PUXADO FISICAMENTE DO COMPUTADOR!
                print("\n[!] ALERTA CRÍTICO: Dispositivo USB desconectado!")
                print("[!] Acionando wipe imediato de RAM e destruição de sessão...")
                emergency_panic_wipe()
                if self.on_disconnect_callback:
                    try:
                        self.on_disconnect_callback()
                    except Exception:
                        pass
                # Encerra o processo imediatamente
                os._exit(1)
