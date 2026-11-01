import json
import sqlite3
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

ROOT = Path(__file__).resolve().parent.parent


class MySQLCursorAdapter:
    def __init__(self, cursor, dictionary=False):
        self.cursor = cursor
        self.dictionary = dictionary

    def execute(self, query, values=()):
        return self.cursor.execute(query.replace('%s', '?'), values)

    def executemany(self, query, values):
        return self.cursor.executemany(query.replace('%s', '?'), values)

    def fetchone(self):
        row = self.cursor.fetchone()
        return dict(row) if row is not None and self.dictionary else row

    def fetchall(self):
        rows = self.cursor.fetchall()
        return [dict(row) for row in rows] if self.dictionary else rows

    def close(self):
        self.cursor.close()


class MySQLConnectionAdapter:
    """Executa as transações do sincronizador em um segundo banco real de teste."""
    def __init__(self, path):
        self.raw = sqlite3.connect(path)
        self.raw.row_factory = sqlite3.Row

    def cursor(self, dictionary=False):
        return MySQLCursorAdapter(self.raw.cursor(), dictionary)

    def commit(self):
        self.raw.commit()

    def rollback(self):
        self.raw.rollback()

    def close(self):
        self.raw.close()


@pytest.fixture
def storage(tmp_path, monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT))
    from database import DatabaseManager, SQLITE_SCHEMA, read_snapshot
    from settings import load_settings

    monkeypatch.setenv('CONTROLE_ESTOQUE_DB_PATH', str(tmp_path / 'local.db'))
    monkeypatch.setenv('DATABASE_BACKEND', 'auto')
    settings = load_settings(tmp_path)
    manager = DatabaseManager(settings, tmp_path)
    manager.initialize_sqlite()
    remote_path = tmp_path / 'remote.db'
    with sqlite3.connect(remote_path) as conn:
        for statement in SQLITE_SCHEMA:
            conn.execute(statement)
    (tmp_path / 'controlestoque.sql').write_text((ROOT / 'controlestoque.sql').read_text(encoding='utf-8'), encoding='utf-8')

    def remote():
        return MySQLConnectionAdapter(remote_path)

    def snapshot(factory):
        conn = factory()
        try:
            return read_snapshot(conn)
        finally:
            conn.close()

    monkeypatch.setattr(manager, 'open_mysql', lambda connector: remote())
    return manager, remote, snapshot


def test_empty_mysql_receives_sqlite_with_ids_access_and_timestamps(storage):
    manager, remote, snapshot = storage
    before = snapshot(manager.sqlite_connection)
    conn = manager.connect(object())
    conn.close()
    assert manager.selected == 'mysql'
    assert snapshot(remote) == before
    assert snapshot(manager.sqlite_connection) == before
    assert before['User'][0][4:6] == ('admin', 'approved')


def test_mysql_commits_update_the_sqlite_backup(storage):
    manager, remote, snapshot = storage
    conn = manager.connect(object())
    cursor = conn.cursor()
    cursor.execute("UPDATE ProdutosSemPatrimonio SET Total = %s WHERE ProdutoID = %s", (777, 1))
    cursor.execute("UPDATE User SET role_user = 'admin' WHERE id = 2")
    cursor.execute('DELETE FROM ProdutosComPatrimonio WHERE ProdutoID = 1')
    cursor.close()
    conn.commit()
    conn.close()
    assert snapshot(manager.sqlite_connection) == snapshot(remote)
    assert snapshot(remote)['ProdutosSemPatrimonio'][0][-1] == 777
    assert snapshot(remote)['User'][1][4] == 'admin'


def test_offline_sqlite_changes_are_restored_when_mysql_did_not_change(storage, monkeypatch):
    from database import DatabaseManager
    manager, remote, snapshot = storage
    manager.connect(object()).close()

    def unavailable(connector):
        raise OSError('Servidor indisponível')

    monkeypatch.setattr(manager, 'open_mysql', unavailable)
    conn = manager.connect(object())
    conn.execute('UPDATE ProdutosSemPatrimonio SET Total = 888 WHERE ProdutoID = 1')
    conn.commit()
    conn.close()
    offline = snapshot(manager.sqlite_connection)
    restarted = DatabaseManager(manager.settings, manager.base_dir)
    monkeypatch.setattr(restarted, 'open_mysql', lambda connector: remote())
    restarted.connect(object()).close()
    assert restarted.selected == 'mysql'
    assert snapshot(remote) == offline


