import sqlite3
from html.parser import HTMLParser
from unittest.mock import MagicMock

import pytest


def find_user(app_module, email):
    return next(user for user in app_module.list_users() if user['email_user'] == email)


def register(form_post, client, email='nova@example.com', **extra):
    return form_post(client, '/cadastro', data={
        'name': 'Nova pessoa', 'email': email, 'password': 'senha123', **extra,
    })


def login(form_post, client, email, password='senha123', perfil='user'):
    return form_post(client, '/login', data={'email': email, 'password': password, 'perfil': perfil})


def test_index_offers_both_access_areas(guest_client):
    response = guest_client.get('/')
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert 'Administrador' in html and 'Usuário' in html
    assert '/login?perfil=admin' in html and '/login?perfil=user' in html
    assert '/cadastro' in html


@pytest.mark.parametrize('role', ['user', 'admin'])
def test_register_requires_approval(app_module, guest_client, admin_client, form_post, role):
    # Campos extras do formulário público nunca aprovam nem promovem a conta.
    response = register(form_post, guest_client, role='admin', status='approved', name='Alice')
    assert response.status_code == 302
    user = find_user(app_module, 'nova@example.com')
    assert user['role_user'] == 'user'
    assert user['status_user'] == 'pending'
    stored = app_module.get_user(user['id'])['password_user']
    assert stored != 'senha123'
    assert app_module.check_password_hash(stored, 'senha123')

    response = login(form_post, guest_client, 'nova@example.com')
    assert response.status_code == 403
    assert 'aguardando aprovação' in response.get_data(as_text=True)
    with guest_client.session_transaction() as session:
        assert 'user_id' not in session

    response = admin_client.get('/contrl')
    assert response.status_code == 200
    assert 'nova@example.com' in response.get_data(as_text=True)
    assert f"/aprovar_usuario/{user['id']}" in response.get_data(as_text=True)

    response = form_post(admin_client, f"/aprovar_usuario/{user['id']}", data={'role': role})
    assert response.status_code == 302
    approved = app_module.get_user(user['id'])
    assert approved['status_user'] == 'approved'
    assert approved['role_user'] == role

    response = login(form_post, guest_client, 'nova@example.com', perfil=role)
    assert response.status_code == 302
    assert response.headers['Location'] == ('/contrl' if role == 'admin' else '/estoque')
    with guest_client.session_transaction() as session:
        assert session['user_id'] == user['id']
        assert 'user_password' not in session
        assert 'user_role' not in session


def test_normal_user_cannot_enter_admin_login(client, form_post):
    response = login(form_post, client, 'bob@example.com', 'password456', perfil='admin')
    assert response.status_code == 403
    assert 'não tem permissão de administrador' in response.get_data(as_text=True)
    assert client.get('/contrl').status_code == 302


def test_invalid_login_stays_on_selected_area(guest_client, form_post):
    response = login(form_post, guest_client, 'alice@example.com', 'incorreta', perfil='admin')
    assert response.status_code == 401
    html = response.get_data(as_text=True)
    assert 'E-mail ou senha incorretos' in html
    assert 'value="admin"' in html
    assert '/cadastro' in html


@pytest.mark.parametrize('path,method', [
    ('/contrl', 'GET'), ('/control', 'GET'),
    ('/estoque', 'GET'), ('/estoque_sem_patrimonio', 'GET'), ('/estoque_com_patrimonio', 'GET'),
    ('/exportar_excel', 'GET'), ('/editar_sem_patrimonio/1', 'GET'), ('/editar_com_patrimonio/1', 'GET'),
    ('/adicionar_sem_patrimonio', 'POST'), ('/adicionar_com_patrimonio', 'POST'),
    ('/editar_sem_patrimonio/1', 'POST'), ('/editar_com_patrimonio/1', 'POST'),
    ('/remover_sem_patrimonio/1', 'POST'), ('/remover_com_patrimonio/1', 'POST'),
    ('/adicionar_usuario_admin', 'POST'), ('/aprovar_usuario/2', 'POST'),
    ('/alterar_perfil_usuario/2', 'POST'), ('/remover_usuario/2', 'POST'),
])
def test_anonymous_cannot_access_private_routes(guest_client, path, method):
    response = guest_client.open(path, method=method)
    assert response.status_code == 302
    assert response.headers['Location'].startswith('/login?perfil=')


