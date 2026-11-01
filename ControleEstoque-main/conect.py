import os
import secrets
import unicodedata
from io import BytesIO

from flask import Flask, abort, flash, g, redirect, render_template, request, send_file, session, url_for
from openpyxl import Workbook
from werkzeug.security import check_password_hash, generate_password_hash

from database import DatabaseManager, is_sqlite_connection, migrate_user_access
from settings import load_settings

try:
    import mysql.connector
except ImportError:  # pragma: no cover - depende do ambiente
    mysql = None

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SETTINGS = load_settings(BASE_DIR)
DB_PATH = str(SETTINGS['sqlite_path'])
database_manager = DatabaseManager(SETTINGS, BASE_DIR)

app = Flask(__name__)
app.secret_key = SETTINGS['secret_key'] or secrets.token_hex(32)
app.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE='Lax')


INVENTORY_FILTER_FIELDS = {
    'sem': {
        'descricao_comercial': ('Descrição comercial', 'DescricaoComercial'),
        'unidade': ('Unidade', 'Unidade'),
        'marca_modelo': ('Marca/Modelo', 'MarcaModelo'),
        'total': ('Total', 'Total'),
    },
    'com': {
        'responsavel': ('Responsável', 'Responsavel'),
        'cargo': ('Cargo', 'Cargo'),
        'local_obra': ('Local/Obra', 'LocalObra'),
        'marca_modelo': ('Marca/Modelo', 'MarcaModelo'),
        'serial_numero': ('Serial/Número', 'SerialNumero'),
        'sequencial': ('Sequencial', 'Sequencial'),
        'observacao': ('Observação', 'Observacao'),
    },
}
INVENTORY_FILTER_FIELDS['todos'] = {
    **INVENTORY_FILTER_FIELDS['sem'], **INVENTORY_FILTER_FIELDS['com'],
}


def normalize_search(value):
    text = unicodedata.normalize('NFKD', str(value if value is not None else '').casefold())
    return ''.join(character for character in text if not unicodedata.combining(character))


def inventory_filters(tipo):
    campo = request.args.get('campo', 'todos')
    if campo not in INVENTORY_FILTER_FIELDS[tipo]:
        campo = 'todos'
    return {'busca': request.args.get('busca', '').strip(), 'campo': campo}


def inventory_filter_args(tipo):
    filtros = inventory_filters(tipo)
    args = {key: value for key, value in filtros.items() if value and (key != 'campo' or value != 'todos')}
    size = inventory_page_size()
    if size != 20:
        args['por_pagina'] = size
    page = request.args.get('pagina', 1, type=int) or 1
    if page > 1:
        args['pagina'] = page
    return args


def inventory_list_url(tipo):
    return url_for(f'estoque_{tipo}_patrimonio', **inventory_filter_args(tipo))


def inventory_page_size():
    size = request.args.get('por_pagina', 20, type=int)
    return size if size in (20, 50, 100) else 20


def inventory_pagination_url(endpoint, page_key, page):
    args = {
        key: request.args[key]
        for key in ('busca', 'campo', 'tipo', 'por_pagina', 'pagina', 'pagina_sem', 'pagina_com')
        if key in request.args
    }
    if page > 1:
        args[page_key] = page
    else:
        args.pop(page_key, None)
    return url_for(endpoint, **args)