def test_divergent_databases_are_preserved_until_explicit_choice(storage, monkeypatch):
    from database import DatabaseManager, SyncConflict
    manager, remote, snapshot = storage
    manager.connect(object()).close()
    local = manager.sqlite_connection()
    local.execute('UPDATE ProdutosSemPatrimonio SET Total = 888 WHERE ProdutoID = 1')
    local.commit()
    local.close()
    other = remote()
    other.cursor().execute('UPDATE ProdutosSemPatrimonio SET Total = 999 WHERE ProdutoID = 1')
    other.commit()
    other.close()
    before_local, before_remote = snapshot(manager.sqlite_connection), snapshot(remote)
    restarted = DatabaseManager(manager.settings, manager.base_dir)
    monkeypatch.setattr(restarted, 'open_mysql', lambda connector: remote())
    restarted.connect(object()).close()
    assert restarted.selected == 'sqlite'
    assert 'alterações diferentes' in restarted.last_error
    with pytest.raises(SyncConflict):
        restarted.restore_mysql(object())
    assert snapshot(manager.sqlite_connection) == before_local
    assert snapshot(remote) == before_remote
    result = restarted.restore_mysql(object(), replace_existing=True)
    assert Path(result['backup_mysql_anterior']).is_file()
    assert json.loads(Path(result['backup_mysql_anterior']).read_text(encoding='utf-8'))['ProdutosSemPatrimonio'][0][-1] == 999
    assert snapshot(remote) == before_local


def test_mysql_only_changes_refresh_backup_and_archive_previous_copy(storage, monkeypatch):
    from database import DatabaseManager
    manager, remote, snapshot = storage
    manager.connect(object()).close()
    other = remote()
    other.cursor().execute('DELETE FROM ProdutosSemPatrimonio WHERE ProdutoID = 3')
    other.commit()
    other.close()
    restarted = DatabaseManager(manager.settings, manager.base_dir)
    monkeypatch.setattr(restarted, 'open_mysql', lambda connector: remote())
    restarted.connect(object()).close()
    assert snapshot(manager.sqlite_connection) == snapshot(remote)
    assert len(list((manager.base_dir / 'backups').glob('*.sqlite3'))) == 1


def test_existing_mysql_is_used_when_sqlite_has_only_initial_examples(storage):
    from database import replace_snapshot
    manager, remote, snapshot = storage
    existing = snapshot(manager.sqlite_connection)
    rows = list(existing['ProdutosSemPatrimonio'])
    rows[0] = (*rows[0][:-1], 999)
    existing['ProdutosSemPatrimonio'] = rows
    conn = remote()
    replace_snapshot(conn, existing)
    conn.commit()
    conn.close()
    manager.connect(object()).close()
    assert manager.selected == 'mysql'
    assert snapshot(manager.sqlite_connection) == existing


def test_explicit_backup_saves_local_changes_before_using_mysql(storage):
    manager, remote, snapshot = storage
    manager.connect(object()).close()
    local = manager.sqlite_connection()
    local.execute('UPDATE ProdutosSemPatrimonio SET Total = 111 WHERE ProdutoID = 1')
    local.commit()
    local.close()
    result = manager.backup_sqlite(object())
    archive = sqlite3.connect(result['backup_sqlite_anterior'])
    try:
        assert archive.execute('SELECT Total FROM ProdutosSemPatrimonio WHERE ProdutoID = 1').fetchone()[0] == 111
    finally:
        archive.close()
    assert snapshot(manager.sqlite_connection) == snapshot(remote)


def test_backup_failure_preserves_offline_changes_and_blocks_stale_fallback(storage, monkeypatch):
    manager, _, snapshot = storage
    conn = manager.connect(object())
    local = manager.sqlite_connection()
    local.execute('UPDATE ProdutosSemPatrimonio SET Total = 111 WHERE ProdutoID = 1')
    local.commit()
    local.close()
    conn.cursor().execute('UPDATE ProdutosSemPatrimonio SET Total = 222 WHERE ProdutoID = 1')
    conn.commit()
    conn.close()
    assert manager.backup_error
    assert snapshot(manager.sqlite_connection)['ProdutosSemPatrimonio'][0][-1] == 111
    monkeypatch.setattr(manager, 'open_mysql', MagicMock(side_effect=OSError('indisponível')))
    with pytest.raises(OSError):
        manager.connect(object())


def test_known_stale_backup_is_not_used_to_recreate_mysql(storage, monkeypatch):
    manager, remote, snapshot = storage
    manager.connect(object()).close()
    before = snapshot(remote)
    manager.backup_error = 'Falha anterior na copia'

    def recreated(connector):
        manager._recreated = True
        return remote()

    monkeypatch.setattr(manager, 'open_mysql', recreated)
    with pytest.raises(RuntimeError, match='desatualizada'):
        manager.connect(object())
    assert snapshot(remote) == before


def test_deleted_database_is_restored_even_after_mysql_was_selected(storage, monkeypatch):
    manager, remote, snapshot = storage
    manager.connect(object()).close()
    expected = snapshot(manager.sqlite_connection)
    cleared = remote()
    for table in ('User', 'ProdutosSemPatrimonio', 'ProdutosComPatrimonio'):
        cleared.cursor().execute(f'DELETE FROM {table}')
    cleared.commit()
    cleared.close()

    def recreated(connector):
        manager._recreated = True
        return remote()

    monkeypatch.setattr(manager, 'open_mysql', recreated)
    manager.connect(object()).close()
    assert snapshot(remote) == expected