@pytest.mark.parametrize('path,method', [
    ('/contrl', 'GET'), ('/control', 'GET'), ('/adicionar_usuario_admin', 'POST'),
    ('/aprovar_usuario/2', 'POST'), ('/alterar_perfil_usuario/2', 'POST'), ('/remover_usuario/1', 'POST'),
])
def test_user_cannot_manage_accounts(app_module, client, path, method):
    before = app_module.list_users()
    response = client.open(path, method=method, data={'role': 'admin'})
    assert response.status_code == 403
    assert app_module.list_users() == before


def test_admin_can_promote_and_demote_with_immediate_effect(app_module, admin_client, client, form_post):
    response = form_post(admin_client, '/alterar_perfil_usuario/2', data={'role': 'admin'})
    assert response.status_code == 302
    assert client.get('/contrl').status_code == 200

    # Reenviar uma aprovação não pode ser usado para alterar o perfil de uma conta ativa.
    form_post(admin_client, '/aprovar_usuario/2', data={'role': 'user'})
    assert app_module.get_user(2)['role_user'] == 'admin'

    form_post(admin_client, '/alterar_perfil_usuario/2', data={'role': 'user'})
    assert client.get('/contrl').status_code == 403
    assert client.get('/estoque').status_code == 200
    assert app_module.get_user(2)['role_user'] == 'user'


def test_deleted_account_loses_its_session(app_module, admin_client, client, form_post):
    form_post(admin_client, '/remover_usuario/2')
    assert app_module.get_user(2) is None
    assert client.get('/estoque').status_code == 302
    with client.session_transaction() as session:
        assert 'user_id' not in session


def test_admin_cannot_remove_or_demote_self(app_module, admin_client, form_post):
    form_post(admin_client, '/alterar_perfil_usuario/1', data={'role': 'user'})
    form_post(admin_client, '/remover_usuario/1')
    assert app_module.get_user(1)['role_user'] == 'admin'
    assert admin_client.get('/contrl').status_code == 200


def test_admin_can_reject_a_request(app_module, admin_client, guest_client, form_post):
    register(form_post, guest_client)
    user = find_user(app_module, 'nova@example.com')
    response = form_post(admin_client, f"/remover_usuario/{user['id']}")
    assert response.status_code == 302
    assert app_module.get_user(user['id']) is None
    assert login(form_post, guest_client, 'nova@example.com').status_code == 401


@pytest.mark.parametrize('role', ['user', 'admin'])
def test_admin_can_create_an_approved_account(app_module, admin_client, form_post, role):
    response = form_post(admin_client, '/adicionar_usuario_admin', data={
        'name': 'Conta criada pelo admin', 'email': 'conta@example.com', 'password': 'senha123', 'role': role,
    })
    assert response.status_code == 302
    user = find_user(app_module, 'conta@example.com')
    assert user['status_user'] == 'approved'
    assert user['role_user'] == role


def test_invalid_roles_do_not_change_access(app_module, admin_client, guest_client, form_post):
    register(form_post, guest_client)
    pending = find_user(app_module, 'nova@example.com')
    form_post(admin_client, f"/aprovar_usuario/{pending['id']}", data={'role': 'superadmin'})
    form_post(admin_client, '/alterar_perfil_usuario/2', data={'role': 'superadmin'})
    assert app_module.get_user(pending['id'])['status_user'] == 'pending'
    assert app_module.get_user(2)['role_user'] == 'user'


def test_email_is_case_insensitive_and_cannot_be_duplicated(app_module, guest_client, form_post):
    register(form_post, guest_client, email='BOB@EXAMPLE.COM')
    assert len(app_module.list_users()) == 2
    response = login(form_post, guest_client, 'BOB@EXAMPLE.COM', 'password456')
    assert response.status_code == 302


@pytest.mark.parametrize('token', [None, 'incorreto', 'inválido'])
def test_csrf_is_required_for_admin_actions(app_module, admin_client, token):
    data = {'role': 'admin'}
    if token is not None:
        data['csrf_token'] = token
    response = admin_client.post('/alterar_perfil_usuario/2', data=data)
    assert response.status_code == 400
    assert app_module.get_user(2)['role_user'] == 'user'


