

const rows = document.querySelectorAll(
    "#inventoryTable tr"
);

let selectedRow = null;


rows.forEach(row => {

    row.addEventListener("click", function () {

        rows.forEach(r => {
            r.classList.remove("selected");
        });

        this.classList.add("selected");

        selectedRow = this;

    });

});



const categorySelect = document.getElementById("categorySelect");
const categoryText = document.getElementById("categoryText");

categorySelect.addEventListener("change", function () {
    document.getElementById("categoryForm").submit();
});

/* =========================
Add Item Modal
========================= */

const addItemModal =
    document.getElementById("addItemModal");

const openAddModal =
    document.getElementById("openAddModal");

const closeAddModal =
    document.getElementById("closeAddModal");

const cancelAddModal =
    document.getElementById("cancelAddModal");

const addItemForm =
    document.getElementById("addItemForm");


/* Open modal */

openAddModal.addEventListener("click", function () {

    addItemModal.classList.add("active");

    document.body.style.overflow = "hidden";

});


/* Close with X button */

closeAddModal.addEventListener("click", function () {

    closeModal();

});


/* Close with Cancel button */

cancelAddModal.addEventListener("click", function () {

    closeModal();

});


function closeModal() {

    addItemModal.classList.remove("active");

    document.body.style.overflow = "";

    addItemForm.reset();

}

/* =========================
Edit Item Modal
========================= */

const editItemModal =
    document.getElementById("editItemModal");

const openEditModal =
    document.getElementById("openEditModal");

const closeEditModal =
    document.getElementById("closeEditModal");

const cancelEditModal =
    document.getElementById("cancelEditModal");


/* Edit button */

openEditModal.addEventListener("click", function () {

    if (selectedRow === null) {

        alert("Please select an item first.");

        return;
    }


    /* Selected row data */

    document.getElementById("editItemId").value =
        selectedRow.dataset.id;

    document.getElementById("editItemName").value =
        selectedRow.dataset.name;

    document.getElementById("editItemCategory").value =
        selectedRow.dataset.category;

    document.getElementById("editItemUnit").value =
        selectedRow.dataset.unit;

    document.getElementById("editItemStock").value =
        selectedRow.dataset.quantity;

    document.getElementById("editItemReorder").value =
        selectedRow.dataset.minimumStock;

    document.getElementById("editItemSupplier").value =
        selectedRow.dataset.supplierId;


    /* Open modal */

    editItemModal.classList.add("active");

    document.body.style.overflow = "hidden";

});


/* X button */

closeEditModal.addEventListener("click", function () {

    closeEditItemModal();

});


/* Cancel button */

cancelEditModal.addEventListener("click", function () {

    closeEditItemModal();

});


function closeEditItemModal() {

    editItemModal.classList.remove("active");

    document.body.style.overflow = "";

}

/* =========================
   Delete Item Modal
========================= */

const deleteItemModal =
    document.getElementById("deleteItemModal");

const openDeleteModal =
    document.getElementById("openDeleteModal");

const closeDeleteModal =
    document.getElementById("closeDeleteModal");

const cancelDeleteModal =
    document.getElementById("cancelDeleteModal");


/* Delete button */

openDeleteModal.addEventListener("click", function () {

    if (selectedRow === null) {

        alert("Please select an item first.");

        return;
    }


    /* Selected item */

    document.getElementById("deleteItemId").value =
        selectedRow.dataset.id;

    document.getElementById("deleteItemName").textContent =
        selectedRow.dataset.name;


    /* Open modal */

    deleteItemModal.classList.add("active");

    document.body.style.overflow = "hidden";

});


/* X button */

closeDeleteModal.addEventListener("click", function () {

    closeDeleteItemModal();

});


/* Cancel button */

cancelDeleteModal.addEventListener("click", function () {

    closeDeleteItemModal();

});


function closeDeleteItemModal() {

    deleteItemModal.classList.remove("active");

    document.body.style.overflow = "";

}