def inventory_page(tipo, filtros, page_key='pagina', endpoint=None):
    """Conta os resultados e busca apenas a página solicitada no banco."""
    table = 'ProdutosSemPatrimonio' if tipo == 'sem' else 'ProdutosComPatrimonio'
    conn = get_db_connection()
    try:
        sqlite = is_sqlite_connection(conn)
        placeholder = '?' if sqlite else '%s'
        cursor = conn.cursor()
        cursor.execute(f'SELECT COUNT(*) FROM {table}')
        total = cursor.fetchone()[0]
        where = ''
        params = []
        search = normalize_search(filtros['busca'])
        if search:
            fields = INVENTORY_FILTER_FIELDS[tipo]
            if filtros['campo'] != 'todos' and filtros['campo'] not in fields:
                where = ' WHERE 1 = 0'
            else:
                columns = [fields[filtros['campo']][1]] if filtros['campo'] != 'todos' else [field[1] for field in fields.values()]
                pattern = '%' + search.replace('!', '!!').replace('%', '!%').replace('_', '!_') + '%'
                if sqlite:
                    conn.create_function('NORMALIZE_SEARCH', 1, normalize_search, deterministic=True)
                    expressions = [f'NORMALIZE_SEARCH({column})' for column in columns]
                else:
                    expressions = [
                        f'CONVERT(COALESCE(CAST({column} AS CHAR), \'\') USING utf8mb4) COLLATE utf8mb4_unicode_ci'
                        for column in columns
                    ]
                where = ' WHERE (' + ' OR '.join(f"{expression} LIKE {placeholder} ESCAPE '!'" for expression in expressions) + ')'
                params = [pattern] * len(columns)
        cursor.execute(f'SELECT COUNT(*) FROM {table}{where}', tuple(params))
        matched = cursor.fetchone()[0]
        size = inventory_page_size()
        pages = max(1, (matched + size - 1) // size)
        requested = request.args.get(page_key, 1, type=int) or 1
        page = min(max(1, requested), pages)
        offset = (page - 1) * size
        cursor.close()
        cursor = conn.cursor() if sqlite else conn.cursor(dictionary=True)
        cursor.execute(
            f'SELECT * FROM {table}{where} ORDER BY ProdutoID DESC LIMIT {placeholder} OFFSET {placeholder}',
            (*params, size, offset),
        )
        products = [dict(row) for row in cursor.fetchall()]
        cursor.close()
        endpoint = endpoint or f'estoque_{tipo}_patrimonio'
        pagination = {
            'pagina': page, 'paginas': pages, 'por_pagina': size, 'total': matched,
            'inicio': offset + 1 if matched else 0, 'fim': offset + len(products),
            'anterior': inventory_pagination_url(endpoint, page_key, page - 1) if page > 1 else None,
            'proxima': inventory_pagination_url(endpoint, page_key, page + 1) if page < pages else None,
            'primeira': inventory_pagination_url(endpoint, page_key, 1),
            'ultima': inventory_pagination_url(endpoint, page_key, pages),
        }
        return products, total, pagination
    finally:
        conn.close()


def inventory_totals():
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute('SELECT (SELECT COUNT(*) FROM ProdutosSemPatrimonio), (SELECT COUNT(*) FROM ProdutosComPatrimonio)')
        sem, com = cursor.fetchone()
        cursor.close()
        return sem, com
    finally:
        conn.close()


def inventory_context(tipo):
    campos = INVENTORY_FILTER_FIELDS[tipo]
    filtros = inventory_filters(tipo)
    encontrados, total, pagination = inventory_page(tipo, filtros)
    return {
        f'produtos_{tipo}_patrimonio': encontrados,
        'filtros': filtros,
        'filtros_url': inventory_filter_args(tipo),
        'campos_filtro': {key: field[0] for key, field in campos.items()},
        'rota_estoque': f'estoque_{tipo}_patrimonio',
        'total_itens': total,
        'total_resultados': pagination['total'],
        'paginacao': pagination,
        'por_pagina': pagination['por_pagina'],
    }


def get_db_connection():
    connector = mysql.connector if mysql is not None else None
    return database_manager.connect(connector)


def init_sqlite_database():
    database_manager.initialize_sqlite()


def fetch_user(email, password):
    conn = get_db_connection()
    try:
        if is_sqlite_connection(conn):
            row = conn.execute(
                'SELECT * FROM User WHERE LOWER(email_user) = ?',
                (email.lower(),),
            ).fetchone()
            user = dict(row) if row else None
        else:
            cursor = conn.cursor(dictionary=True)
            cursor.execute('SELECT * FROM User WHERE LOWER(email_user) = %s', (email.lower(),))
            user = cursor.fetchone()
        if user is None:
            return None

        stored_password = user['password_user']
        if stored_password.startswith(('scrypt:', 'pbkdf2:')):
            return user if check_password_hash(stored_password, password) else None
        # Converte a senha de contas antigas após o primeiro login correto.
        if not secrets.compare_digest(stored_password.encode('utf-8'), password.encode('utf-8')):
            return None
        password_hash = generate_password_hash(password)
        if is_sqlite_connection(conn):
            conn.execute('UPDATE User SET password_user = ? WHERE id = ?', (password_hash, user['id']))
        else:
            cursor.execute('UPDATE User SET password_user = %s WHERE id = %s', (password_hash, user['id']))
        conn.commit()
        user['password_user'] = password_hash
        return user
    finally:
        conn.close()


def is_admin_user(user):
    return bool(user and user['role_user'] == 'admin' and user['status_user'] == 'approved')


def get_user(user_id):
    conn = get_db_connection()
    try:
        if is_sqlite_connection(conn):
            row = conn.execute('SELECT * FROM User WHERE id = ?', (user_id,)).fetchone()
            return dict(row) if row else None
        cursor = conn.cursor(dictionary=True)
        cursor.execute('SELECT * FROM User WHERE id = %s', (user_id,))
        return cursor.fetchone()
    finally:
        conn.close()


def current_user():
    if 'current_user' not in g:
        user = get_user(session['user_id']) if session.get('user_id') else None
        if user and (user['status_user'] != 'approved' or user['email_user'] != session.get('user_email')):
            user = None
        if user is None and session.get('user_id'):
            session.clear()
        g.current_user = user
    return g.current_user


def csrf_token():
    if '_csrf_token' not in session:
        session['_csrf_token'] = secrets.token_urlsafe(32)
    return session['_csrf_token']


@app.context_processor
def auth_context():
    return {'current_user': current_user(), 'csrf_token': csrf_token}


@app.before_request
def protect_access():
    if request.endpoint is None or request.endpoint == 'static':
        return None
    public_endpoints = {'index', 'login', 'cadastro', 'logout'}
    admin_endpoints = {
        'contrl', 'control_alias', 'adicionar_usuario_admin', 'remover_usuario',
        'aprovar_usuario', 'alterar_perfil_usuario',
    }
    if request.endpoint not in public_endpoints:
        user = current_user()
        if user is None:
            flash('Faça login com uma conta aprovada para acessar o sistema.')
            return redirect(url_for('login', perfil='admin' if request.endpoint in admin_endpoints else 'user'))
        if request.endpoint in admin_endpoints and not is_admin_user(user):
            abort(403, description='Acesso restrito ao administrador.')
    if request.method == 'POST':
        token = request.form.get('csrf_token', '')
        if not token or not secrets.compare_digest(session.get('_csrf_token', '').encode('utf-8'), token.encode('utf-8')):
            abort(400, description='Formulário expirado ou inválido. Recarregue a página e tente novamente.')
    return None


@app.errorhandler(403)
def acesso_negado(error):
    return render_template('acesso_negado.html', mensagem=error.description), 403


def list_sem_patrimonio():
    conn = get_db_connection()
    try:
        if is_sqlite_connection(conn):
            rows = conn.execute('SELECT * FROM ProdutosSemPatrimonio ORDER BY ProdutoID DESC').fetchall()
            return [dict(row) for row in rows]
        cursor = conn.cursor(dictionary=True)
        cursor.execute('SELECT * FROM ProdutosSemPatrimonio ORDER BY ProdutoID DESC')
        return cursor.fetchall()
    finally:
        conn.close()


def list_com_patrimonio():
    conn = get_db_connection()
    try:
        if is_sqlite_connection(conn):
            rows = conn.execute('SELECT * FROM ProdutosComPatrimonio ORDER BY ProdutoID DESC').fetchall()
            return [dict(row) for row in rows]
        cursor = conn.cursor(dictionary=True)
        cursor.execute('SELECT * FROM ProdutosComPatrimonio ORDER BY ProdutoID DESC')
        return cursor.fetchall()
    finally:
        conn.close()


def get_sem_patrimonio(product_id):
    conn = get_db_connection()
    try:
        if is_sqlite_connection(conn):
            row = conn.execute('SELECT * FROM ProdutosSemPatrimonio WHERE ProdutoID = ?', (product_id,)).fetchone()
            return dict(row) if row else None
        cursor = conn.cursor(dictionary=True)
        cursor.execute('SELECT * FROM ProdutosSemPatrimonio WHERE ProdutoID = %s', (product_id,))
        return cursor.fetchone()
    finally:
        conn.close()


def get_com_patrimonio(product_id):
    conn = get_db_connection()
    try:
        if is_sqlite_connection(conn):
            row = conn.execute('SELECT * FROM ProdutosComPatrimonio WHERE ProdutoID = ?', (product_id,)).fetchone()
            return dict(row) if row else None
        cursor = conn.cursor(dictionary=True)
        cursor.execute('SELECT * FROM ProdutosComPatrimonio WHERE ProdutoID = %s', (product_id,))
        return cursor.fetchone()
    finally:
        conn.close()


def list_users():
    conn = get_db_connection()
    try:
        if is_sqlite_connection(conn):
            rows = conn.execute('SELECT id, name_user, email_user, role_user, status_user FROM User ORDER BY id').fetchall()
            return [dict(row) for row in rows]
        cursor = conn.cursor(dictionary=True)
        cursor.execute('SELECT id, name_user, email_user, role_user, status_user FROM User ORDER BY id')
        return cursor.fetchall()
    finally:
        conn.close()


def create_user(name, email, password, role='user', status='pending'):
    if role not in ('user', 'admin') or status not in ('pending', 'approved'):
        return False
    conn = get_db_connection()
    try:
        email = email.lower()
        cursor = conn.cursor()
        placeholder = '?' if is_sqlite_connection(conn) else '%s'
        cursor.execute(f'SELECT id FROM User WHERE LOWER(email_user) = {placeholder}', (email,))
        if cursor.fetchone():
            return False
        password_hash = generate_password_hash(password)
        if is_sqlite_connection(conn):
            conn.execute(
                'INSERT INTO User (name_user, email_user, password_user, role_user, status_user) VALUES (?, ?, ?, ?, ?)',
                (name, email, password_hash, role, status),
            )
            conn.commit()
            return True
        cursor.execute(
            'INSERT INTO User (name_user, email_user, password_user, role_user, status_user) VALUES (%s, %s, %s, %s, %s)',
            (name, email, password_hash, role, status),
        )
        conn.commit()
        return True
    except Exception:
        conn.rollback()
        app.logger.exception('Erro ao criar solicitação de conta.')
        return False
    finally:
        conn.close()


def update_user_access(user_id, role):
    if role not in ('user', 'admin'):
        return False
    conn = get_db_connection()
    try:
        if is_sqlite_connection(conn):
            conn.execute(
                "UPDATE User SET role_user = ?, status_user = 'approved', updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (role, user_id),
            )
        else:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE User SET role_user = %s, status_user = 'approved', updated_at = CURRENT_TIMESTAMP WHERE id = %s",
                (role, user_id),
            )
        conn.commit()
        return True
    except Exception:
        conn.rollback()
        app.logger.exception('Erro ao atualizar o acesso do usuário.')
        return False
    finally:
        conn.close()


