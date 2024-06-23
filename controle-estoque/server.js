const express = require('express');
const path = require('path');
const { Pool } = require('pg');

const app = express();
const port = process.env.PORT || 3000;

// Configuração do pool de conexão com o PostgreSQL
const pool = new Pool({
    user: 'seu_usuario',
    host: 'localhost',
    database: 'seu_banco_de_dados',
    password: 'sua_senha',
    port: 5432,
});

// Teste da conexão com o banco de dados
pool.query('SELECT NOW()', (err, res) => {
    if (err) {
        console.error('Erro ao conectar ao banco de dados:', err);
    } else {
        console.log('Conexão com o banco de dados estabelecida em:', res.rows[0].now);
    }
});

// Middleware para servir arquivos estáticos
app.use(express.static(path.join(__dirname, 'public')));
app.use(express.urlencoded({ extended: true }));
app.use(express.json());

// Rotas para servir as páginas HTML
app.get('/login', (req, res) => {
    res.sendFile(path.join(__dirname, 'views', 'login.html'));
});

app.get('/cadastro', (req, res) => {
    res.sendFile(path.join(__dirname, 'views', 'cadastro.html'));
});

app.get('/aditens', (req, res) => {
    res.sendFile(path.join(__dirname, 'views', 'aditens.html'));
});

app.get('/vial', (req, res) => {
    res.sendFile(path.join(__dirname, 'views', 'vial.html'));
});

// Rotas CRUD para o estoque
app.post('/api/items', async (req, res) => {
    const { name, quantity, status } = req.body;
    try {
        const result = await pool.query(
            'INSERT INTO items (name, quantity, status) VALUES ($1, $2, $3) RETURNING *',
            [name, quantity, status]
        );
        res.status(201).json(result.rows[0]);
    } catch (err) {
        console.error('Erro ao adicionar item:', err);
        res.status(500).json({ error: 'Erro ao adicionar item' });
    }
});

app.get('/api/items', async (req, res) => {
    try {
        const result = await pool.query('SELECT * FROM items');
        res.status(200).json(result.rows);
    } catch (err) {
        console.error('Erro ao buscar itens:', err);
        res.status(500).json({ error: 'Erro ao buscar itens' });
    }
});

app.put('/api/items/:id', async (req, res) => {
    const { id } = req.params;
    const { name, quantity, status } = req.body;
    try {
        const result = await pool.query(
            'UPDATE items SET name = $1, quantity = $2, status = $3 WHERE id = $4 RETURNING *',
            [name, quantity, status, id]
        );
        res.status(200).json(result.rows[0]);
    } catch (err) {
        console.error('Erro ao atualizar item:', err);
        res.status(500).json({ error: 'Erro ao atualizar item' });
    }
});

app.delete('/api/items/:id', async (req, res) => {
    const { id } = req.params;
    try {
        await pool.query('DELETE FROM items WHERE id = $1', [id]);
        res.status(204).end();
    } catch (err) {
        console.error('Erro ao deletar item:', err);
        res.status(500).json({ error: 'Erro ao deletar item' });
    }
});

// Iniciar o servidor
app.listen(port, () => {
    console.log(`Servidor Node.js rodando em http://localhost:${port}`);
});
