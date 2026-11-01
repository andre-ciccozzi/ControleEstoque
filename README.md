# ControleEstoque — AGS Solution

Sistema web para gerenciar itens com e sem patrimônio, controlar o acesso de usuários e exportar o estoque para Excel. A aplicação usa Python e Flask, com páginas HTML/Jinja e CSS local. 

O MySQL pode funcionar como banco principal. O SQLite funciona como banco local quando o MySQL não está disponível e como cópia dos dados confirmados no MySQL.

## Funcionalidades

- Tela inicial com escolha entre Administrador e Usuário.
- Login, logout e solicitação de conta com aprovação obrigatória.
- Painel administrativo para aprovar, rejeitar e excluir contas, definir perfis e criar contas já aprovadas.
- CRUD completo dos itens com e sem patrimônio: cadastrar, consultar, editar e excluir.
- Resumo do estoque com as duas categorias na mesma página.
- Filtros gerais e por categoria, por texto, campo e tipo de item.
- Busca por partes do texto, sem diferenciar maiúsculas e acentos.
- Paginação no banco: 20, 50 ou 100 itens por página, mantendo os filtros.
- Downloads separados de itens com patrimônio, sem patrimônio ou estoque completo.
- Criação do banco MySQL ausente e recuperação a partir do SQLite.
- Atualização da cópia SQLite depois das gravações confirmadas no MySQL.
- Carga opcional e repetível de 100 itens de teste em cada categoria.
- Testes de acesso, CRUD, filtros, paginação, exportação e recuperação dos bancos.

## Requisitos

- Python 3.10 ou superior; desenvolvimento e testes também executados no Python 3.14.
- Bibliotecas de `ControleEstoque-main/requirements.txt`.
- MySQL 8 ou compatível, somente se quiser usar esse banco. O servidor precisa estar instalado e iniciado; o projeto cria o banco e as tabelas, não instala o servidor MySQL.

SQLite já acompanha o Python. A interface usa arquivos locais e não depende de CDN para carregar os estilos.

## Como executar

