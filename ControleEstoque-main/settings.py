"""Configuração local opcional, com precedência das variáveis de ambiente."""

import json
import os
import re
from pathlib import Path


def load_settings(base_dir):
    base_dir = Path(base_dir)
    path = base_dir / 'config.local.json'
    local = json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}
    if not isinstance(local, dict) or not isinstance(local.get('mysql', {}), dict):
        raise ValueError('config.local.json deve conter um objeto de configuração válido.')
    mysql = local.get('mysql', {})
    backend = os.environ.get('DATABASE_BACKEND', local.get('database_backend', 'auto')).lower()
    if backend not in ('auto', 'sqlite', 'mysql'):
        raise ValueError('DATABASE_BACKEND deve ser auto, sqlite ou mysql.')
    database = os.environ.get('MYSQL_DATABASE', mysql.get('database', 'controlestoque'))
    if not re.fullmatch(r'[A-Za-z0-9_]{1,64}', database):
        raise ValueError('MYSQL_DATABASE aceita apenas letras, números e sublinhado, até 64 caracteres.')
    sqlite_path = Path(os.environ.get('CONTROLE_ESTOQUE_DB_PATH', local.get('sqlite_path', 'controlestoque.db')))
    if not sqlite_path.is_absolute():
        sqlite_path = base_dir / sqlite_path
    return {
        'backend': backend,
        'sqlite_path': sqlite_path,
        'secret_key': os.environ.get('SECRET_KEY') or local.get('secret_key') or None,
        'mysql': {
            'host': os.environ.get('MYSQL_HOST', mysql.get('host', '127.0.0.1')),
            'port': int(os.environ.get('MYSQL_PORT', mysql.get('port', 3306))),
            'user': os.environ.get('MYSQL_USER', mysql.get('user', 'root')),
            'password': os.environ.get('MYSQL_PASSWORD', mysql.get('password', '')),
            'database': database, 'connection_timeout': 3, 'charset': 'utf8mb4',
        },
    }
