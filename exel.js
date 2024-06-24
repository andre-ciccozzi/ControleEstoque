document.getElementById('import-btn').addEventListener('click', function() {
    var input = document.getElementById('excel-file');

    var file = input.files[0];
    var reader = new FileReader();

    reader.onload = function(e) {
        var data = new Uint8Array(e.target.result);
        var workbook = XLSX.read(data, { type: 'array' });

        var sheetName = workbook.SheetNames[0];
        var sheet = workbook.Sheets[sheetName];

        var excelData = XLSX.utils.sheet_to_json(sheet);

        // Limpar tabela atual
        var tableBody = document.querySelector('#inventory-table tbody');
        tableBody.innerHTML = '';

        // Preencher tabela com os dados do Excel
        excelData.forEach(function(row) {
            var newRow = document.createElement('tr');
            newRow.innerHTML = `
                <td>${row['Nome do Item']}</td>
                <td>${row['Quantidade']}</td>
                <td>${row['Status']}</td>
                <td>
                    <button class="btn-edit">Editar</button>
                    <button class="btn-delete">Excluir</button>
                </td>
            `;
            tableBody.appendChild(newRow);
        });

        // Exibir mensagem de sucesso
        var messageDiv = document.getElementById('message');
        messageDiv.textContent = 'Dados importados com sucesso.';
    };

    reader.readAsArrayBuffer(file);
});
