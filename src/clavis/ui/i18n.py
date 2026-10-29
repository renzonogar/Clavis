"""Small runtime translation catalog for the two supported interface languages."""

from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QComboBox, QWidget


_LANGUAGE = "en"

_PT_TO_EN = {
    "Seu cofre. Seu dispositivo. Seu controle.": "Your vault. Your device. Your control.",
    "Clavis é um gerenciador local de senhas. Seu arquivo KDBX é criptografado e pode ser armazenado em uma unidade USB ou em outro local escolhido.": "Clavis is a local password manager. Your encrypted KDBX file can be stored on a USB drive or another location you choose.",
    "UNIDADE REMOVÍVEL / LOCAL DE ARMAZENAMENTO:": "REMOVABLE DRIVE / STORAGE LOCATION:",
    "Atualizar": "Refresh",
    "Criar novo cofre": "Create new vault",
    "Abrir cofre existente...": "Open existing vault...",
    "A unidade USB não protege contra malware ou keyloggers no computador. O cofre fica descriptografado em memória enquanto está desbloqueado.": "USB storage does not protect against malware or keyloggers on this computer. The vault is decrypted in memory while unlocked.",
    "Nenhuma unidade USB detectada (clique para procurar)": "No USB drive detected (browse to choose a location)",
    "Senhas salvas": "Saved Passwords",
    "Senhas": "Passwords",
    "Lixeira": "Trash",
    "Saúde das senhas": "Password Health",
    "Saúde": "Health",
    "Gerar senha": "Password Generator",
    "Cofre": "Vault",
    "Cofre USB": "USB Vault",
    "Configurações": "Settings",
    "Sobre": "About",
    "ARQUIVO KDBX LOCAL": "LOCAL KDBX FILE",
    "Alterações salvas": "Changes saved",
    "Salvar cofre": "Save vault",
    "Bloquear": "Lock",
    "Buscar por serviço, usuário ou URL...": "Search credentials, websites, or emails...",
    "Esvaziar lixeira permanentemente": "Empty trash permanently",
    "Nenhuma credencial corresponde à busca.": "No credentials match your search.",
    "A lixeira está vazia.": "Trash is empty.",
    "Nenhuma credencial ainda. Use + para criar uma.": "No credentials yet. Click + to create one.",
    "Nova credencial": "New Credential",
    "Editar credencial": "Edit Credential",
    "Alternar entre lista e grade": "Toggle list and grid",
    "Ver detalhes": "View details",
    "Editar credencial": "Edit credential",
    "Excluir permanentemente": "Delete permanently",
    "Mover para a lixeira": "Move to trash",
    "Serviço": "Service",
    "Sem URL": "No URL",
    "Sem anotações.": "No notes.",
    "← Voltar à lista": "← Back to list",
    "Editar": "Edit",
    "Restaurar": "Restore",
    "USUÁRIO / E-MAIL": "LOGIN / USERNAME",
    "Copiar": "Copy",
    "SENHA": "PASSWORD",
    "SITE": "WEBSITE",
    "Abrir site": "Open website",
    "Mostrar": "Reveal",
    "Ocultar": "Hide",
    "Mostrar ou ocultar senha": "Show or hide password",
    "ANOTAÇÕES": "NOTES",
    "HISTÓRICO DE SENHAS": "PASSWORD HISTORY",
    "Senha copiada · limpeza automática ativa": "Password copied · automatic clearing enabled",
    "Copiada": "Copied",
    "Copiada ({seconds}s)": "Copied ({seconds}s)",
    "Excluir": "Delete",
    "Excluir definitivamente": "Delete permanently",
    "Mover para a lixeira": "Move to trash",
    "Confirmar exclusão permanente": "Confirm permanent deletion",
    "Mover '{title}' para a lixeira?": "Move '{title}' to the trash?",
    "Excluir '{title}' permanentemente do cofre? Esta ação não pode ser desfeita.": "Permanently delete '{title}' from the vault? This cannot be undone.",
    "Esvaziar lixeira": "Empty trash",
    "Excluir permanentemente todos os itens? A remoção do cofre criptografado não garante a eliminação física de blocos antigos da memória flash.": "Permanently delete all items? Removing data from the encrypted vault cannot guarantee physical erasure of old flash storage blocks.",
    "Alterações não salvas": "Unsaved changes",
    "● Alterações não salvas": "● Unsaved changes",
    "Execute uma análise para revisar o cofre.": "Run a scan to review your vault.",
    "Analisar cofre": "Scan vault",
    "TOTAL": "TOTAL",
    "FRACAS": "WEAK",
    "REUTILIZADAS": "REUSED",
    "Não há credenciais ativas para analisar.": "No active credentials to scan.",
    "Nenhuma senha fraca ou reutilizada foi encontrada.": "No weak or reused passwords found.",
    "{count} credencial(is) precisam de atenção. Selecione um item para abrir.": "{count} credential(s) need attention. Select an item to open it.",
    "Senha fraca": "Weak password",
    "Senha reutilizada": "Reused password",
    "Pode ser mais forte": "Could be stronger",
    "Força": "Strength",
    "Vazia": "Empty",
    "Muito fraca": "Very weak",
    "Fraca": "Weak",
    "Razoável": "Fair",
    "Forte": "Strong",
    "Muito forte": "Very strong",
    "Configurações": "Settings",
    "SESSÃO E PRIVACIDADE": "SESSION & PRIVACY",
    "Bloquear após inatividade": "Lock after inactivity",
    "1 minuto": "1 minute",
    "5 minutos": "5 minutes",
    "15 minutos": "15 minutes",
    "30 minutos": "30 minutes",
    "Nunca (menos seguro)": "Never (less secure)",
    "Limpar senha copiada após": "Clear copied password after",
    "15 segundos": "15 seconds",
    "30 segundos": "30 seconds",
    "1 minuto": "1 minute",
    "2 minutos": "2 minutes",
    "Não limpar automaticamente": "Do not clear automatically",
    "A senha só é removida se a área de transferência ainda contiver o valor copiado pelo Clavis.": "The password is cleared only if the clipboard still contains the value copied by Clavis.",
    "INTERFACE E BACKUP": "INTERFACE & BACKUP",
    "Tamanho da fonte": "Font size",
    "Escala da interface": "Interface scale",
    "Recomendado": "Recommended",
    "Recomendado para esta tela: {scale}%. Reinicie o Clavis para aplicar alterações.": "Recommended for this screen: {scale}%. Restart Clavis to apply changes.",
    "Reinicie o Clavis para aplicar a nova escala da interface.": "Restart Clavis to apply the new interface scale.",
    "Preservar arquivo .bak antes de substituir o cofre": "Keep a .bak backup before replacing the vault",
    "IDIOMA DA INTERFACE": "INTERFACE LANGUAGE",
    "Idioma": "Language",
    "SENHAS SALVAS": "SAVED PASSWORDS",
    "LIXEIRA": "TRASH",
    "CONFIGURAÇÕES": "SETTINGS",
    "GERADOR DE SENHA": "PASSWORD GENERATOR",
    "GERENCIAR COFRE USB": "MANAGE USB VAULT",
    "SOBRE O CLAVIS": "ABOUT CLAVIS",
    "SAÚDE DAS SENHAS": "PASSWORD HEALTH",
    "Todos os itens": "All items",
    "Senhas fracas": "Weak passwords",
    "Senhas reutilizadas": "Reused passwords",
    "SERVIÇO & URL": "SERVICE & URL",
    "LOGIN / USUÁRIO": "LOGIN / USERNAME",
    "SEGURANÇA": "SECURITY",
    "AÇÕES": "ACTIONS",
    "Aviso de segurança: enquanto o cofre está desbloqueado, dados podem residir na memória. O sistema operacional pode usar paginação ou gerar dumps.": "Security notice: while the vault is unlocked, data may reside in memory. The operating system may use paging or create memory dumps.",
    "Nenhuma senha corresponde a este filtro.": "No passwords match this filter.",
    "Senha oculta": "Hidden password",
    "Revelar senha por 10 segundos": "Reveal password for 10 seconds",
    "Copiar usuário": "Copy username",
    "Copiar senha": "Copy password",
    "Ejetar cofre USB": "Eject USB vault",
    "Sair do Clavis": "Exit Clavis",
    "Nova senha": "New Password",
    "Salvar": "Save",
    "LOCAL VAULT": "LOCAL VAULT",
    "Sem alterações": "No changes",
    "Cofre local de senhas": "Local password vault",
    "Clavis — Cofre local de senhas": "Clavis — Local Password Vault",
    "Bloqueio em {minutes}m {seconds:02d}s": "Auto-lock in {minutes}m {seconds:02d}s",
    "Bloqueio em: {minutes}m {seconds:02d}s": "Auto-lock in: {minutes}m {seconds:02d}s",
    "Salvar": "Save",
    "Descartar": "Discard",
    "Cancelar": "Cancel",
    "Sim": "Yes",
    "Não": "No",
    "SENHA MESTRA": "MASTER PASSWORD",
    "A alteração regrava o arquivo KDBX com a nova senha mestra. Use uma senha longa e exclusiva.": "Changing this re-encrypts the KDBX file with the new master password. Use a long, unique password.",
    "Nova senha mestra (mínimo 12 caracteres)": "New master password (12 characters minimum)",
    "Confirme a nova senha mestra": "Confirm the new master password",
    "Alterar senha mestra": "Change master password",
    "ARQUIVO DO COFRE": "VAULT FILE",
    "Caminho": "Path",
    "Tamanho": "Size",
    "Modificado": "Modified",
    "Formato": "Format",
    "Cifra identificada": "Identified cipher",
    "Derivação de chave": "Key derivation",
    "indisponível": "unavailable",
    "desconhecido": "unknown",
    "LIMITAÇÕES DE SEGURANÇA": "SECURITY LIMITATIONS",
    "O cofre é mantido em memória enquanto está desbloqueado. Python não garante apagamento seguro da memória; o sistema operacional pode usar paginação/swap ou gerar dumps. Malware, keyloggers e captura de tela no dispositivo desbloqueado podem expor dados. Mantenha backups criptografados e proteja a unidade física.": "The vault is held in memory while unlocked. Python cannot guarantee secure memory erasure; the OS may use swap/page files or create dumps. Malware, keyloggers, and screen capture can expose data while unlocked. Keep encrypted backups and protect the physical drive.",
    "Gerar senha": "Generate Password",
    "Crie senhas localmente com o módulo secrets. O histórico desta sessão é mantido apenas em memória e descartado ao bloquear o cofre.": "Generate passwords locally using Python's secrets module. This session history stays in memory and is discarded when the vault is locked.",
    "OPÇÕES DE GERAÇÃO": "GENERATION OPTIONS",
    "Comprimento": "Length",
    "Minúsculas": "Lowercase",
    "Maiúsculas": "Uppercase",
    "Números": "Numbers",
    "Símbolos": "Symbols",
    "Excluir caracteres ambíguos": "Exclude ambiguous characters",
    "SENHA GERADA": "GENERATED PASSWORD",
    "Clique em gerar para criar uma senha": "Click Generate to create a password",
    "O resultado fica visível apenas nesta sessão.": "The result is available only in this session.",
    "Gerar senha": "Generate password",
    "Mostrar": "Reveal",
    "Ocultar": "Hide",
    "Salvar como credencial": "Save as credential",
    "Histórico recente: nenhum": "Recent history: none",
    "Histórico recente desta sessão: {count} senha(s).": "Recent history this session: {count} password(s).",
    "Cofre USB": "USB Vault",
    "BACKUP E TRANSFERÊNCIA": "BACKUP & TRANSFER",
    "Exportar cria uma cópia criptografada KDBX. Importar mescla as credenciais de outro cofre KDBX aberto pelo usuário; o arquivo atual não é substituído.": "Export creates an encrypted KDBX copy. Import merges credentials from another KDBX vault you unlock; the current file is not replaced.",
    "Exportar cópia criptografada": "Export encrypted copy",
    "Importar de outro cofre": "Import from another vault",
    "Não identificada como unidade removível": "Not identified as a removable drive",
    "Sobre o Clavis": "About Clavis",
    "CLAVIS · GERENCIADOR LOCAL DE SENHAS": "CLAVIS · LOCAL PASSWORD MANAGER",
    "Aplicativo local para administrar credenciais em cofres KeePass KDBX. O aplicativo não envia dados para serviços remotos.": "A local application for managing credentials in KeePass KDBX vaults. Clavis does not send data to remote services.",
    "Tecnologias: Python · PySide6 · PyKeePass · formato KDBX": "Technologies: Python · PySide6 · PyKeePass · KDBX format",
    "Atalhos\nCtrl+N  Nova credencial\nCtrl+F  Buscar\nCtrl+L  Bloquear cofre\nCtrl+E  Instruções de ejeção segura\nAlt+C  Copiar senha selecionada": "Shortcuts\nCtrl+N  New credential\nCtrl+F  Search\nCtrl+L  Lock vault\nCtrl+E  Safe-eject instructions\nAlt+C  Copy selected password",
    "Python não garante apagamento seguro da memória; swap, dumps e um dispositivo comprometido podem expor dados enquanto o cofre está desbloqueado.": "Python cannot guarantee secure memory erasure; swap, dumps, or a compromised device can expose data while the vault is unlocked.",
    "Desbloquear cofre Clavis": "Unlock Clavis Vault",
    "Senha mestra:": "Master password:",
    "Confirme a senha mestra:": "Confirm master password:",
    "Não há senha de recuperação. Se perder a senha mestra, não será possível desbloquear o cofre.": "There is no recovery password. If you lose your master password, the vault cannot be unlocked.",
    "Voltar": "Back",
    "Desbloquear cofre": "Unlock vault",
    "Definir senha mestra do cofre": "Set vault master password",
    "Criar cofre KDBX": "Create KDBX vault",
    "Escolha uma senha longa e exclusiva (12 caracteres ou mais). Não há recuperação caso seja esquecida.": "Choose a long, unique password (12 characters or more). It cannot be recovered if forgotten.",
    "Os dados são carregados em memória enquanto o cofre está aberto. Python e o sistema operacional não garantem que páginas de memória ou dumps não sejam gravados em disco.": "Data is loaded into memory while the vault is open. Python and the operating system cannot guarantee memory pages or dumps are not written to disk.",
    "A senha mestra não pode ficar vazia.": "Master password cannot be empty.",
    "As senhas não coincidem. Verifique a confirmação.": "Passwords do not match. Check the confirmation.",
    "Use uma senha mestra com pelo menos 12 caracteres.": "Use a master password with at least 12 characters.",
    "Serviço *": "Service *",
    "Ex.: e-mail, banco, trabalho": "e.g. email, bank, work",
    "Usuário / e-mail *": "Username / email *",
    "nome@exemplo.com": "name@example.com",
    "Senha *": "Password *",
    "Força: vazia": "Strength: empty",
    "Gerador de senhas": "Password generator",
    "Gerar": "Generate",
    "Tamanho: {length}": "Length: {length}",
    "Sem ambíguos": "Exclude ambiguous characters",
    "Endereço do site (opcional)": "Website URL (optional)",
    "Anotações (opcional)": "Notes (optional)",
    "Anotações privadas...": "Private notes...",
    "Cancelar": "Cancel",
    "Salvar credencial": "Save credential",
    "Força: <b style='color: {color}'>{label}</b> ({entropy} bits estimados)": "Strength: <b style='color: {color}'>{label}</b> ({entropy} estimated bits)",
    "Não foi possível abrir o cofre. Verifique a senha e o arquivo.": "Could not open the vault. Check the password and file.",
    "Senha incorreta ou cofre inválido.": "Incorrect password or invalid vault.",
    "Formato de cofre inválido: {error}": "Invalid vault format: {error}",
    "Erro de armazenamento: {error}": "Storage error: {error}",
    "Unidade desconectada": "Drive disconnected",
    "A unidade do cofre foi removida ou ficou inacessível. A sessão foi bloqueada; alterações ainda não salvas podem ter sido perdidas.": "The vault drive was removed or became inaccessible. The session was locked; unsaved changes may have been lost.",
    "Falha ao salvar": "Save failed",
    "O bloqueio automático foi adiado para evitar perder alterações: {error}": "Automatic locking was delayed to avoid losing changes: {error}",
    "Sessão encerrada": "Session ended",
    "O cofre foi bloqueado por inatividade.": "The vault was locked due to inactivity.",
    "Cofre bloqueado": "Vault locked",
    "Bloqueio em: {minutes}m {seconds:02d}s": "Auto-lock in: {minutes}m {seconds:02d}s",
    "Bloqueio automático desativado": "Auto-lock disabled",
    "Cofre salvo": "Vault saved",
    "Espaço insuficiente": "Insufficient space",
    "Erro": "Error",
    "Falha ao salvar o cofre: {error}": "Failed to save vault: {error}",
    "Senha mestra alterada e cofre salvo": "Master password changed and vault saved",
    "A senha mestra não pôde ser salva: {error}": "The master password could not be saved: {error}",
    "Há alterações não salvas. Deseja salvar antes de bloquear o cofre?": "There are unsaved changes. Save before locking the vault?",
    "Não foi possível salvar as alterações: {error}": "Could not save changes: {error}",
    "Há alterações não salvas. Deseja salvar antes de sair?": "There are unsaved changes. Save before quitting?",
    "Não foi possível salvar: {error}. O aplicativo continuará aberto.": "Could not save: {error}. The app will remain open.",
    "LOCAL VAULT": "LOCAL VAULT",
    "Sem alterações": "No changes",
    "Bloqueio automático": "Auto-lock",
    "Remover para lixeira": "Move to trash",
    "A senha não pode ficar vazia.": "Password cannot be empty.",
    "Informe o serviço.": "Enter a service name.",
    "Informe o usuário ou e-mail.": "Enter a username or email.",
    "Senha gerada": "Generated password",
    "Ejeção segura": "Safe eject",
    "Este dispositivo não oferece uma operação de ejeção segura compatível. Salve e bloqueie o cofre antes de remover a unidade.": "This device does not offer a compatible safe-eject operation. Save and lock the vault before removing the drive.",
    "Apenas endereços HTTP ou HTTPS válidos podem ser abertos.": "Only valid HTTP or HTTPS addresses can be opened.",
    "Endereço inválido": "Invalid URL",
    "Somente endereços HTTP ou HTTPS válidos podem ser abertos.": "Only valid HTTP or HTTPS addresses can be opened.",
    "Não foi possível abrir": "Unable to open",
    "O sistema não conseguiu abrir este endereço.": "The system could not open this address.",
    "Exportação": "Export",
    "Escolha um destino diferente do cofre aberto.": "Choose a destination different from the open vault.",
    "Exportação concluída": "Export complete",
    "Cópia criptografada criada.": "Encrypted copy created.",
    "Falha na exportação": "Export failed",
    "Importação concluída": "Import complete",
    "As credenciais foram adicionadas ao cofre aberto.": "Credentials were added to the open vault.",
    "Falha na importação": "Import failed",
    "Copiar usuário": "Copy username",
    "Copiar senha": "Copy password",
    "Excluir permanentemente": "Delete permanently",
    "Mover para a lixeira": "Move to trash",
    "Nova senha": "New Password",
    "Esvaziar lixeira permanentemente": "Empty trash permanently",
    "Analisar cofre": "Scan vault",
    "Arquivo: {path}\nTamanho: {size:,} bytes\nÚltima modificação: {modified}\nDispositivo: {device}\nFormato: KDBX {version} · Cifra: {encryption}": "File: {path}\nSize: {size:,} bytes\nLast modified: {modified}\nDevice: {device}\nFormat: KDBX {version} · Cipher: {encryption}",
    "Dispositivo:": "Device:",
    "Formato:": "Format:",
    "Última modificação:": "Last modified:",
    "Não foi possível consultar o arquivo do cofre: {error}": "Could not read vault file information: {error}",
    "Sem URL": "No URL",
    "Sem anotações.": "No notes.",
    "Força: vazia": "Strength: empty",
    "Serviço": "Service",
    "USUÁRIO / E-MAIL": "LOGIN / USERNAME",
    "SITE": "WEBSITE",
    "ANOTAÇÕES": "NOTES",
    "HISTÓRICO DE SENHAS": "PASSWORD HISTORY",
    "Ejeção segura": "Safe eject",
    "Sair do Clavis": "Exit Clavis",
    "Salvar": "Save",
    "Cofre salvo": "Vault saved",
    "Senha mestra alterada e cofre salvo": "Master password changed and vault saved",
    "Não foi possível abrir": "Unable to open",
    "Falha na importação": "Import failed",
    "Erro no gerador": "Generator error",
    "Campo obrigatório": "Required field",
    "Erro no gerador": "Generator error",
    "Unidade removível": "Removable drive",
    "bytes livres": "bytes free",
    "Arquivo: {path}\nTamanho: {size:,} bytes\nÚltima modificação: {modified}\nDispositivo: {device}\nFormato: KDBX {version} · Cifra: {encryption}": "File: {path}\nSize: {size:,} bytes\nLast modified: {modified}\nDevice: {device}\nFormat: KDBX {version} · Cipher: {encryption}",
    "Não foi possível consultar o arquivo do cofre: {error}": "Could not read vault file information: {error}",
}

