// Exemplo básico para manipulação de eventos de edição e exclusão
document.addEventListener('DOMContentLoaded', function() {
    var tableBody = document.querySelector('#inventory-table tbody');

    // Exemplo de manipulação de clique no botão de editar
    tableBody.addEventListener('click', function(event) {
        var target = event.target;
        if (target.classList.contains('btn-edit')) {
            var row = target.closest('tr');
            // Lógica para editar o item da linha selecionada
            // Implemente conforme necessário
            console.log('Editar item:', row.textContent.trim());
        }
    });

    // Exemplo de manipulação de clique no botão de excluir
    tableBody.addEventListener('click', function(event) {
        var target = event.target;
        if (target.classList.contains('btn-delete')) {
            var row = target.closest('tr');
            // Lógica para excluir o item da linha selecionada
            // Implemente conforme necessário
            console.log('Excluir item:', row.textContent.trim());
            row.remove(); // Exemplo: remove a linha da tabela
        }
    });
});
