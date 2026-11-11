(() => {
    const form = document.querySelector("#reset-form");
    if (!(form instanceof HTMLFormElement)) {
        return;
    }
    const nueva = document.querySelector("#new-password");
    const repetida = document.querySelector("#repeat-password");
    const otp = document.querySelector("#otp");
    const mensaje = document.querySelector("#form-message");
    const boton = document.querySelector("#submit-button");
    if (!(nueva instanceof HTMLInputElement) || !(repetida instanceof HTMLInputElement)
        || !(mensaje instanceof HTMLElement) || !(boton instanceof HTMLButtonElement)) {
        return;
    }

    const avisar = (texto, estado) => {
        mensaje.dataset.state = estado;
        mensaje.textContent = texto;
        mensaje.hidden = false;
    };

    form.addEventListener("submit", async (evento) => {
        evento.preventDefault();
        mensaje.hidden = true;
        if (nueva.value !== repetida.value) {
            avisar("Las dos contraseñas no coinciden.", "error");
            return;
        }
        boton.disabled = true;
        try {
            const respuesta = await fetch(form.dataset.url, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    token: form.dataset.token,
                    contrasena: nueva.value,
                    ...(otp instanceof HTMLInputElement ? { codigo: otp.value } : {}),
                }),
            });
            const resultado = await respuesta.json();
            if (!respuesta.ok) {
                avisar(resultado.error || "No se pudo cambiar la contraseña.", "error");
                return;
            }
            form.reset();
            avisar(resultado.mensaje + " Te llevamos al inicio de sesión…", "success");
            window.setTimeout(() => window.location.assign(form.dataset.loginUrl), 2000);
        } catch {
            avisar("No se pudo conectar con el servidor. Inténtalo de nuevo.", "error");
        } finally {
            boton.disabled = false;
        }
    });
})();
