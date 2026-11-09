// Añade el token CSRF (cookie legible `mettav_csrf`) a toda petición fetch que
// modifica datos en este mismo sitio. El servidor lo compara con el de la sesión.
(() => {
    const metodosSeguros = new Set(["GET", "HEAD", "OPTIONS"]);
    const leerToken = () => {
        const coincidencia = document.cookie.match(/(?:^|;\s*)mettav_csrf=([^;]*)/);
        return coincidencia ? decodeURIComponent(coincidencia[1]) : "";
    };
    const fetchOriginal = window.fetch.bind(window);

    window.fetch = (entrada, opciones = {}) => {
        const peticion = entrada instanceof Request ? entrada : null;
        const metodo = String(opciones.method || (peticion && peticion.method) || "GET").toUpperCase();
        const url = new URL(peticion ? peticion.url : String(entrada), window.location.href);

        if (!metodosSeguros.has(metodo) && url.origin === window.location.origin) {
            const token = leerToken();
            if (token) {
                const cabeceras = new Headers(opciones.headers || (peticion ? peticion.headers : undefined));
                if (!cabeceras.has("X-CSRF-Token")) {
                    cabeceras.set("X-CSRF-Token", token);
                }
                opciones = { ...opciones, headers: cabeceras };
            }
        }
        return fetchOriginal(entrada, opciones);
    };
})();