_EN_TO_PT = {english: portuguese for portuguese, english in _PT_TO_EN.items()}


def set_language(language: str) -> None:
    global _LANGUAGE
    _LANGUAGE = "pt_BR" if language == "pt_BR" else "en"


def current_language() -> str:
    return _LANGUAGE


def tr(text: str, **values: object) -> str:
    """Translate a catalog string and interpolate optional values."""
    if _LANGUAGE == "en":
        text = _PT_TO_EN.get(text, text)
    if values:
        try:
            return text.format(**values)
        except (KeyError, ValueError):
            return text
    return text


def set_translated_text(
    widget: QWidget, source_text: str, **values: object
) -> None:
    """Set a dynamic widget label and keep its Portuguese source for later toggles."""
    widget.setProperty("clavis_no_translate", False)
    widget.setProperty("clavis_source_text", source_text)
    widget.setProperty("clavis_translation_values", values)
    setter = getattr(widget, "setText", None)
    if callable(setter):
        setter(tr(source_text, **_translate_values(values)))


def set_untranslated_text(widget: QWidget, text: str) -> None:
    """Set user data without allowing it to be mistaken for interface copy."""
    widget.setProperty("clavis_no_translate", True)
    widget.setProperty("clavis_source_text", None)
    widget.setProperty("clavis_translation_values", {})
    setter = getattr(widget, "setText", None)
    if callable(setter):
        setter(text)


