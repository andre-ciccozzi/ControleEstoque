import importlib.util
import secrets
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def app_module(tmp_path, monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT))
    monkeypatch.setenv('DATABASE_BACKEND', 'sqlite')
    monkeypatch.setenv('CONTROLE_ESTOQUE_DB_PATH', str(tmp_path / 'test_estoque.db'))
    spec = importlib.util.spec_from_file_location('controle_app', ROOT / 'conect.py')
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, spec.name, module)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, 'mysql', None)
    module.app.config['TESTING'] = True
    return module


@pytest.fixture
def guest_client(app_module):
    return app_module.app.test_client()


@pytest.fixture
def client(app_module):
    client = app_module.app.test_client()
    with client.session_transaction() as session:
        session['user_id'] = 2
        session['user_email'] = 'bob@example.com'
    return client


@pytest.fixture
def admin_client(app_module):
    client = app_module.app.test_client()
    with client.session_transaction() as session:
        session['user_id'] = 1
        session['user_email'] = 'alice@example.com'
    return client


@pytest.fixture
def form_post():
    def post(client, path, data=None, **kwargs):
        with client.session_transaction() as session:
            token = session.setdefault('_csrf_token', secrets.token_urlsafe(32))
        return client.post(path, data={**(data or {}), 'csrf_token': token}, **kwargs)
    return post
