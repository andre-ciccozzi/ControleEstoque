"""Ferramentas de recuperação: SQLite -> MySQL e MySQL -> SQLite."""

import argparse
import json
from pathlib import Path

from database import DatabaseManager
from settings import load_settings


def main():
    parser = argparse.ArgumentParser(description='Gerencia o MySQL e a cópia SQLite do ControleEstoque.')
    parser.add_argument('command', choices=('status', 'restore-mysql', 'backup-sqlite'))
    parser.add_argument('--replace', action='store_true', help='Substitui os dados MySQL após salvar uma cópia dos dados anteriores.')
    args = parser.parse_args()
    if args.replace and args.command != 'restore-mysql':
        parser.error('--replace é usado apenas com restore-mysql.')
    base_dir = Path(__file__).resolve().parent
    manager = DatabaseManager(load_settings(base_dir), base_dir)
    manager.initialize_sqlite()
    try:
        import mysql.connector
        connector = mysql.connector
    except ImportError:
        connector = None
    try:
        if args.command == 'restore-mysql':
            result = manager.restore_mysql(connector, replace_existing=args.replace)
        elif args.command == 'backup-sqlite':
            result = manager.backup_sqlite(connector)
        else:
            conn = manager.connect(connector)
            try:
                cursor = conn.cursor()
                counts = {}
                for table in ('User', 'ProdutosSemPatrimonio', 'ProdutosComPatrimonio'):
                    cursor.execute(f'SELECT COUNT(*) FROM `{table}`')
                    counts[table] = cursor.fetchone()[0]
                cursor.close()
                result = {
                    'banco_ativo': manager.selected, 'sqlite': str(manager.sqlite_path),
                    'registros': counts, 'observacao': manager.last_error,
                    'erro_backup': manager.backup_error,
                }
            finally:
                conn.close()
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except Exception as error:
        parser.exit(1, f'Banco de dados: {error}\n')


if __name__ == '__main__':
    main()
