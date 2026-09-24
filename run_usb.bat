@echo off
:: ============================================================================
:: PyVault USB - Inicializador de Alta Segurança para Windows
:: Garante que NENHUM arquivo .pyc (bytecode compilado) seja escrito no PC hospedeiro!
:: ============================================================================
title PyVault USB - Execucao Segura em RAM

:: 1. Desabilita gravação de bytecode .pyc em disco
set PYTHONDONTWRITEBYTECODE=1

:: 2. Força seed aleatória de hashing para mitigar colisões
set PYTHONHASHSEED=random

:: 3. Define pasta temporária apontando para o próprio USB (nunca C:\Users\...\Temp)
set TEMP=%~dp0.temp
set TMP=%~dp0.temp

:: Executa a aplicação com a flag -B (não gravar .pyc)
python -B safevault_app.py

:: Ao fechar, garante limpeza imediata
exit /b
