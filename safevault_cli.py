#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
safevault_cli.py - Modo Terminal Interativo do PyVault USB
Interface minimalista, rápida e segura para operação sem interface gráfica.
Protegida com mlock e destruição de memória por sinal.
"""

import os
import sys
import getpass
import secrets
import string
from vault_crypto import VaultCrypto
from memory_security import setup_security_hooks, emergency_panic_wipe, schedule_clipboard_wipe
from usb_detector import USBDetector


def main():
    setup_security_hooks()
    print("=" * 60)
    print("  PyVault USB - Gerenciador de Senhas Portátil em RAM (CLI)")
    print("=" * 60)

    drives = USBDetector.get_removable_drives()
    print("\n[+] Unidades de Armazenamento Detectadas:")
    for idx, d in enumerate(drives):
        print(f"  [{idx + 1}] {d['name']} ({d['path']})")

    choice = input("\nSelecione a unidade USB [1]: ").strip()
    drive_idx = int(choice) - 1 if choice.isdigit() and 1 <= int(choice) <= len(drives) else 0
    usb_path = drives[drive_idx]['path']
    vault_path = os.path.join(usb_path, ".vault.enc")

    if not os.path.exists(vault_path):
        print(f"\n[*] Nenhum cofre existente em {usb_path}.")
        create = input("Deseja criar um novo cofre neste pendrive? (s/n): ").strip().lower()
        if create != 's':
            sys.exit(0)
        pw = getpass.getpass("Defina a Senha Mestra: ")
        initial_data = {"version": 1, "entries": []}
        enc_bytes = VaultCrypto.encrypt_vault(initial_data, pw)
        with open(vault_path, "wb") as f:
            f.write(enc_bytes)
        print("[+] Cofre criado com sucesso no pendrive!")

    pw = getpass.getpass("Senha Mestra para desbloqueio: ")
    try:
        with open(vault_path, "rb") as f:
            data = f.read()
        vault = VaultCrypto.decrypt_vault(data, pw)
        print("[+] Cofre descriptografado com sucesso em RAM!")
    except Exception as e:
        print(f"[-] Falha na autenticação: {e}")
        sys.exit(1)

    while True:
        print("\n--- MENU DO COFRE ---")
        print(" [1] Listar todas as credenciais")
        print(" [2] Buscar credencial")
        print(" [3] Adicionar nova senha")
        print(" [4] Gerar senha aleatória forte")
        print(" [5] Salvar alterações no USB")
        print(" [0] Pânico / Bloquear e Sair")

        op = input("\nEscolha uma opção: ").strip()
        if op == '1':
            entries = vault.get("entries", [])
            print(f"\nTotal de registros: {len(entries)}")
            for i, ent in enumerate(entries):
                print(f" [{i+1}] {ent.get('title')} | Usuário: {ent.get('username')} | Senha: {ent.get('password')}")
        elif op == '2':
            term = input("Termo de busca: ").lower()
            for ent in vault.get("entries", []):
                if term in ent.get("title", "").lower() or term in ent.get("username", "").lower():
                    print(f" -> {ent.get('title')} | {ent.get('username')} | {ent.get('password')}")
        elif op == '3':
            title = input("Título / Serviço: ").strip()
            user = input("Usuário / E-mail: ").strip()
            password = getpass.getpass("Senha: ").strip()
            url = input("URL (opcional): ").strip()
            vault.setdefault("entries", []).append({
                "title": title, "username": user, "password": password, "url": url, "category": "Geral"
            })
            print("[+] Credencial adicionada à RAM!")
        elif op == '4':
            chars = string.ascii_letters + string.digits + "!@#$%^&*"
            rand_pw = "".join(secrets.choice(chars) for _ in range(24))
            print(f"\n[+] Senha Gerada (24 caracteres): {rand_pw}")
        elif op == '5':
            enc_bytes = VaultCrypto.encrypt_vault(vault, pw)
            with open(vault_path, "wb") as f:
                f.write(enc_bytes)
            print("[+] Dados criptografados e salvos no pendrive!")
        elif op == '0':
            print("\n[!] Zerando memória RAM e encerrando...")
            emergency_panic_wipe()
            break


if __name__ == "__main__":
    main()
