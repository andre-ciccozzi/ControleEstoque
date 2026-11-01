import re
from html import unescape
from io import BytesIO
from urllib.parse import parse_qs, urlencode, urlsplit

import pytest
from openpyxl import load_workbook


def table_html(response, table_id='inventory-table'):
    match = re.search(
        rf'<table id="{re.escape(table_id)}">(.*?)</table>',
        response.get_data(as_text=True), re.DOTALL,
    )
    return unescape(match.group(1)) if match else ''


def product_ids(response):
    return [int(value) for value in re.findall(
        r'href="/editar_(?:sem|com)_patrimonio/(\d+)(?:\?[^\"]*)?"',
        table_html(response),
    )]


@pytest.mark.parametrize('tipo,cases', [
    ('sem', [
        ({}, [3, 2, 1]),
        ({'busca': '  LAPIS  '}, [3]),
        ({'busca': 'PECA', 'campo': 'unidade'}, [3, 1]),
        ({'busca': 'caneta', 'campo': 'descricao_comercial'}, [1]),
        ({'busca': 'faber', 'campo': 'marca_modelo'}, [3]),
        ({'busca': '500', 'campo': 'total'}, [1]),
        ({'busca': 'caneta', 'campo': 'marca_modelo'}, []),
        ({'busca': 'caneta', 'campo': 'campo_invalido'}, [1]),
    ]),
    ('com', [
        ({}, [2, 1]),
        ({'busca': 'CARLOS', 'campo': 'responsavel'}, [1]),
        ({'busca': 'gerente', 'campo': 'cargo'}, [1]),
        ({'busca': 'obra b', 'campo': 'local_obra'}, [2]),
        ({'busca': 'inspiron', 'campo': 'marca_modelo'}, [1]),
        ({'busca': 'sn654', 'campo': 'serial_numero'}, [2]),
        ({'busca': '2', 'campo': 'sequencial'}, [2]),
        ({'busca': 'para uso na obra a', 'campo': 'observacao'}, [1]),
        ({'busca': 'Dell', 'campo': 'responsavel'}, []),
        ({'busca': 'Dell', 'campo': 'campo_invalido'}, [1]),
    ]),
])
def test_separate_stock_filters(client, tipo, cases):
    for filters, expected in cases:
        response = client.get(f'/estoque_{tipo}_patrimonio', query_string=filters)
        assert response.status_code == 200
        assert product_ids(response) == expected, filters
        if not expected:
            assert 'Nenhum item encontrado para os filtros informados.' in table_html(response)


def test_search_handles_accents_numbers_and_literal_characters(app_module, client):
    app_module.add_com_patrimonio('João', 'Técnico', 'São José', 'Equipamento 50%', '', 0, '')
    for filters in [
        {'busca': 'JOAO'}, {'busca': 'tecnico'}, {'busca': 'sao jose'},
        {'busca': '%'}, {'busca': '0', 'campo': 'sequencial'},
    ]:
        response = client.get('/estoque_com_patrimonio', query_string=filters)
        assert product_ids(response) == [3], filters
    for term in ['_', "' OR 1=1 --", 'todos']:
        response = client.get('/estoque_com_patrimonio', query_string={'busca': term})
        assert product_ids(response) == []