def test_pending_or_forged_session_does_not_grant_access(app_module, guest_client, form_post):
    register(form_post, guest_client)
    user = find_user(app_module, 'nova@example.com')
    with guest_client.session_transaction() as session:
        session.update(user_id=user['id'], user_email=user['email_user'], user_role='admin')
    assert guest_client.get('/estoque').status_code == 302
    with guest_client.session_transaction() as session:
        session.update(user_id=1, user_email='outra@example.com', user_role='admin')
    assert guest_client.get('/contrl').status_code == 302


def test_legacy_accounts_are_migrated_once(app_module, guest_client, form_post):
    with sqlite3.connect(app_module.DB_PATH) as conn:
        conn.execute('DROP TABLE User')
        conn.execute('''CREATE TABLE User (
            id INTEGER PRIMARY KEY, name_user TEXT, email_user TEXT UNIQUE,
            password_user TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')
        conn.executemany('INSERT INTO User (id, name_user, email_user, password_user) VALUES (?, ?, ?, ?)', [
            (1, 'Alice', 'alice@example.com', 'password123'),
            (2, 'Alice', 'outra@example.com', 'senha123'),
        ])
    app_module.init_sqlite_database()
    assert app_module.get_user(1)['role_user'] == 'admin'
    assert app_module.get_user(2)['role_user'] == 'user'
    assert app_module.get_user(2)['status_user'] == 'approved'

    response = login(form_post, guest_client, 'alice@example.com', 'password123', perfil='admin')
    assert response.status_code == 302
    assert app_module.check_password_hash(app_module.get_user(1)['password_user'], 'password123')

    app_module.update_user_access(1, 'user')
    app_module.init_sqlite_database()
    assert app_module.get_user(1)['role_user'] == 'user'


def test_mysql_schema_migration_preserves_new_roles(app_module):
    conn = MagicMock()
    conn.cursor.return_value.fetchall.return_value = [
        ('id', 'int'), ('password_user', 'varchar(100)'), ('email_user', 'varchar(90)'),
    ]
    app_module.migrate_user_access(conn)
    queries = [call.args[0] for call in conn.cursor.return_value.execute.call_args_list]
    assert any('MODIFY password_user VARCHAR(255)' in query for query in queries)
    assert any('ADD COLUMN role_user' in query for query in queries)
    assert any('ADD COLUMN status_user' in query for query in queries)
    conn.commit.assert_called_once()

    conn.reset_mock()
    conn.cursor.return_value.fetchall.return_value = [
        ('id', 'int'), ('password_user', 'varchar(255)'),
        ('role_user', 'varchar(10)'), ('status_user', 'varchar(10)'),
    ]
    app_module.migrate_user_access(conn)
    queries = [call.args[0] for call in conn.cursor.return_value.execute.call_args_list]
    assert queries == ['SHOW COLUMNS FROM User']


class FormParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.forms = []
        self.active_form = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'form':
            self.active_form = {'action': attrs.get('action'), 'method': attrs.get('method', 'GET').upper(), 'fields': {}}
            self.forms.append(self.active_form)
        elif tag == 'input' and self.active_form is not None:
            self.active_form['fields'][attrs.get('name')] = attrs.get('value', '')

    def handle_endtag(self, tag):
        if tag == 'form':
            self.active_form = None


def test_forms_include_csrf_and_user_navigation_respects_roles(guest_client, admin_client, client, form_post):
    register(form_post, guest_client)
    for browser, path in [
        (guest_client, '/login?perfil=admin'), (guest_client, '/cadastro'),
        (admin_client, '/contrl'), (client, '/estoque_sem_patrimonio'),
        (client, '/estoque_com_patrimonio'), (client, '/editar_com_patrimonio/1'),
    ]:
        response = browser.get(path)
        assert response.status_code == 200
        parser = FormParser()
        parser.feed(response.get_data(as_text=True))
        assert parser.forms
        assert all(form['fields'].get('csrf_token') for form in parser.forms if form['method'] == 'POST')
    for path in ['/estoque', '/estoque_com_patrimonio', '/estoque_sem_patrimonio']:
        assert 'href="/contrl"' not in client.get(path).get_data(as_text=True)


def test_logout_returns_to_access_selection(client):
    response = client.get('/logout')
    assert response.status_code == 302
    assert response.headers['Location'] == '/'
    assert client.get('/estoque').status_code == 302
