(() => {
    const form = document.querySelector("#auth-form");
    const username = document.querySelector("#username");
    const password = document.querySelector("#password");
    const message = document.querySelector("#form-message");
    const submitButton = document.querySelector("#submit-button");

    if (
        !(form instanceof HTMLFormElement) ||
        !(username instanceof HTMLInputElement) ||
        !(password instanceof HTMLInputElement) ||
        !(message instanceof HTMLParagraphElement) ||
        !(submitButton instanceof HTMLButtonElement)
    ) {
        throw new Error("No se pudo inicializar el formulario de autenticación.");
    }

    form.addEventListener("submit", async (event) => {
        event.preventDefault();
        message.hidden = true;
        message.textContent = "";
        submitButton.disabled = true;

        try {
            const response = await fetch(form.dataset.loginUrl, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    usuario: username.value,
                    contrasena: password.value,
                }),
            });
            const result = await response.json();

            if (!response.ok) {
                message.dataset.state = "error";
                message.textContent = result.error || "No se pudo completar la solicitud.";
                message.hidden = false;
                return;
            }

            window.location.assign(form.dataset.dashboardUrl);
        } catch {
            message.dataset.state = "error";
            message.textContent = "No se pudo conectar con el servidor. Inténtalo de nuevo.";
            message.hidden = false;
        } finally {
            submitButton.disabled = false;
        }
    });
})();
