document.addEventListener("DOMContentLoaded", function () {
    const orderRows = document.querySelectorAll(".order-row");

    const statusFilter = document.getElementById("status-filter");

    const addModalButton = document.getElementById(
        "open-add-modal-button"
    );

    const editModalButton = document.getElementById(
        "open-edit-modal-button"
    );

    const deleteModalButton = document.getElementById(
        "open-delete-modal-button"
    );

    const addModal = document.getElementById("add-order-modal");
    const editModal = document.getElementById("edit-order-modal");
    const deleteModal = document.getElementById("delete-order-modal");

    let selectedRow = null;


    /* =====================================================
       STATUS FILTER
    ====================================================== */

    if (statusFilter) {
        statusFilter.addEventListener("change", function () {
            statusFilter.closest("form").submit();
        });
    }


    /* =====================================================
       SELECT TABLE ROW
    ====================================================== */

    function selectOrderRow(row) {
        orderRows.forEach(function (currentRow) {
            currentRow.classList.remove("selected");
        });

        row.classList.add("selected");
        selectedRow = row;

        editModalButton.disabled = false;
        deleteModalButton.disabled = false;
    }

    orderRows.forEach(function (row) {
        row.addEventListener("click", function () {
            selectOrderRow(row);
        });

        row.addEventListener("keydown", function (event) {
            if (event.key === "Enter" || event.key === " ") {
                event.preventDefault();
                selectOrderRow(row);
            }
        });
    });


    /* =====================================================
       OPEN AND CLOSE MODALS
    ====================================================== */

    function openModal(modal) {
        if (!modal) {
            return;
        }

        modal.classList.add("open");
        modal.setAttribute("aria-hidden", "false");

        document.body.style.overflow = "hidden";
    }

    function closeModal(modal) {
        if (!modal) {
            return;
        }

        modal.classList.remove("open");
        modal.setAttribute("aria-hidden", "true");

        document.body.style.overflow = "";
    }


    /* =====================================================
       ADD ORDER MODAL
    ====================================================== */

    if (addModalButton) {
        addModalButton.addEventListener("click", function () {
            const addForm = document.getElementById("add-order-form");
            const addDateInput = document.getElementById("add-order-date");

            if (addForm) {
                addForm.reset();
            }

            if (addDateInput) {
                const today = new Date();
                const year = today.getFullYear();
                const month = String(today.getMonth() + 1).padStart(2, "0");
                const day = String(today.getDate()).padStart(2, "0");

                addDateInput.value = `${year}-${month}-${day}`;
            }

            openModal(addModal);
        });
    }


    /* =====================================================
       EDIT ORDER MODAL
    ====================================================== */

    if (editModalButton) {
        editModalButton.addEventListener("click", function () {
            if (!selectedRow) {
                return;
            }

            const orderId = selectedRow.dataset.orderId;
            const supplierId = selectedRow.dataset.supplierId;
            const inventoryId = selectedRow.dataset.inventoryId;
            const quantity = selectedRow.dataset.quantity;
            const orderDate = selectedRow.dataset.orderDate;
            const status = selectedRow.dataset.status;

            document.getElementById("edit-order-id").value = orderId;

            document.getElementById(
                "edit-order-number"
            ).textContent = formatOrderNumber(orderId);

            document.getElementById(
                "edit-supplier-id"
            ).value = supplierId;

            document.getElementById(
                "edit-inventory-id"
            ).value = inventoryId;

            document.getElementById(
                "edit-quantity"
            ).value = quantity;

            document.getElementById(
                "edit-order-date"
            ).value = orderDate;

            document.getElementById(
                "edit-status"
            ).value = status;

            openModal(editModal);
        });
    }


    /* =====================================================
       DELETE ORDER MODAL
    ====================================================== */

    if (deleteModalButton) {
        deleteModalButton.addEventListener("click", function () {
            if (!selectedRow) {
                return;
            }

            const orderId = selectedRow.dataset.orderId;

            document.getElementById(
                "delete-order-id"
            ).value = orderId;

            document.getElementById(
                "delete-order-number"
            ).textContent = formatOrderNumber(orderId);

            openModal(deleteModal);
        });
    }


    /* =====================================================
       CLOSE BUTTONS
    ====================================================== */

    const closeButtons = document.querySelectorAll(
        "[data-close-modal]"
    );

    closeButtons.forEach(function (button) {
        button.addEventListener("click", function () {
            const modalId = button.dataset.closeModal;
            const modal = document.getElementById(modalId);

            closeModal(modal);
        });
    });


    /* =====================================================
       CLICK OUTSIDE MODAL
    ====================================================== */

    const allModals = document.querySelectorAll(".modal");

    allModals.forEach(function (modal) {
        modal.addEventListener("click", function (event) {
            if (event.target === modal) {
                closeModal(modal);
            }
        });
    });


    /* =====================================================
       ESCAPE KEY
    ====================================================== */

    document.addEventListener("keydown", function (event) {
        if (event.key !== "Escape") {
            return;
        }

        allModals.forEach(function (modal) {
            if (modal.classList.contains("open")) {
                closeModal(modal);
            }
        });
    });


    /* =====================================================
       ORDER NUMBER FORMAT
    ====================================================== */

    function formatOrderNumber(orderId) {
        return "RO-" + String(orderId).padStart(4, "0");
    }
});