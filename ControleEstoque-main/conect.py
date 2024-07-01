from flask import Flask, render_template, request, redirect, url_for, flash
import mysql.connector
from time import sleep

app = Flask(__name__)
app.secret_key = 'sua_chave_secreta'

# Configurações do banco de dados
db_config = {
    'user': 'root',
    'password': 'Pamonha2332!',
    'host': 'localhost',
    'database': 'controlestoque'
}

def get_db_connection():
    return mysql.connector.connect(**db_config)

@app.route('/')
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        cnx = get_db_connection()
        cursor = cnx.cursor(dictionary=True)
        cursor.execute("SELECT * FROM User WHERE email_user = %s AND password_user = %s", (email, password))
        user = cursor.fetchone()
        cursor.close()
        cnx.close()
        if user:
            return redirect(url_for('opcontrol'))
        else:
            flash('Login inválido/inexistente! Tente novamente')
            sleep(1)
            return redirect(url_for('cadastro'))
    return render_template('login.html')

@app.route('/opcontrol')
def opcontrol():
    return render_template('opcontrol.html')

@app.route('/estoque_com_patrimonio')
def estoque_com_patrimonio():
    return render_template('estoque_com_patrimonio.html')

@app.route('/estoque_sem_patrimonio')
def estoque_sem_patrimonio():
    cnx = get_db_connection()
    cursor = cnx.cursor(dictionary=True)
    cursor.execute("SELECT * FROM ProdutosSemPatrimonio")
    produtos_sem_patrimonio = cursor.fetchall()
    cursor.close()
    cnx.close()
    return render_template('estoque_sem_patrimonio.html', produtos_sem_patrimonio=produtos_sem_patrimonio)

@app.route('/estoque')
def estoque():
    cnx = get_db_connection()
    cursor = cnx.cursor(dictionary=True)
    cursor.execute("SELECT * FROM ProdutosSemPatrimonio")
    produtos_sem_patrimonio = cursor.fetchall()
    cursor.execute("SELECT * FROM ProdutosComPatrimonio")
    produtos_com_patrimonio = cursor.fetchall()
    cursor.close()
    cnx.close()
    return render_template('estoque.html', produtos_sem_patrimonio=produtos_sem_patrimonio, produtos_com_patrimonio=produtos_com_patrimonio)

@app.route('/cadastro', methods=['GET', 'POST'])
def cadastro():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = request.form['password']
        cnx = get_db_connection()
        cursor = cnx.cursor()
        cursor.execute("INSERT INTO User (name_user, email_user, password_user) VALUES (%s, %s, %s)", (name, email, password))
        cnx.commit()
        cursor.close()
        cnx.close()
        flash('Usuário cadastrado com sucesso!')
        sleep(2)
        return redirect(url_for('login'))
    return render_template('cadastro.html')

if __name__ == '__main__':
    app.run(debug=True)
