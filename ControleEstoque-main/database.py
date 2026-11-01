"""MySQL principal com cópia SQLite transacional e recuperação de dados."""

import hashlib
import json
import logging
import sqlite3
import threading
from pathlib import Path
from uuid import uuid4

from werkzeug.security import generate_password_hash

logger = logging.getLogger(__name__)
TABLE_COLUMNS = {
    'User': ('id', 'name_user', 'email_user', 'password_user', 'role_user', 'status_user', 'created_at', 'updated_at'),
    'ProdutosSemPatrimonio': ('ProdutoID', 'DescricaoComercial', 'Unidade', 'MarcaModelo', 'Total'),
    'ProdutosComPatrimonio': ('ProdutoID', 'Responsavel', 'Cargo', 'LocalObra', 'MarcaModelo', 'SerialNumero', 'Sequencial', 'Observacao'),
}
SQLITE_SCHEMA = (
    '''CREATE TABLE IF NOT EXISTS User (
        id INTEGER PRIMARY KEY AUTOINCREMENT, name_user TEXT NOT NULL,
        email_user TEXT NOT NULL UNIQUE, password_user TEXT NOT NULL,
        role_user TEXT NOT NULL DEFAULT 'user', status_user TEXT NOT NULL DEFAULT 'pending',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''',
    '''CREATE TABLE IF NOT EXISTS ProdutosSemPatrimonio (
        ProdutoID INTEGER PRIMARY KEY AUTOINCREMENT, DescricaoComercial TEXT,
        Unidade TEXT, MarcaModelo TEXT, Total INTEGER
    )''',
    '''CREATE TABLE IF NOT EXISTS ProdutosComPatrimonio (
        ProdutoID INTEGER PRIMARY KEY AUTOINCREMENT, Responsavel TEXT, Cargo TEXT,
        LocalObra TEXT, MarcaModelo TEXT, SerialNumero TEXT, Sequencial INTEGER, Observacao TEXT
    )''',
    'CREATE TABLE IF NOT EXISTS _storage_state (name TEXT PRIMARY KEY, value TEXT NOT NULL)',
)


class SyncConflict(RuntimeError):
    pass


def is_sqlite_connection(conn):
    return isinstance(conn, sqlite3.Connection)


def migrate_user_access(conn):
    cursor = conn.cursor()
    try:
        if is_sqlite_connection(conn):
            cursor.execute('PRAGMA table_info(User)')
            columns = {row[1] for row in cursor.fetchall()}
        else:
            cursor.execute('SHOW COLUMNS FROM User')
            types = {row[0]: row[1].lower() for row in cursor.fetchall()}
            columns = set(types)
            if types.get('password_user') == 'varchar(100)':
                cursor.execute('ALTER TABLE User MODIFY password_user VARCHAR(255) NOT NULL')
        if 'role_user' not in columns:
            cursor.execute("ALTER TABLE User ADD COLUMN role_user VARCHAR(10) NOT NULL DEFAULT 'user'")
            cursor.execute("UPDATE User SET role_user = 'admin' WHERE LOWER(email_user) = 'alice@example.com'")
        if 'status_user' not in columns:
            cursor.execute("ALTER TABLE User ADD COLUMN status_user VARCHAR(10) NOT NULL DEFAULT 'pending'")
            cursor.execute("UPDATE User SET status_user = 'approved'")
        conn.commit()
    finally:
        cursor.close()


def read_snapshot(conn):
    snapshot = {}
    cursor = conn.cursor()
    try:
        for table, columns in TABLE_COLUMNS.items():
            names = ', '.join(f'`{name}`' for name in columns)
            cursor.execute(f'SELECT {names} FROM `{table}` ORDER BY `{columns[0]}`')
            snapshot[table] = [tuple(value if value is None or isinstance(value, (str, int, float)) else str(value)
                                     for value in row) for row in cursor.fetchall()]
        return snapshot
    finally:
        cursor.close()


def snapshot_digest(snapshot):
    content = json.dumps(snapshot, sort_keys=True, ensure_ascii=True, separators=(',', ':'))
    return hashlib.sha256(content.encode('utf-8')).hexdigest()


def replace_snapshot(conn, snapshot):
    """Substitui apenas as tabelas da aplicação; quem chama confirma a transação."""
    placeholder = '?' if is_sqlite_connection(conn) else '%s'
    cursor = conn.cursor()
    try:
        for table in reversed(TABLE_COLUMNS):
            cursor.execute(f'DELETE FROM `{table}`')
        for table, columns in TABLE_COLUMNS.items():
            if snapshot[table]:
                names = ', '.join(f'`{name}`' for name in columns)
                values = ', '.join([placeholder] * len(columns))
                cursor.executemany(f'INSERT INTO `{table}` ({names}) VALUES ({values})', snapshot[table])
    except Exception:
        conn.rollback()
        raise
    finally:
        cursor.close()


