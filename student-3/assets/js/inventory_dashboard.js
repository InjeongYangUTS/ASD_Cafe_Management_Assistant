document.addEventListener("DOMContentLoaded", () => {
    const button = document.getElementById("mcp-check-button");
    const status = document.getElementById("mcp-status");
    const tableBody = document.getElementById("mcp-stock-items");

    function showMessage(message) {
        const row = document.createElement("tr");
        const cell = document.createElement("td");

        cell.colSpan = 5;
        cell.className = "empty-message";
        cell.textContent = message;

        row.appendChild(cell);
        tableBody.replaceChildren(row);
    }

    button.addEventListener("click", async () => {
        button.disabled = true;
        status.textContent = "Checking stock...";
        showMessage("Loading...");

        try {
            const response = await fetch(button.dataset.url, {
                headers: {
                    "Accept": "application/json"
                }
            });

            const data = await response.json();

            if (!response.ok || data.success === false) {
                throw new Error(data.error || "Stock check failed.");
            }

            if (!Array.isArray(data.items)) {
                throw new Error("Unexpected stock check result.");
            }

            status.textContent =
                `Stock check complete: ${data.items.length} items found.`;

            if (data.items.length === 0) {
                showMessage("No low-stock or out-of-stock items.");
                return;
            }

            tableBody.replaceChildren();

            data.items.forEach((item) => {
                const row = document.createElement("tr");

                const values = [
                    item.id,
                    item.name,
                    `${item.quantity} ${item.unit}`,
                    `${item.minimum_stock} ${item.unit}`,
                    item.status
                ];

                values.forEach((value) => {
                    const cell = document.createElement("td");
                    cell.textContent = value;
                    row.appendChild(cell);
                });

                tableBody.appendChild(row);
            });

        } catch (error) {
            status.textContent = `Error: ${error.message}`;
            showMessage("Unable to retrieve stock.");

        } finally {
            button.disabled = false;
        }
    });
});