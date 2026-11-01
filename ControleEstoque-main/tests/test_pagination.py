import importlib.util
import re
from html import unescape
from io import BytesIO
from pathlib import Path
from urllib.parse import parse_qs, urlsplit
from unittest.mock import MagicMock

import pytest
from openpyxl import load_workbook


@pytest.fixture
def demo_inventory(app_module):
    path = Path(app_module.__file__).with_name('seed_demo.py')
    spec = importlib.util.spec_from_file_location('seed_demo_test', path)
    seed_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(seed_module)
    conn = app_module.get_db_connection()
    try:
        users_before = [tuple(row) for row in conn.execute('SELECT * FROM User ORDER BY id')]
        original_sem = app_module.list_sem_patrimonio()
        original_com = app_module.list_com_patrimonio()
        result = seed_module.seed_inventory(conn)
        assert result == {'sem_patrimonio_adicionados': 100, 'com_patrimonio_adicionados': 100}
        assert [tuple(row) for row in conn.execute('SELECT * FROM User ORDER BY id')] == users_before
    finally:
        conn.close()
    return seed_module, original_sem, original_com


def stock_rows(response, table_id='inventory-table'):
    html = response.get_data(as_text=True)
    match = re.search(rf'<table id="{table_id}">(.*?)</table>', html, re.DOTALL)
    if not match:
        return []
    body = re.search(r'<tbody>(.*?)</tbody>', match.group(1), re.DOTALL).group(1)
    return [row for row in re.findall(r'<tr>(.*?)</tr>', body, re.DOTALL) if 'colspan=' not in row]


def next_urls(response):
    return [unescape(path) for path in re.findall(r'href="([^"]+)" rel="next"', response.get_data(as_text=True))]


def test_demo_load_is_repeatable_and_preserves_existing_items(app_module, demo_inventory):
    seed, original_sem, original_com = demo_inventory
    sem = app_module.list_sem_patrimonio()
    com = app_module.list_com_patrimonio()
    assert len(sem) == len(original_sem) + 100
    assert len(com) == len(original_com) + 100
    assert sem[-len(original_sem):] == original_sem
    assert com[-len(original_com):] == original_com
    assert len({item['SerialNumero'] for item in com}) == len(com)
    conn = app_module.get_db_connection()
    try:
        assert seed.seed_inventory(conn) == {'sem_patrimonio_adicionados': 0, 'com_patrimonio_adicionados': 0}
    finally:
        conn.close()
    assert app_module.list_sem_patrimonio() == sem
    assert app_module.list_com_patrimonio() == com


@pytest.mark.parametrize('tipo,total', [('sem', 103), ('com', 102)])
def test_lists_limit_rows_and_handle_invalid_pages(client, demo_inventory, tipo, total):
    path = f'/estoque_{tipo}_patrimonio'
    first = client.get(path)
    assert len(stock_rows(first)) == 20
    assert 'Página 1 de 6' in first.get_data(as_text=True)
    second = client.get(next_urls(first)[0])
    assert len(stock_rows(second)) == 20
    assert set(stock_rows(first)).isdisjoint(stock_rows(second))
    for size, expected in [(50, 50), (100, 100), (99999, 20), (-1, 20), ('texto', 20)]:
        response = client.get(path, query_string={'por_pagina': size})
        assert len(stock_rows(response)) == expected
    for page in [0, -5, 'texto']:
        response = client.get(path, query_string={'pagina': page})
        assert 'Página 1 de 6' in response.get_data(as_text=True)
    last = client.get(path, query_string={'pagina': 99999})
    assert len(stock_rows(last)) == total - 100
    assert 'Página 6 de 6' in last.get_data(as_text=True)
    empty = client.get(path, query_string={'busca': 'produto inexistente', 'pagina': 99999})
    assert len(stock_rows(empty)) == 0
    assert 'Exibindo 0 a 0 de 0 itens.' in empty.get_data(as_text=True)


@pytest.mark.parametrize('tipo,campo', [('sem', 'descricao_comercial'), ('com', 'observacao')])
def test_pagination_preserves_search_and_size(client, demo_inventory, tipo, campo):
    response = client.get(f'/estoque_{tipo}_patrimonio', query_string={
        'busca': 'teste', 'campo': campo, 'por_pagina': 50,
    })
    assert len(stock_rows(response)) == 50
    assert '100 de ' in response.get_data(as_text=True)
    url = next_urls(response)[0]
    assert parse_qs(urlsplit(url).query) == {
        'busca': ['teste'], 'campo': [campo], 'por_pagina': ['50'], 'pagina': ['2'],
    }
    assert len(stock_rows(client.get(url))) == 50


def test_summary_has_independent_pagination_and_three_downloads(client, demo_inventory):
    response = client.get('/estoque?pagina_sem=2&pagina_com=3')
    html = response.get_data(as_text=True)
    assert len(stock_rows(response, 'stock-sem-table')) == 20
    assert len(stock_rows(response, 'stock-com-table')) == 20
    assert 'Baixar planilha completa' in html
    assert 'Baixar sem patrimônio' in html
    assert 'Baixar com patrimônio' in html
    assert 'independentemente dos filtros ou da página exibida' in html
    urls = next_urls(response)
    assert len(urls) == 2
    assert parse_qs(urlsplit(urls[0]).query) == {'pagina_sem': ['3'], 'pagina_com': ['3']}
    assert parse_qs(urlsplit(urls[1]).query) == {'pagina_sem': ['2'], 'pagina_com': ['4']}


