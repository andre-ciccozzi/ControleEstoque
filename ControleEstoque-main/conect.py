import os
import sqlite3
from io import BytesIO
from time import sleep

from flask import Flask, flash, redirect, render_template, request, send_file, session, url_for
from openpyxl import Workbook

try:
    import mysql.connector
except ImportError:  # pragma: no cover - depende do ambiente
    mysql = None

app = Flask(__name__)
app.secret_key = 'sua_chave_secreta'

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'controlestoque.db')

MYSQL_CONFIG = {
    'user': 'root',
    'password': 'Pamonha2332!',
    'host': 'localhost',
    'database': 'controlestoque',
}


def is_sqlite_connection(conn):
    return conn.__class__.__module__ == 'sqlite3'


def get_db_connection():
    if mysql is not None:
        try:
            conn = mysql.connector.connect(**MYSQL_CONFIG)
            if conn.is_connected():
                return conn
        except Exception:
            pass
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_sqlite_database():
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        '''
        CREATE TABLE IF NOT EXISTS User (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name_user TEXT NOT NULL,
            email_user TEXT NOT NULL UNIQUE,
            password_user TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        '''
    )
    conn.execute(
        '''
        CREATE TABLE IF NOT EXISTS ProdutosSemPatrimonio (
            ProdutoID INTEGER PRIMARY KEY AUTOINCREMENT,
            DescricaoComercial TEXT,
            Unidade TEXT,
            MarcaModelo TEXT,
            Total INTEGER
        )
        '''
    )
    conn.execute(
        '''
        CREATE TABLE IF NOT EXISTS ProdutosComPatrimonio (
            ProdutoID INTEGER PRIMARY KEY AUTOINCREMENT,
            Responsavel TEXT,
            Cargo TEXT,
            LocalObra TEXT,
            MarcaModelo TEXT,
            SerialNumero TEXT,
            Sequencial INTEGER,
            Observacao TEXT
        )
        '''
    )

    user_count = conn.execute('SELECT COUNT(*) FROM User').fetchone()[0]
    if user_count == 0:
        conn.executemany(
            'INSERT INTO User (name_user, email_user, password_user) VALUES (?, ?, ?)',
            [
                ('Alice', 'alice@example.com', 'password123'),
                ('Bob', 'bob@example.com', 'password456'),
            ],
        )

    sem_count = conn.execute('SELECT COUNT(*) FROM ProdutosSemPatrimonio').fetchone()[0]
    if sem_count == 0:
        conn.executemany(
            'INSERT INTO ProdutosSemPatrimonio (DescricaoComercial, Unidade, MarcaModelo, Total) VALUES (?, ?, ?, ?)',
            [
                ('Caneta Esferográfica Azul', 'Peça', 'BIC Cristal', 500),
                ('Papel Sulfite A4', 'Pacote', 'Chamex A4', 300),
                ('Lápis Preto', 'Peça', 'Faber-Castell 2B', 1000),
            ],
        )

    com_count = conn.execute('SELECT COUNT(*) FROM ProdutosComPatrimonio').fetchone()[0]
    if com_count == 0:
        conn.executemany(
            'INSERT INTO ProdutosComPatrimonio (Responsavel, Cargo, LocalObra, MarcaModelo, SerialNumero, Sequencial, Observacao) VALUES (?, ?, ?, ?, ?, ?, ?)',
            [
                ('Carlos', 'Gerente', 'Obra A', 'Dell Inspiron', 'SN123456', 1, 'Notebook para uso na obra A'),
                ('Diana', 'Engenheira', 'Obra B', 'HP Pavilion', 'SN654321', 2, 'Notebook para uso na obra B'),
            ],
        )

    conn.commit()
    conn.close()


def fetch_user(email, password):
    conn = get_db_connection()
    try:
        if is_sqlite_connection(conn):
            row = conn.execute(
                'SELECT * FROM User WHERE email_user = ? AND password_user = ?',
                (email, password),
            ).fetchone()
            return dict(row) if row else None
        cursor = conn.cursor(dictionary=True)
        cursor.execute('SELECT * FROM User WHERE email_user = %s AND password_user = %s', (email, password))
        return cursor.fetchone()
    finally:
        conn.close()


def is_admin_user(user):
    if not user:
        return False
    email = str(user.get('email_user', '') or '').lower()
    name = str(user.get('name_user', '') or '').lower()
    return email == 'alice@example.com' or name == 'alice'


def current_user():
    if not session.get('user_email'):
        return None
    return fetch_user(session.get('user_email'), session.get('user_password', ''))


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


def list_users():
    conn = get_db_connection()
    try:
        if is_sqlite_connection(conn):
            rows = conn.execute('SELECT id, name_user, email_user FROM User ORDER BY id').fetchall()
            return [dict(row) for row in rows]
        cursor = conn.cursor(dictionary=True)
        cursor.execute('SELECT id, name_user, email_user FROM User ORDER BY id')
        return cursor.fetchall()
    finally:
        conn.close()


