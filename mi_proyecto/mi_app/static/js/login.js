(() => {
    const form = document.querySelector("#auth-form");
    const username = document.querySelector("#username");
    const password = document.querySelector("#password");
    const message = document.querySelector("#form-message");
    const submitButton = document.querySelector("#submit-button");
    const modeToggle = document.querySelector("#mode-toggle");

    if (
        !(form instanceof HTMLFormElement) ||
        !(username instanceof HTMLInputElement) ||
        !(password instanceof HTMLInputElement) ||
        !(message instanceof HTMLParagraphElement) ||
        !(submitButton instanceof HTMLButtonElement) ||
        !(modeToggle instanceof HTMLButtonElement)
    ) {
        throw new Error("No se pudo inicializar el formulario de autenticación.");
    }

    const setMode = (mode) => {
        const registering = mode === "register";
        form.dataset.mode = mode;
        password.autocomplete = registering ? "new-password" : "current-password";
        submitButton.textContent = registering ? "REGISTRAR CUENTA" : "INICIAR SESIÓN";
        modeToggle.textContent = registering ? "Volver a iniciar sesión" : "Registrar nueva cuenta";
        message.hidden = true;
        message.textContent = "";
        message.removeAttribute("data-state");
    };

    modeToggle.addEventListener("click", () => {
        setMode(form.dataset.mode === "login" ? "register" : "login");
    });

    form.addEventListener("submit", async (event) => {
        event.preventDefault();
        message.hidden = true;
        message.textContent = "";
        submitButton.disabled = true;

        const registering = form.dataset.mode === "register";
        const endpoint = registering ? form.dataset.registerUrl : form.dataset.loginUrl;

        try {
            const response = await fetch(endpoint, {
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

            if (registering) {
                setMode("login");
            } else {
                window.location.assign(form.dataset.dashboardUrl);
                return;
            }
            message.dataset.state = "success";
            message.textContent = registering
                ? "Cuenta creada. Ya puedes iniciar sesión."
                : `Sesión iniciada correctamente${result.usuario?.usuario ? ` como ${result.usuario.usuario}` : ""}.`;
            message.hidden = false;
            password.value = "";
        } catch {
            message.dataset.state = "error";
            message.textContent = "No se pudo conectar con el servidor. Inténtalo de nuevo.";
            message.hidden = false;
        } finally {
            submitButton.disabled = false;
        }
    });
})();
