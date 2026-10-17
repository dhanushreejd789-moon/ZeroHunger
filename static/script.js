document.addEventListener("DOMContentLoaded", function () {
    // Show or hide password
    document.querySelectorAll("[data-toggle-password]").forEach(function (button) {
        button.addEventListener("click", function () {
            const id = button.getAttribute("data-toggle-password");
            const field = document.getElementById(id);

            if (field) {
                field.type = field.type === "password" ? "text" : "password";
            }
        });
    });

    // Search table records
    const searchBox = document.getElementById("tableSearch");

    if (searchBox) {
        searchBox.addEventListener("input", function () {
            const search = searchBox.value.toLowerCase();

            document.querySelectorAll("#dataTable tbody tr").forEach(function (row) {
                row.style.display =
                    row.textContent.toLowerCase().includes(search) ? "" : "none";
            });
        });
    }

    // Confirm before submitting forms marked for confirmation
    document.querySelectorAll("form[data-confirm]").forEach(function (form) {
        form.addEventListener("submit", function (event) {
            if (!confirm(form.dataset.confirm)) {
                event.preventDefault();
            }
        });
    });
});