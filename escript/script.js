document.addEventListener('DOMContentLoaded', () => {
    const form = document.getElementById('add-item-form');
    const tableBody = document.querySelector('#inventory-table tbody');
    const messageDiv = document.getElementById('message');

    form.addEventListener('submit', (e) => {
        e.preventDefault();

        const itemName = document.getElementById('item-name').value;
        const itemQuantity = document.getElementById('item-quantity').value;
        const itemStatus = document.getElementById('item-status').value;

        const row = document.createElement('tr');
        row.innerHTML = `
            <td>${itemName}</td>
            <td>${itemQuantity}</td>
            <td>${itemStatus}</td>
            <td><button class="delete-btn">Excluir</button></td>
        `;

        tableBody.appendChild(row);

        form.reset();
        showMessage('Item adicionado com sucesso!', 'success');
    });

    tableBody.addEventListener('click', (e) => {
        if (e.target.classList.contains('delete-btn')) {
            const row = e.target.closest('tr');
            row.remove();
            showMessage('Item removido com sucesso!', 'success');
        }
    });

    function showMessage(message, type) {
        messageDiv.textContent = message;
        messageDiv.className = type;
        setTimeout(() => {
            messageDiv.textContent = '';
            messageDiv.className = '';
        }, 3000);
    }
});
document.addEventListener('DOMContentLoaded', () => {
    const loginForm = document.getElementById('login-form');
    const registerForm = document.getElementById('register-form');
    const addItemForm = document.getElementById('add-item-form');
    const tableBody = document.querySelector('#inventory-table tbody');
    const messageDiv = document.getElementById('message');

    // Login form submission
    if (loginForm) {
        loginForm.addEventListener('submit', (e) => {
            e.preventDefault();
            // Handle login logic
            alert('Login logic not implemented');
        });
    }

    // Register form submission
    if (registerForm) {
        registerForm.addEventListener('submit', (e) => {
            e.preventDefault();
            // Handle register logic
            alert('Register logic not implemented');
        });
    }

    // Add item form submission
    if (addItemForm) {
        addItemForm.addEventListener('submit', (e) => {
            e.preventDefault();

            const itemName = document.getElementById('item-name').value;
            const itemQuantity = document.getElementById('item-quantity').value;
            const itemStatus = document.getElementById('item-status').value;

            const row = document.createElement('tr');
            row.innerHTML = `
                <td>${itemName}</td>
                <td>${itemQuantity}</td>
                <td>${itemStatus}</td>
                <td><button class="delete-btn">Excluir</button></td>
            `;

            tableBody.appendChild(row);
            addItemForm.reset();
            showMessage('Item adicionado com sucesso!', 'success');
        });

        // Delete item
        tableBody.addEventListener('click', (e) => {
            if (e.target.classList.contains('delete-btn')) {
                const row = e.target.closest('tr');
                row.remove();
                showMessage('Item removido com sucesso!', 'success');
            }
        });
    }

    function showMessage(message, type) {
        messageDiv.textContent = message;
        messageDiv.className = type;
        setTimeout(() => {
            messageDiv.textContent = '';
            messageDiv.className = '';
        }, 3000);
    }
});
