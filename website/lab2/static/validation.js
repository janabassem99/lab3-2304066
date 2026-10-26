document.querySelectorAll("form[data-validation]").forEach((form) => {
    form.addEventListener("submit", (event) => {
        const kind = form.dataset.validation;
        const errors = {};
        const value = (name) => form.elements.namedItem(name).value;
        const length = (text) => Array.from(text).length;

        form.querySelectorAll("[data-error]").forEach((element) => {
            element.textContent = "";
        });
        form.querySelectorAll("[aria-invalid]").forEach((element) => {
            element.setAttribute("aria-invalid", "false");
        });

        if (kind === "register") {
            const name = value("name").trim();
            if (!name) errors.name = "Name is required";
            else if (length(name) > 100) errors.name = "Name is too long (100 characters at most)";
            const email = value("email").trim().toLowerCase();
            if (!email) errors.email = "Email is required";
            else if (length(email) > 255) errors.email = "Email is too long (255 characters at most)";
            const password = value("password");
            if (!password) errors.password = "Password is required";
            else if (new TextEncoder().encode(password).length > 72) errors.password = "Password is too long (72 UTF-8 bytes at most)";
            const confirmation = value("confirm_password");
            if (!confirmation) errors.confirm_password = "Confirm password is required";
            else if (password && password !== confirmation) errors.confirm_password = "Passwords do not match";
        }

        if (kind === "login") {
            if (!value("email").trim()) errors.email = "Email is required";
            if (!value("password")) errors.password = "Password is required";
        }

        if (kind === "todo") {
            const title = value("title").trim();
            if (!title) errors.title = "Title is required";
            else if (length(title) > 200) errors.title = "Title is too long (200 characters at most)";
        }

        if (Object.keys(errors).length > 0) {
            event.preventDefault();
            Object.entries(errors).forEach(([name, message]) => {
                form.querySelector(`[data-error="${name}"]`).textContent = message;
                form.elements.namedItem(name).setAttribute("aria-invalid", "true");
            });
            form.elements.namedItem(Object.keys(errors)[0]).focus();
        }
    });
});

document.querySelectorAll(".cancel-delete").forEach((button) => {
    button.hidden = false;
    button.addEventListener("click", () => {
        button.closest("details").open = false;
    });
});