def test_missing_mysql_database_is_created_without_dropping_existing_data(storage):
    from database import DatabaseManager
    manager, _, _ = storage
    real = DatabaseManager(manager.settings, manager.base_dir)
    error = RuntimeError('Unknown database')
    error.errno = 1049
    raw = MagicMock()
    raw.cursor.return_value.fetchall.return_value = [
        ('password_user', 'varchar(255)'), ('role_user', 'varchar(10)'), ('status_user', 'varchar(10)'),
    ]
    connector = MagicMock()
    connector.connect.side_effect = [error, raw]
    assert real.open_mysql(connector) is raw
    assert 'database' in connector.connect.call_args_list[0].kwargs
    assert 'database' not in connector.connect.call_args_list[1].kwargs
    queries = [call.args[0] for call in raw.cursor.return_value.execute.call_args_list]
    assert any(query.startswith('CREATE DATABASE IF NOT EXISTS') for query in queries)
    assert sum(query.startswith('CREATE TABLE IF NOT EXISTS') for query in queries) == 3
    assert not any('DROP ' in query or query.startswith('DELETE ') for query in queries)


def test_unavailable_mysql_uses_sqlite_without_retrying_every_query(storage, monkeypatch):
    manager, _, _ = storage
    unavailable = MagicMock(side_effect=OSError('indisponível'))
    monkeypatch.setattr(manager, 'open_mysql', unavailable)
    manager.connect(object()).close()
    manager.connect(object()).close()
    unavailable.assert_called_once()
    manager.settings['backend'] = 'mysql'
    with pytest.raises(OSError):
        manager.connect(object())


def test_restarting_does_not_repopulate_deliberately_empty_stock(storage):
    manager, _, _ = storage
    conn = manager.sqlite_connection()
    conn.execute('DELETE FROM ProdutosSemPatrimonio')
    conn.commit()
    conn.close()
    manager.initialize_sqlite()
    conn = manager.sqlite_connection()
    try:
        assert conn.execute('SELECT COUNT(*) FROM ProdutosSemPatrimonio').fetchone()[0] == 0
    finally:
        conn.close()


def test_settings_environment_precedence_and_database_name_validation(tmp_path, monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT))
    from settings import load_settings
    (tmp_path / 'config.local.json').write_text(json.dumps({'mysql': {'password': 'local-secret'}}), encoding='utf-8')
    monkeypatch.setenv('MYSQL_PASSWORD', 'environment-secret')
    assert load_settings(tmp_path)['mysql']['password'] == 'environment-secret'
    monkeypatch.setenv('MYSQL_DATABASE', 'controle; DROP DATABASE outro')
    with pytest.raises(ValueError):
        load_settings(tmp_path)


def test_empty_mysql_cannot_erase_the_local_backup(storage):
    from database import SyncConflict
    manager, _, snapshot = storage
    before = snapshot(manager.sqlite_connection)
    with pytest.raises(SyncConflict):
        manager.backup_sqlite(object())
    assert snapshot(manager.sqlite_connection) == before


def test_failed_restore_rolls_back_every_table(storage):
    from database import read_snapshot, replace_snapshot
    manager, _, snapshot = storage
    before = snapshot(manager.sqlite_connection)
    invalid = {table: list(rows) for table, rows in before.items()}
    user = list(invalid['User'][0])
    user[0] = 999
    invalid['User'].append(tuple(user))  # Mesmo e-mail viola a restrição UNIQUE.
    conn = manager.sqlite_connection()
    try:
        with pytest.raises(sqlite3.IntegrityError):
            replace_snapshot(conn, invalid)
        assert read_snapshot(conn) == before
    finally:
        conn.close()


def test_application_stock_and_access_changes_are_mirrored(app_module, client, admin_client, form_post, tmp_path, monkeypatch):
    from database import SQLITE_SCHEMA, read_snapshot
    remote_path = tmp_path / 'application_remote.db'
    with sqlite3.connect(remote_path) as conn:
        for statement in SQLITE_SCHEMA:
            conn.execute(statement)
    app_module.database_manager.settings['backend'] = 'auto'
    monkeypatch.setattr(app_module, 'mysql', SimpleNamespace(connector=object()))
    monkeypatch.setattr(app_module.database_manager, 'open_mysql', lambda connector: MySQLConnectionAdapter(remote_path))
    response = form_post(client, '/adicionar_sem_patrimonio', data={
        'descricao_comercial': 'Item espelhado', 'unidade': 'Peça', 'marca_modelo': 'Teste', 'total': '42',
    })
    assert response.status_code == 302
    response = form_post(admin_client, '/alterar_perfil_usuario/2', data={'role': 'admin'})
    assert response.status_code == 302
    local = app_module.database_manager.sqlite_connection()
    remote = MySQLConnectionAdapter(remote_path)
    try:
        assert read_snapshot(local) == read_snapshot(remote)
        assert local.execute('SELECT Total FROM ProdutosSemPatrimonio WHERE DescricaoComercial = ?', ('Item espelhado',)).fetchone()[0] == 42
        assert local.execute('SELECT role_user FROM User WHERE id = 2').fetchone()[0] == 'admin'
    finally:
        local.close()
        remote.close()
