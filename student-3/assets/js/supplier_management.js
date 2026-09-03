

/* ========================================
    SUPPLIER ROW SELECTION
======================================== */

const supplierRows = document.querySelectorAll(
    "#supplier-table-body tr"
);

let selectedSupplierRow = null;


supplierRows.forEach(row => {

    row.addEventListener("click", function () {

        supplierRows.forEach(otherRow => {
            otherRow.classList.remove("selected");
        });

        this.classList.add("selected");

        selectedSupplierRow = this;

    });

});

const addSupplierModal =
    document.getElementById("add-supplier-modal");

const openAddSupplierButton =
    document.getElementById("open-add-supplier-modal");

const closeAddSupplierButton =
    document.getElementById("close-add-supplier-modal");

const cancelAddSupplierButton =
    document.getElementById("cancel-add-supplier");


function openAddSupplierModal() {
    addSupplierModal.classList.add("is-open");
    addSupplierModal.setAttribute("aria-hidden", "false");
    document.body.classList.add("modal-open");

    document.getElementById("supplier-name").focus();
}


function closeAddSupplierModal() {
    addSupplierModal.classList.remove("is-open");
    addSupplierModal.setAttribute("aria-hidden", "true");
    document.body.classList.remove("modal-open");
}


openAddSupplierButton.addEventListener(
    "click",
    openAddSupplierModal
);

closeAddSupplierButton.addEventListener(
    "click",
    closeAddSupplierModal
);

cancelAddSupplierButton.addEventListener(
    "click",
    closeAddSupplierModal
);


addSupplierModal.addEventListener("click", function (event) {
    if (event.target === addSupplierModal) {
        closeAddSupplierModal();
    }
});


document.addEventListener("keydown", function (event) {
    if (
        event.key === "Escape" &&
        addSupplierModal.classList.contains("is-open")
    ) {
        closeAddSupplierModal();
    }
});

/* ========================================
    EDIT SUPPLIER
======================================== */

const editSupplierModal =
    document.getElementById("edit-supplier-modal");

const openEditSupplierButton =
    document.getElementById("open-edit-supplier-modal");

const closeEditSupplierButton =
    document.getElementById("close-edit-supplier-modal");

const cancelEditSupplierButton =
    document.getElementById("cancel-edit-supplier");


openEditSupplierButton.addEventListener("click", function () {

    if (selectedSupplierRow === null) {
        alert("Please select a supplier first.");
        return;
    }

    document.getElementById("edit-supplier-id").value =
        selectedSupplierRow.dataset.id;

    document.getElementById("edit-supplier-name").value =
        selectedSupplierRow.dataset.name;

    document.getElementById("edit-contact-name").value =
        selectedSupplierRow.dataset.contactName;

    document.getElementById("edit-supplier-email").value =
        selectedSupplierRow.dataset.email;

    document.getElementById("edit-supplier-phone").value =
        selectedSupplierRow.dataset.phone;

    document.getElementById("edit-supplier-supplies").value =
        selectedSupplierRow.dataset.supplies;

    document.getElementById("edit-supplier-status").value =
        selectedSupplierRow.dataset.status;

    editSupplierModal.classList.add("is-open");
    editSupplierModal.setAttribute("aria-hidden", "false");

    document.body.classList.add("modal-open");

});


function closeEditSupplierModal() {

    editSupplierModal.classList.remove("is-open");
    editSupplierModal.setAttribute("aria-hidden", "true");

    document.body.classList.remove("modal-open");

}


closeEditSupplierButton.addEventListener(
    "click",
    closeEditSupplierModal
);

cancelEditSupplierButton.addEventListener(
    "click",
    closeEditSupplierModal
);

editSupplierModal.addEventListener("click", function (event) {

    if (event.target === editSupplierModal) {
        closeEditSupplierModal();
    }

});

/* ========================================
    DELETE SUPPLIER
======================================== */

const deleteSupplierModal =
    document.getElementById("delete-supplier-modal");

const openDeleteSupplierButton =
    document.getElementById("open-delete-supplier-modal");

const closeDeleteSupplierButton =
    document.getElementById("close-delete-supplier-modal");

const cancelDeleteSupplierButton =
    document.getElementById("cancel-delete-supplier");


openDeleteSupplierButton.addEventListener("click", function () {

    if (selectedSupplierRow === null) {
        alert("Please select a supplier first.");
        return;
    }

    document.getElementById("delete-supplier-id").value =
        selectedSupplierRow.dataset.id;

    document.getElementById("delete-supplier-name").textContent =
        selectedSupplierRow.dataset.name;

    deleteSupplierModal.classList.add("is-open");
    deleteSupplierModal.setAttribute("aria-hidden", "false");

    document.body.classList.add("modal-open");

});


function closeDeleteSupplierModal() {

    deleteSupplierModal.classList.remove("is-open");
    deleteSupplierModal.setAttribute("aria-hidden", "true");

    document.body.classList.remove("modal-open");

}


closeDeleteSupplierButton.addEventListener(
    "click",
    closeDeleteSupplierModal
);

cancelDeleteSupplierButton.addEventListener(
    "click",
    closeDeleteSupplierModal
);

deleteSupplierModal.addEventListener("click", function (event) {

    if (event.target === deleteSupplierModal) {
        closeDeleteSupplierModal();
    }

});