@pytest.mark.parametrize('tipo,data,term', [
    ('sem', {
        'descricao_comercial': 'Caneta editada', 'unidade': 'Caixa',
        'marca_modelo': 'BIC Cristal', 'total': '25',
    }, 'BIC'),
    ('com', {
        'responsavel': 'Responsável atualizado', 'cargo': 'Técnico',
        'local_obra': 'Obra nova', 'marca_modelo': 'Dell Inspiron',
        'serial_numero': 'SN-EDITADO', 'sequencial': '15', 'observacao': 'Observação editada',
    }, 'Dell'),
])
def test_filters_are_preserved_during_crud(client, form_post, tipo, data, term):
    filters = {'busca': term, 'campo': 'marca_modelo'}
    query = urlencode(filters)
    list_path = f'/estoque_{tipo}_patrimonio'
    edit_path = f'/editar_{tipo}_patrimonio/1'

    response = client.get(list_path, query_string=filters)
    assert product_ids(response) == [1]
    assert f'href="{edit_path}?{query}"' in table_html(response)

    response = client.get(f'{edit_path}?{query}')
    html = unescape(response.get_data(as_text=True))
    assert f'action="{edit_path}?{query}"' in html
    assert f'href="{list_path}?{query}" class="btn-cancel">Cancelar' in html
    assert f'value="{term}"' in html

    response = form_post(client, f'{edit_path}?{query}', data=data)
    assert response.status_code == 302
    assert parse_qs(urlsplit(response.headers['Location']).query) == {'busca': [term], 'campo': ['marca_modelo']}
    assert product_ids(client.get(response.headers['Location'])) == [1]

    response = form_post(client, f'/adicionar_{tipo}_patrimonio?{query}', data=data)
    assert response.status_code == 302
    assert parse_qs(urlsplit(response.headers['Location']).query) == {'busca': [term], 'campo': ['marca_modelo']}
    assert len(product_ids(client.get(response.headers['Location']))) == 2

    response = form_post(client, f'/remover_{tipo}_patrimonio/1?{query}')
    assert response.status_code == 302
    assert parse_qs(urlsplit(response.headers['Location']).query) == {'busca': [term], 'campo': ['marca_modelo']}
    assert len(product_ids(client.get(response.headers['Location']))) == 1
    assert len(product_ids(client.get(list_path))) > 1


def test_complete_stock_shows_both_types_and_filter_in_same_page(client):
    response = client.get('/estoque')
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert 'Caneta Esferográfica Azul' in table_html(response, 'stock-sem-table')
    assert 'Carlos' in table_html(response, 'stock-com-table')
    assert '5 de 5 itens encontrados.' in html
    assert '<form action="/estoque" method="GET"' in html
    assert 'name="tipo"' in html
    assert 'Baixar planilha completa' in html
    assert client.get('/_filtros_estoque').status_code == 404


def test_complete_stock_combines_search_field_and_type(client):
    cases = [
        ({'busca': 'notebook'}, [], ['Carlos', 'Diana']),
        ({'busca': 'PECA', 'campo': 'unidade'}, ['Caneta', 'Lápis'], []),
        ({'busca': 'hp', 'campo': 'marca_modelo'}, [], ['Diana']),
        ({'busca': 'caneta', 'campo': 'responsavel'}, [], []),
        ({'tipo': 'sem'}, ['Caneta', 'Papel', 'Lápis'], []),
        ({'tipo': 'com'}, [], ['Carlos', 'Diana']),
        ({'tipo': 'sem', 'busca': 'HP'}, [], []),
        ({'tipo': 'invalido', 'campo': 'invalido'}, ['Caneta', 'Papel', 'Lápis'], ['Carlos', 'Diana']),
        ({'busca': '   '}, ['Caneta', 'Papel', 'Lápis'], ['Carlos', 'Diana']),
    ]
    for filters, expected_sem, expected_com in cases:
        response = client.get('/estoque', query_string=filters)
        assert response.status_code == 200
        sem = table_html(response, 'stock-sem-table')
        com = table_html(response, 'stock-com-table')
        for name in ['Caneta', 'Papel', 'Lápis']:
            assert (name in sem) == (name in expected_sem), filters
        for name in ['Carlos', 'Diana']:
            assert (name in com) == (name in expected_com), filters
        assert f'{len(expected_sem) + len(expected_com)} de 5 ' in response.get_data(as_text=True)


def test_complete_export_includes_all_items_despite_screen_filters(client):
    response = client.get('/estoque?busca=Dell&campo=marca_modelo&tipo=com')
    html = response.get_data(as_text=True)
    export_path = unescape(re.search(r'class="btn-secondary" href="([^"]+)"', html).group(1))
    assert parse_qs(urlsplit(export_path).query) == {'tipo': ['todos']}

    response = client.get(export_path)
    assert response.status_code == 200
    workbook = load_workbook(BytesIO(response.data), read_only=True)
    try:
        assert workbook.sheetnames == ['SemPatrimonio', 'ComPatrimonio']
        assert workbook['SemPatrimonio'].max_row == 4
        assert workbook['ComPatrimonio'].max_row == 3
        assert {row[1] for row in workbook['SemPatrimonio'].iter_rows(min_row=2, values_only=True)} == {
            'Caneta Esferográfica Azul', 'Papel Sulfite A4', 'Lápis Preto',
        }
        assert {row[1] for row in workbook['ComPatrimonio'].iter_rows(min_row=2, values_only=True)} == {'Carlos', 'Diana'}
    finally:
        workbook.close()
