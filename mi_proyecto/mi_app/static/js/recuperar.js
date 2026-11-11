(() => {
    const form = document.querySelector("#recover-form");
    const campo = document.querySelector("#identifier");
    const mensaje = document.querySelector("#form-message");
    const boton = document.querySelector("#submit-button");
    if (!(form instanceof HTMLFormElement) || !(campo instanceof HTMLInputElement)
        || !(mensaje instanceof HTMLElement) || !(boton instanceof HTMLButtonElement)) {
        return;
    }

    form.addEventListener("submit", async (evento) => {
        evento.preventDefault();
        mensaje.hidden = true;
        boton.disabled = true;
        try {
            const respuesta = await fetch(form.dataset.url, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ identificador: campo.value }),
            });
            const resultado = await respuesta.json();
            mensaje.dataset.state = respuesta.ok ? "success" : "error";
            mensaje.textContent = resultado.mensaje || resultado.error || "No se pudo completar la solicitud.";
            mensaje.hidden = false;
        } catch {
            mensaje.dataset.state = "error";
            mensaje.textContent = "No se pudo conectar con el servidor. Inténtalo de nuevo.";
            mensaje.hidden = false;
        } finally {
            boton.disabled = false;
        }
    });
})();
