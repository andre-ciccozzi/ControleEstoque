-- Criando e usando o banco de dados
CREATE DATABASE IF NOT EXISTS controlestoque;
USE controlestoque;

-- Criando a tabela User
CREATE TABLE IF NOT EXISTS User(
    id INT AUTO_INCREMENT PRIMARY KEY,
    name_user VARCHAR(90) NOT NULL,
    email_user VARCHAR(90) NOT NULL UNIQUE,
    password_user VARCHAR(100) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

-- Criando a tabela ProdutosSemPatrimonio
CREATE TABLE ProdutosSemPatrimonio (
    ProdutoID INT AUTO_INCREMENT PRIMARY KEY,
    DescricaoComercial TEXT,
    Unidade VARCHAR(50),
    MarcaModelo VARCHAR(100),
    Total INT
);

-- Criando a tabela ProdutosComPatrimonio
CREATE TABLE ProdutosComPatrimonio (
    ProdutoID INT AUTO_INCREMENT PRIMARY KEY,
    Responsavel VARCHAR(100),
    Cargo VARCHAR(100),
    LocalObra VARCHAR(100),
    MarcaModelo VARCHAR(100),
    SerialNumero VARCHAR(100),
    Sequencial INT,
    Observacao TEXT
);

-- Inserindo dados na tabela User
INSERT INTO User (name_user, email_user, password_user) VALUES 
('Alice', 'alice@example.com', 'password123'),
('Bob', 'bob@example.com', 'password456');

-- Inserindo dados na tabela ProdutosSemPatrimonio
INSERT INTO ProdutosSemPatrimonio (DescricaoComercial, Unidade, MarcaModelo, Total) VALUES 
('Caneta Esferográfica Azul', 'Peça', 'BIC Cristal', 500),
('Papel Sulfite A4', 'Pacote', 'Chamex A4', 300),
('Lápis Preto', 'Peça', 'Faber-Castell 2B', 1000);

-- Inserindo dados na tabela ProdutosComPatrimonio
INSERT INTO ProdutosComPatrimonio (Responsavel, Cargo, LocalObra, MarcaModelo, SerialNumero, Sequencial, Observacao) VALUES 
('Carlos', 'Gerente', 'Obra A', 'Dell Inspiron', 'SN123456', 1, 'Notebook para uso na obra A'),
('Diana', 'Engenheira', 'Obra B', 'HP Pavilion', 'SN654321', 2, 'Notebook para uso na obra B');

-- Selecionando todos os dados da tabela User
SELECT * FROM User;

-- Selecionando todos os dados da tabela ProdutosSemPatrimonio
SELECT * FROM ProdutosSemPatrimonio;

-- Selecionando todos os dados da tabela ProdutosComPatrimonio
SELECT * FROM ProdutosComPatrimonio;
