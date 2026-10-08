"""Backup explícito antes do deploy. Não importa app.py nem inicializa bancos."""
import argparse
import os
from pathlib import Path
import shutil
import sqlite3

ROOT=Path(__file__).resolve().parents[1]

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--destino',required=True,help='Diretório novo em disco persistente; baixe a cópia antes de atualizar.')
    args=parser.parse_args()
    target=Path(args.destino).resolve()
    if target.exists():raise SystemExit('O destino já existe. Escolha outro para não sobrescrever backups.')
    target.mkdir(parents=True,mode=0o700)
    for env,default,name in [('TRIADE_AUTH_DB','accounts.db','accounts.db'),('KAKA_DB','kaka/database.db','kaka.db'),('SECTEST_DB','sectest/database.db','sectest.db'),('VORTEX7_DB','vortex7/database.db','vortex7.db')]:
        source=Path(os.environ.get(env,ROOT/default)).resolve()
        if not source.is_file():
            print(env+': não encontrado; não foi criado um banco vazio.')
            continue
        with sqlite3.connect(source.as_uri()+'?mode=ro',uri=True) as conn, sqlite3.connect(target/name) as backup:
            conn.backup(backup)
            if backup.execute('PRAGMA integrity_check').fetchone()[0]!='ok':raise SystemExit('Verificação falhou: '+name)
        os.chmod(target/name,0o600)
        print(env+': cópia íntegra.')
    for rel in ['kaka/static/uploads','vortex7/static/images/products']:
        source=ROOT/rel
        if source.exists():shutil.copytree(source,target/rel)
    secret=ROOT/'.session-secret'
    if secret.exists():
        shutil.copy2(secret,target/'.session-secret');os.chmod(target/'.session-secret',0o600)
    print('Backup concluído. Contém dados privados: guarde fora do Git e não publique.')

if __name__=='__main__':main()
