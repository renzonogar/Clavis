# Clavis — Portable Offline-First Password Manager

> **"Your vault. Your device. Your control."**

Clavis is a portable, offline-first password manager designed to keep your encrypted vault physically with you.

Official description: *"Clavis is a portable, offline-first password manager designed to keep your encrypted vault physically with you."*

---

## 1. Security Architecture & Principles

### Offline by Architecture
Clavis is built with a hard boundary against network connectivity. There are:
- **No user accounts or cloud servers**
- **No telemetry or analytics**
- **No remote APIs or background network requests**
- **No remote asset CDNs**

All cryptographic operations and database queries occur entirely on the local machine.

### Physical USB Vault Storage
Your vault file resides on a physical removable USB flash drive.
- Plaintext credentials and unencrypted databases are **never** persisted to the host filesystem.
- When unlocked with your master password, the vault deserializes strictly into a transient in-memory SQLite database (`:memory:`).
- When locked, the in-memory database connection is closed, buffers are scrubbed, and references are dropped for garbage collection.
- If the USB drive is unplugged while the vault is unlocked, Clavis detects the missing mount point, immediately locks the vault, and halts writes to prevent accidental redirects to the host disk.

### Cryptographic Foundation
Clavis adheres to modern cryptographic standards and never invents custom algorithms:
1. **Authenticated Encryption:** AES-256-GCM (Galois/Counter Mode).
2. **Key Derivation Function:** Argon2id (RFC 9106) with memory-hard parameters (default: 64 MiB RAM, 3 iterations, 4 parallel lanes).
3. **Fresh Nonce Guarantee:** A unique 96-bit cryptographically secure random nonce (`secrets.token_bytes(12)`) is generated fresh for every encryption operation. A nonce is never reused with the same key.
4. **Header Authentication (AAD):** All vault header metadata (version, KDF parameters, salt, nonce, and device metadata) is bound and authenticated as Associated Authenticated Data (AAD) during AES-GCM encryption. Any bit-flip or modification of the header causes immediate authentication rejection.
5. **Generic Error Response:** On authentication failure, a generic message is displayed (*"Authentication failed or vault is corrupted"*). The application never reveals whether the failure was caused by an incorrect password, a corrupted ciphertext, or a modified header.
6. **No Backdoor:** There is no escrow key, recovery backdoor, or developer bypass. If the master password is lost, data recovery is mathematically impossible.

### Safe Atomic Persistence
When saving changes to your USB:
1. The in-memory SQLite database is serialized and encrypted.
2. The payload is written to a temporary file (`.tmp.<rand>`) on the same filesystem.
3. The system forces a hardware sync (`fsync`) to flush OS write caches directly to flash media.
4. An encrypted backup (`.bak`) is created.
5. An atomic replacement (`os.replace`) swaps the new vault in place.
6. If disk space is exhausted (`ENOSPC`) or write fails, the existing valid vault remains untouched.

---

## 2. Threat Model & Transparent Security Limitations

Offline operation drastically reduces the remote attack surface, but no software can claim to be invincible:

1. **Compromised Host OS:** If the computer running Clavis is infected with kernel-level malware, memory scanners, or hardware/software keyloggers, secrets can be intercepted while the vault is unlocked in RAM.
2. **OS Swap and Pagefiles:** Modern operating systems (Windows, Linux, macOS) may swap virtual memory pages containing decrypted RAM to disk. Clavis attempts best-effort in-memory cleanup, but complete kernel-level zeroization cannot be guaranteed in user-space runtimes.
3. **Flash Storage Wear-Leveling:** Flash drives (USB thumb drives and SSDs) use internal microcontrollers that balance write cycles across NAND blocks. When Clavis replaces a file or performs a logical deletion, old physical NAND blocks may retain magnetic/charge remnants until garbage-collected by the flash controller. Logical deletion cannot guarantee physical erasure on flash storage.
4. **Auxiliary USB UUID Check:** Clavis supports an auxiliary USB volume check. This is strictly a convenience check to ensure you are saving to the intended physical drive. **A USB UUID is NOT a secret and is NOT a second-factor authentication mechanism (2FA).** It can be copied, spoofed, or cloned.

---

## 3. Installation & Requirements

### Supported Operating Systems
- **Linux:** Ubuntu, Debian, Fedora, Arch, etc.
- **macOS:** macOS 12 Monterey or newer.
- **Windows:** Windows 10 / 11 (64-bit).

### Python Version & Dependencies
Python 3.10+ is recommended.

Install dependencies:
```bash
pip install -r requirements.txt
```