def delete_user(user_id):
    conn = get_db_connection()
    try:
        if is_sqlite_connection(conn):
            conn.execute('DELETE FROM User WHERE id = ?', (user_id,))
        else:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM User WHERE id = %s', (user_id,))
        conn.commit()
        return True
    except Exception:
        return False
    finally:
        conn.close()


def add_sem_patrimonio(descricao, unidade, marca_modelo, total):
    conn = get_db_connection()
    try:
        if is_sqlite_connection(conn):
            conn.execute(
                'INSERT INTO ProdutosSemPatrimonio (DescricaoComercial, Unidade, MarcaModelo, Total) VALUES (?, ?, ?, ?)',
                (descricao, unidade, marca_modelo, int(total or 0)),
            )
        else:
            cursor = conn.cursor()
            cursor.execute(
                'INSERT INTO ProdutosSemPatrimonio (DescricaoComercial, Unidade, MarcaModelo, Total) VALUES (%s, %s, %s, %s)',
                (descricao, unidade, marca_modelo, int(total or 0)),
            )
        conn.commit()
        return True
    except Exception:
        return False
    finally:
        conn.close()


def add_com_patrimonio(responsavel, cargo, local_obra, marca_modelo, serial_numero, sequencial, observacao):
    conn = get_db_connection()
    try:
        if is_sqlite_connection(conn):
            conn.execute(
                'INSERT INTO ProdutosComPatrimonio (Responsavel, Cargo, LocalObra, MarcaModelo, SerialNumero, Sequencial, Observacao) VALUES (?, ?, ?, ?, ?, ?, ?)',
                (responsavel, cargo, local_obra, marca_modelo, serial_numero, int(sequencial or 0), observacao),
            )
        else:
            cursor = conn.cursor()
            cursor.execute(
                'INSERT INTO ProdutosComPatrimonio (Responsavel, Cargo, LocalObra, MarcaModelo, SerialNumero, Sequencial, Observacao) VALUES (%s, %s, %s, %s, %s, %s, %s)',
                (responsavel, cargo, local_obra, marca_modelo, serial_numero, int(sequencial or 0), observacao),
            )
        conn.commit()
        return True
    except Exception:
        return False
    finally:
        conn.close()


