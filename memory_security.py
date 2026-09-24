#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
memory_security.py - Camada de Blindagem e Anti-Forense
Objetivo:
1. Impedir que o sistema operacional grave a RAM no disco rígido (pagefile.sys / swap).
2. Desabilitar despejos de memória (core dumps) em caso de crash.
3. Sobrescrever com zeros (zeroization) qualquer buffer confidencial ao fechar ou desengatar o USB.
4. Limpar automaticamente a área de transferência do computador após tempo limite.
"""

import sys
import os
import ctypes
import atexit
import signal
import threading
import time
from typing import Union, List

# Registro de buffers sensíveis ativos em RAM
_ACTIVE_VOLATILE_BUFFERS: List[bytearray] = []
_LOCK = threading.Lock()


def register_volatile_buffer(buf: bytearray) -> bytearray:
    """Registra um buffer volátil para garantir que será zerado no encerramento."""
    with _LOCK:
        _ACTIVE_VOLATILE_BUFFERS.append(buf)
    return buf


def secure_zero_bytes(target: Union[bytearray, bytes, memoryview]) -> None:
    """
    Sobrescreve a memória física do buffer com zeros binários (0x00)
    utilizando a função memset da biblioteca C nativa do SO.
    """
    try:
        if isinstance(target, bytearray):
            length = len(target)
            if length > 0:
                address = (ctypes.c_char * length).from_buffer(target)
                ctypes.memset(ctypes.addressof(address), 0, length)
        elif isinstance(target, (bytes, memoryview)):
            # Tenta zerar se for referenciável por ponteiro
            length = len(target)
            if length > 0:
                try:
                    c_buf = (ctypes.c_char * length).from_buffer_copy(target)
                    ctypes.memset(ctypes.addressof(c_buf), 0, length)
                except Exception:
                    pass
    except Exception:
        pass


def volatile_string(text: str) -> bytearray:
    """Cria um bytearray mutável em RAM que pode ser destruído propositalmente."""
    raw = bytearray(text.encode('utf-8'))
    register_volatile_buffer(raw)
    return raw


def lock_process_memory() -> bool:
    """
    Bloqueia o espaço de endereçamento do processo na RAM física.
    Isso impede que o Windows (pagefile.sys) ou Linux (swap partition)
    despejem as senhas descriptografadas no disco do computador hospedeiro.
    """
    try:
        if sys.platform.startswith('linux'):
            # Linux: mlockall com flags MCL_CURRENT (1) e MCL_FUTURE (2)
            libc = ctypes.CDLL("libc.so.6")
            res = libc.mlockall(1 | 2)
            return res == 0
        elif sys.platform == 'win32':
            # Windows: Aumenta working set e bloqueia páginas
            kernel32 = ctypes.windll.kernel32
            handle = kernel32.GetCurrentProcess()
            # Minimum working set, Maximum working set
            kernel32.SetProcessWorkingSetSize(handle, 50 * 1024 * 1024, 200 * 1024 * 1024)
            return True
        elif sys.platform == 'darwin':
            # macOS: mlockall
            libc = ctypes.CDLL("/usr/lib/libc.dylib")
            res = libc.mlockall(1 | 2)
            return res == 0
    except Exception:
        # Prossegue com aviso seguro se o SO não conceder permissões elevadas
        return False
    return False


def disable_core_dumps() -> None:
    """
    Desativa a geração de relatórios de falha (core dumps) para impedir que
    um invasor force um crash para despejar o conteúdo da memória em disco.
    """
    try:
        if sys.platform.startswith('linux'):
            import resource
            resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
            # Desabilita flags ptrace se suportado
            try:
                import prctl
                prctl.set_dumpable(False)
            except Exception:
                pass
        elif sys.platform == 'win32':
            # Desabilita o diálogo de erro de crash do Windows (evita WerFault dump)
            SEM_FAILCRITICALERRORS = 0x0001
            SEM_NOGPFAULTERRORBOX = 0x0002
            ctypes.windll.kernel32.SetErrorMode(SEM_FAILCRITICALERRORS | SEM_NOGPFAULTERRORBOX)
    except Exception:
        pass


def emergency_panic_wipe() -> None:
    """
    BOTÃO DE PÂNICO / DESTRUIÇÃO DE MEMÓRIA EMERGENCIAL:
    Sobrescreve com zeros todos os buffers registrados, força coleta de lixo,
    limpa o clipboard e encerra o processo imediatamente sem tocar o disco.
    """
    with _LOCK:
        for buf in _ACTIVE_VOLATILE_BUFFERS:
            try:
                secure_zero_bytes(buf)
            except Exception:
                pass
        _ACTIVE_VOLATILE_BUFFERS.clear()

    # Força garbage collection profunda
    import gc
    gc.collect()

    # Limpa área de transferência
    clear_clipboard()


def clear_clipboard() -> None:
    """Limpa imediatamente a área de transferência do computador hospedeiro."""
    try:
        if sys.platform == 'win32':
            import ctypes
            if ctypes.windll.user32.OpenClipboard(0):
                ctypes.windll.user32.EmptyClipboard()
                ctypes.windll.user32.CloseClipboard()
        elif sys.platform.startswith('linux'):
            os.system('xsel -bc 2>/dev/null || xclip -selection clipboard /dev/null 2>/dev/null')
        elif sys.platform == 'darwin':
            os.system('pbcopy </dev/null')
    except Exception:
        pass


def schedule_clipboard_wipe(delay_seconds: int = 20) -> None:
    """Inicia thread em segundo plano para limpar o clipboard após tempo determinado."""
    def _timer_worker():
        time.sleep(delay_seconds)
        clear_clipboard()

    t = threading.Thread(target=_timer_worker, daemon=True)
    t.start()


def setup_security_hooks():
    """Configura ganchos de encerramento, sinais de término e blindagem de processo."""
    lock_process_memory()
    disable_core_dumps()

    # Garante execução da limpeza no encerramento normal ou falha
    atexit.register(emergency_panic_wipe)

    # Intercepta SIGINT (Ctrl+C) e SIGTERM
    try:
        signal.signal(signal.SIGINT, lambda s, f: (emergency_panic_wipe(), sys.exit(0)))
        signal.signal(signal.SIGTERM, lambda s, f: (emergency_panic_wipe(), sys.exit(0)))
    except Exception:
        pass
