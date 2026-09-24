#!/usr/bin/env bash
# ==============================================================================
# PyVault USB - Inicializador de Alta Segurança para Linux & macOS
# ==============================================================================

# 1. Garante que nada de bytecode .pyc seja escrito no sistema de arquivos do PC
export PYTHONDONTWRITEBYTECODE=1
export PYTHONHASHSEED=random

# 2. Desabilita core dumps no terminal atual
ulimit -c 0

# 3. Diretório do script (no pendrive)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# 4. Executa com python3 sem criar caches
if command -v python3 >/dev/null 2>&1; then
    python3 -B "$SCRIPT_DIR/safevault_app.py"
else
    echo "Python 3 não encontrado no sistema hospedeiro."
    read -p "Pressione Enter para sair..."
fi