class MirroredMySQLConnection:
    def __init__(self, raw, manager):
        self.raw = raw
        self.manager = manager

    def __getattr__(self, name):
        return getattr(self.raw, name)

    def commit(self):
        self.raw.commit()
        try:
            self.manager.refresh_backup(self.raw)
        except Exception as error:
            self.manager.backup_error = str(error)
            logger.error('Gravação MySQL concluída, mas a cópia SQLite falhou: %s', error)


class DatabaseManager:
    def __init__(self, settings, base_dir):
        self.settings = settings
        self.base_dir = Path(base_dir)
        self.sqlite_path = Path(settings['sqlite_path'])
        self.selected = None
        self.last_error = None
        self.backup_error = None
        self._prepared = False
        self._recreated = False
        self._lock = threading.RLock()

    def sqlite_connection(self):
        conn = sqlite3.connect(self.sqlite_path, timeout=15)
        conn.row_factory = sqlite3.Row
        return conn

    def initialize_sqlite(self):
        fresh = not self.sqlite_path.exists() or self.sqlite_path.stat().st_size == 0
        self.sqlite_path.parent.mkdir(parents=True, exist_ok=True)
        conn = self.sqlite_connection()
        try:
            for statement in SQLITE_SCHEMA:
                conn.execute(statement)
            migrate_user_access(conn)
            if fresh:
                conn.executemany(
                    'INSERT INTO User (name_user, email_user, password_user, role_user, status_user) VALUES (?, ?, ?, ?, ?)',
                    [('Alice', 'alice@example.com', generate_password_hash('password123'), 'admin', 'approved'),
                     ('Bob', 'bob@example.com', generate_password_hash('password456'), 'user', 'approved')],
                )
                conn.executemany(
                    'INSERT INTO ProdutosSemPatrimonio (DescricaoComercial, Unidade, MarcaModelo, Total) VALUES (?, ?, ?, ?)',
                    [('Caneta Esferográfica Azul', 'Peça', 'BIC Cristal', 500),
                     ('Papel Sulfite A4', 'Pacote', 'Chamex A4', 300),
                     ('Lápis Preto', 'Peça', 'Faber-Castell 2B', 1000)],
                )
                conn.executemany(
                    'INSERT INTO ProdutosComPatrimonio (Responsavel, Cargo, LocalObra, MarcaModelo, SerialNumero, Sequencial, Observacao) VALUES (?, ?, ?, ?, ?, ?, ?)',
                    [('Carlos', 'Gerente', 'Obra A', 'Dell Inspiron', 'SN123456', 1, 'Notebook para uso na obra A'),
                     ('Diana', 'Engenheira', 'Obra B', 'HP Pavilion', 'SN654321', 2, 'Notebook para uso na obra B')],
                )
                conn.execute(
                    "INSERT INTO _storage_state (name, value) VALUES ('bootstrap_digest', ?)",
                    (snapshot_digest(read_snapshot(conn)),),
                )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def archive_sqlite(self):
        folder = self.base_dir / 'backups'
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / f'sqlite_{uuid4().hex[:12]}.sqlite3'
        source = self.sqlite_connection()
        destination = sqlite3.connect(path)
        try:
            source.backup(destination)
        finally:
            source.close()
            destination.close()
        return path

    def archive_mysql(self, snapshot):
        folder = self.base_dir / 'backups'
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / f'mysql_{uuid4().hex[:12]}.json'
        path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding='utf-8')
        return path

    def open_mysql(self, connector):
        if connector is None:
            raise RuntimeError('Instale mysql-connector-python para usar MySQL.')
        config = dict(self.settings['mysql'])
        try:
            conn = connector.connect(**config)
        except Exception as error:
            if getattr(error, 'errno', None) != 1049:
                raise
            database = config.pop('database')
            conn = connector.connect(**config)
            try:
                cursor = conn.cursor()
                cursor.execute(f'CREATE DATABASE IF NOT EXISTS `{database}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci')
                cursor.execute(f'USE `{database}`')
                cursor.close()
                self._prepared = False
                self._recreated = True
            except Exception:
                conn.close()
                raise
        try:
            if not self._prepared:
                cursor = conn.cursor()
                schema = (self.base_dir / 'controlestoque.sql').read_text(encoding='utf-8')
                statements = '\n'.join(line for line in schema.splitlines() if not line.lstrip().startswith('--'))
                for statement in statements.split(';'):
                    if statement.strip():
                        cursor.execute(statement.strip())
                cursor.close()
                migrate_user_access(conn)
                self._prepared = True
            return conn
        except Exception:
            conn.close()
            raise

    def _save_sqlite(self, snapshot):
        conn = self.sqlite_connection()
        try:
            replace_snapshot(conn, snapshot)
            conn.execute(
                "INSERT INTO _storage_state (name, value) VALUES ('mysql_digest', ?) "
                'ON CONFLICT(name) DO UPDATE SET value = excluded.value',
                (snapshot_digest(snapshot),),
            )
            conn.execute("DELETE FROM _storage_state WHERE name = 'bootstrap_digest'")
            conn.commit()
            self.backup_error = None
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _local_state(self):
        conn = self.sqlite_connection()
        try:
            row = conn.execute("SELECT value FROM _storage_state WHERE name = 'mysql_digest'").fetchone()
            return read_snapshot(conn), row[0] if row else None
        finally:
            conn.close()

    def reconcile(self, conn):
        local, checkpoint = self._local_state()
        remote = read_snapshot(conn)
        local_hash, remote_hash = snapshot_digest(local), snapshot_digest(remote)
        if local_hash == remote_hash:
            self._save_sqlite(remote)
        elif not any(remote.values()) or checkpoint == remote_hash:
            replace_snapshot(conn, local)
            conn.commit()
            self._save_sqlite(read_snapshot(conn))
        elif not any(local.values()) or checkpoint == local_hash or self._only_initial_examples(local_hash):
            self.archive_sqlite()
            self._save_sqlite(remote)
        else:
            raise SyncConflict('MySQL e SQLite contêm alterações diferentes. Ambos foram preservados. Use manage_database.py para escolher qual cópia restaurar.')

    def _only_initial_examples(self, local_hash):
        conn = self.sqlite_connection()
        try:
            row = conn.execute("SELECT value FROM _storage_state WHERE name = 'bootstrap_digest'").fetchone()
            return bool(row and row[0] == local_hash)
        finally:
            conn.close()

    def refresh_backup(self, conn):
        with self._lock:
            local, checkpoint = self._local_state()
            if checkpoint is not None and snapshot_digest(local) != checkpoint:
                raise SyncConflict('SQLite foi alterado fora desta conexão; a cópia local foi preservada.')
            self._save_sqlite(read_snapshot(conn))

    def connect(self, connector=None):
        with self._lock:
            if self.settings['backend'] == 'sqlite' or (connector is None and self.settings['backend'] != 'mysql'):
                self.selected = 'sqlite'
                return self.sqlite_connection()
            if self.selected == 'sqlite' and self.settings['backend'] == 'auto':
                return self.sqlite_connection()
            conn = None
            try:
                conn = self.open_mysql(connector)
                if self._recreated and self.backup_error:
                    raise RuntimeError('A cópia SQLite está desatualizada após uma falha de backup; a recuperação automática foi interrompida.')
                if self.selected != 'mysql' or self._recreated:
                    self.reconcile(conn)
                    self._recreated = False
                self.selected = 'mysql'
                self.last_error = None
                return MirroredMySQLConnection(conn, self)
            except Exception as error:
                if conn is not None:
                    conn.close()
                self.last_error = str(error)
                if self.settings['backend'] == 'mysql' or self.backup_error:
                    raise
                self.selected = 'sqlite'
                logger.warning('SQLite ativo: %s', error)
                return self.sqlite_connection()

    def restore_mysql(self, connector, replace_existing=False):
        with self._lock:
            conn = self.open_mysql(connector)
            try:
                local, _ = self._local_state()
                remote = read_snapshot(conn)
                archive = None
                if any(remote.values()) and snapshot_digest(local) != snapshot_digest(remote):
                    if not replace_existing:
                        raise SyncConflict('MySQL já contém dados diferentes. Use --replace somente para substituí-los pelo SQLite.')
                    archive = self.archive_mysql(remote)
                replace_snapshot(conn, local)
                conn.commit()
                self._save_sqlite(read_snapshot(conn))
                self.selected = 'mysql'
                self.last_error = None
                return {'registros': {table: len(rows) for table, rows in local.items()}, 'backup_mysql_anterior': str(archive) if archive else None}
            except Exception:
                conn.rollback()
                raise
            finally:
                conn.close()

    def backup_sqlite(self, connector):
        with self._lock:
            conn = self.open_mysql(connector)
            try:
                snapshot = read_snapshot(conn)
                if not any(snapshot.values()):
                    raise SyncConflict('MySQL está vazio. Use restore-mysql para recuperar os dados do SQLite.')
                archive = self.archive_sqlite()
                self._save_sqlite(snapshot)
                self.selected = 'mysql'
                return {'backup_sqlite_anterior': str(archive), 'registros': {table: len(rows) for table, rows in snapshot.items()}}
            finally:
                conn.close()