def update_sem_patrimonio(product_id, descricao, unidade, marca_modelo, total):
    conn = get_db_connection()
    try:
        values = (descricao, unidade, marca_modelo, total, product_id)
        if is_sqlite_connection(conn):
            conn.execute(
                'UPDATE ProdutosSemPatrimonio SET DescricaoComercial = ?, Unidade = ?, MarcaModelo = ?, Total = ? WHERE ProdutoID = ?',
                values,
            )
        else:
            cursor = conn.cursor()
            cursor.execute(
                'UPDATE ProdutosSemPatrimonio SET DescricaoComercial = %s, Unidade = %s, MarcaModelo = %s, Total = %s WHERE ProdutoID = %s',
                values,
            )
        conn.commit()
        return True
    except Exception:
        conn.rollback()
        app.logger.exception('Erro ao atualizar item sem patrimônio.')
        return False
    finally:
        conn.close()


def update_com_patrimonio(product_id, responsavel, cargo, local_obra, marca_modelo, serial_numero, sequencial, observacao):
    conn = get_db_connection()
    try:
        values = (responsavel, cargo, local_obra, marca_modelo, serial_numero, sequencial, observacao, product_id)
        if is_sqlite_connection(conn):
            conn.execute(
                'UPDATE ProdutosComPatrimonio SET Responsavel = ?, Cargo = ?, LocalObra = ?, MarcaModelo = ?, SerialNumero = ?, Sequencial = ?, Observacao = ? WHERE ProdutoID = ?',
                values,
            )
        else:
            cursor = conn.cursor()
            cursor.execute(
                'UPDATE ProdutosComPatrimonio SET Responsavel = %s, Cargo = %s, LocalObra = %s, MarcaModelo = %s, SerialNumero = %s, Sequencial = %s, Observacao = %s WHERE ProdutoID = %s',
                values,
            )
        conn.commit()
        return True
    except Exception:
        conn.rollback()
        app.logger.exception('Erro ao atualizar item com patrimônio.')
        return False
    finally:
        conn.close()


