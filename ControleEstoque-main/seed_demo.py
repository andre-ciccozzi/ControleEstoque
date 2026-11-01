"""Carga opcional e repetível de itens de teste, sem alterar contas de acesso."""

import argparse
import json
import sqlite3
from pathlib import Path
from uuid import uuid4


SUPPLIES = [
    ('Caneta Esferográfica Azul', 'Peça', 'BIC Cristal', 500),
    ('Papel Sulfite A4', 'Pacote', 'Chamex A4', 300),
    ('Lápis Preto', 'Peça', 'Faber-Castell 2B', 1000),
    ('Borracha Branca', 'Peça', 'Faber-Castell', 150),
    ('Marcador de Texto Amarelo', 'Peça', 'Pilot Lumi Color', 80),
    ('Fita Adesiva Transparente', 'Rolo', '3M Scotch', 60),
    ('Pasta Arquivo', 'Peça', 'Dello Ofício', 120),
    ('Grampo para Grampeador', 'Caixa', 'Bacchi 26/6', 100),
    ('Caderno Universitário', 'Peça', 'Tilibra 96 Folhas', 90),
    ('Envelope Pardo', 'Pacote', 'Foroni A4', 200),
]

EQUIPMENT = [
    ('Carlos', 'Gerente', 'Obra A', 'Dell Inspiron'),
    ('Diana', 'Engenheira', 'Obra B', 'HP Pavilion'),
    ('Ana Souza', 'Técnica', 'Obra C', 'Lenovo ThinkPad'),
    ('Bruno Lima', 'Analista de Obra', 'Obra D', 'Dell Latitude'),
    ('Eduardo Santos', 'Supervisor', 'Obra E', 'HP ProBook'),
    ('Fernanda Alves', 'Coordenadora', 'Obra A', 'Acer Aspire'),
    ('Gabriela Costa', 'Engenheira', 'Obra B', 'Lenovo IdeaPad'),
    ('Henrique Silva', 'Técnico', 'Obra C', 'Asus VivoBook'),
    ('Isabela Martins', 'Analista de Obra', 'Obra D', 'Samsung Book'),
    ('João Pereira', 'Gerente', 'Obra E', 'Dell Vostro'),
]


def seed_inventory(conn, quantidade=100):
    if not 1 <= quantidade <= 1000:
        raise ValueError('A quantidade deve estar entre 1 e 1000 por categoria.')
    sqlite = conn.__class__.__module__ == 'sqlite3'
    placeholder = '?' if sqlite else '%s'
    cursor = conn.cursor()
    try:
        cursor.execute('SELECT DescricaoComercial FROM ProdutosSemPatrimonio')
        descriptions = {row[0] for row in cursor.fetchall()}
        cursor.execute('SELECT SerialNumero FROM ProdutosComPatrimonio')
        serials = {row[0] for row in cursor.fetchall()}
        cursor.execute('SELECT COALESCE(MAX(Sequencial), 0) FROM ProdutosComPatrimonio')
        sequence = cursor.fetchone()[0]
        supplies = []
        equipment = []
        for index in range(1, quantidade + 1):
            description, unit, model, total = SUPPLIES[(index - 1) % len(SUPPLIES)]
            description = f'{description} - Teste {index:03d}'
            if description not in descriptions:
                supplies.append((description, unit, model, total + ((index - 1) // len(SUPPLIES)) * 10))

            serial = f'SN-TESTE-{index:06d}'
            if serial not in serials:
                responsible, job, location, model = EQUIPMENT[(index - 1) % len(EQUIPMENT)]
                sequence += 1
                equipment.append((
                    responsible, job, location, model, serial, sequence,
                    f'Notebook para uso na {location.lower()}. Registro de teste {index:03d}.',
                ))

        if supplies:
            cursor.executemany(
                'INSERT INTO ProdutosSemPatrimonio (DescricaoComercial, Unidade, MarcaModelo, Total) '
                f'VALUES ({", ".join([placeholder] * 4)})',
                supplies,
            )
        if equipment:
            cursor.executemany(
                'INSERT INTO ProdutosComPatrimonio '
                '(Responsavel, Cargo, LocalObra, MarcaModelo, SerialNumero, Sequencial, Observacao) '
                f'VALUES ({", ".join([placeholder] * 7)})',
                equipment,
            )
        conn.commit()
        return {'sem_patrimonio_adicionados': len(supplies), 'com_patrimonio_adicionados': len(equipment)}
    except Exception:
        conn.rollback()
        raise
    finally:
        cursor.close()


def main():
    parser = argparse.ArgumentParser(description='Adiciona itens de teste nas duas categorias de estoque.')
    parser.add_argument('--quantidade', type=int, default=100, help='Quantidade por categoria (padrão: 100).')
    args = parser.parse_args()
    if not 1 <= args.quantidade <= 1000:
        parser.error('A quantidade deve estar entre 1 e 1000 por categoria.')

    from conect import get_db_connection, is_sqlite_connection

    conn = get_db_connection()
    try:
        result = {'banco': 'SQLite' if is_sqlite_connection(conn) else 'MySQL'}
        if is_sqlite_connection(conn):
            backup_dir = Path(__file__).resolve().parent / 'backups'
            backup_dir.mkdir(exist_ok=True)
            backup_path = backup_dir / f'antes_carga_teste_{uuid4().hex[:12]}.sqlite3'
            backup = sqlite3.connect(backup_path)
            try:
                conn.backup(backup)
            finally:
                backup.close()
            result['backup'] = str(backup_path)
        result.update(seed_inventory(conn, args.quantidade))
        print(json.dumps(result, ensure_ascii=False))
    finally:
        conn.close()


if __name__ == '__main__':
    main()
