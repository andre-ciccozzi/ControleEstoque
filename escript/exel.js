document.getElementById('import-btn').addEventListener('click', function() {
    var input = document.getElementById('excel-file');

    var file = input.files[0];
    var reader = new FileReader();

    reader.onload = function(e) {
        var data = new Uint8Array(e.target.result);
        var workbook = XLSX.read(data, { type: 'array' });

        var sheetName = workbook.SheetNames[0];
        var sheet = workbook.Sheets[sheetName];

        // Converta a planilha para JSON
        var excelData = XLSX.utils.sheet_to_json(sheet, { defval: '' });

        console.log(excelData); // Verificar os dados importados no console

        // Limpar tabela atual
        var tableBody = document.querySelector('#inventory-table tbody');
        tableBody.innerHTML = '';

        // Campos desejados
        var desiredFields = ['responsável', 'Cargo', 'local/obra', 'marca-modelo', 'serial', 'Sequencial', 'observação'];

        // Verificar se há dados e cabeçalhos
        if (excelData.length > 0) {
            // Filtrar os cabeçalhos
            var filteredData = excelData.map(row => {
                var filteredRow = {};
                desiredFields.forEach(field => {
                    filteredRow[field] = row[field];
                });
                return filteredRow;
            });

            // Adicionar cabeçalhos
            var thead = document.querySelector('#inventory-table thead');
            thead.innerHTML = '';
            var headerRow = document.createElement('tr');
            desiredFields.forEach(function(header) {
                var th = document.createElement('th');
                th.textContent = header;
                headerRow.appendChild(th);
            });
            headerRow.innerHTML += '<th>Ações</th>';
            thead.appendChild(headerRow);

            // Preencher tabela com os dados do Excel
            filteredData.forEach(function(row) {
                var newRow = document.createElement('tr');
                desiredFields.forEach(function(field) {
                    var td = document.createElement('td');
                    td.textContent = row[field];
                    newRow.appendChild(td);
                });
                var actionTd = document.createElement('td');
                actionTd.innerHTML = `
                    <button class="btn-edit">Editar</button>
                    <button class="btn-delete">Excluir</button>
                `;
                newRow.appendChild(actionTd);
                tableBody.appendChild(newRow);
            });
        } else {
            console.error('No data found in the Excel sheet.');
        }

        // Exibir mensagem de sucesso
        var messageDiv = document.getElementById('message');
        messageDiv.textContent = 'Dados importados com sucesso.';
    };

    reader.readAsArrayBuffer(file);
});
