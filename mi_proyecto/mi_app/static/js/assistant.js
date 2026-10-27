(() => {
    const root = document.querySelector("#assistant");
    if (!(root instanceof HTMLElement)) {
        return;
    }

    const panel = document.querySelector("#assistant-panel");
    const toggle = document.querySelector("#assistant-toggle");
    const closeButton = document.querySelector("#assistant-close");
    const clearButton = document.querySelector("#assistant-clear");
    const messages = document.querySelector("#assistant-messages");
    const form = document.querySelector("#assistant-form");
    const input = document.querySelector("#assistant-input");
    const sendButton = document.querySelector("#assistant-send");
    const url = root.dataset.assistantUrl;
    const welcome = messages.innerHTML;
    // Conversación que se envía como contexto en cada pregunta.
    let history = [];
    let busy = false;

    const setOpen = (open) => {
        panel.hidden = !open;
        toggle.setAttribute("aria-expanded", String(open));
        root.classList.toggle("is-open", open);
        if (open) {
            input.focus();
        }
    };

    const addMessage = (text, kind) => {
        const bubble = document.createElement("p");
        bubble.className = `assistant-message assistant-message--${kind}`;
        // Por si el modelo usa Markdown igualmente, se quitan los asteriscos de negrita.
        bubble.textContent = kind === "bot" ? text.replace(/\*\*(.+?)\*\*/g, "$1") : text;
        messages.append(bubble);
        messages.scrollTop = messages.scrollHeight;
        return bubble;
    };

    const resizeInput = () => {
        input.style.height = "auto";
        input.style.height = `${Math.min(input.scrollHeight, 140)}px`;
    };

    toggle.addEventListener("click", () => setOpen(panel.hidden));
    closeButton.addEventListener("click", () => setOpen(false));
    clearButton.addEventListener("click", () => {
        history = [];
        messages.innerHTML = welcome;
        input.focus();
    });
    document.addEventListener("keydown", (event) => {
        if (event.key === "Escape" && !panel.hidden && !document.querySelector("dialog[open]")) {
            setOpen(false);
        }
    });

    input.addEventListener("input", resizeInput);
    input.addEventListener("keydown", (event) => {
        if (event.key === "Enter" && !event.shiftKey) {
            event.preventDefault();
            form.requestSubmit();
        }
    });

    form.addEventListener("submit", async (event) => {
        event.preventDefault();
        const question = input.value.trim();
        if (!question || busy) {
            return;
        }

        busy = true;
        sendButton.disabled = true;
        addMessage(question, "user");
        input.value = "";
        resizeInput();
        const pending = addMessage("Pensando...", "bot");
        pending.classList.add("is-pending");

        try {
            const response = await fetch(url, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ pregunta: question, historial: history }),
            });
            const data = await response.json().catch(() => ({}));
            pending.remove();
            if (!response.ok) {
                addMessage(data.error || "No se pudo obtener una respuesta.", "error");
                return;
            }
            addMessage(data.respuesta, "bot");
            history.push({ rol: "usuario", texto: question }, { rol: "asistente", texto: data.respuesta });
        } catch {
            pending.remove();
            addMessage("No se pudo conectar con el servidor.", "error");
        } finally {
            busy = false;
            sendButton.disabled = false;
            input.focus();
        }
    });
})();
