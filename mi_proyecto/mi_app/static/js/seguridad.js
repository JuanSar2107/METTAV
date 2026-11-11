// Sección «Seguridad» del perfil: cambio de contraseña y verificación en dos pasos (TOTP).
(() => {
    const seccion = document.querySelector("#security-section");
    if (!(seccion instanceof HTMLElement)) {
        return;
    }
    const $ = (selector) => seccion.querySelector(selector);
    const mostrar = (elemento, visible) => { elemento.hidden = !visible; };

    const avisar = (elemento, texto, error) => {
        elemento.textContent = texto;
        elemento.dataset.state = error ? "error" : "success";
        elemento.hidden = false;
    };

    const enviar = async (url, metodo, cuerpo) => {
        const respuesta = await fetch(url, {
            method: metodo,
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(cuerpo),
        });
        let datos = {};
        try { datos = await respuesta.json(); } catch { /* respuesta sin JSON */ }
        return { ok: respuesta.ok, datos };
    };

    // ----- contraseña
    const formularioClave = $("#password-form");
    const mensajeClave = $("#password-message");
    formularioClave.addEventListener("submit", async (evento) => {
        evento.preventDefault();
        const actual = $("#security-current-password");
        const nueva = $("#security-new-password");
        mensajeClave.hidden = true;
        const { ok, datos } = await enviar(seccion.dataset.passwordUrl, "PUT", {
            contrasena: nueva.value,
            contrasena_actual: actual.value,
        });
        if (ok) {
            formularioClave.reset();
            avisar(mensajeClave, "Contraseña cambiada. Las demás sesiones abiertas se cerraron.", false);
        } else {
            avisar(mensajeClave, datos.error || "No se pudo cambiar la contraseña.", true);
        }
    });

    // ----- dos pasos
    const estado = $("#twofa-status");
    const mensaje = $("#twofa-message");
    const formInicio = $("#twofa-start-form");
    const formActivar = $("#twofa-activate-form");
    const formDesactivar = $("#twofa-deactivate-form");

    const pintar = (activo) => {
        estado.textContent = activo
            ? "Activada: al iniciar sesión se pedirá un código de tu aplicación."
            : "Desactivada. Actívala para proteger tu cuenta aunque alguien sepa tu contraseña.";
        mostrar(formInicio, !activo);
        mostrar(formActivar, false);
        mostrar(formDesactivar, activo);
    };
    pintar(seccion.dataset["2faActive"] === "true");

    formInicio.addEventListener("submit", async (evento) => {
        evento.preventDefault();
        mensaje.hidden = true;
        const clave = $("#twofa-start-password");
        const { ok, datos } = await enviar(seccion.dataset["2faStartUrl"], "POST", { contrasena: clave.value });
        if (!ok) {
            avisar(mensaje, datos.error || "No se pudo iniciar la configuración.", true);
            return;
        }
        clave.value = "";
        $("#twofa-secret").textContent = datos.secreto.replace(/(.{4})/g, "$1 ").trim();
        $("#twofa-uri").setAttribute("href", datos.uri);
        mostrar(formInicio, false);
        mostrar(formActivar, true);
    });

    formActivar.addEventListener("submit", async (evento) => {
        evento.preventDefault();
        mensaje.hidden = true;
        const codigo = $("#twofa-activate-code");
        const { ok, datos } = await enviar(seccion.dataset["2faActivateUrl"], "POST", { codigo: codigo.value });
        if (!ok) {
            avisar(mensaje, datos.error || "No se pudo activar.", true);
            return;
        }
        codigo.value = "";
        $("#twofa-secret").textContent = "";
        pintar(true);
        avisar(mensaje, "Verificación en dos pasos activada.", false);
    });

    formDesactivar.addEventListener("submit", async (evento) => {
        evento.preventDefault();
        mensaje.hidden = true;
        const clave = $("#twofa-deactivate-password");
        const codigo = $("#twofa-deactivate-code");
        const { ok, datos } = await enviar(seccion.dataset["2faDeactivateUrl"], "POST", {
            contrasena: clave.value,
            codigo: codigo.value,
        });
        if (!ok) {
            avisar(mensaje, datos.error || "No se pudo desactivar.", true);
            return;
        }
        clave.value = "";
        codigo.value = "";
        pintar(false);
        avisar(mensaje, "Verificación en dos pasos desactivada.", false);
    });
})();