@pytest.mark.parametrize('tipo,sheets', [
    ('todos', {'SemPatrimonio': 104, 'ComPatrimonio': 103}),
    ('sem', {'SemPatrimonio': 104}),
    ('com', {'ComPatrimonio': 103}),
])
def test_exports_include_every_page_and_are_not_filtered(client, demo_inventory, tipo, sheets):
    summary = client.get('/estoque?busca=Dell&tipo=com&por_pagina=20&pagina_com=2')
    assert f'/exportar_excel?tipo={tipo}' in summary.get_data(as_text=True)
    response = client.get(f'/exportar_excel?tipo={tipo}&pagina=2&por_pagina=20&busca=Dell')
    assert response.status_code == 200
    workbook = load_workbook(BytesIO(response.data), read_only=True)
    try:
        assert workbook.sheetnames == list(sheets)
        for name, rows in sheets.items():
            assert workbook[name].max_row == rows
    finally:
        workbook.close()


def test_database_limits_queries_instead_of_loading_entire_stock(app_module, client, demo_inventory, monkeypatch):
    queries = []
    original = app_module.get_db_connection

    def traced_connection():
        conn = original()
        conn.set_trace_callback(queries.append)
        return conn

    monkeypatch.setattr(app_module, 'get_db_connection', traced_connection)
    assert client.get('/estoque?busca=teste&pagina_sem=2&pagina_com=2').status_code == 200
    reads = [query for query in queries if query.startswith('SELECT * FROM Produtos')]
    assert len(reads) == 2
    assert all('LIMIT 20 OFFSET 20' in query for query in reads)


@pytest.mark.parametrize('tipo,campo,data', [
    ('sem', 'descricao_comercial', {
        'descricao_comercial': 'Caneta de teste editada', 'unidade': 'Peça',
        'marca_modelo': 'BIC Cristal', 'total': '25',
    }),
    ('com', 'observacao', {
        'responsavel': 'Carlos', 'cargo': 'Gerente', 'local_obra': 'Obra A',
        'marca_modelo': 'Dell Inspiron', 'serial_numero': 'SN-EDITADO',
        'sequencial': '200', 'observacao': 'Notebook de teste editado',
    }),
])
def test_edit_preserves_page_search_and_size(client, form_post, demo_inventory, tipo, campo, data):
    response = client.get(f'/estoque_{tipo}_patrimonio', query_string={
        'busca': 'teste', 'campo': campo, 'por_pagina': 50, 'pagina': 2,
    })
    html = unescape(response.get_data(as_text=True))
    edit_url = re.search(r'href="(/editar_[^\"]+)"', html).group(1)
    expected = {'busca': ['teste'], 'campo': [campo], 'por_pagina': ['50'], 'pagina': ['2']}
    assert parse_qs(urlsplit(edit_url).query) == expected
    edit_page = client.get(edit_url)
    assert 'Página 2 de 2' in edit_page.get_data(as_text=True)
    response = form_post(client, edit_url, data=data)
    assert response.status_code == 302
    assert parse_qs(urlsplit(response.headers['Location']).query) == expected
    assert 'Página 2 de 2' in client.get(response.headers['Location']).get_data(as_text=True)


def test_delete_last_page_adjusts_to_available_page(app_module, client, form_post, demo_inventory):
    path = '/estoque_sem_patrimonio?pagina=2&por_pagina=100'
    last_items = app_module.list_sem_patrimonio()[100:]
    assert len(last_items) == 3
    for item in last_items:
        response = form_post(client, f"/remover_sem_patrimonio/{item['ProdutoID']}?pagina=2&por_pagina=100")
        assert response.status_code == 302
        assert parse_qs(urlsplit(response.headers['Location']).query) == {'pagina': ['2'], 'por_pagina': ['100']}
    response = client.get(path)
    assert 'Página 1 de 1' in response.get_data(as_text=True)
    assert len(stock_rows(response)) == 100


def test_mysql_pagination_uses_parameters_and_limits(app_module, monkeypatch):
    conn = MagicMock()
    counter = MagicMock()
    counter.fetchone.side_effect = [(103,), (100,)]
    reader = MagicMock()
    reader.fetchall.return_value = [{'ProdutoID': 1, 'Total': 50}]
    conn.cursor.side_effect = [counter, reader]
    monkeypatch.setattr(app_module, 'get_db_connection', lambda: conn)
    with app_module.app.test_request_context('/estoque_sem_patrimonio?por_pagina=50&pagina=2'):
        _, total, page = app_module.inventory_page('sem', {'busca': '50%_', 'campo': 'marca_modelo'})
    query, params = reader.execute.call_args.args
    assert 'COLLATE utf8mb4_unicode_ci' in query
    assert "LIKE %s ESCAPE '!'" in query
    assert query.endswith('LIMIT %s OFFSET %s')
    assert params == ('%50!%!_%', 50, 50)
    assert total == 103 and page['total'] == 100
    conn.close.assert_called_once()
