-- Schema used by database.py. Data is restored from SQLite.
CREATE TABLE IF NOT EXISTS User(
    id INT AUTO_INCREMENT PRIMARY KEY,
    name_user VARCHAR(90) NOT NULL,
    email_user VARCHAR(90) NOT NULL UNIQUE,
    password_user VARCHAR(255) NOT NULL,
    role_user VARCHAR(10) NOT NULL DEFAULT 'user',
    status_user VARCHAR(10) NOT NULL DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Criando a tabela ProdutosSemPatrimonio
CREATE TABLE IF NOT EXISTS ProdutosSemPatrimonio (
    ProdutoID INT AUTO_INCREMENT PRIMARY KEY,
    DescricaoComercial TEXT,
    Unidade VARCHAR(50),
    MarcaModelo VARCHAR(100),
    Total INT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Criando a tabela ProdutosComPatrimonio
CREATE TABLE IF NOT EXISTS ProdutosComPatrimonio (
    ProdutoID INT AUTO_INCREMENT PRIMARY KEY,
    Responsavel VARCHAR(100),
    Cargo VARCHAR(100),
    LocalObra VARCHAR(100),
    MarcaModelo VARCHAR(100),
    SerialNumero VARCHAR(100),
    Sequencial INT,
    Observacao TEXT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