Abra o terminal na raiz do repositório:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r .\ControleEstoque-main\requirements.txt
.\.venv\Scripts\python.exe .\ControleEstoque-main\conect.py
```

Abra **http://127.0.0.1:5000**. Para encerrar, pressione `Ctrl+C` no terminal.

Se `python` abrir a Microsoft Store, use o caminho do interpretador instalado. Por exemplo, para uma instalação Python 3.14 nesse diretório:

```powershell
& "$env:LOCALAPPDATA\Programs\Python\Python314\python.exe" -m venv .venv
```

Depois use os comandos com `.\.venv\Scripts\python.exe` acima. Não é necessário ativar o ambiente virtual no PowerShell.

Para testar apenas com SQLite, antes de iniciar:

```powershell
$env:DATABASE_BACKEND = "sqlite"
.\.venv\Scripts\python.exe .\ControleEstoque-main\conect.py
```

O modo padrão é `auto`: tenta MySQL no primeiro acesso ao banco e usa SQLite se o servidor ou a conexão não estiverem disponíveis. Ao escolher SQLite como alternativa, mantém esse banco durante o processo para evitar alternância entre cópias. Reinicie a aplicação para tentar MySQL novamente.

Em uma instalação nova, o SQLite e as tabelas são criados automaticamente, com estas contas de demonstração já aprovadas:

| Perfil | E-mail | Senha inicial |
| --- | --- | --- |
| Administrador | `alice@example.com` | `password123` |
| Usuário | `bob@example.com` | `password456` |

Também são criados três itens sem patrimônio e dois com patrimônio. Bancos existentes são preservados; esvaziar uma categoria não faz os exemplos reaparecerem na próxima inicialização.

Para uso com contas próprias, crie uma conta administrativa pelo painel, entre com ela e remova as contas de demonstração.

## Configuração do MySQL e da sessão

Copie o exemplo na primeira configuração:

```powershell
Copy-Item .\ControleEstoque-main\config.example.json .\ControleEstoque-main\config.local.json
```

Edite `config.local.json` com o usuário, senha, endereço e nome do banco do seu servidor. Esse arquivo é ignorado pelo Git.

Se você definiu `DATABASE_BACKEND=sqlite` no terminal para testar, volte ao automático com `$env:DATABASE_BACKEND = "auto"` antes de reiniciar usando MySQL.

```json
{
  "database_backend": "auto",
  "sqlite_path": "controlestoque.db",
  "secret_key": "",
  "mysql": {
    "host": "127.0.0.1",
    "port": 3306,
    "user": "root",
    "password": "",
    "database": "controlestoque"
  }
}
```

Para definir uma chave de sessão, gere um valor e coloque-o em `secret_key`:

```powershell
.\.venv\Scripts\python.exe -c "import secrets; print(secrets.token_hex(32))"
```

Sem uma chave configurada, a aplicação gera uma nova a cada inicialização e exige novo login depois de reiniciar.

As variáveis de ambiente têm precedência sobre o JSON:

| Variável | Uso | Padrão |
| --- | --- | --- |
| `DATABASE_BACKEND` | `auto`, `sqlite` ou `mysql` | `auto` |
| `MYSQL_HOST` | Endereço do servidor | `127.0.0.1` |
| `MYSQL_PORT` | Porta | `3306` |
| `MYSQL_USER` | Usuário do servidor | `root` |
| `MYSQL_PASSWORD` | Senha do servidor | Vazia |
| `MYSQL_DATABASE` | Nome do banco | `controlestoque` |
| `CONTROLE_ESTOQUE_DB_PATH` | Caminho do arquivo SQLite | `ControleEstoque-main/controlestoque.db` |
| `SECRET_KEY` | Chave de assinatura da sessão | Gerada em cada inicialização |
| `APP_DEBUG` | `1` ou `true` para recarregar código durante desenvolvimento | Desligado |

Um caminho SQLite relativo no JSON é resolvido a partir de `ControleEstoque-main/`. O nome MySQL aceita letras, números e sublinhado. O usuário MySQL precisa poder criar o banco e as tabelas quando estiverem ausentes, além de consultar e alterar os registros.

O modo `mysql` exige esse servidor e mostra o erro se ele estiver indisponível; use `auto` para permitir a alternativa SQLite.

## Como os bancos e a recuperação funcionam

O sistema preserva os IDs, os campos dos itens, as senhas armazenadas, os perfis, a aprovação das contas e as datas dos cadastros.

| Situação | Comportamento no modo `auto` |
| --- | --- |
| Sem servidor MySQL ou sem conexão | Usa SQLite local; o sistema continua disponível. |
| Servidor disponível, mas banco configurado não existe | Cria o banco e as tabelas e copia os dados do SQLite. |
| MySQL está vazio | Recupera os dados do SQLite. |
| Instalação nova, SQLite contém somente os exemplos iniciais e MySQL já tem dados | Usa o MySQL existente e atualiza a cópia SQLite, salvando antes os exemplos locais. |
| Gravação confirmada no MySQL | Atualiza a cópia SQLite das três tabelas da aplicação em uma transação. |
| Mudanças feitas no SQLite durante uma indisponibilidade | Ao reiniciar, copia essas mudanças para MySQL se a cópia MySQL não mudou desde a última sincronização. |
| Apenas MySQL mudou desde a última sincronização | Salva uma cópia anterior do SQLite e atualiza o banco local. |
| Ambos mudaram, ou dois bancos existentes diferentes nunca foram sincronizados | Preserva ambos e continua em SQLite, informando o conflito no log. A escolha da origem é explícita pelos comandos abaixo. |

A tabela interna `_storage_state` do SQLite guarda a identificação da última sincronização. A cópia inclui usuários e estoque; a carga de 100 registros de teste altera somente itens de estoque.

O modo foi preparado para uma instância da aplicação. Não use cópias independentes do SQLite como se fossem um banco distribuído. Uma falha de cópia após uma gravação MySQL é registrada no log; a operação principal já foi salva. Nesse processo, o sistema bloqueia a troca para uma cópia SQLite que sabe estar desatualizada, até resolver a falha.

### Conferir o banco ativo

```powershell
.\.venv\Scripts\python.exe .\ControleEstoque-main\manage_database.py status
```

O resultado mostra o banco selecionado, o caminho SQLite, as quantidades de registros e o motivo de uma alternativa ou conflito. Esse comando usa a mesma configuração da aplicação e também pode inicializar um banco ausente.

### Criar ou recuperar MySQL usando o SQLite

Com o servidor MySQL iniciado e a configuração preenchida:

```powershell
.\.venv\Scripts\python.exe .\ControleEstoque-main\manage_database.py restore-mysql
```

Se o banco não existir, ele será criado. O script usa `controlestoque.sql` para as tabelas e copia os dados do SQLite, incluindo os IDs e as permissões. Não é necessário importar o SQL manualmente.

Se MySQL já tiver dados diferentes, o comando recusa a substituição. Para escolher explicitamente o SQLite como origem, pare a aplicação e execute:

```powershell
.\.venv\Scripts\python.exe .\ControleEstoque-main\manage_database.py restore-mysql --replace
```

Essa opção salva os registros MySQL anteriores em um JSON privado em `ControleEstoque-main/backups/` antes de substituir os dados das três tabelas. Não remove o servidor nem o banco inteiro. Reinicie a aplicação após a recuperação.

### Escolher MySQL como origem e atualizar SQLite

Pare a aplicação e execute:

```powershell
.\.venv\Scripts\python.exe .\ControleEstoque-main\manage_database.py backup-sqlite
```

O comando salva uma cópia do SQLite atual em `backups/` e o atualiza com os registros MySQL. Um MySQL vazio não pode apagar essa cópia local: nesse caso, o comando orienta usar `restore-mysql`.

Arquivos SQLite, arquivos de recuperação, credenciais locais e cópias JSON não são publicados no GitHub. Guarde uma cópia dos seus dados fora do repositório antes de trocar de computador.

## Telas e como usar

| Tela | Endereço | Acesso | Funcionalidades |
| --- | --- | --- | --- |
| Início | `/` | Público | Escolher Administrador ou Usuário, solicitar conta e acessar a área de uma sessão existente. |
| Login administrativo | `/login?perfil=admin` | Público | Autenticar uma conta administrativa aprovada. Um usuário comum não ganha esse perfil ao escolher a opção. |
| Login de usuário | `/login?perfil=user` | Público | Autenticar conta aprovada para acessar o estoque; administradores também podem usar essa área. |
| Solicitação de conta | `/cadastro` | Público | Enviar nome, e-mail e senha. A conta fica pendente; quem aprova define o perfil. |
| Painel administrativo | `/contrl` | Administrador aprovado | Ver quantidades, aprovar ou rejeitar solicitações, criar contas aprovadas, promover ou rebaixar outras contas e excluir usuários. |
| Estoque completo | `/estoque` | Conta aprovada | Consultar as duas categorias, filtrar por texto/campo/tipo, navegar nas páginas independentes e baixar uma das três planilhas. |
| Sem patrimônio | `/estoque_sem_patrimonio` | Conta aprovada | Cadastrar, listar, filtrar, paginar, editar e excluir itens sem patrimônio. |
| Com patrimônio | `/estoque_com_patrimonio` | Conta aprovada | Cadastrar, listar, filtrar, paginar, editar e excluir equipamentos com patrimônio. |
| Edição de item | `/editar_sem_patrimonio/<id>` ou `/editar_com_patrimonio/<id>` | Conta aprovada | Usar o formulário preenchido, salvar alterações ou cancelar, mantendo a busca e a página. |
| Acesso restrito | Resposta HTTP `403` | Conforme a tentativa | Explicar a restrição e oferecer o retorno ao estoque ou à seleção de acesso. |

`/control` é um redirecionamento compatível com o painel `/contrl`. Os arquivos `_filtros_estoque.html` e `_paginacao_estoque.html` são componentes das telas existentes, sem endereço próprio.

### Aprovação e perfis

1. A pessoa solicita a conta em **Solicitar conta**.
2. Um administrador abre **Solicitações de acesso**, escolhe **Usuário** ou **Administrador** e aprova. Também pode rejeitar.
3. Após a aprovação, a pessoa faz login pela área correspondente.
4. Em **Contas aprovadas**, um administrador pode mudar o perfil de outra pessoa. A mudança é aplicada na próxima requisição, inclusive para sessões já abertas.

O administrador não pode excluir nem alterar o próprio perfil pelo painel. Contas removidas perdem o acesso na próxima requisição. Usuários aprovados gerenciam o estoque; somente administradores gerenciam as contas.

Senhas novas são armazenadas como hash. Senhas antigas são convertidas após um login correto. A sessão não guarda a senha. As rotas verificam aprovação e perfil no banco e os formulários POST têm proteção CSRF.

### Campos do estoque

| Categoria | Campos |
| --- | --- |
| Sem patrimônio | Descrição comercial, unidade, marca/modelo e total. |
| Com patrimônio | Responsável, cargo, local/obra, marca/modelo, serial/número, sequencial e observação. |

Os campos obrigatórios são identificados nos formulários. Na edição, total e sequencial devem ser números inteiros não negativos. Para excluir, confirme a ação solicitada pela tela.

### Busca, paginação e Excel

Em **Filtrar itens**, digite uma palavra ou parte do texto, selecione o campo e clique em **Filtrar**. **Limpar filtros** restaura a lista. No resumo, também é possível selecionar o tipo de item.

Escolha 20, 50 ou 100 itens por página. **Primeira**, **Anterior**, **Próxima** e **Última** mantêm a busca e o tamanho da página. As consultas usam `COUNT`, `LIMIT` e `OFFSET` no banco.

No resumo, os três botões de download ficam juntos:

| Botão | Arquivo | Conteúdo |
| --- | --- | --- |
| Baixar planilha completa | `estoque_todos.xlsx` | Todos os registros, nas abas `SemPatrimonio` e `ComPatrimonio`. |
| Baixar sem patrimônio | `estoque_sem.xlsx` | Todos os itens sem patrimônio. |
| Baixar com patrimônio | `estoque_com.xlsx` | Todos os equipamentos com patrimônio. |

A exportação inclui todos os registros da categoria, independentemente dos filtros e da página exibida.

## Adicionar itens para testar volume

```powershell
.\.venv\Scripts\python.exe .\ControleEstoque-main\seed_demo.py --quantidade 100
```

Acrescenta até 100 itens de teste em cada categoria, sem criar ou alterar contas de usuário ou administrador. Segue os padrões dos exemplos, usando descrições `Teste 001` e seriais `SN-TESTE-000001` para identificação. Preserva os itens anteriores e não duplica os mesmos registros ao executar novamente.

No SQLite, salva uma cópia em `ControleEstoque-main/backups/` antes da carga. Se MySQL estiver ativo, a gravação também atualiza a cópia SQLite pelo gerenciador de banco.

## Estrutura e funções principais

```text
ControleEstoque/
├── .gitignore
├── README.md
└── ControleEstoque-main/
    ├── conect.py                 # Aplicação Flask, autenticação, rotas e regras do estoque
    ├── database.py               # Conexões, esquema SQLite, sincronização e recuperação
    ├── settings.py               # Configuração JSON e variáveis de ambiente
    ├── config.example.json       # Modelo público sem senha de servidor
    ├── controlestoque.sql        # Esquema MySQL usado pelo gerenciador
    ├── manage_database.py        # Comandos status, restore-mysql e backup-sqlite
    ├── seed_demo.py              # Carga opcional de itens de teste
    ├── requirements.txt          # Dependências da aplicação
    ├── requirements-dev.txt      # Dependências dos testes
    ├── templates/                # Telas e componentes Jinja
    ├── static/                   # CSS e imagens efetivamente utilizados
    └── tests/                    # Testes automatizados
