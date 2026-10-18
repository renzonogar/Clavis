# Clavis — Portable Offline-First Password Manager

**"Your vault. Your device. Your control."**

Clavis is a portable password manager designed to keep your passwords secure and under your control. It works completely offline and stores its encrypted vault on a USB flash drive, without cloud services, accounts, telemetry, or internet connections.

## Security and Privacy

Clavis uses AES-256-GCM encryption and Argon2id to protect the vault. All passwords are decrypted and managed in a temporary in-memory SQLite database, avoiding intentional storage of plaintext credentials on the computer's disk.

It also includes automatic locking when the USB drive is disconnected, secure file-saving procedures, encrypted backups, and protection against unauthorized modifications. However, malware, memory attacks, and limitations of USB flash storage can still pose risks.

## Main Features

- Store and manage passwords, usernames, websites, and notes.
- Generate secure passwords using cryptographically secure randomness.
- Check for weak and reused passwords locally.
- View password history and restore deleted credentials from the trash.
- Keep passwords hidden by default.
- Automatically clear copied passwords from the clipboard after 30 seconds.
- Lock the vault automatically after a configurable period of inactivity.
- Detect USB disconnections and protect against accidental writes to the wrong location.

## Technologies

Clavis is developed in Python and uses PySide6 for its graphical interface, SQLite for temporary in-memory database management, `cryptography` for encryption, `argon2-cffi` for key derivation, and `psutil` for detecting removable drives.

It is designed to support Windows, Linux, and macOS.

## Testing and Reliability

The project includes automated tests for encryption, data integrity, vault creation, password management, backups, file-saving operations, password generation, and session locking.

The goal is to make Clavis reliable, secure, and easy to use while keeping its main functionality completely offline.

## Project Goal

Clavis is an open-source project focused on privacy, portability, and local security. Its main idea is simple: keep your encrypted password vault physically with you, without depending on cloud services or trusting remote servers.

**Your vault. Your device. Your control.**
