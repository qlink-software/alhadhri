/** @odoo-module **/

document.addEventListener("DOMContentLoaded", () => {
    document.body.addEventListener("click", (ev) => {
        if (ev.target.classList?.contains("bd-pdf-builder-preview")) {
            ev.preventDefault();
            const preview = ev.target.closest("form")?.querySelector(".bd-pdf-builder__preview");
            if (preview) {
                preview.classList.toggle("o_hidden");
            }
        }
    });
});