def _translate_values(values: dict[str, object]) -> dict[str, object]:
    if _LANGUAGE != "en":
        return values
    return {
        key: _PT_TO_EN.get(value, value) if isinstance(value, str) else value
        for key, value in values.items()
    }


def apply_translations(root: QWidget, language: Optional[str] = None) -> None:
    """Translate currently displayed widget strings while retaining source text."""
    if language is not None:
        set_language(language)
    widgets = [root, *root.findChildren(QWidget)]
    for widget in widgets:
        _translate_widget(widget)


def _translate_widget(widget: QWidget) -> None:
    for getter_name, setter_name in (
        ("text", "setText"),
        ("placeholderText", "setPlaceholderText"),
        ("toolTip", "setToolTip"),
        ("windowTitle", "setWindowTitle"),
    ):
        getter = getattr(widget, getter_name, None)
        setter = getattr(widget, setter_name, None)
        if not callable(getter) or not callable(setter):
            continue
        if getter_name == "text" and widget.property("clavis_no_translate"):
            continue
        text = getter()
        if not text:
            continue
        source = widget.property(f"clavis_source_{getter_name}")
        if source is None:
            source = _EN_TO_PT.get(text, text)
            if source not in _PT_TO_EN:
                continue
            widget.setProperty(f"clavis_source_{getter_name}", source)
        values = widget.property("clavis_translation_values")
        if not isinstance(values, dict):
            values = {}
        translated = tr(source, **_translate_values(values))
        if translated != text:
            setter(translated)

    if isinstance(widget, QComboBox):
        for index in range(widget.count()):
            text = widget.itemText(index)
            source = widget.itemData(index, Qt.ItemDataRole.UserRole + 1)
            if source is None:
                source = _EN_TO_PT.get(text, text)
                if source in _PT_TO_EN:
                    widget.setItemData(index, source, Qt.ItemDataRole.UserRole + 1)
                else:
                    continue
            translated = _PT_TO_EN.get(source, source) if _LANGUAGE == "en" else source
            if text != translated:
                widget.setItemText(index, translated)
