
document.addEventListener("DOMContentLoaded", function () {

    // Mobile navigation
    const menuToggle = document.getElementById("menuToggle");
    const mainNav = document.getElementById("mainNavigation");

    if (menuToggle && mainNav) {
        menuToggle.addEventListener("click", function () {
            mainNav.classList.toggle("active");

            const isOpen = mainNav.classList.contains("active");
            menuToggle.setAttribute("aria-expanded", isOpen);
        });
    }

    // Form confirmation
    document.querySelectorAll("form[data-confirm]").forEach(function (form) {
        form.addEventListener("submit", function (event) {
            const message = form.dataset.confirm;

            if (message && !confirm(message)) {
                event.preventDefault();
            }
        });
    });

    // Password visibility toggle
    document.querySelectorAll("[data-password-toggle]").forEach(function (button) {
        button.addEventListener("click", function () {
            const input = document.getElementById(
                button.dataset.passwordToggle
            );

            if (!input) return;

            const isPassword = input.type === "password";
            input.type = isPassword ? "text" : "password";
            button.textContent = isPassword ? "Hide" : "Show";
            button.setAttribute(
                "aria-label",
                isPassword ? "Hide password" : "Show password"
            );
        });
    });

    // Alert close buttons
    document.querySelectorAll(".alert-close").forEach(function (button) {
        button.addEventListener("click", function () {
            const alert = button.closest(".alert");
            if (alert) alert.remove();
        });
    });

    // Automatically fade alerts
    setTimeout(function () {
        document.querySelectorAll(".alert").forEach(function (alert) {
            alert.classList.add("fade");

            setTimeout(function () {
                alert.remove();
            }, 500);
        });
    }, 4500);

    // Prevent accidental double form submission
    document.querySelectorAll("form[data-loading]").forEach(function (form) {
        form.addEventListener("submit", function () {
            const submitButton = form.querySelector(
                'button[type="submit"], input[type="submit"]'
            );

            if (submitButton && form.checkValidity()) {
                submitButton.disabled = true;

                if (submitButton.tagName === "BUTTON") {
                    submitButton.textContent = "Please wait...";
                }
            }
        });
    });

});