```

Arquivos locais criados durante o uso: `controlestoque.db`, `config.local.json` e `backups/`. Eles são ignorados pelo Git.

| Funções ou grupos | Responsabilidade |
| --- | --- |
| `settings.load_settings` | Ler a configuração, aplicar a precedência do ambiente e validar o nome do banco. |
| `DatabaseManager.initialize_sqlite` | Preparar o esquema local, migrar permissões antigas e criar os exemplos apenas em banco novo. |
| `DatabaseManager.connect` / `open_mysql` | Selecionar o banco, conectar ao servidor e criar o MySQL ausente. |
| `DatabaseManager.reconcile` | Comparar os bancos com a última sincronização e recuperar alterações sem sobrescrever conflitos silenciosamente. |
| `MirroredMySQLConnection.commit` / `refresh_backup` | Confirmar a gravação principal e atualizar a cópia SQLite. |
| `restore_mysql` / `backup_sqlite` / `archive_sqlite` | Recuperar o destino escolhido e preservar cópias anteriores. |
| `read_snapshot` / `replace_snapshot` / `snapshot_digest` | Copiar as três tabelas preservando IDs e dados, em transação, e identificar mudanças. |
| `migrate_user_access` | Adicionar perfil/aprovação a esquemas antigos e preservar a conta administrativa inicial. |
| `fetch_user`, `get_user`, `current_user`, `is_admin_user` | Autenticar, consultar contas e verificar o acesso atual. |
| `protect_access`, `csrf_token`, `auth_context` | Proteger rotas e formulários e fornecer os dados da sessão às telas. |
| `create_user`, `list_users`, `update_user_access`, `delete_user` | Criar solicitações/contas, listar, aprovar, definir perfis e excluir usuários. |
| `list_*`, `get_*`, `add_*`, `update_*`, `delete_*` dos itens | Ler, cadastrar, editar e excluir registros de cada categoria com SQL parametrizado. |
| `normalize_search`, `inventory_filters`, `inventory_page`, `inventory_context`, `inventory_totals` | Normalizar buscas, validar filtros e montar listas e contadores com paginação. |
| `inventory_filter_args`, `inventory_list_url`, `inventory_pagination_url` | Preservar filtros e páginas na navegação e nas operações do estoque. |
| `exportar_excel` | Gerar as planilhas em memória e entregá-las como download. |
| `seed_inventory` | Adicionar os itens de teste nas tabelas de estoque, sem duplicar a carga. |

### Ações HTTP

Os formulários usam as rotas abaixo; as ações POST exigem token CSRF.

| Rota | Método | Ação e permissão |
| --- | --- | --- |
| `/login` | GET/POST | Exibir login e autenticar conta aprovada. |
| `/cadastro` | GET/POST | Exibir e enviar solicitação pública. |
| `/logout` | GET | Encerrar a sessão e voltar ao início. |
| `/adicionar_usuario_admin` | POST | Administrador cria conta já aprovada. |
| `/aprovar_usuario/<id>` | POST | Administrador aprova uma solicitação e define o perfil. |
| `/alterar_perfil_usuario/<id>` | POST | Administrador muda o perfil de outra conta aprovada. |
| `/remover_usuario/<id>` | POST | Administrador rejeita solicitação ou exclui outra conta. |
| `/adicionar_sem_patrimonio` | POST | Conta aprovada cadastra item sem patrimônio. |
| `/adicionar_com_patrimonio` | POST | Conta aprovada cadastra equipamento com patrimônio. |
| `/editar_sem_patrimonio/<id>` | GET/POST | Conta aprovada consulta o formulário e salva alterações. |
| `/editar_com_patrimonio/<id>` | GET/POST | Conta aprovada consulta o formulário e salva alterações. |
| `/remover_sem_patrimonio/<id>` | POST | Conta aprovada exclui item sem patrimônio. |
| `/remover_com_patrimonio/<id>` | POST | Conta aprovada exclui equipamento com patrimônio. |
| `/exportar_excel?tipo=todos`, `sem` ou `com` | GET | Conta aprovada baixa a planilha escolhida. |

## Testes

```powershell
.\.venv\Scripts\python.exe -m pip install -r .\ControleEstoque-main\requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest .\ControleEstoque-main\tests -q
```

Os testes usam bancos SQLite temporários. Os caminhos MySQL são verificados com conexões simuladas e um adaptador que executa as transações de cópia em um segundo banco de teste; um servidor MySQL real não é necessário para executar a suíte.

Há cobertura de perfis, aprovação/rejeição, promoção e remoção de contas, proteção de rotas e CSRF, CRUD, filtros com acentos, paginação com carga de 100 itens por categoria, downloads completos, criação de banco, cópia, indisponibilidade, recuperação e conflitos entre bancos. Os dados locais da aplicação não são usados nos testes.



O `.gitignore` exclui bancos locais, arquivos de recuperação, `config.local.json`, `.env`, ambientes virtuais, caches, logs e configurações locais do editor. Publique `config.example.json`, preenchendo as credenciais somente na sua cópia local.

A versão Node/PostgreSQL, os JavaScripts antigos, páginas não utilizadas, estilos sem referência e o script antigo de conexão foram removidos. O ponto de entrada da aplicação é **`ControleEstoque-main/conect.py`**.