def delete_sem_patrimonio(product_id):
    conn = get_db_connection()
    try:
        if is_sqlite_connection(conn):
            conn.execute('DELETE FROM ProdutosSemPatrimonio WHERE ProdutoID = ?', (product_id,))
        else:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM ProdutosSemPatrimonio WHERE ProdutoID = %s', (product_id,))
        conn.commit()
        return True
    except Exception:
        return False
    finally:
        conn.close()


def delete_com_patrimonio(product_id):
    conn = get_db_connection()
    try:
        if is_sqlite_connection(conn):
            conn.execute('DELETE FROM ProdutosComPatrimonio WHERE ProdutoID = ?', (product_id,))
        else:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM ProdutosComPatrimonio WHERE ProdutoID = %s', (product_id,))
        conn.commit()
        return True
    except Exception:
        return False
    finally:
        conn.close()


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    perfil = request.form.get('perfil', 'user') if request.method == 'POST' else request.args.get('perfil', 'user')
    if perfil not in ('admin', 'user'):
        abort(400, description='Perfil de acesso inválido.')
    status_code = 200
    email = ''
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        user = fetch_user(email, password)
        session.clear()
        g.current_user = None
        if user is None:
            flash('E-mail ou senha incorretos. Confira seus dados ou solicite uma conta.')
            status_code = 401
        elif user['status_user'] != 'approved':
            flash('Sua solicitação está aguardando aprovação de um administrador.')
            status_code = 403
        elif perfil == 'admin' and not is_admin_user(user):
            flash('Sua conta não tem permissão de administrador. Entre pela área do usuário.')
            status_code = 403
        else:
            session['user_id'] = user.get('id')
            session['user_email'] = user.get('email_user')
            return redirect(url_for('contrl' if perfil == 'admin' else 'estoque'))
    return render_template('login.html', perfil=perfil, email=email), status_code


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))


