import mysql.connector

# Conectar ao banco de dados
cnx = mysql.connector.connect(
    user='root', 
    password='Pamonha2332!',
    host='localhost',
    database='controlestoque'
)

print("Conectado=", cnx.is_connected())
print("Conjunto de caracteres=", cnx.charset)

# Criar um cursor
cursor = cnx.cursor()

# Selecionar e exibir dados da tabela User
cursor.execute("SELECT * FROM User")
print("\nTabela User:")
for (id, name_user, email_user, password_user, created_at, updated_at) in cursor:
    print(f"ID: {id}, Name: {name_user}, Email: {email_user}, Password: {password_user}, Created At: {created_at}, Updated At: {updated_at}")

# Selecionar e exibir dados da tabela ProdutosSemPatrimonio
cursor.execute("SELECT * FROM ProdutosSemPatrimonio")
print("\nTabela ProdutosSemPatrimonio:")
for (ProdutoID, DescricaoComercial, Unidade, MarcaModelo, Total) in cursor:
    print(f"ProdutoID: {ProdutoID}, DescricaoComercial: {DescricaoComercial}, Unidade: {Unidade}, MarcaModelo: {MarcaModelo}, Total: {Total}")

# Selecionar e exibir dados da tabela ProdutosComPatrimonio
cursor.execute("SELECT * FROM ProdutosComPatrimonio")
print("\nTabela ProdutosComPatrimonio:")
for (ProdutoID, Responsavel, Cargo, LocalObra, MarcaModelo, SerialNumero, Sequencial, Observacao) in cursor:
    print(f"ProdutoID: {ProdutoID}, Responsavel: {Responsavel}, Cargo: {Cargo}, LocalObra: {LocalObra}, MarcaModelo: {MarcaModelo}, SerialNumero: {SerialNumero}, Sequencial: {Sequencial}, Observacao: {Observacao}")

# Fechar o cursor e a conexão
cursor.close()
cnx.close()
