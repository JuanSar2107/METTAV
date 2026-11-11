(() => {
    const form = document.querySelector("#change-form");
    const actual = document.querySelector("#current-password");
    const nueva = document.querySelector("#new-password");
    const mensaje = document.querySelector("#form-message");
    const guardar = document.querySelector("#submit-button");
    const salir = document.querySelector("#logout-button");
    if (!(form instanceof HTMLFormElement) || !(actual instanceof HTMLInputElement) || !(nueva instanceof HTMLInputElement)
        || !(mensaje instanceof HTMLElement) || !(guardar instanceof HTMLButtonElement) || !(salir instanceof HTMLButtonElement)) {
        return;
    }

    const cerrarSesion = async () => {
        try { sessionStorage.removeItem("mettav_pestana"); } catch { /* sin almacenamiento */ }
        try { await fetch(form.dataset.logoutUrl, { method: "POST" }); } finally { window.location.assign("/"); }
    };
    salir.addEventListener("click", cerrarSesion);

    form.addEventListener("submit", async (evento) => {
        evento.preventDefault();
        mensaje.hidden = true;
        guardar.disabled = true;
        try {
            const respuesta = await fetch(form.dataset.url, {
                method: "PUT",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ contrasena: nueva.value, contrasena_actual: actual.value }),
            });
            const resultado = await respuesta.json();
            if (!respuesta.ok) {
                mensaje.dataset.state = "error";
                mensaje.textContent = resultado.error || "No se pudo cambiar la contraseña.";
                mensaje.hidden = false;
                return;
            }
            window.location.assign(form.dataset.dashboardUrl);
        } catch {
            mensaje.dataset.state = "error";
            mensaje.textContent = "No se pudo conectar con el servidor. Inténtalo de nuevo.";
            mensaje.hidden = false;
        } finally {
            guardar.disabled = false;
        }
    });
})();