@app.route('/contrl')
def contrl():
    usuarios = list_users()
    total_sem, total_com = inventory_totals()
    return render_template(
        'contrl.html',
        usuarios=[user for user in usuarios if user['status_user'] == 'approved'],
        pendentes=[user for user in usuarios if user['status_user'] == 'pending'],
        total_usuarios=sum(user['status_user'] == 'approved' for user in usuarios),
        total_pendentes=sum(user['status_user'] == 'pending' for user in usuarios),
        total_sem_patrimonio=total_sem,
        total_com_patrimonio=total_com,
    )


@app.route('/control')
def control_alias():
    return redirect(url_for('contrl'))


@app.route('/estoque_com_patrimonio')
def estoque_com_patrimonio():
    return render_template('estoque_com_patrimonio.html', **inventory_context('com'))


@app.route('/estoque_sem_patrimonio')
def estoque_sem_patrimonio():
    return render_template('estoque_sem_patrimonio.html', **inventory_context('sem'))


@app.route('/estoque')
def estoque():
    filtros = inventory_filters('todos')
    tipo = request.args.get('tipo', 'todos')
    filtros['tipo'] = tipo if tipo in ('todos', 'sem', 'com') else 'todos'
    total_sem, total_com = inventory_totals()
    encontrados_sem, paginacao_sem = [], None
    encontrados_com, paginacao_com = [], None
    if filtros['tipo'] != 'com':
        encontrados_sem, _, paginacao_sem = inventory_page('sem', filtros, 'pagina_sem', 'estoque')
    if filtros['tipo'] != 'sem':
        encontrados_com, _, paginacao_com = inventory_page('com', filtros, 'pagina_com', 'estoque')
    return render_template(
        'estoque.html',
        produtos_sem_patrimonio=encontrados_sem,
        produtos_com_patrimonio=encontrados_com,
        total_sem_patrimonio=total_sem,
        total_com_patrimonio=total_com,
        total_itens=total_sem + total_com,
        total_resultados=(paginacao_sem['total'] if paginacao_sem else 0) + (paginacao_com['total'] if paginacao_com else 0),
        paginacao_sem=paginacao_sem,
        paginacao_com=paginacao_com,
        por_pagina=inventory_page_size(),
        filtros=filtros,
        campos_filtro={key: field[0] for key, field in INVENTORY_FILTER_FIELDS['todos'].items()},
        rota_estoque='estoque',
    )


