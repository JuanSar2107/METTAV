// Seguridad del lado del navegador:
//  1. Añade el token CSRF (cookie legible `mettav_csrf`) a todo fetch que modifica datos.
//  2. Si la sesión caduca (401) estando en el panel, vuelve al inicio de sesión.
//  3. Cierra la sesión al cerrar la pestaña: el panel solo se abre en la pestaña donde
//     se inició sesión (marca en sessionStorage, que muere con la pestaña). Si se abre
//     el panel sin esa marca, se cierra la sesión y se muestra el login.
(() => {
    const MARCA = "mettav_pestana";
    const metodosSeguros = new Set(["GET", "HEAD", "OPTIONS"]);
    const leerToken = () => {
        const coincidencia = document.cookie.match(/(?:^|;\s*)mettav_csrf=([^;]*)/);
        return coincidencia ? decodeURIComponent(coincidencia[1]) : "";
    };
    const fetchOriginal = window.fetch.bind(window);
    const enPanel = window.location.pathname === "/dashboard";

    window.fetch = async (entrada, opciones = {}) => {
        const peticion = entrada instanceof Request ? entrada : null;
        const metodo = String(opciones.method || (peticion && peticion.method) || "GET").toUpperCase();
        const url = new URL(peticion ? peticion.url : String(entrada), window.location.href);
        const mismoSitio = url.origin === window.location.origin;

        if (!metodosSeguros.has(metodo) && mismoSitio) {
            const token = leerToken();
            if (token) {
                const cabeceras = new Headers(opciones.headers || (peticion ? peticion.headers : undefined));
                if (!cabeceras.has("X-CSRF-Token")) {
                    cabeceras.set("X-CSRF-Token", token);
                }
                opciones = { ...opciones, headers: cabeceras };
            }
        }
        const respuesta = await fetchOriginal(entrada, opciones);
        if (enPanel && mismoSitio && respuesta.status === 401 && !url.pathname.startsWith("/api/login")) {
            window.location.replace("/");
        }
        return respuesta;
    };

    if (enPanel) {
        let hayMarca = true;
        try {
            hayMarca = sessionStorage.getItem(MARCA) === "1";
        } catch {
            hayMarca = true; // sin sessionStorage no se puede comprobar: no se bloquea
        }
        if (!hayMarca) {
            document.documentElement.style.visibility = "hidden";
            fetchOriginal("/api/logout", { method: "POST", headers: { "X-CSRF-Token": leerToken() } })
                .catch(() => {})
                .finally(() => window.location.replace("/"));
        }
    }
})();
