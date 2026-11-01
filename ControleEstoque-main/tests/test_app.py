import sqlite3
from unittest.mock import MagicMock

import pytest

def test_login_routes_by_role(client, form_post):
    response = form_post(client,
        "/login",
        data={"email": "alice@example.com", "password": "password123", "perfil": "admin"},
        follow_redirects=False,
    )
    assert response.status_code == 302
    assert response.headers["Location"] == "/contrl"

    response = form_post(client,
        "/login",
        data={"email": "bob@example.com", "password": "password456", "perfil": "user"},
        follow_redirects=False,
    )
    assert response.status_code == 302
    assert response.headers["Location"] == "/estoque"

    response = client.get("/contrl")
    assert response.status_code == 403

    response = client.get("/exportar_excel?tipo=todos")
    assert response.status_code == 200
    assert response.headers["Content-Type"].startswith("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


@pytest.fixture(params=[
    {
        'tipo': 'sem_patrimonio',
        'tabela': 'ProdutosSemPatrimonio',
        'cadastro': {
            'descricao_comercial': 'Caneta de teste',
            'unidade': 'Caixa',
            'marca_modelo': 'Marca original',
            'total': '10',
        },
        'edicao': {
            'descricao_comercial': 'Caneta atualizada',
            'unidade': 'Peça',
            'marca_modelo': 'Marca atualizada',
            'total': '25',
        },
        'esperado': {
            'DescricaoComercial': 'Caneta atualizada',
            'Unidade': 'Peça',
            'MarcaModelo': 'Marca atualizada',
            'Total': 25,
        },
        'campo_obrigatorio': 'descricao_comercial',
        'campo_numerico': 'total',
    },
    {
        'tipo': 'com_patrimonio',
        'tabela': 'ProdutosComPatrimonio',
        'cadastro': {
            'responsavel': 'Responsável original',
            'cargo': 'Técnico',
            'local_obra': 'Obra original',
            'marca_modelo': 'Modelo original',
            'serial_numero': 'SN-TESTE-01',
            'sequencial': '10',
            'observacao': 'Observação original',
        },
        'edicao': {
            'responsavel': 'Responsável atualizado',
            'cargo': 'Engenheiro',
            'local_obra': 'Obra atualizada',
            'marca_modelo': 'Modelo atualizado',
            'serial_numero': 'SN-TESTE-02',
            'sequencial': '25',
            'observacao': 'Observação atualizada',
        },
        'esperado': {
            'Responsavel': 'Responsável atualizado',
            'Cargo': 'Engenheiro',
            'LocalObra': 'Obra atualizada',
            'MarcaModelo': 'Modelo atualizado',
            'SerialNumero': 'SN-TESTE-02',
            'Sequencial': 25,
            'Observacao': 'Observação atualizada',
        },
        'campo_obrigatorio': 'responsavel',
        'campo_numerico': 'sequencial',
    },
], ids=['sem-patrimonio', 'com-patrimonio'])
def product_case(request):
    return request.param


def read_products(app_module, product_case):
    with sqlite3.connect(app_module.DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        return [dict(row) for row in conn.execute(
            f"SELECT * FROM {product_case['tabela']} ORDER BY ProdutoID"
        )]


def test_product_crud(app_module, client, product_case, form_post):
    tipo = product_case['tipo']
    before = read_products(app_module, product_case)

    response = form_post(client, f'/adicionar_{tipo}', data=product_case['cadastro'])
    assert response.status_code == 302
    assert response.headers['Location'] == f'/estoque_{tipo}'
    created = read_products(app_module, product_case)
    assert len(created) == len(before) + 1
    product_id = created[-1]['ProdutoID']

    response = client.get(f'/estoque_{tipo}')
    assert response.status_code == 200
    assert f'/editar_{tipo}/{product_id}' in response.get_data(as_text=True)

    response = client.get(f'/editar_{tipo}/{product_id}')
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert 'Salvar alterações' in html
    assert 'Cancelar' in html
    edit_form = html.split('<form ', 1)[1].split('</form>', 1)[0]
    assert f'action="/editar_{tipo}/{product_id}"' in edit_form
    for value in product_case['cadastro'].values():
        assert value in edit_form
    assert read_products(app_module, product_case) == created

    response = form_post(client, f'/editar_{tipo}/{product_id}', data=product_case['edicao'])
    assert response.status_code == 302
    assert response.headers['Location'] == f'/estoque_{tipo}'
    updated = read_products(app_module, product_case)
    assert updated[:-1] == before
    assert updated[-1] == {'ProdutoID': product_id, **product_case['esperado']}

    response = client.get(f'/estoque_{tipo}')
    assert 'atualizado com sucesso' in response.get_data(as_text=True)
    assert product_case['edicao'][product_case['campo_obrigatorio']] in response.get_data(as_text=True)

    response = form_post(client, f'/remover_{tipo}/{product_id}')
    assert response.status_code == 302
    assert read_products(app_module, product_case) == before


@pytest.mark.parametrize('invalid_value', ['-1', '1.5', 'texto'])
def test_edit_rejects_invalid_numbers(app_module, client, product_case, invalid_value, form_post):
    before = read_products(app_module, product_case)
    product_id = before[0]['ProdutoID']
    data = {**product_case['edicao'], product_case['campo_numerico']: invalid_value}

    response = form_post(client, f"/editar_{product_case['tipo']}/{product_id}", data=data)

    assert response.status_code == 400
    html = response.get_data(as_text=True)
    assert 'número inteiro maior ou igual a zero' in html
    assert product_case['edicao'][product_case['campo_obrigatorio']] in html
    assert read_products(app_module, product_case) == before


def test_edit_requires_mandatory_fields(app_module, client, product_case, form_post):
    before = read_products(app_module, product_case)
    data = {**product_case['edicao'], product_case['campo_obrigatorio']: '   '}

    response = form_post(client, f"/editar_{product_case['tipo']}/{before[0]['ProdutoID']}", data=data)

    assert response.status_code == 400
    assert 'Preencha os dados obrigatórios' in response.get_data(as_text=True)
    assert read_products(app_module, product_case) == before


def test_edit_empty_numeric_field(app_module, client, product_case, form_post):
    before = read_products(app_module, product_case)
    data = {**product_case['edicao'], product_case['campo_numerico']: ''}

    response = form_post(client, f"/editar_{product_case['tipo']}/{before[0]['ProdutoID']}", data=data)

    if product_case['tipo'] == 'sem_patrimonio':
        assert response.status_code == 400
        assert read_products(app_module, product_case) == before
    else:
        assert response.status_code == 302
        assert read_products(app_module, product_case)[0] == {
            'ProdutoID': before[0]['ProdutoID'],
            **product_case['esperado'],
            'Sequencial': 0,
        }


@pytest.mark.parametrize('method', ['GET', 'POST'])
def test_edit_unknown_item_returns_404(app_module, client, product_case, method, form_post):
    before = read_products(app_module, product_case)

    path = f"/editar_{product_case['tipo']}/999999"
    response = form_post(client, path, data=product_case['edicao']) if method == 'POST' else client.get(path)

    assert response.status_code == 404
    assert read_products(app_module, product_case) == before


def test_edit_without_changes_succeeds(app_module, client, product_case, form_post):
    form_post(client, f"/adicionar_{product_case['tipo']}", data=product_case['cadastro'])
    before = read_products(app_module, product_case)

    response = form_post(client,
        f"/editar_{product_case['tipo']}/{before[-1]['ProdutoID']}",
        data=product_case['cadastro'],
    )

    assert response.status_code == 302
    assert read_products(app_module, product_case) == before


def test_edit_database_failure_does_not_report_success(app_module, client, product_case, form_post):
    before = read_products(app_module, product_case)
    with sqlite3.connect(app_module.DB_PATH) as conn:
        conn.execute(f"""
            CREATE TRIGGER reject_update BEFORE UPDATE ON {product_case['tabela']}
            BEGIN SELECT RAISE(ABORT, 'Falha simulada'); END
        """)

    response = form_post(client,
        f"/editar_{product_case['tipo']}/{before[0]['ProdutoID']}",
        data=product_case['edicao'],
    )

    assert response.status_code == 500
    html = response.get_data(as_text=True)
    assert 'Não foi possível atualizar' in html
    assert 'atualizado com sucesso' not in html
    assert product_case['edicao'][product_case['campo_obrigatorio']] in html
    assert read_products(app_module, product_case) == before


@pytest.mark.parametrize('failure', [False, True], ids=['sucesso', 'falha'])
def test_mysql_update_transaction(app_module, monkeypatch, product_case, failure):
    conn = MagicMock()
    cursor = conn.cursor.return_value
    if failure:
        cursor.execute.side_effect = RuntimeError('Falha simulada no MySQL')
    monkeypatch.setattr(app_module, 'get_db_connection', lambda: conn)
    values = tuple(product_case['esperado'].values())

    result = getattr(app_module, f"update_{product_case['tipo']}")(123, *values)

    query, parameters = cursor.execute.call_args.args
    assert query.startswith(f"UPDATE {product_case['tabela']} SET ")
    assert query.endswith('WHERE ProdutoID = %s')
    assert query.count('%s') == len(parameters)
    assert parameters == (*values, 123)
    if failure:
        assert result is False
        conn.rollback.assert_called_once()
        conn.commit.assert_not_called()
    else:
        assert result is True
        conn.commit.assert_called_once()
        conn.rollback.assert_not_called()
    conn.close.assert_called_once()