def create_user(name, email, password):
    conn = get_db_connection()
    try:
        if is_sqlite_connection(conn):
            conn.execute(
                'INSERT INTO User (name_user, email_user, password_user) VALUES (?, ?, ?)',
                (name, email, password),
            )
            conn.commit()
            return True
        cursor = conn.cursor()
        cursor.execute(
            'INSERT INTO User (name_user, email_user, password_user) VALUES (%s, %s, %s)',
            (name, email, password),
        )
        conn.commit()
        return True
    except Exception:
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
    return redirect(url_for('login'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '').strip()
        user = fetch_user(email, password)
        if user:
            session['user_id'] = user.get('id')
            session['user_name'] = user.get('name_user')
            session['user_email'] = user.get('email_user')
            session['user_password'] = user.get('password_user')
            session['user_role'] = 'admin' if is_admin_user(user) else 'user'
            if is_admin_user(user):
                return redirect(url_for('contrl'))
            return redirect(url_for('estoque'))
        flash('Login inválido/inexistente! Tente novamente.')
        sleep(1)
        return redirect(url_for('cadastro'))
    return render_template('login.html')


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


@app.route('/opcontrol')
def opcontrol():
    return render_template('opcontrol.html')


@app.route('/contrl')
def contrl():
    if session.get('user_role') != 'admin':
        flash('Acesso restrito ao administrador.')
        return redirect(url_for('estoque'))

    return render_template(
        'contrl.html',
        usuarios=list_users(),
        total_usuarios=len(list_users()),
        total_sem_patrimonio=len(list_sem_patrimonio()),
        total_com_patrimonio=len(list_com_patrimonio()),
    )


@app.route('/control')
def control_alias():
    return redirect(url_for('contrl'))


@app.route('/estoque_com_patrimonio')
def estoque_com_patrimonio():
    return render_template('estoque_com_patrimonio.html', produtos_com_patrimonio=list_com_patrimonio())


@app.route('/estoque_sem_patrimonio')
def estoque_sem_patrimonio():
    return render_template('estoque_sem_patrimonio.html', produtos_sem_patrimonio=list_sem_patrimonio())


@app.route('/estoque')
def estoque():
    return render_template(
        'estoque.html',
        produtos_sem_patrimonio=list_sem_patrimonio(),
        produtos_com_patrimonio=list_com_patrimonio(),
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
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '').strip()
        if not name or not email or not password:
            flash('Preencha todos os campos corretamente.')
            return redirect(url_for('cadastro'))
        if create_user(name, email, password):
            flash('Usuário cadastrado com sucesso!')
            sleep(1)
            return redirect(url_for('login'))
        flash('Não foi possível cadastrar o usuário. Verifique os dados.')
        return redirect(url_for('cadastro'))
    return render_template('cadastro.html')


@app.route('/adicionar_usuario_admin', methods=['POST'])
def adicionar_usuario_admin():
    name = request.form.get('name', '').strip()
    email = request.form.get('email', '').strip()
    password = request.form.get('password', '').strip()

    if not name or not email or not password:
        flash('Preencha nome, e-mail e senha para cadastrar o usuário.')
        return redirect(url_for('contrl'))

    if create_user(name, email, password):
        flash('Usuário adicionado com sucesso!')
    else:
        flash('Não foi possível adicionar o usuário.')
    return redirect(url_for('contrl'))


@app.route('/remover_usuario/<int:user_id>', methods=['POST'])
def remover_usuario(user_id):
    if delete_user(user_id):
        flash('Usuário removido com sucesso!')
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
        return redirect(url_for('estoque_sem_patrimonio'))

    add_sem_patrimonio(descricao, unidade, marca_modelo, total)
    flash('Item adicionado com sucesso!')
    return redirect(url_for('estoque_sem_patrimonio'))


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
        return redirect(url_for('estoque_com_patrimonio'))

    add_com_patrimonio(responsavel, cargo, local_obra, marca_modelo, serial_numero, sequencial, observacao)
    flash('Item com patrimônio adicionado com sucesso!')
    return redirect(url_for('estoque_com_patrimonio'))


@app.route('/remover_sem_patrimonio/<int:produto_id>', methods=['POST'])
def remover_sem_patrimonio(produto_id):
    delete_sem_patrimonio(produto_id)
    flash('Item removido com sucesso!')
    return redirect(url_for('estoque_sem_patrimonio'))


@app.route('/remover_com_patrimonio/<int:produto_id>', methods=['POST'])
def remover_com_patrimonio(produto_id):
    delete_com_patrimonio(produto_id)
    flash('Item removido com sucesso!')
    return redirect(url_for('estoque_com_patrimonio'))


init_sqlite_database()


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