@app.route('/exportar_excel')
def exportar_excel():
    tipo = request.args.get('tipo', 'todos').lower()
    buffer = BytesIO()
    workbook = Workbook()

    if tipo in ('todos', 'sem', 'com'):
        if tipo in ('todos', 'sem'):
            sheet = workbook.active
            sheet.title = 'SemPatrimonio'
            sheet.append(['ProdutoID', 'DescricaoComercial', 'Unidade', 'MarcaModelo', 'Total'])
            for item in list_sem_patrimonio():
                sheet.append([
                    item.get('ProdutoID'),
                    item.get('DescricaoComercial'),
                    item.get('Unidade'),
                    item.get('MarcaModelo'),
                    item.get('Total'),
                ])

        if tipo in ('todos', 'com'):
            if tipo == 'todos':
                sheet = workbook.create_sheet('ComPatrimonio')
            else:
                sheet = workbook.active
                sheet.title = 'ComPatrimonio'
            sheet.append(['ProdutoID', 'Responsavel', 'Cargo', 'LocalObra', 'MarcaModelo', 'SerialNumero', 'Sequencial', 'Observacao'])
            for item in list_com_patrimonio():
                sheet.append([
                    item.get('ProdutoID'),
                    item.get('Responsavel'),
                    item.get('Cargo'),
                    item.get('LocalObra'),
                    item.get('MarcaModelo'),
                    item.get('SerialNumero'),
                    item.get('Sequencial'),
                    item.get('Observacao'),
                ])

    workbook.save(buffer)
    buffer.seek(0)

    nome = f'estoque_{tipo}.xlsx'
    return send_file(buffer, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', as_attachment=True, download_name=nome)


@app.route('/cadastro', methods=['GET', 'POST'])
def cadastro():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        if not name or not email or '@' not in email or not password.strip():
            flash('Preencha todos os campos corretamente.')
            return redirect(url_for('cadastro'))
        if create_user(name, email, password):
            flash('Solicitação enviada! Aguarde a aprovação de um administrador para entrar.')
            return redirect(url_for('login', perfil='user'))
        flash('Não foi possível enviar a solicitação. Verifique se o e-mail já está cadastrado.')
        return redirect(url_for('cadastro'))
    return render_template('cadastro.html')


@app.route('/adicionar_usuario_admin', methods=['POST'])
def adicionar_usuario_admin():
    name = request.form.get('name', '').strip()
    email = request.form.get('email', '').strip()
    password = request.form.get('password', '')
    role = request.form.get('role', 'user')

    if not name or not email or '@' not in email or not password.strip() or role not in ('user', 'admin'):
        flash('Preencha nome, e-mail, senha e um perfil válido para cadastrar o usuário.')
        return redirect(url_for('contrl'))

    if create_user(name, email, password, role=role, status='approved'):
        flash('Conta criada e aprovada com sucesso!')
    else:
        flash('Não foi possível adicionar o usuário.')
    return redirect(url_for('contrl'))


@app.route('/aprovar_usuario/<int:user_id>', methods=['POST'])
def aprovar_usuario(user_id):
    user = get_user(user_id)
    if user is None:
        abort(404, description='Solicitação não encontrada.')
    role = request.form.get('role', 'user')
    if user['status_user'] != 'pending':
        flash('Essa conta já foi aprovada.')
    elif role not in ('user', 'admin'):
        flash('Selecione um perfil válido para aprovar a conta.')
    elif update_user_access(user_id, role):
        flash('Conta aprovada com sucesso! A pessoa já pode fazer login.')
    else:
        flash('Não foi possível aprovar a conta. Tente novamente.')
    return redirect(url_for('contrl'))


@app.route('/alterar_perfil_usuario/<int:user_id>', methods=['POST'])
def alterar_perfil_usuario(user_id):
    user = get_user(user_id)
    if user is None:
        abort(404, description='Usuário não encontrado.')
    role = request.form.get('role', '')
    if user_id == current_user()['id']:
        flash('Você não pode alterar o próprio perfil. Peça a outro administrador.')
    elif user['status_user'] != 'approved':
        flash('Aprove a solicitação antes de alterar o perfil da conta.')
    elif role not in ('user', 'admin'):
        flash('Selecione um perfil válido.')
    elif update_user_access(user_id, role):
        flash('Perfil atualizado com sucesso!')
    else:
        flash('Não foi possível atualizar o perfil.')
    return redirect(url_for('contrl'))


@app.route('/remover_usuario/<int:user_id>', methods=['POST'])
def remover_usuario(user_id):
    user = get_user(user_id)
    if user is None:
        abort(404, description='Usuário não encontrado.')
    if user_id == current_user()['id']:
        flash('Você não pode excluir a própria conta administrativa.')
    elif delete_user(user_id):
        flash('Solicitação rejeitada.' if user['status_user'] == 'pending' else 'Usuário removido com sucesso!')
    else:
        flash('Não foi possível remover o usuário.')
    return redirect(url_for('contrl'))


@app.route('/adicionar_sem_patrimonio', methods=['POST'])
def adicionar_sem_patrimonio():
    descricao = request.form.get('descricao_comercial', '').strip()
    unidade = request.form.get('unidade', '').strip()
    marca_modelo = request.form.get('marca_modelo', '').strip()
    total = request.form.get('total', '0').strip()

    if not descricao or not unidade or not marca_modelo:
        flash('Preencha os dados obrigatórios do item sem patrimônio.')
        return redirect(inventory_list_url('sem'))

    add_sem_patrimonio(descricao, unidade, marca_modelo, total)
    flash('Item adicionado com sucesso!')
    return redirect(inventory_list_url('sem'))


@app.route('/adicionar_com_patrimonio', methods=['POST'])
def adicionar_com_patrimonio():
    responsavel = request.form.get('responsavel', '').strip()
    cargo = request.form.get('cargo', '').strip()
    local_obra = request.form.get('local_obra', '').strip()
    marca_modelo = request.form.get('marca_modelo', '').strip()
    serial_numero = request.form.get('serial_numero', '').strip()
    sequencial = request.form.get('sequencial', '0').strip()
    observacao = request.form.get('observacao', '').strip()

    if not responsavel or not cargo or not local_obra or not marca_modelo:
        flash('Preencha os dados obrigatórios do item com patrimônio.')
        return redirect(inventory_list_url('com'))

    add_com_patrimonio(responsavel, cargo, local_obra, marca_modelo, serial_numero, sequencial, observacao)
    flash('Item com patrimônio adicionado com sucesso!')
    return redirect(inventory_list_url('com'))


@app.route('/editar_sem_patrimonio/<int:produto_id>', methods=['GET', 'POST'])
def editar_sem_patrimonio(produto_id):
    produto = get_sem_patrimonio(produto_id)
    if produto is None:
        abort(404, description='Item sem patrimônio não encontrado.')

    status_code = 200
    if request.method == 'POST':
        produto.update({
            'DescricaoComercial': request.form.get('descricao_comercial', '').strip(),
            'Unidade': request.form.get('unidade', '').strip(),
            'MarcaModelo': request.form.get('marca_modelo', '').strip(),
            'Total': request.form.get('total', '').strip(),
        })
        errors = []
        if not produto['DescricaoComercial'] or not produto['Unidade'] or not produto['MarcaModelo']:
            errors.append('Preencha os dados obrigatórios do item sem patrimônio.')
        try:
            total = int(produto['Total'])
            if total < 0:
                raise ValueError
        except ValueError:
            errors.append('O total deve ser um número inteiro maior ou igual a zero.')

        status_code = 400
        if not errors:
            if update_sem_patrimonio(produto_id, produto['DescricaoComercial'], produto['Unidade'], produto['MarcaModelo'], total):
                flash('Item sem patrimônio atualizado com sucesso!')
                return redirect(inventory_list_url('sem'))
            errors.append('Não foi possível atualizar o item sem patrimônio. Tente novamente.')
            status_code = 500
        for error in errors:
            flash(error)

    return render_template(
        'estoque_sem_patrimonio.html',
        produto_edicao=produto,
        **inventory_context('sem'),
    ), status_code


@app.route('/editar_com_patrimonio/<int:produto_id>', methods=['GET', 'POST'])
def editar_com_patrimonio(produto_id):
    produto = get_com_patrimonio(produto_id)
    if produto is None:
        abort(404, description='Item com patrimônio não encontrado.')

    status_code = 200
    if request.method == 'POST':
        produto.update({
            'Responsavel': request.form.get('responsavel', '').strip(),
            'Cargo': request.form.get('cargo', '').strip(),
            'LocalObra': request.form.get('local_obra', '').strip(),
            'MarcaModelo': request.form.get('marca_modelo', '').strip(),
            'SerialNumero': request.form.get('serial_numero', '').strip(),
            'Sequencial': request.form.get('sequencial', '').strip(),
            'Observacao': request.form.get('observacao', '').strip(),
        })
        errors = []
        if not produto['Responsavel'] or not produto['Cargo'] or not produto['LocalObra'] or not produto['MarcaModelo']:
            errors.append('Preencha os dados obrigatórios do item com patrimônio.')
        try:
            sequencial = int(produto['Sequencial'] or 0)
            if sequencial < 0:
                raise ValueError
        except ValueError:
            errors.append('O sequencial deve ser um número inteiro maior ou igual a zero.')

        status_code = 400
        if not errors:
            if update_com_patrimonio(
                produto_id, produto['Responsavel'], produto['Cargo'], produto['LocalObra'],
                produto['MarcaModelo'], produto['SerialNumero'], sequencial, produto['Observacao'],
            ):
                flash('Item com patrimônio atualizado com sucesso!')
                return redirect(inventory_list_url('com'))
            errors.append('Não foi possível atualizar o item com patrimônio. Tente novamente.')
            status_code = 500
        for error in errors:
            flash(error)

    return render_template(
        'estoque_com_patrimonio.html',
        produto_edicao=produto,
        **inventory_context('com'),
    ), status_code


@app.route('/remover_sem_patrimonio/<int:produto_id>', methods=['POST'])
def remover_sem_patrimonio(produto_id):
    delete_sem_patrimonio(produto_id)
    flash('Item removido com sucesso!')
    return redirect(inventory_list_url('sem'))


@app.route('/remover_com_patrimonio/<int:produto_id>', methods=['POST'])
def remover_com_patrimonio(produto_id):
    delete_com_patrimonio(produto_id)
    flash('Item removido com sucesso!')
    return redirect(inventory_list_url('com'))


init_sqlite_database()


if __name__ == '__main__':
    app.run(debug=os.environ.get('APP_DEBUG', '').lower() in ('1', 'true'), host='127.0.0.1', port=5000)
