#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
safevault_app.py - Interface Gráfica Segura Portátil
Execução autônoma em Python com suporte a Windows, Linux e macOS.
Não depende de bibliotecas externas pesadas (usa Tkinter nativo do Python).
Todas as senhas são mantidas exclusivamente em memória volátil.
"""

import os
import sys
import json
import secrets
import string
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, filedialog, PhotoImage
from typing import Dict, Any, Optional

from vault_crypto import VaultCrypto
from memory_security import (
    setup_security_hooks,
    emergency_panic_wipe,
    schedule_clipboard_wipe,
    clear_clipboard
)
from usb_detector import USBDetector, USBHeartbeatMonitor


class SafeVaultGUI:
    """Aplicação Gráfica Principal do PyVault USB."""

    VAULT_FILENAME = ".vault.enc"
    KEY_FILENAME = ".vault.key"

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Clavis - Sistema Portátil em RAM")
        self.root.geometry("880x620")
        self.root.minsize(880, 620)

        # Configura ganchos de segurança e bloqueio de memória
        setup_security_hooks()

        self.current_usb_path = ""
        self.master_password = ""
        self.keyfile_bytes: Optional[bytes] = None
        self.vault_data: Dict[str, Any] = {"version": 1, "entries": []}
        self.is_unlocked = False
        self.heartbeat_monitor: Optional[USBHeartbeatMonitor] = None
        self.inactivity_timeout_minutes = 5
        self.inactivity_timer_id = None

        self._configure_styles()
        self._bind_user_activity()
        self.show_login_screen()

    def _bind_user_activity(self):
        """Monitora qualquer interação de teclado ou mouse para reiniciar o timer de inatividade."""
        self.root.bind_all("<Key>", self._on_user_activity)
        self.root.bind_all("<Motion>", self._on_user_activity)
        self.root.bind_all("<Button>", self._on_user_activity)
        self.root.bind_all("<MouseWheel>", self._on_user_activity)

    def _on_user_activity(self, event=None):
        if self.is_unlocked:
            self.reset_inactivity_timer()

    def reset_inactivity_timer(self):
        """Reinicia o temporizador de bloqueio por inatividade."""
        if self.inactivity_timer_id:
            try:
                self.root.after_cancel(self.inactivity_timer_id)
            except Exception:
                pass
            self.inactivity_timer_id = None

        if self.inactivity_timeout_minutes > 0 and self.is_unlocked:
            ms = int(self.inactivity_timeout_minutes * 60 * 1000)
            self.inactivity_timer_id = self.root.after(ms, self._on_inactivity_timeout)

    def _on_inactivity_timeout(self):
        """Acionado após o tempo limite sem eventos de mouse ou teclado: zera RAM e fecha sessão."""
        if self.is_unlocked:
            self.lock_vault()
            messagebox.showinfo("Inatividade Detectada", "O cofre foi bloqueado automaticamente por inatividade e a memória RAM foi higienizada.")

    def _configure_styles(self):
        self.root.configure(bg="#1f1f21")
        style = ttk.Style()
        style.theme_use('clam')
        style.configure("TLabel", background="#1f1f21", foreground="#f8fafc", font=("Segoe UI", 10))
        style.configure("Header.TLabel", font=("Segoe UI", 14, "bold"), foreground="#38bdf8")
        style.configure("TButton", font=("Segoe UI", 10), padding=6)
        style.configure("Treeview", background="#1e293b", foreground="#f8fafc", fieldbackground="#1e293b", rowheight=28)
        style.map("Treeview", background=[('selected', '#0284c7')])

    def clear_screen(self):
        for widget in self.root.winfo_children():
            widget.destroy()

    def show_login_screen(self):
        """Tela inicial de desbloqueio e seleção de Pendrive USB."""
        self.clear_screen()
        self.is_unlocked = False

        container = tk.Frame(self.root, bg="#1f1f21", padx=30, pady=30)
        container.pack(expand=True)

        logo_path = os.path.join(os.path.dirname(__file__), "assets", "header_logo.png")
        self.logo_image = tk.PhotoImage(file=logo_path)

        if self.logo_image.width() > 560:
            scale = (self.logo_image.width() + 559) // 560
            self.logo_image = self.logo_image.subsample(scale, scale)

        tk.Label(container, image=self.logo_image, bg="#1f1f21").pack(pady=5)

        # Seleção de Pendrive
        drive_frame = tk.LabelFrame(container, text=" Unidade de Armazenamento USB ", bg="#1f1f21", fg="#38bdf8", padx=15, pady=15)
        drive_frame.pack(fill="x", pady=15)

        drives = USBDetector.get_removable_drives()
        drive_options = [f"{d['name']} -> {d['path']}" for d in drives]
        self.selected_drive_var = tk.StringVar(value=drive_options[0] if drive_options else "")

        tk.Label(drive_frame, text="Pendrive Detectado:", bg="#1f1f21", fg="#cbd5e1").pack(anchor="w")
        drive_combo = ttk.Combobox(drive_frame, textvariable=self.selected_drive_var, values=drive_options, state="readonly", width=50)
        drive_combo.pack(fill="x", pady=5)

        # Senha Mestra
        auth_frame = tk.LabelFrame(container, text=" Autenticação Mestra ", bg="#1f1f21", fg="#38bdf8", padx=15, pady=15)
        auth_frame.pack(fill="x", pady=10)

        tk.Label(auth_frame, text="Senha Mestra do Cofre:", bg="#1f1f21", fg="#cbd5e1").pack(anchor="w")
        self.password_entry = tk.Entry(auth_frame, show="•", bg="#1e293b", fg="#ffffff", insertbackground="white", font=("Segoe UI", 11), relief="flat")
        self.password_entry.pack(fill="x", pady=5, ipady=4)
        self.password_entry.focus()
        self.password_entry.bind("<Return>", lambda e: self.unlock_vault())

        # Opção de Chave Física (.key)
        self.use_keyfile_var = tk.BooleanVar(value=False)
        tk.Checkbutton(auth_frame, text="Exigir segundo fator físico (.vault.key gravado no USB)", variable=self.use_keyfile_var, bg="#1f1f21", fg="#cbd5e1", selectcolor="#1e293b", activebackground="#1f1f21").pack(anchor="w", pady=5)

        # Botões de Ação
        btn_frame = tk.Frame(container, bg="#1f1f21")
        btn_frame.pack(fill="x", pady=15)

        unlock_btn = tk.Button(btn_frame, text=" Desbloquear Cofre em RAM ", bg="#0284c7", fg="white", font=("Segoe UI", 11, "bold"), relief="flat", padx=15, pady=8, command=self.unlock_vault)
        unlock_btn.pack(side="left", expand=True, fill="x", padx=5)

        new_vault_btn = tk.Button(btn_frame, text=" Criar Novo Cofre no USB ", bg="#334155", fg="white", font=("Segoe UI", 10), relief="flat", padx=10, pady=8, command=self.create_new_vault)
        new_vault_btn.pack(side="right", expand=True, fill="x", padx=5)

    def _get_target_usb_path(self) -> str:
        sel = self.selected_drive_var.get()
        if " -> " in sel:
            return sel.split(" -> ")[-1].strip()
        return os.path.abspath(os.path.dirname(__file__))

    def unlock_vault(self):
        """Lê o arquivo cifrado do pendrive e descriptografa EXCLUSIVAMENTE na RAM."""
        master_pw = self.password_entry.get().strip()
        if not master_pw:
            messagebox.showerror("Erro", "Informe a senha mestra!")
            return

        usb_path = self._get_target_usb_path()
        vault_file = os.path.join(usb_path, self.VAULT_FILENAME)

        if not os.path.exists(vault_file):
            messagebox.showerror("Cofre não Encontrado", f"Nenhum cofre existente em {usb_path}.\nClique em 'Criar Novo Cofre'.")
            return

        keyfile_bytes = None
        if self.use_keyfile_var.get():
            kf_path = os.path.join(usb_path, self.KEY_FILENAME)
            if not os.path.exists(kf_path):
                messagebox.showerror("Chave Física Ausente", f"Arquivo {self.KEY_FILENAME} não encontrado no USB!")
                return
            with open(kf_path, "rb") as kf:
                keyfile_bytes = kf.read()

        try:
            with open(vault_file, "rb") as f:
                encrypted_bytes = f.read()

            # Decifra diretamente na RAM
            self.vault_data = VaultCrypto.decrypt_vault(encrypted_bytes, master_pw, keyfile_bytes)
            self.current_usb_path = usb_path
            self.master_password = master_pw
            self.keyfile_bytes = keyfile_bytes
            self.is_unlocked = True

            # Inicia o monitor de presença física do USB
            self.heartbeat_monitor = USBHeartbeatMonitor(usb_path, on_disconnect_callback=self.on_usb_unplugged)
            self.heartbeat_monitor.start()

            self.show_dashboard()
        except Exception as exc:
            messagebox.showerror("Falha de Autenticação", f"Erro: {str(exc)}")

    def create_new_vault(self):
        """Inicializa um novo cofre criptografado no pendrive USB."""
        master_pw = self.password_entry.get().strip()
        if len(master_pw) < 8:
            messagebox.showwarning("Senha Curta", "A senha mestra deve conter ao menos 8 caracteres para proteção AES-256.")
            return

        usb_path = self._get_target_usb_path()
        vault_file = os.path.join(usb_path, self.VAULT_FILENAME)

        keyfile_bytes = None
        if self.use_keyfile_var.get():
            keyfile_bytes = secrets.token_bytes(32)
            kf_path = os.path.join(usb_path, self.KEY_FILENAME)
            with open(kf_path, "wb") as kf:
                kf.write(keyfile_bytes)

        initial_data = {
            "version": 1,
            "created_at": "now",
            "entries": []
        }

        # Cifra em RAM e grava os bytes cifrados diretamente no USB
        enc_bytes = VaultCrypto.encrypt_vault(initial_data, master_pw, keyfile_bytes)
        with open(vault_file, "wb") as vf:
            vf.write(enc_bytes)

        messagebox.showinfo("Sucesso", f"Cofre criado com sucesso em:\n{vault_file}")
        self.unlock_vault()

    def show_dashboard(self):
        """Painel com gerenciamento completo de senhas em memória volátil."""
        self.clear_screen()

        # Barra Superior
        top_bar = tk.Frame(self.root, bg="#1e293b", padx=15, pady=10)
        top_bar.pack(fill="x")

        tk.Label(top_bar, text=" Clavis USB", font=("Segoe UI", 12, "bold"), bg="#1e293b", fg="#38bdf8").pack(side="left")
        tk.Label(top_bar, text=f"Unidade: {self.current_usb_path}", font=("Segoe UI", 9), bg="#1e293b", fg="#94a3b8").pack(side="left", padx=10)

        # Seletor de Inatividade
        tk.Label(top_bar, text="Auto-lock:", font=("Segoe UI", 9), bg="#1e293b", fg="#94a3b8").pack(side="left", padx=(10, 2))
        self.inactivity_var = tk.StringVar(value=f"{self.inactivity_timeout_minutes} min" if self.inactivity_timeout_minutes > 0 else "Desativado")
        inactivity_combo = ttk.Combobox(top_bar, textvariable=self.inactivity_var, values=["1 min (teste)", "5 min", "15 min", "30 min", "Desativado"], state="readonly", width=13)
        inactivity_combo.pack(side="left", padx=2)

        def _on_inactivity_select(event):
            sel = self.inactivity_var.get()
            if "1 min" in sel:
                self.inactivity_timeout_minutes = 1
            elif "5 min" in sel:
                self.inactivity_timeout_minutes = 5
            elif "15 min" in sel:
                self.inactivity_timeout_minutes = 15
            elif "30 min" in sel:
                self.inactivity_timeout_minutes = 30
            else:
                self.inactivity_timeout_minutes = 0
            self.reset_inactivity_timer()

        inactivity_combo.bind("<<ComboboxSelected>>", _on_inactivity_select)

        # Inicia temporizador de inatividade
        self.reset_inactivity_timer()

        # Botão de Pânico / Desconectar
        panic_btn = tk.Button(top_bar, text=" Zerar RAM e Sair ", bg="#ef4444", fg="white", font=("Segoe UI", 9, "bold"), relief="flat", padx=8, pady=4, command=self.emergency_exit)
        panic_btn.pack(side="right", padx=5)

        lock_btn = tk.Button(top_bar, text=" Bloquear Cofre ", bg="#475569", fg="white", font=("Segoe UI", 9), relief="flat", padx=8, pady=4, command=self.lock_vault)
        lock_btn.pack(side="right", padx=5)

        # Barra de Ferramentas
        toolbar = tk.Frame(self.root, bg="#1f1f21", padx=15, pady=10)
        toolbar.pack(fill="x")

        tk.Button(toolbar, text=" + Nova Senha ", bg="#0284c7", fg="white", font=("Segoe UI", 9, "bold"), relief="flat", padx=10, pady=5, command=self.add_entry_dialog).pack(side="left", padx=5)
        tk.Button(toolbar, text=" Gerador Aleatório ", bg="#334155", fg="white", font=("Segoe UI", 9), relief="flat", padx=10, pady=5, command=self.show_generator_dialog).pack(side="left", padx=5)
        tk.Button(toolbar, text=" Salvar no USB ", bg="#10b981", fg="white", font=("Segoe UI", 9, "bold"), relief="flat", padx=10, pady=5, command=self.save_vault_to_usb).pack(side="left", padx=5)
        tk.Button(toolbar, text=" Importar / Exportar ", bg="#0369a1", fg="white", font=("Segoe UI", 9), relief="flat", padx=10, pady=5, command=self.show_import_export_dialog).pack(side="left", padx=5)

        # Campo de Busca
        tk.Label(toolbar, text="Buscar:", bg="#1f1f21", fg="#94a3b8").pack(side="left", padx=(20, 5))
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *a: self.refresh_entries())
        search_entry = tk.Entry(toolbar, textvariable=self.search_var, bg="#1e293b", fg="white", insertbackground="white", width=25, relief="flat")
        search_entry.pack(side="left", ipady=3)

        # Tabela de Entradas
        table_frame = tk.Frame(self.root, bg="#1f1f21", padx=15, pady=5)
        table_frame.pack(fill="both", expand=True)

        columns = ("title", "category", "username", "password", "url")
        self.tree = ttk.Treeview(table_frame, columns=columns, show="headings", selectmode="browse")
        self.tree.heading("title", text="Título / Serviço")
        self.tree.heading("category", text="Categoria")
        self.tree.heading("username", text="Usuário / E-mail")
        self.tree.heading("password", text="Senha (Oculta)")
        self.tree.heading("url", text="URL / Host")

        self.tree.column("title", width=180)
        self.tree.column("category", width=110)
        self.tree.column("username", width=180)
        self.tree.column("password", width=120)
        self.tree.column("url", width=200)

        self.tree.pack(fill="both", expand=True, side="left")
        scroll = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")

        # Barra inferior de ações de item
        action_bar = tk.Frame(self.root, bg="#1e293b", padx=15, pady=10)
        action_bar.pack(fill="x")

        tk.Button(action_bar, text=" Copiar Senha (Auto-Clear 20s) ", bg="#0284c7", fg="white", relief="flat", padx=10, pady=5, command=self.copy_selected_password).pack(side="left", padx=5)
        tk.Button(action_bar, text=" Copiar Usuário ", bg="#334155", fg="white", relief="flat", padx=10, pady=5, command=self.copy_selected_username).pack(side="left", padx=5)
        tk.Button(action_bar, text=" Editar ", bg="#334155", fg="white", relief="flat", padx=10, pady=5, command=self.edit_selected_entry).pack(side="left", padx=5)
        tk.Button(action_bar, text=" Excluir ", bg="#dc2626", fg="white", relief="flat", padx=10, pady=5, command=self.delete_selected_entry).pack(side="left", padx=5)

        self.status_label = tk.Label(action_bar, text="Pronto | Proteção de memória mlock ativa", bg="#1e293b", fg="#10b981", font=("Segoe UI", 9))
        self.status_label.pack(side="right", padx=10)

        self.refresh_entries()

    def refresh_entries(self):
        for item in self.tree.get_children():
            self.tree.delete(item)

        query = self.search_var.get().lower().strip()
        for idx, entry in enumerate(self.vault_data.get("entries", [])):
            t = entry.get("title", "")
            u = entry.get("username", "")
            c = entry.get("category", "Geral")
            url = entry.get("url", "")
            if query and not (query in t.lower() or query in u.lower() or query in c.lower() or query in url.lower()):
                continue

            self.tree.insert("", "end", iid=str(idx), values=(t, c, u, "••••••••••••", url))

    def copy_selected_password(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Aviso", "Selecione uma credencial na tabela.")
            return
        idx = int(sel[0])
        entry = self.vault_data["entries"][idx]
        pw = entry.get("password", "")

        self.root.clipboard_clear()
        self.root.clipboard_append(pw)
        self.root.update()

        # Agenda a limpeza da área de transferência após 20 segundos
        schedule_clipboard_wipe(20)
        self.status_label.config(text="Senha copiada! Será apagada do clipboard em 20s.", fg="#f59e0b")

    def copy_selected_username(self):
        sel = self.tree.selection()
        if not sel:
            return
        idx = int(sel[0])
        u = self.vault_data["entries"][idx].get("username", "")
        self.root.clipboard_clear()
        self.root.clipboard_append(u)
        self.root.update()
        self.status_label.config(text="Usuário copiado para o clipboard.", fg="#38bdf8")

    def add_entry_dialog(self):
        self._entry_dialog("Nova Credencial", {})

    def edit_selected_entry(self):
        sel = self.tree.selection()
        if not sel:
            return
        idx = int(sel[0])
        self._entry_dialog("Editar Credencial", self.vault_data["entries"][idx], idx)

    def _entry_dialog(self, title: str, entry_data: Dict[str, Any], edit_idx: Optional[int] = None):
        dialog = tk.Toplevel(self.root)
        dialog.title(title)
        dialog.geometry("420x460")
        dialog.configure(bg="#1f1f21")
        dialog.transient(self.root)
        dialog.grab_set()

        fields = [
            ("Título:", "title", entry_data.get("title", "")),
            ("Categoria:", "category", entry_data.get("category", "Geral")),
            ("Usuário / E-mail:", "username", entry_data.get("username", "")),
            ("Senha:", "password", entry_data.get("password", "")),
            ("URL / Serviço:", "url", entry_data.get("url", "")),
            ("Notas (Opcional):", "notes", entry_data.get("notes", ""))
        ]

        entries = {}
        for row, (lbl, key, val) in enumerate(fields):
            tk.Label(dialog, text=lbl, bg="#1f1f21", fg="#cbd5e1").pack(anchor="w", padx=20, pady=(8, 2))
            ent = tk.Entry(dialog, bg="#1e293b", fg="white", insertbackground="white", relief="flat")
            ent.insert(0, val)
            ent.pack(fill="x", padx=20, ipady=3)
            entries[key] = ent

        def save():
            new_item = {k: ent.get().strip() for k, ent in entries.items()}
            if not new_item["title"] or not new_item["password"]:
                messagebox.showerror("Erro", "Título e Senha são obrigatórios!")
                return
            if edit_idx is not None:
                self.vault_data["entries"][edit_idx] = new_item
            else:
                self.vault_data.setdefault("entries", []).append(new_item)
            self.refresh_entries()
            dialog.destroy()
            self.save_vault_to_usb(silent=True)

        tk.Button(dialog, text="Salvar Credencial", bg="#0284c7", fg="white", relief="flat", font=("Segoe UI", 10, "bold"), pady=6, command=save).pack(fill="x", padx=20, pady=20)

    def delete_selected_entry(self):
        sel = self.tree.selection()
        if not sel:
            return
        idx = int(sel[0])
        if messagebox.askyesno("Confirmar Exclusão", "Deseja realmente excluir esta credencial permanentemente?"):
            del self.vault_data["entries"][idx]
            self.refresh_entries()
            self.save_vault_to_usb(silent=True)

    def show_generator_dialog(self):
        pw = "".join(secrets.choice(string.ascii_letters + string.digits + "!@#$%^&*()-_=+") for _ in range(20))
        res = simpledialog.askstring("Gerador de Senha Segura", "Senha gerada aleatoriamente (alta entropia):", initialvalue=pw, parent=self.root)
        if res:
            self.root.clipboard_clear()
            self.root.clipboard_append(res)
            schedule_clipboard_wipe(20)
            self.status_label.config(text="Senha gerada copiada para o clipboard!", fg="#10b981")

    def show_import_export_dialog(self):
        """Janela modal para Importar e Exportar dados (.csv ou .json com confirmação de senha)."""
        dialog = tk.Toplevel(self.root)
        dialog.title("Importação & Exportação Segura (RAM)")
        dialog.geometry("520x480")
        dialog.configure(bg="#1f1f21")
        dialog.transient(self.root)
        dialog.grab_set()

        tk.Label(dialog, text="Importação & Exportação de Credenciais", bg="#1f1f21", fg="#38bdf8", font=("Segoe UI", 12, "bold")).pack(pady=(15, 3))
        tk.Label(dialog, text="Processamento volátil 100% em memória RAM", bg="#1f1f21", fg="#94a3b8", font=("Segoe UI", 9)).pack(pady=(0, 12))

        # --- SEÇÃO EXPORTAÇÃO ---
        exp_frame = tk.LabelFrame(dialog, text=" 1. Exportar Dados ", bg="#1e293b", fg="#cbd5e1", font=("Segoe UI", 10, "bold"), padx=12, pady=8)
        exp_frame.pack(fill="x", padx=20, pady=(0, 12))

        fmt_var = tk.StringVar(value="json")
        enc_var = tk.BooleanVar(value=True)

        f_box = tk.Frame(exp_frame, bg="#1e293b")
        f_box.pack(fill="x", pady=2)
        tk.Label(f_box, text="Formato:", bg="#1e293b", fg="#94a3b8").pack(side="left")
        tk.Radiobutton(f_box, text="JSON (.json)", variable=fmt_var, value="json", bg="#1e293b", fg="white", selectcolor="#1f1f21").pack(side="left", padx=10)
        tk.Radiobutton(f_box, text="Planilha CSV (.csv)", variable=fmt_var, value="csv", bg="#1e293b", fg="white", selectcolor="#1f1f21").pack(side="left")

        enc_box = tk.Frame(exp_frame, bg="#1e293b")
        enc_box.pack(fill="x", pady=2)
        tk.Checkbutton(enc_box, text="Criptografar saída com AES-256-GCM + Argon2id (JSON)", variable=enc_var, bg="#1e293b", fg="#38bdf8", selectcolor="#1f1f21").pack(anchor="w")

        def do_export():
            # Camada obrigatória de confirmação de senha antes do download/export
            pw = simpledialog.askstring("Segurança: Confirmação de Senha", "Digite sua SENHA MESTRA para autorizar o download do arquivo:", show="*", parent=dialog)
            if not pw:
                return
            if pw != self.master_password:
                messagebox.showerror("Acesso Negado", "Senha mestra incorreta! Exportação cancelada.")
                return

            fmt = fmt_var.get()
            should_enc = enc_var.get() and fmt == "json"

            if fmt == "csv":
                filepath = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV Files", "*.csv")], title="Salvar Exportação CSV")
                if not filepath:
                    return
                csv_content = VaultCrypto.export_to_csv(self.vault_data.get("entries", []))
                with open(filepath, "w", encoding="utf-8", newline="") as f:
                    f.write(csv_content)
                messagebox.showinfo("Exportação Concluída", f"Exportação CSV salva em: {filepath}\nAtenção: senhas salvas em texto puro!")
            else:
                ext = ".vault.json" if should_enc else ".json"
                filepath = filedialog.asksaveasfilename(defaultextension=ext, filetypes=[("JSON Files", "*.json")], title="Salvar Exportação JSON")
                if not filepath:
                    return
                if should_enc:
                    enc_bytes = VaultCrypto.encrypt_vault(self.vault_data, self.master_password, self.keyfile_bytes, use_argon2=True)
                    with open(filepath, "wb") as f:
                        f.write(enc_bytes)
                    messagebox.showinfo("Exportação Concluída", f"Backup criptografado com AES-256-GCM e Argon2id gerado em:\n{filepath}")
                else:
                    with open(filepath, "w", encoding="utf-8") as f:
                        json.dump(self.vault_data.get("entries", []), f, indent=2, ensure_ascii=False)
                    messagebox.showinfo("Exportação Concluída", f"Arquivo JSON exportado em:\n{filepath}")

            dialog.destroy()

        tk.Button(exp_frame, text="Confirmar Senha & Exportar Arquivo", bg="#0284c7", fg="white", font=("Segoe UI", 9, "bold"), relief="flat", pady=4, command=do_export).pack(fill="x", pady=(6, 2))

        # --- SEÇÃO IMPORTAÇÃO ---
        imp_frame = tk.LabelFrame(dialog, text=" 2. Importar Dados (.csv ou .json) ", bg="#1e293b", fg="#cbd5e1", font=("Segoe UI", 10, "bold"), padx=12, pady=8)
        imp_frame.pack(fill="x", padx=20, pady=(0, 10))

        def do_import():
            filepath = filedialog.askopenfilename(filetypes=[("Arquivos Suportados", "*.csv;*.json;*.enc"), ("CSV", "*.csv"), ("JSON", "*.json")], title="Selecionar Arquivo para Importação")
            if not filepath:
                return

            try:
                new_entries = []
                if filepath.endswith(".csv"):
                    with open(filepath, "r", encoding="utf-8", errors="replace") as f:
                        new_entries = VaultCrypto.parse_csv_entries(f.read())
                else:
                    with open(filepath, "rb") as f:
                        raw = f.read()
                    try:
                        parsed = json.loads(raw.decode("utf-8"))
                        if isinstance(parsed, list):
                            new_entries = parsed
                        elif isinstance(parsed, dict) and "entries" in parsed:
                            new_entries = parsed["entries"]
                    except Exception:
                        dec_pw = simpledialog.askstring("Cofre Criptografado", "Este arquivo parece estar cifrado. Insira a senha mestra dele:", show="*", parent=dialog)
                        if not dec_pw:
                            return
                        dec_data = VaultCrypto.decrypt_vault(raw, dec_pw)
                        new_entries = dec_data.get("entries", [])

                if not new_entries:
                    messagebox.showwarning("Aviso", "Nenhum registro encontrado no arquivo.")
                    return

                action = messagebox.askyesnocancel("Modo de Importação", f"Foram encontrados {len(new_entries)} registros.\n\nClique 'Sim' para MESCLAR com os registros atuais.\nClique 'Não' para SUBSTITUIR todo o cofre atual.")
                if action is None:
                    return

                if action is False:
                    self.vault_data["entries"] = new_entries
                else:
                    titles = {e.get("title", "").lower() for e in self.vault_data.get("entries", [])}
                    for item in new_entries:
                        if item.get("title", "").lower() not in titles:
                            self.vault_data.setdefault("entries", []).append(item)

                self.refresh_entries()
                self.save_vault_to_usb(silent=True)
                messagebox.showinfo("Sucesso", f"{len(new_entries)} credenciais importadas para a RAM com sucesso!")
                dialog.destroy()
            except Exception as e:
                messagebox.showerror("Erro de Importação", f"Falha ao importar: {str(e)}")

        tk.Button(imp_frame, text="Selecionar Arquivo para Importar na RAM", bg="#10b981", fg="white", font=("Segoe UI", 9, "bold"), relief="flat", pady=4, command=do_import).pack(fill="x", pady=4)

    def save_vault_to_usb(self, silent: bool = False):
        """Cifra os dados atualizados em RAM e grava atomicamente no pendrive USB."""
        try:
            vault_file = os.path.join(self.current_usb_path, self.VAULT_FILENAME)
            enc_bytes = VaultCrypto.encrypt_vault(self.vault_data, self.master_password, self.keyfile_bytes)
            # Escrita atômica para evitar corrupção
            tmp_target = vault_file + ".tmp"
            with open(tmp_target, "wb") as f:
                f.write(enc_bytes)
            if os.path.exists(vault_file):
                os.replace(tmp_target, vault_file)
            else:
                os.rename(tmp_target, vault_file)

            if not silent:
                messagebox.showinfo("Cofre Salvo", "Dados cifrados e persistidos com sucesso no pendrive USB!")
                self.status_label.config(text="Cofre gravado com sucesso no USB.", fg="#10b981")
        except Exception as exc:
            messagebox.showerror("Erro ao Salvar", f"Falha ao persistir no USB: {str(exc)}")

    def lock_vault(self):
        """Bloqueia o cofre e zera as estruturas da memória RAM."""
        if self.inactivity_timer_id:
            try:
                self.root.after_cancel(self.inactivity_timer_id)
            except Exception:
                pass
            self.inactivity_timer_id = None
        if self.heartbeat_monitor:
            self.heartbeat_monitor.stop()
        self.vault_data = {"version": 1, "entries": []}
        self.master_password = ""
        self.keyfile_bytes = None
        emergency_panic_wipe()
        self.show_login_screen()

    def emergency_exit(self):
        """Zera toda a memória volátil e mata o processo."""
        emergency_panic_wipe()
        self.root.destroy()
        sys.exit(0)

    def on_usb_unplugged(self):
        """Disparado pelo monitor heartbeat quando o pendrive é removido."""
        self.root.after(0, self.root.destroy)


if __name__ == "__main__":
    app_root = tk.Tk()
    app = SafeVaultGUI(app_root)
    app_root.mainloop()