Core dependencies in `requirements.txt`:
- `cryptography`: High-assurance AES-256-GCM authenticated encryption.
- `argon2-cffi`: RFC 9106 Argon2id password-hashing and key-derivation.
- `PySide6`: Modern, cross-platform Qt GUI framework.
- `pytest`: Automated test harness.
- `psutil`: Hardware and mount inspection.

---

## 4. Running Clavis

To start the desktop application:
```bash
python3 main.py
```

### Vault Creation Workflow
1. Insert your USB flash drive into your computer.
2. Launch Clavis; the app will detect connected removable drives.
3. Select your USB drive and click **Create New Vault on USB**.
4. Choose your master password and confirm it. Follow the password strength indicator.
5. Clavis generates a 128-bit random salt, derives a 256-bit AES key via Argon2id, initializes the in-memory SQLite schema, encrypts the vault, and writes it atomically to the USB drive.

### Vault Opening Workflow
1. Insert your USB drive.
2. Click **Open Existing Vault...** and select the `.vault` file.
3. Enter your master password.
4. Clavis validates the header, derives the Argon2id key, checks the GCM authentication tag, and loads the credentials directly into an in-memory SQLite database.

---

## 5. Password Management Features

- **Credential Records:** Title/service, username/email, password, website URL, and formatted notes.
- **Masked Passwords:** Passwords remain masked as `••••••••` by default. Intentional click required to reveal or copy.
- **Password History:** When an existing password is changed, the previous version is logged in the history table with a timestamp. History can be inspected or cleared per entry.
- **Trash & Soft Delete:** Deleted credentials move to the Trash section. They can be restored or permanently purged.
- **Password Generator (CSPRNG):** Cryptographically secure generator (`secrets`) with configurable lengths (8–128), uppercase, lowercase, numbers, symbols, and ambiguous character filtering.
- **Entropy & Strength Estimator:** Shannon entropy calculation with heuristic penalty for repetition. Includes an explicit disclaimer that entropy scores do not guarantee safety against targeted dictionary attacks.
- **Configurable Inactivity Auto-Lock:** Automatically locks after 1, 5, 15, or 30 minutes of inactivity.

---

## 6. Running the Test Suite

Run all unit tests, cryptographic round-trips, tamper simulations, and session tests using `pytest`:

```bash
pytest tests/ -v
```

### Test Coverage Summary:
- `test_crypto.py`:
  - Argon2id parameter validation & DoS bounds checking
  - AES-256-GCM encryption/decryption round trips
  - Tampered ciphertext rejection
  - Tampered header AAD rejection
  - Nonce uniqueness across consecutive encryptions (never reused)
  - Zeroization of sensitive bytearrays
  - Absence of plaintext in encrypted vault files
- `test_vault.py`:
  - Vault creation and reopening
  - In-memory SQLite lifecycle
  - Credential CRUD, search filtering, and password history tracking
  - Soft delete, trash recovery, and permanent deletion
- `test_storage.py`:
  - Atomic write and replace (`os.replace`)
  - Backup file `.bak` preservation
  - Insufficient disk space error handling
- `test_password_generator.py`:
  - Length and character set constraints
  - Guaranteed character class distribution
  - Entropy and strength scoring
- `test_session.py`:
  - Inactivity timeout and auto-lock callback
  - USB disconnect detection and emergency lock

---

## 7. Project Structure

```
clavis/
├── main.py                     # Application entry point
├── requirements.txt            # Python dependencies
├── README.md                   # System documentation and threat model
├── src/
│   └── clavis/
│       ├── __init__.py
│       ├── crypto.py           # AES-256-GCM, AAD packaging, zeroization
│       ├── kdf.py              # Argon2id derivation & bounds validation
│       ├── vault.py            # Vault lifecycle controller
│       ├── storage.py          # Atomic writes, fsync, backups
│       ├── database.py         # SQLite in-memory database & CRUD
│       ├── usb.py              # Removable drive detection & monitoring
│       ├── password_generator.py # CSPRNG generator & entropy scoring
│       ├── session.py          # Idle timeout & USB disconnect watcher
│       └── ui/
│           ├── __init__.py
│           ├── main_window.py  # Top-level window & status bar
│           ├── welcome_view.py # USB selector & welcome screen
│           ├── unlock_view.py  # Master password entry & error states
│           ├── vault_view.py   # Main workspace, list & details
│           ├── credential_dialog.py # Form & embedded generator
│           └── settings_view.py# Timeout, master password & threat model
└── tests/
    ├── __init__.py
    ├── test_crypto.py
    ├── test_vault.py
    ├── test_storage.py
    ├── test_password_generator.py
    └── test_session.py
```

---

## 8. License

Clavis is open-source software built for local privacy and individual sovereignty.
*"Your vault. Your device. Your control."*
