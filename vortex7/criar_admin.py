#!/usr/bin/env python3
"""Cria o admin da VORTEX 7 (se não existir) ou reseta a senha de um já existente.

Uso:
    python vortex7/criar_admin.py
    python vortex7/criar_admin.py meuemail@loja.com.br
"""
import getpass
import os
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from werkzeug.security import generate_password_hash

from vortex7.common import DB_PATH, ensure_schema, now_iso


def main():
    email = (sys.argv[1] if len(sys.argv) > 1 else input("E-mail do admin: ")).strip().lower()
    if not email or "@" not in email:
        print("E-mail inválido."); return 1

    p1 = getpass.getpass("Nova senha (mín. 8 caracteres): ")
    if len(p1) < 8:
        print("A senha deve ter pelo menos 8 caracteres."); return 1
    p2 = getpass.getpass("Confirme a senha: ")
    if p1 != p2:
        print("As senhas não coincidem."); return 1

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    ensure_schema(conn)
    pwd_hash = generate_password_hash(p1)

    existing = conn.execute("SELECT id FROM admins WHERE email = ?", (email,)).fetchone()
    if existing:
        conn.execute("UPDATE admins SET password = ? WHERE id = ?", (pwd_hash, existing["id"]))
        print(f"Senha atualizada para {email}.")
    else:
        conn.execute(
            "INSERT INTO admins (name, email, password, created_at) VALUES (?, ?, ?, ?)",
            ("Administrador", email, pwd_hash, now_iso()),
        )
        print(f"Admin {email} criado.")
    conn.commit()
    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
