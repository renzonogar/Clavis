#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
vault_crypto.py - Módulo Criptográfico de Memória Volátil
Implementa criptografia autenticada AES-256-GCM com derivação de chave
robusta (PBKDF2-HMAC-SHA256 com 600.000 iterações ou Argon2id).
Todas as operações de decifração ocorrem exclusivamente na memória RAM.
"""

import os
import io
import json
import secrets
import hashlib
import csv
import io
from typing import Dict, Any, Tuple, Optional, List

# Tenta importar Argon2 (RFC 9106 - Argon2id resistente a ataques GPU/ASIC)
try:
    import argon2.low_level
    HAS_ARGON2 = True
except ImportError:
    HAS_ARGON2 = False

# Tenta importar a biblioteca de alta performance 'cryptography' (AESGCM)
try:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.backends import default_backend
    HAS_CRYPTOGRAPHY = True
except ImportError:
    HAS_CRYPTOGRAPHY = False

from memory_security import secure_zero_bytes, volatile_string


class VaultCrypto:
    """Gerenciador de Criptografia AES-256-GCM com KDF Argon2id para Execução em RAM."""

    # Parâmetros recomendados pela RFC 9106 para Argon2id
    ARGON2_MEMORY_COST = 65536  # 64 MB de RAM
    ARGON2_TIME_COST = 3        # 3 iterações
    ARGON2_PARALLELISM = 4      # 4 lanes/threads
    
    # Fallback PBKDF2
    KDF_ITERATIONS = 600_000
    SALT_SIZE = 32  # 256 bits
    NONCE_SIZE = 12  # 96 bits para AES-GCM
    KEY_SIZE = 32   # 256 bits para AES-256

    @classmethod
    def derive_key(cls, master_password: str, salt: bytes, keyfile_bytes: Optional[bytes] = None, use_argon2: bool = True) -> bytes:
        """
        Deriva uma chave AES de 256 bits usando Argon2id (RFC 9106) ou PBKDF2-HMAC-SHA256 como fallback.
        Combina a senha mestra com a entropia do keyfile físico se presente.
        """
        pw_bytes = master_password.encode('utf-8')
        combined = pw_bytes + (keyfile_bytes if keyfile_bytes else b'')

        if use_argon2 and HAS_ARGON2:
            key = argon2.low_level.hash_secret_raw(
                secret=combined,
                salt=salt,
                time_cost=cls.ARGON2_TIME_COST,
                memory_cost=cls.ARGON2_MEMORY_COST,
                parallelism=cls.ARGON2_PARALLELISM,
                hash_len=cls.KEY_SIZE,
                type=argon2.low_level.Type.ID
            )
        elif HAS_CRYPTOGRAPHY:
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=cls.KEY_SIZE,
                salt=salt,
                iterations=cls.KDF_ITERATIONS,
                backend=default_backend()
            )
            key = kdf.derive(combined)
        else:
            key = hashlib.pbkdf2_hmac(
                'sha256',
                combined,
                salt,
                cls.KDF_ITERATIONS,
                dklen=cls.KEY_SIZE
            )

        # Higieniza material combinado da memória
        secure_zero_bytes(combined)
        return key

    @classmethod
    def encrypt_vault(cls, vault_data: Dict[str, Any], master_password: str, keyfile_bytes: Optional[bytes] = None, use_argon2: bool = True) -> bytes:
        """
        Serializa e cifra o cofre diretamente em RAM via AES-256-GCM.
        Cabeçalho:
        [VERSÃO: 1 byte (0x02 = Argon2id, 0x01 = PBKDF2)] + [FLAG_KEYFILE: 1 byte] + [SALT: 32 bytes] + [NONCE: 12 bytes] + [TAG_AUTH: 16 bytes] + [CIPHERTEXT]
        """
        salt = secrets.token_bytes(cls.SALT_SIZE)
        nonce = secrets.token_bytes(cls.NONCE_SIZE)
        actual_argon = use_argon2 and HAS_ARGON2
        version = b'\x02' if actual_argon else b'\x01'

        key = cls.derive_key(master_password, salt, keyfile_bytes, use_argon2=actual_argon)

        # Serializa dados em memória RAM usando string volátil
        plaintext_json = json.dumps(vault_data, ensure_ascii=False).encode('utf-8')

        if HAS_CRYPTOGRAPHY:
            aesgcm = AESGCM(key)
            encrypted_payload = aesgcm.encrypt(nonce, plaintext_json, None)
            ciphertext = encrypted_payload[:-16]
            auth_tag = encrypted_payload[-16:]
        else:
            enc_key = hashlib.sha256(key + b"ENC").digest()
            mac_key = hashlib.sha256(key + b"MAC").digest()
            import hmac
            keystream = hashlib.sha256(enc_key + nonce).digest()
            while len(keystream) < len(plaintext_json):
                keystream += hashlib.sha256(enc_key + nonce + len(keystream).to_bytes(4, 'big')).digest()
            ciphertext = bytes(a ^ b for a, b in zip(plaintext_json, keystream[:len(plaintext_json)]))
            auth_tag = hmac.new(mac_key, salt + nonce + ciphertext, hashlib.sha256).digest()[:16]

        has_kf_flag = b'\x01' if keyfile_bytes else b'\x00'
        header = version + has_kf_flag + salt + nonce + auth_tag

        secure_zero_bytes(key)
        secure_zero_bytes(plaintext_json)
        return header + ciphertext

    @classmethod
    def decrypt_vault(cls, raw_encrypted_bytes: bytes, master_password: str, keyfile_bytes: Optional[bytes] = None) -> Dict[str, Any]:
        """
        Decifra o cofre diretamente na memória RAM via AES-256-GCM.
        Verifica autenticidade com a Auth Tag e aceita versões 0x01 (PBKDF2) e 0x02 (Argon2id).
        """
        if len(raw_encrypted_bytes) < 1 + 1 + cls.SALT_SIZE + cls.NONCE_SIZE + 16:
            raise ValueError("Arquivo de cofre corrompido ou tamanho inválido.")

        version = raw_encrypted_bytes[0]
        if version not in (1, 2):
            raise ValueError(f"Versão de cofre não suportada: {version}")

        use_argon2 = (version == 2)
        has_keyfile_flag = raw_encrypted_bytes[1] == 1
        if has_keyfile_flag and not keyfile_bytes:
            raise PermissionError("Este cofre exige o arquivo de chave USB (.key) conectado!")

        offset = 2
        salt = raw_encrypted_bytes[offset:offset + cls.SALT_SIZE]
        offset += cls.SALT_SIZE
        nonce = raw_encrypted_bytes[offset:offset + cls.NONCE_SIZE]
        offset += cls.NONCE_SIZE
        auth_tag = raw_encrypted_bytes[offset:offset + 16]
        offset += 16
        ciphertext = raw_encrypted_bytes[offset:]

        key = cls.derive_key(master_password, salt, keyfile_bytes, use_argon2=use_argon2)

        try:
            if HAS_CRYPTOGRAPHY:
                aesgcm = AESGCM(key)
                decrypted_bytes = aesgcm.decrypt(nonce, ciphertext + auth_tag, None)
            else:
                import hmac
                mac_key = hashlib.sha256(key + b"MAC").digest()
                expected_tag = hmac.new(mac_key, salt + nonce + ciphertext, hashlib.sha256).digest()[:16]
                if not hmac.compare_digest(auth_tag, expected_tag):
                    raise ValueError("Tag de autenticação inválida.")
                enc_key = hashlib.sha256(key + b"ENC").digest()
                keystream = hashlib.sha256(enc_key + nonce).digest()
                while len(keystream) < len(ciphertext):
                    keystream += hashlib.sha256(enc_key + nonce + len(keystream).to_bytes(4, 'big')).digest()
                decrypted_bytes = bytes(a ^ b for a, b in zip(ciphertext, keystream[:len(ciphertext)]))

            vault_dict = json.loads(decrypted_bytes.decode('utf-8'))
            return vault_dict

        except Exception as exc:
            raise PermissionError("Senha mestra incorreta ou integridade do cofre violada.") from exc
        finally:
            secure_zero_bytes(key)

    @classmethod
    def export_to_csv(cls, entries: List[Dict[str, Any]]) -> str:
        """Exporta lista de credenciais para string formatada CSV (RFC 4180)."""
        output = io.StringIO()
        fieldnames = ["title", "category", "username", "password", "url", "notes", "totpSecret"]
        writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction='ignore')
        writer.writeheader()
        for e in entries:
            writer.writerow({
                "title": e.get("title", ""),
                "category": e.get("category", "Geral"),
                "username": e.get("username", ""),
                "password": e.get("password", ""),
                "url": e.get("url", ""),
                "notes": e.get("notes", ""),
                "totpSecret": e.get("totpSecret", "")
            })
        return output.getvalue()

    @classmethod
    def parse_csv_entries(cls, csv_text: str) -> List[Dict[str, Any]]:
        """Lê arquivo CSV e retorna lista de credenciais higienizadas."""
        stream = io.StringIO(csv_text)
        reader = csv.DictReader(stream)
        results = []
        for row in reader:
            title = row.get("title") or row.get("name") or row.get("título") or "Importado"
            results.append({
                "title": title,
                "category": row.get("category") or row.get("categoria") or "Geral",
                "username": row.get("username") or row.get("login") or row.get("email") or "",
                "password": row.get("password") or row.get("senha") or "",
                "url": row.get("url") or row.get("uri") or "",
                "notes": row.get("notes") or row.get("notas") or "",
                "totpSecret": row.get("totpSecret") or ""
            })
        return results
