(() => {
    const logoutButton = document.querySelector("#logout-button");
    const searchInput = document.querySelector("#inventory-search");
    const categoryFilter = document.querySelector("#category-filter");
    let cards = [...document.querySelectorAll(".inventory-card")];
    const resultsCount = document.querySelector("#results-count");
    const emptySearch = document.querySelector("#empty-search");
    const dialog = document.querySelector("#item-dialog");
    const entryForm = document.querySelector("#entry-form");
    const entryButton = document.querySelector("#entry-button");
    const entryQuantityInput = document.querySelector("#entry-quantity");
    const entryMessage = document.querySelector("#entry-message");
    const withdrawForm = document.querySelector("#withdraw-form");
    const withdrawButton = document.querySelector("#withdraw-button");
    const quantityInput = document.querySelector("#withdraw-quantity");
    const message = document.querySelector("#dialog-message");
    const profileTrigger = document.querySelector("#profile-trigger");
    const profileDialog = document.querySelector("#profile-dialog");
    const profileForm = document.querySelector("#profile-form");
    const actionToast = document.querySelector("#action-toast");
    const actionToastMessage = document.querySelector("#action-toast-message");
    let selectedCard = null;
    let toastTimeout = null;

    const showToast = (text) => {
        actionToastMessage.textContent = text;
        actionToast.hidden = false;
        window.clearTimeout(toastTimeout);
        toastTimeout = window.setTimeout(() => {
            actionToast.hidden = true;
        }, 4500);
    };

    if (logoutButton instanceof HTMLButtonElement) {
        logoutButton.addEventListener("click", async () => {
            logoutButton.disabled = true;
            try {
                await fetch("/api/logout", { method: "POST" });
            } finally {
                window.location.assign("/");
            }
        });
    }

    document.querySelectorAll(".item-image, #dialog-image").forEach((image) => {
        image.addEventListener("error", () => {
            const fallback = image.dataset.fallback;
            if (fallback && !image.src.endsWith(fallback)) {
                image.src = fallback;
            }
        });
    });

    const avatarImage = document.querySelector("#profile-trigger-image");
    const avatarInitials = document.querySelector("#profile-trigger-initials");
    if (avatarImage) {
        avatarImage.addEventListener("error", () => {
            avatarImage.classList.add("is-hidden");
            avatarInitials.classList.remove("is-hidden");
        });
    }

    if (
        profileTrigger instanceof HTMLButtonElement &&
        profileDialog instanceof HTMLDialogElement &&
        profileForm instanceof HTMLFormElement
    ) {
        const closeProfile = document.querySelector("#close-profile");
        const imageInput = document.querySelector("#profile-image-input");
        const imagePreview = document.querySelector("#profile-image-preview");
        const imageInitials = document.querySelector("#profile-image-initials");
        const message = document.querySelector("#profile-message");
        const saveButton = document.querySelector("#profile-save-button");
        const originalImage = imagePreview.getAttribute("src") || "";
        let previewUrl = null;

        profileTrigger.addEventListener("click", () => profileDialog.showModal());
        closeProfile.addEventListener("click", () => profileDialog.close());
        profileDialog.addEventListener("click", (event) => {
            if (event.target === profileDialog) {
                profileDialog.close();
            }
        });

        imageInput.addEventListener("change", () => {
            const image = imageInput.files[0];
            if (previewUrl) {
                URL.revokeObjectURL(previewUrl);
                previewUrl = null;
            }
            message.hidden = true;
            if (!image) {
                imagePreview.src = originalImage;
                imagePreview.hidden = !originalImage;
                imageInitials.hidden = Boolean(originalImage);
                return;
            }
            if (image.size > 5 * 1024 * 1024) {
                imageInput.value = "";
                message.textContent = "La imagen supera el límite de 5 MB.";
                message.dataset.state = "error";
                message.hidden = false;
                return;
            }
            previewUrl = URL.createObjectURL(image);
            imagePreview.src = previewUrl;
            imagePreview.hidden = false;
            imageInitials.hidden = true;
        });

        profileForm.addEventListener("submit", async (event) => {
            event.preventDefault();
            saveButton.disabled = true;
            message.hidden = true;
            try {
                const response = await fetch(profileForm.dataset.profileUrl, {
                    method: "POST",
                    body: new FormData(profileForm),
                });
                const result = await response.json();
                if (!response.ok) {
                    throw new Error(result.error || "No se pudo guardar el perfil.");
                }
                window.location.reload();
            } catch (error) {
                message.textContent = error.message || "No se pudo conectar con el servidor.";
                message.dataset.state = "error";
                message.hidden = false;
                saveButton.disabled = false;
            }
        });
    }

    const updateSummary = () => {
        const totalUnits = cards.reduce((total, card) => total + Number(card.dataset.stock), 0);
        const lowStock = cards.filter((card) => Number(card.dataset.stock) <= 5).length;
        const categoryCount = new Set(cards.map((card) => (card.dataset.category || "").trim()).filter(Boolean)).size;
        document.querySelector("#summary-items").textContent = cards.length;
        document.querySelector("#summary-units").textContent = totalUnits;
        document.querySelector("#summary-low-stock").textContent = lowStock;
        document.querySelector("#summary-category-count").textContent = `${categoryCount} ${categoryCount === 1 ? "categoría" : "categorías"}`;
        document.querySelector("#summary-low-stock-caption").textContent = lowStock ? "Requiere reabastecimiento" : "Todo en orden";
        document.querySelector("#summary-low-stock-card").classList.toggle("is-clear", lowStock === 0);
    };

    const updateResultsCount = () => {
        const visibleCount = cards.filter((card) => !card.hidden).length;
        resultsCount.textContent = `${visibleCount} ${visibleCount === 1 ? "artículo" : "artículos"}`;
        emptySearch.hidden = visibleCount > 0;
    };

    const normalizeSearchText = (value) =>
        value.toLocaleLowerCase("es").normalize("NFD").replace(/[\u0300-\u036f]/g, "");

    const applyFilters = () => {
        const query = searchInput instanceof HTMLInputElement ? normalizeSearchText(searchInput.value.trim()) : "";
        const selectedCategory = categoryFilter instanceof HTMLSelectElement
            ? normalizeSearchText(categoryFilter.value.trim())
            : "";

        cards.forEach((card) => {
            const content = normalizeSearchText(`${card.dataset.name || ""} ${card.dataset.code || ""} ${card.dataset.internalCode || ""} ${card.dataset.category || ""}`);
            const cardCategory = normalizeSearchText((card.dataset.category || "").trim());

            const matchesQuery = !query || content.includes(query);
            const matchesCategory = !selectedCategory || cardCategory === selectedCategory;

            card.hidden = !(matchesQuery && matchesCategory);
        });
        updateResultsCount();
    };

    if (searchInput instanceof HTMLInputElement) {
        searchInput.addEventListener("input", applyFilters);
    }

    if (categoryFilter instanceof HTMLSelectElement) {
        categoryFilter.addEventListener("change", applyFilters);
    }

    document.querySelectorAll(".delete-item").forEach((button) => {
        button.addEventListener("click", async () => {
            const card = button.closest(".inventory-card");
            if (!card || !window.confirm(`¿Eliminar "${card.dataset.name}" del inventario?`)) {
                return;
            }

            button.disabled = true;
            try {
                const response = await fetch(card.dataset.deleteUrl, { method: "DELETE" });
                const result = await response.json();
                if (!response.ok) {
                    throw new Error(result.error || "No se pudo eliminar el artículo.");
                }
                card.remove();
                cards = cards.filter((item) => item !== card);
                updateSummary();
                updateResultsCount();
            } catch (error) {
                window.alert(error.message || "No se pudo conectar con el servidor.");
                button.disabled = false;
            }
        });
    });

    const addDialog = document.querySelector("#add-item-dialog");
    const addButton = document.querySelector("#open-add-item");
    const createForm = document.querySelector("#create-item-form");
    const imageInput = document.querySelector("#new-item-image");
    const imagePreview = document.querySelector("#new-item-preview");
    const imageFileName = document.querySelector("#new-item-file-name");
    const createMessage = document.querySelector("#create-item-message");
    const createButton = document.querySelector("#create-item-button");
    let previewUrl = null;

    if (
        addDialog instanceof HTMLDialogElement &&
        addButton instanceof HTMLButtonElement &&
        createForm instanceof HTMLFormElement
    ) {
        addButton.addEventListener("click", () => addDialog.showModal());
        document.querySelector("#close-add-item").addEventListener("click", () => addDialog.close());
        addDialog.addEventListener("click", (event) => {
            if (event.target === addDialog) {
                addDialog.close();
            }
        });

        imageInput.addEventListener("change", () => {
            const image = imageInput.files[0];
            if (previewUrl) {
                URL.revokeObjectURL(previewUrl);
                previewUrl = null;
            }
            imagePreview.hidden = !image;
            if (!image) {
                imageFileName.textContent = "Selecciona una imagen para previsualizarla.";
                return;
            }
            if (image.size > 5 * 1024 * 1024) {
                imageInput.value = "";
                imagePreview.hidden = true;
                imageFileName.textContent = "El archivo supera el límite de 5 MB.";
                return;
            }
            previewUrl = URL.createObjectURL(image);
            imagePreview.src = previewUrl;
            imageFileName.textContent = image.name;
        });

        createForm.addEventListener("submit", async (event) => {
            event.preventDefault();
            createButton.disabled = true;
            createMessage.hidden = true;
            try {
                const response = await fetch(createForm.dataset.createUrl, {
                    method: "POST",
                    body: new FormData(createForm),
                });
                const result = await response.json();
                if (!response.ok) {
                    throw new Error(result.error || "No se pudo guardar el artículo.");
                }
                addDialog.close();
                window.location.reload();
            } catch (error) {
                createMessage.textContent = error.message || "No se pudo conectar con el servidor.";
                createMessage.dataset.state = "error";
                createMessage.hidden = false;
                createButton.disabled = false;
            }
        });
    }

    const importDialog = document.querySelector("#import-items-dialog");
    const importOpenButton = document.querySelector("#open-import-items");
    const importForm = document.querySelector("#import-items-form");

    if (
        importDialog instanceof HTMLDialogElement &&
        importOpenButton instanceof HTMLButtonElement &&
        importForm instanceof HTMLFormElement
    ) {
        const importMessage = document.querySelector("#import-items-message");
        const importErrors = document.querySelector("#import-items-errors");
        const importButton = document.querySelector("#import-items-button");
        let importDone = false;

        importOpenButton.addEventListener("click", () => importDialog.showModal());
        document.querySelector("#close-import-items").addEventListener("click", () => importDialog.close());
        importDialog.addEventListener("click", (event) => {
            if (event.target === importDialog) {
                importDialog.close();
            }
        });
        // Al cerrar después de importar se recarga para ver los artículos nuevos.
        importDialog.addEventListener("close", () => {
            if (importDone) {
                window.location.reload();
            }
        });

        importForm.addEventListener("submit", async (event) => {
            event.preventDefault();
            importButton.disabled = true;
            importMessage.hidden = true;
            importErrors.hidden = true;
            importErrors.replaceChildren();
            try {
                const response = await fetch(importForm.dataset.importUrl, {
                    method: "POST",
                    body: new FormData(importForm),
                });
                const result = await response.json();
                if (!response.ok) {
                    throw new Error(result.error || "No se pudo importar el archivo.");
                }
                importDone = result.creados + result.actualizados > 0;
                const avisos = result.avisos || [];
                importMessage.textContent = `Importación lista: ${result.creados} creados, ${result.actualizados} actualizados`
                    + (result.errores.length ? `, ${result.errores.length} filas con error` : "")
                    + (avisos.length ? `, ${avisos.length} avisos` : "") + ".";
                importMessage.dataset.state = result.errores.length ? "error" : "success";
                importMessage.hidden = false;
                [...result.errores, ...avisos].forEach((fila) => {
                    const item = document.createElement("li");
                    item.textContent = `Fila ${fila.fila}${fila.codigo ? ` (${fila.codigo})` : ""}: ${fila.error || `aviso, ${fila.aviso}`}`;
                    importErrors.append(item);
                });
                importErrors.hidden = result.errores.length + avisos.length === 0;
            } catch (error) {
                importMessage.textContent = error.message || "No se pudo conectar con el servidor.";
                importMessage.dataset.state = "error";
                importMessage.hidden = false;
            } finally {
                importButton.disabled = false;
            }
        });
    }

    const exitDialog = document.querySelector("#integrated-exit-dialog");
    const exitOpenButton = document.querySelector("#open-integrated-exit");
    const exitForm = document.querySelector("#integrated-exit-form");

    if (
        exitDialog instanceof HTMLDialogElement &&
        exitOpenButton instanceof HTMLButtonElement &&
        exitForm instanceof HTMLFormElement
    ) {
        const exitParts = document.querySelector("#integrated-exit-parts");
        const exitMessage = document.querySelector("#integrated-exit-message");
        const exitButton = document.querySelector("#integrated-exit-button");
        const principalLine = exitForm.querySelector('[data-line="principal"]');
        // "ZF-MAQ-CO-001 · Banco" -> tarjeta del artículo, para saber su id y stock.
        const cardsByLabel = new Map(
            [...document.querySelectorAll(".inventory-card")].map((card) => [
                `${card.dataset.code} · ${card.dataset.name}`,
                card,
            ]),
        );

        const addPartLine = () => {
            const line = document.createElement("div");
            line.className = "exit-line";
            line.dataset.line = "parte";
            const article = document.createElement("input");
            article.type = "text";
            article.setAttribute("list", "integrated-exit-articles");
            article.placeholder = "Parte: código o nombre";
            article.setAttribute("aria-label", "Parte integrada");
            article.autocomplete = "off";
            const quantity = document.createElement("input");
            quantity.type = "number";
            quantity.min = "1";
            quantity.step = "1";
            quantity.value = "1";
            quantity.setAttribute("aria-label", "Cantidad de la parte");
            const remove = document.createElement("button");
            remove.type = "button";
            remove.className = "exit-line-remove";
            remove.textContent = "Quitar";
            remove.setAttribute("aria-label", "Quitar parte");
            remove.addEventListener("click", () => line.remove());
            line.append(article, quantity, remove);
            exitParts.append(line);
            article.focus();
        };

        const readLine = (line) => {
            const [article, quantity] = line.querySelectorAll("input");
            const label = article.value.trim();
            if (!label) {
                return null;
            }
            const card = cardsByLabel.get(label);
            if (!card) {
                throw new Error(`"${label}" no es un artículo del inventario. Elígelo de la lista.`);
            }
            const cantidad = Number(quantity.value);
            if (!Number.isInteger(cantidad) || cantidad < 1) {
                throw new Error(`Indica una cantidad válida para ${card.dataset.code}.`);
            }
            if (cantidad > Number(card.dataset.stock)) {
                throw new Error(`Solo hay ${card.dataset.stock} ${card.dataset.unit} de ${card.dataset.code}.`);
            }
            return { id: Number(card.dataset.id), cantidad };
        };

        exitOpenButton.addEventListener("click", () => {
            exitForm.reset();
            exitParts.replaceChildren();
            exitMessage.hidden = true;
            addPartLine();
            exitDialog.showModal();
        });
        document.querySelector("#close-integrated-exit").addEventListener("click", () => exitDialog.close());
        exitDialog.addEventListener("click", (event) => {
            if (event.target === exitDialog) {
                exitDialog.close();
            }
        });
        document.querySelector("#integrated-exit-add-part").addEventListener("click", addPartLine);

        exitForm.addEventListener("submit", async (event) => {
            event.preventDefault();
            exitMessage.hidden = true;
            let payload;
            try {
                const componentes = [...exitParts.querySelectorAll(".exit-line")].map(readLine).filter(Boolean);
                if (componentes.length === 0) {
                    throw new Error("Agrega al menos una parte integrada.");
                }
                const formData = new FormData(exitForm);
                payload = {
                    principal: readLine(principalLine),
                    componentes,
                    proceso: formData.get("proceso"),
                    referencia: formData.get("referencia"),
                    operacion_sizfra: formData.get("operacion_sizfra"),
                    formulario: formData.get("formulario"),
                    observaciones: formData.get("observaciones"),
                };
            } catch (error) {
                exitMessage.textContent = error.message;
                exitMessage.dataset.state = "error";
                exitMessage.hidden = false;
                return;
            }

            exitButton.disabled = true;
            try {
                const response = await fetch(exitForm.dataset.exitUrl, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify(payload),
                });
                const result = await response.json();
                if (!response.ok) {
                    throw new Error(result.error || "No se pudo registrar la salida.");
                }
                exitDialog.close();
                window.location.reload();
            } catch (error) {
                exitMessage.textContent = error.message || "No se pudo conectar con el servidor.";
                exitMessage.dataset.state = "error";
                exitMessage.hidden = false;
                exitButton.disabled = false;
            }
        });
    }

    const remissionDialog = document.querySelector("#remission-dialog");
    const remissionOpenButton = document.querySelector("#open-remission");
    const remissionForm = document.querySelector("#remission-form");

    if (
        remissionDialog instanceof HTMLDialogElement &&
        remissionOpenButton instanceof HTMLButtonElement &&
        remissionForm instanceof HTMLFormElement
    ) {
        const remissionLines = document.querySelector("#remission-lines");
        const remissionLineTemplate = document.querySelector("#remission-line-template");
        const remissionMessage = document.querySelector("#remission-message");
        const remissionButton = document.querySelector("#remission-button");
        const cardsByLabel = new Map(
            [...document.querySelectorAll(".inventory-card")].map((card) => [`${card.dataset.code} · ${card.dataset.name}`, card]),
        );

        const addRemissionLine = () => {
            const line = remissionLineTemplate.content.firstElementChild.cloneNode(true);
            line.querySelector(".exit-line-remove").addEventListener("click", () => line.remove());
            remissionLines.append(line);
            line.querySelector("input").focus();
        };

        const showRemissionError = (text) => {
            remissionMessage.textContent = text;
            remissionMessage.dataset.state = "error";
            remissionMessage.hidden = false;
        };

        remissionOpenButton.addEventListener("click", () => {
            remissionForm.reset();
            remissionLines.replaceChildren();
            remissionMessage.hidden = true;
            remissionButton.disabled = false;
            addRemissionLine();
            remissionDialog.showModal();
        });
        document.querySelector("#close-remission").addEventListener("click", () => remissionDialog.close());
        remissionDialog.addEventListener("click", (event) => {
            if (event.target === remissionDialog) remissionDialog.close();
        });
        document.querySelector("#remission-add-line").addEventListener("click", addRemissionLine);

        remissionForm.addEventListener("submit", async (event) => {
            event.preventDefault();
            remissionMessage.hidden = true;
            const lineas = [];
            for (const line of remissionLines.querySelectorAll(".remission-line")) {
                const [article, quantity] = line.querySelectorAll("input");
                const label = article.value.trim();
                if (!label) continue;
                const card = cardsByLabel.get(label);
                if (!card) {
                    showRemissionError(`"${label}" no es un artículo del inventario. Elígelo de la lista.`);
                    return;
                }
                const cantidad = Number(quantity.value);
                if (!Number.isInteger(cantidad) || cantidad < 1 || cantidad > Number(card.dataset.stock)) {
                    showRemissionError(`Indica una cantidad entre 1 y ${card.dataset.stock} para ${card.dataset.code}.`);
                    return;
                }
                lineas.push({ id: Number(card.dataset.id), cantidad, estado_servicio: line.querySelector("select").value });
            }
            if (!lineas.length) {
                showRemissionError("Agrega al menos un artículo a la remisión.");
                return;
            }

            // La pestaña se abre ya (con el clic del usuario) para que el navegador no la bloquee.
            const printWindow = window.open("", "_blank");
            remissionButton.disabled = true;
            try {
                const response = await fetch(remissionForm.dataset.remissionUrl, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ ...Object.fromEntries(new FormData(remissionForm)), lineas }),
                });
                const result = await response.json();
                if (!response.ok) throw new Error(result.error || "No se pudo crear la remisión.");
                if (printWindow) {
                    printWindow.location.href = result.url;
                } else {
                    window.open(result.url, "_blank");
                }
                remissionDialog.close();
                window.location.reload();
            } catch (error) {
                printWindow?.close();
                showRemissionError(error.message || "No se pudo conectar con el servidor.");
                remissionButton.disabled = false;
            }
        });
    }

    const addUserDialog = document.querySelector("#add-user-dialog");
    const addUserButton = document.querySelector("#open-add-user");
    const createUserForm = document.querySelector("#create-user-form");

    if (
        addUserDialog instanceof HTMLDialogElement &&
        addUserButton instanceof HTMLButtonElement &&
        createUserForm instanceof HTMLFormElement
    ) {
        const createUserButton = document.querySelector("#create-user-button");
        const createUserMessage = document.querySelector("#create-user-message");

        addUserButton.addEventListener("click", () => addUserDialog.showModal());
        document.querySelector("#close-add-user").addEventListener("click", () => addUserDialog.close());
        addUserDialog.addEventListener("click", (event) => {
            if (event.target === addUserDialog) {
                addUserDialog.close();
            }
        });

        createUserForm.addEventListener("submit", async (event) => {
            event.preventDefault();
            createUserButton.disabled = true;
            createUserMessage.hidden = true;
            try {
                const response = await fetch(createUserForm.dataset.createUrl, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        usuario: createUserForm.elements.usuario.value,
                        contrasena: createUserForm.elements.contrasena.value,
                    }),
                });
                const result = await response.json();
                if (!response.ok) {
                    throw new Error(result.error || "No se pudo crear el usuario.");
                }
                const createdUsername = result.usuario.usuario;
                createUserForm.reset();
                addUserDialog.close();
                window.location.hash = "#usuarios";
                window.location.reload();
            } catch (error) {
                createUserMessage.textContent = error.message || "No se pudo conectar con el servidor.";
                createUserMessage.dataset.state = "error";
                createUserMessage.hidden = false;
            } finally {
                createUserButton.disabled = false;
            }
        });
    }

    const addCategoryDialog = document.querySelector("#add-category-dialog");
    const createCategoryForm = document.querySelector("#create-category-form");
    const newCategoryNameInput = document.querySelector("#new-category-name");
    const createCategoryButton = document.querySelector("#create-category-button");
    const createCategoryMessage = document.querySelector("#create-category-message");
    const closeAddCategory = document.querySelector("#close-add-category");
    const cancelAddCategory = document.querySelector("#cancel-add-category");
    const btnQuickAddCategory = document.querySelector("#btn-quick-add-category");
    const itemCategorySelect = document.querySelector("#new-item-category");

    const addCategoryToSelects = (catName, selectInItemForm = false) => {
        if (itemCategorySelect instanceof HTMLSelectElement) {
            let option = [...itemCategorySelect.options].find(
                (opt) => opt.value.toLowerCase() === catName.toLowerCase()
            );
            if (!option) {
                option = document.createElement("option");
                option.value = catName;
                option.textContent = catName;
                const newOptionMarker = itemCategorySelect.querySelector('option[value="__NEW_CATEGORY__"]');
                if (newOptionMarker) {
                    itemCategorySelect.insertBefore(option, newOptionMarker);
                } else {
                    itemCategorySelect.appendChild(option);
                }
            }
            if (selectInItemForm) {
                itemCategorySelect.value = option.value;
            }
        }

        if (categoryFilter instanceof HTMLSelectElement) {
            let option = [...categoryFilter.options].find(
                (opt) => opt.value.toLowerCase() === catName.toLowerCase()
            );
            if (!option) {
                option = document.createElement("option");
                option.value = catName;
                option.textContent = catName;
                categoryFilter.appendChild(option);
            }
        }
    };

    const openAddCategoryModal = () => {
        if (!(addCategoryDialog instanceof HTMLDialogElement)) return;
        if (createCategoryForm instanceof HTMLFormElement) {
            createCategoryForm.reset();
        }
        if (createCategoryMessage) {
            createCategoryMessage.hidden = true;
        }
        addCategoryDialog.showModal();
        if (newCategoryNameInput instanceof HTMLInputElement) {
            newCategoryNameInput.focus();
        }
    };

    if (itemCategorySelect instanceof HTMLSelectElement) {
        let lastSelectedCategory = itemCategorySelect.value !== "__NEW_CATEGORY__" ? itemCategorySelect.value : "General";

        itemCategorySelect.addEventListener("focus", () => {
            if (itemCategorySelect.value !== "__NEW_CATEGORY__") {
                lastSelectedCategory = itemCategorySelect.value;
            }
        });

        itemCategorySelect.addEventListener("change", () => {
            if (itemCategorySelect.value === "__NEW_CATEGORY__") {
                itemCategorySelect.value = lastSelectedCategory;
                openAddCategoryModal();
            } else {
                lastSelectedCategory = itemCategorySelect.value;
            }
        });
    }

    if (btnQuickAddCategory instanceof HTMLButtonElement) {
        btnQuickAddCategory.addEventListener("click", () => {
            openAddCategoryModal();
        });
    }

    if (addCategoryDialog instanceof HTMLDialogElement) {
        if (closeAddCategory instanceof HTMLButtonElement) {
            closeAddCategory.addEventListener("click", () => addCategoryDialog.close());
        }
        if (cancelAddCategory instanceof HTMLButtonElement) {
            cancelAddCategory.addEventListener("click", () => addCategoryDialog.close());
        }
        addCategoryDialog.addEventListener("click", (event) => {
            if (event.target === addCategoryDialog) {
                addCategoryDialog.close();
            }
        });

        if (createCategoryForm instanceof HTMLFormElement) {
            createCategoryForm.addEventListener("submit", async (event) => {
                event.preventDefault();
                const nombre = newCategoryNameInput ? newCategoryNameInput.value.trim() : "";
                if (!nombre) return;

                if (createCategoryButton instanceof HTMLButtonElement) {
                    createCategoryButton.disabled = true;
                }
                if (createCategoryMessage) {
                    createCategoryMessage.hidden = true;
                }

                try {
                    const response = await fetch(createCategoryForm.dataset.createUrl, {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({ nombre }),
                    });
                    const result = await response.json();
                    if (!response.ok) {
                        throw new Error(result.error || "No se pudo crear la categoría.");
                    }
                    const categoryName = result.categoria.nombre;
                    addCategoryToSelects(categoryName, true);
                    addCategoryDialog.close();
                    createCategoryForm.reset();
                    showToast(`Categoría "${categoryName}" guardada correctamente.`);
                } catch (error) {
                    if (createCategoryMessage) {
                        createCategoryMessage.textContent = error.message || "Error al conectar con el servidor.";
                        createCategoryMessage.dataset.state = "error";
                        createCategoryMessage.hidden = false;
                    }
                } finally {
                    if (createCategoryButton instanceof HTMLButtonElement) {
                        createCategoryButton.disabled = false;
                    }
                }
            });
        }
    }

    if (!(dialog instanceof HTMLDialogElement)) {
        return;
    }

    const detailImage = document.querySelector("#dialog-image");
    const detailName = document.querySelector("#dialog-title");
    const detailCategory = document.querySelector("#dialog-category");
    const detailDescription = document.querySelector("#dialog-description");
    const detailCode = document.querySelector("#dialog-code");
    const detailLocation = document.querySelector("#dialog-location");
    const detailStock = document.querySelector("#dialog-stock");
    const detailStockMax = document.querySelector("#dialog-stock-max");

    const updateStockLimits = (card) => {
        const stock = Number(card.dataset.stock);
        const maxStock = Number(card.dataset.maxStock);
        // El stock máximo es informativo (el más alto alcanzado); los ingresos no tienen tope.
        detailStockMax.textContent = maxStock > 0
            ? `${maxStock} ${card.dataset.unit}`
            : "Se define con el primer ingreso";
        quantityInput.max = String(stock);
        entryQuantityInput.disabled = false;
        entryButton.disabled = false;
    };

    const showMessage = (text, state = "success") => {
        message.textContent = text;
        message.dataset.state = state;
        message.hidden = false;
    };

    const openDetails = (card) => {
        selectedCard = card;
        detailImage.src = card.dataset.image;
        detailImage.dataset.fallback = card.querySelector(".item-image").dataset.fallback;
        detailImage.alt = card.dataset.name;
        detailName.textContent = card.dataset.name;
        detailCategory.textContent = card.dataset.category;
        detailDescription.textContent = card.dataset.description;
        detailCode.textContent = card.dataset.code;
        detailLocation.textContent = card.dataset.location;
        detailStock.textContent = `${card.dataset.stock} ${card.dataset.unit}`;
        renderDetailFields(card);
        if (serviceForm instanceof HTMLFormElement) {
            serviceForm.elements.cliente.value = card.dataset.client || "";
            serviceForm.elements.tipo_servicio.value = card.dataset.serviceType || "";
            serviceForm.elements.estado_servicio.value = card.dataset.serviceStatus || "";
            serviceMessage.hidden = true;
            serviceEditor.open = false;
        }
        updateStockLimits(card);
        quantityInput.value = Number(card.dataset.stock) > 0 ? "1" : "";
        quantityInput.disabled = Number(card.dataset.stock) === 0;
        withdrawButton.disabled = Number(card.dataset.stock) === 0;
        entryQuantityInput.value = "1";
        entryMessage.hidden = true;
        message.hidden = true;
        movementOperationInput.value = "";
        movementFormInput.value = "";
        movementNotesInput.value = "";
        dialog.showModal();
    };

    // Datos de zona franca, trazabilidad y servicio: solo se muestran los que el artículo tiene.
    const renderDetailFields = (card) => {
        dialog.querySelectorAll("[data-zf-field]").forEach((row) => {
            let value = card.dataset[row.dataset.zfField] || "";
            if (value && row.dataset.zfField === "fob") {
                value = `USD ${Number(value).toLocaleString("es-CO", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
            }
            if (value && row.dataset.zfField === "groupName") {
                value = `${card.dataset.group} · ${value}`;
            }
            if (value && (row.dataset.zfField === "entryDate" || row.dataset.zfField === "exitDate")) {
                value = formatDate(value);
            }
            row.querySelector("dd").textContent = value;
            row.hidden = !value;
        });
    };

    const serviceEditor = document.querySelector("#service-editor");
    const serviceForm = document.querySelector("#service-form");
    const serviceMessage = document.querySelector("#service-message");
    if (serviceForm instanceof HTMLFormElement) {
        serviceForm.addEventListener("submit", async (event) => {
            event.preventDefault();
            if (!selectedCard) return;
            const button = serviceForm.querySelector("button[type=submit]");
            button.disabled = true;
            serviceMessage.hidden = true;
            try {
                const response = await fetch(selectedCard.dataset.serviceUrl, {
                    method: "PATCH",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify(Object.fromEntries(new FormData(serviceForm))),
                });
                const result = await response.json();
                if (!response.ok) throw new Error(result.error || "No se pudo guardar el servicio.");
                const { cliente, tipo_servicio: tipo, estado_servicio: estado } = result.articulo;
                selectedCard.dataset.client = cliente || "";
                selectedCard.dataset.serviceType = tipo || "";
                selectedCard.dataset.serviceStatus = estado || "";
                // Etiqueta del estado sobre la imagen de la tarjeta.
                let label = selectedCard.querySelector(".service-label");
                if (estado) {
                    if (!label) {
                        label = document.createElement("span");
                        selectedCard.querySelector(".item-image-wrap").append(label);
                    }
                    label.className = `service-label service-label--${estado.toLowerCase().replace(/\s+/g, "-")}`;
                    label.textContent = estado;
                } else {
                    label?.remove();
                }
                renderDetailFields(selectedCard);
                serviceMessage.textContent = result.cambios ? "Servicio actualizado." : "No había cambios.";
                serviceMessage.dataset.state = "success";
            } catch (error) {
                serviceMessage.textContent = error.message || "No se pudo conectar con el servidor.";
                serviceMessage.dataset.state = "error";
            } finally {
                serviceMessage.hidden = false;
                button.disabled = false;
            }
        });
    }

    // "2026-05-08" -> "8 may 2026" (sin pasar por la zona horaria del navegador).
    const formatDate = (isoDate) => {
        const [year, month, day] = isoDate.split("-").map(Number);
        return new Date(year, month - 1, day).toLocaleDateString("es-CO", { day: "numeric", month: "short", year: "numeric" });
    };

    const movementOperationInput = document.querySelector("#movement-operation");
    const movementFormInput = document.querySelector("#movement-form-number");
    const movementNotesInput = document.querySelector("#movement-notes");
    const sizfraData = () => ({
        operacion_sizfra: movementOperationInput.value.trim(),
        formulario: movementFormInput.value.trim(),
        observaciones: movementNotesInput.value.trim(),
    });

    const traceButton = document.querySelector("#open-trace");
    const traceDialog = document.querySelector("#trace-dialog");
    if (traceButton instanceof HTMLButtonElement && traceDialog instanceof HTMLDialogElement) {
        const traceTitle = document.querySelector("#trace-title");
        const traceSummary = document.querySelector("#trace-summary");
        const traceMessage = document.querySelector("#trace-message");
        const traceList = document.querySelector("#trace-list");
        const traceDateFormatter = new Intl.DateTimeFormat("es-CO", { dateStyle: "medium", timeStyle: "short" });

        const traceEntry = (evento) => {
            const item = document.createElement("li");
            const header = document.createElement("div");
            const title = document.createElement("strong");
            const when = document.createElement("span");
            const detail = document.createElement("p");
            header.className = "trace-entry-header";
            when.textContent = `${traceDateFormatter.format(new Date(evento.fecha_hora))} · ${evento.empleado} (@${evento.usuario})`;
            const lines = [];
            if (evento.clase === "movimiento") {
                item.className = evento.tipo === "Ingreso" ? "trace-entry trace-entry--entry" : "trace-entry trace-entry--withdrawal";
                title.textContent = `${evento.tipo} de ${evento.cantidad} ${evento.unidad}`;
                if (evento.origen) lines.push(`Origen: ${evento.origen}`);
                if (evento.id_salida) {
                    lines.push(evento.rol === "Principal"
                        ? `Equipo de la salida integrada #${evento.id_salida} (${evento.proceso})`
                        : `Integrada en ${evento.referencia} · salida #${evento.id_salida} (${evento.proceso})`);
                }
                const sizfra = [
                    evento.operacion_sizfra ? `operación ${evento.operacion_sizfra}` : "",
                    evento.formulario ? `formulario ${evento.formulario}` : "",
                ].filter(Boolean).join(", ");
                if (sizfra) lines.push(`Sizfra: ${sizfra}`);
                if (evento.observaciones) lines.push(`Observaciones: ${evento.observaciones}`);
            } else {
                item.className = "trace-entry trace-entry--audit";
                title.textContent = evento.accion;
                if (evento.detalle) lines.push(evento.detalle);
            }
            detail.textContent = lines.join(" · ");
            header.append(title, when);
            item.append(header);
            if (lines.length) item.append(detail);
            return item;
        };

        traceButton.addEventListener("click", async () => {
            if (!selectedCard) return;
            traceTitle.textContent = `${selectedCard.dataset.code} · ${selectedCard.dataset.name}`;
            traceSummary.textContent = "";
            traceList.replaceChildren();
            traceMessage.textContent = "Cargando trazabilidad...";
            traceMessage.dataset.state = "success";
            traceMessage.hidden = false;
            traceDialog.showModal();
            try {
                const url = traceButton.dataset.traceUrl.replace("__CODIGO__", encodeURIComponent(selectedCard.dataset.code));
                const response = await fetch(url);
                const result = await response.json();
                if (!response.ok) {
                    throw new Error(result.error || "No se pudo cargar la trazabilidad.");
                }
                traceSummary.textContent = `${result.eventos.length} registros, del más reciente al más antiguo.`;
                traceList.append(...result.eventos.map(traceEntry));
                traceMessage.hidden = true;
            } catch (error) {
                traceMessage.textContent = error.message || "No se pudo conectar con el servidor.";
                traceMessage.dataset.state = "error";
            }
        });
        document.querySelector("#close-trace").addEventListener("click", () => traceDialog.close());
        traceDialog.addEventListener("click", (event) => {
            if (event.target === traceDialog) traceDialog.close();
        });
    }

    const showEntryMessage = (text, state = "success") => {
        entryMessage.textContent = text;
        entryMessage.dataset.state = state;
        entryMessage.hidden = false;
    };

    document.querySelectorAll(".more-button").forEach((button) => {
        button.addEventListener("click", () => openDetails(button.closest(".inventory-card")));
    });

    document.querySelector("#close-dialog").addEventListener("click", () => dialog.close());

    dialog.addEventListener("click", (event) => {
        if (event.target === dialog) {
            dialog.close();
        }
    });

    if (entryForm instanceof HTMLFormElement) {
        entryForm.addEventListener("submit", async (event) => {
            event.preventDefault();
            if (!selectedCard) {
                return;
            }

            const quantity = Number(entryQuantityInput.value);
            if (!Number.isInteger(quantity) || quantity < 1) {
                showEntryMessage("Indica una cantidad entera mayor que cero.", "error");
                return;
            }

            entryButton.disabled = true;
            entryMessage.hidden = true;
            try {
                const response = await fetch(selectedCard.dataset.entryUrl, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ cantidad: quantity, ...sizfraData() }),
                });
                const result = await response.json();
                if (!response.ok) {
                    throw new Error(result.error || "No se pudo ingresar el artículo.");
                }

                selectedCard.dataset.stock = result.articulo.stock;
                selectedCard.dataset.maxStock = result.articulo.stock_maximo;
                const stockLabel = selectedCard.querySelector(".stock-label");
                selectedCard.querySelector(".stock-value").textContent = result.articulo.stock;
                selectedCard.querySelector(".stock-unit").textContent = `${selectedCard.dataset.unit} disponibles`;
                stockLabel.classList.toggle("is-low", result.articulo.stock <= 5);
                detailStock.textContent = `${result.articulo.stock} ${result.articulo.unidad}`;
                updateStockLimits(selectedCard);
                updateSummary();
                if (typeof renderMovementHistory === "function") {
                    movementRecords.unshift(result.movimiento);
                    renderMovementHistory();
                }
                dialog.close();
                showToast(`Ingresaste ${quantity} ${quantity === 1 ? "unidad" : "unidades"} de ${selectedCard.dataset.name}.`);
            } catch (error) {
                showEntryMessage(error.message || "No se pudo conectar con el servidor.", "error");
            } finally {
                entryButton.disabled = false;
            }
        });
    }

    if (withdrawForm instanceof HTMLFormElement) {
        withdrawForm.addEventListener("submit", async (event) => {
            event.preventDefault();
            if (!selectedCard) {
                return;
            }

            const quantity = Number(quantityInput.value);
            const stock = Number(selectedCard.dataset.stock);
            const maxStock = Number(selectedCard.dataset.maxStock);
            const available = Math.min(stock, maxStock || stock);
            if (!Number.isInteger(quantity) || quantity < 1 || quantity > available) {
                showMessage("Indica una cantidad válida dentro del stock disponible.", "error");
                return;
            }

            withdrawButton.disabled = true;
            try {
                const response = await fetch(selectedCard.dataset.withdrawUrl, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ cantidad: quantity, ...sizfraData() }),
                });
                const result = await response.json();
                if (!response.ok) {
                    throw new Error(result.error || "No se pudo retirar el artículo.");
                }

                selectedCard.dataset.stock = result.articulo.stock;
                selectedCard.dataset.maxStock = result.articulo.stock_maximo;
                const stockLabel = selectedCard.querySelector(".stock-label");
                selectedCard.querySelector(".stock-value").textContent = result.articulo.stock;
                selectedCard.querySelector(".stock-unit").textContent = `${selectedCard.dataset.unit} disponibles`;
                stockLabel.classList.toggle("is-low", result.articulo.stock <= 5);
                detailStock.textContent = `${result.articulo.stock} ${result.articulo.unidad}`;
                updateStockLimits(selectedCard);
                quantityInput.value = result.articulo.stock > 0 ? "1" : "";
                quantityInput.disabled = result.articulo.stock === 0;
                updateSummary();
                if (typeof renderMovementHistory === "function") {
                    movementRecords.unshift(result.movimiento);
                    renderMovementHistory();
                }
                dialog.close();
                showToast(`Retiraste ${quantity} ${quantity === 1 ? "unidad" : "unidades"} de ${selectedCard.dataset.name}.`);
            } catch (error) {
                showMessage(error.message || "No se pudo conectar con el servidor.", "error");
            } finally {
                withdrawButton.disabled = Number(selectedCard.dataset.stock) === 0;
            }
        });
    }

    // ==========================================
    // Navegación por pestañas (Inventario / Usuarios)
    // ==========================================
    const tabButtons = document.querySelectorAll(".tab-button");
    const tabPanels = document.querySelectorAll(".dashboard-tab-panel");
    const openAddUserPanelBtn = document.querySelector("#open-add-user-from-panel");

    if (openAddUserPanelBtn instanceof HTMLButtonElement && addUserDialog instanceof HTMLDialogElement) {
        openAddUserPanelBtn.addEventListener("click", () => addUserDialog.showModal());
    }

    const switchTab = (targetId) => {
        tabButtons.forEach((btn) => {
            const isActive = btn.dataset.target === targetId;
            btn.classList.toggle("is-active", isActive);
            btn.setAttribute("aria-selected", isActive ? "true" : "false");
        });
        tabPanels.forEach((panel) => {
            panel.classList.toggle("is-hidden", panel.id !== targetId);
        });
    };

    const movementHistory = document.querySelector("#movement-history");
    const movementTableWrap = document.querySelector("#movement-table-wrap");
    const movementTableBody = document.querySelector("#movement-table-body");
    const movementHistoryMessage = document.querySelector("#movement-history-message");
    const movementResultsCount = document.querySelector("#movement-results-count");
    const movementFilters = document.querySelector("#movement-filters");
    const movementSearchInput = document.querySelector("#movement-search");
    const movementCategoryFilter = document.querySelector("#movement-category-filter");
    const movementDateInput = document.querySelector("#movement-date");
    const movementFilterReset = document.querySelector("#movement-filter-reset");
    let movementRecords = [];

    const normalizeMovementText = (value) =>
        String(value || "").toLocaleLowerCase("es").normalize("NFD").replace(/[\u0300-\u036f]/g, "");

    const localDateKey = (value) => {
        const date = new Date(value);
        const year = date.getFullYear();
        const month = String(date.getMonth() + 1).padStart(2, "0");
        const day = String(date.getDate()).padStart(2, "0");
        return `${year}-${month}-${day}`;
    };

    const renderMovementHistory = () => {
        if (!(movementTableBody instanceof HTMLTableSectionElement)) return;

        const query = movementSearchInput instanceof HTMLInputElement
            ? normalizeMovementText(movementSearchInput.value.trim())
            : "";
        const category = movementCategoryFilter instanceof HTMLSelectElement
            ? movementCategoryFilter.value
            : "";
        const selectedDate = movementDateInput instanceof HTMLInputElement ? movementDateInput.value : "";

        movementTableBody.replaceChildren();

        const filteredMovements = movementRecords.filter((movimiento) => {
            const searchableText = normalizeMovementText(
                `${movimiento.tipo} ${movimiento.empleado} ${movimiento.usuario} ${movimiento.articulo} ${movimiento.codigo_articulo} ${movimiento.categoria} `
                + `${movimiento.operacion_sizfra || ""} ${movimiento.formulario || ""} ${movimiento.referencia || ""} ${movimiento.proceso || ""} `
                + `${movimiento.observaciones || ""} ${movimiento.origen || ""}`,
            );
            const movementDate = localDateKey(movimiento.fecha_hora);
            return (!query || searchableText.includes(query))
                && (!category || movimiento.categoria === category)
                && (!selectedDate || movementDate === selectedDate);
        });

        if (movementResultsCount) {
            movementResultsCount.textContent = `Mostrando ${filteredMovements.length} de ${movementRecords.length} movimientos`;
        }
        if (filteredMovements.length === 0) {
            movementHistoryMessage.textContent = movementRecords.length
                ? "No hay movimientos que coincidan con los filtros."
                : "Todavía no hay movimientos registrados.";
            movementHistoryMessage.hidden = false;
            movementTableWrap.hidden = true;
            return;
        }

        const dateFormatter = new Intl.DateTimeFormat("es-CO", {
            dateStyle: "medium",
            timeStyle: "short",
        });
        filteredMovements.forEach((movimiento) => {
            const row = document.createElement("tr");
            const dateCell = document.createElement("td");
            const employeeCell = document.createElement("td");
            const typeCell = document.createElement("td");
            const articleCell = document.createElement("td");
            const quantityCell = document.createElement("td");
            const employeeName = document.createElement("span");
            const username = document.createElement("small");
            const movementType = document.createElement("span");
            const articleName = document.createElement("span");
            const articleCode = document.createElement("small");

            dateCell.textContent = dateFormatter.format(new Date(movimiento.fecha_hora));
            employeeName.textContent = movimiento.empleado;
            username.textContent = `@${movimiento.usuario}`;
            movementType.className = movimiento.tipo === "Ingreso"
                ? "movement-type-badge movement-type-badge--entry"
                : "movement-type-badge movement-type-badge--withdrawal";
            movementType.textContent = movimiento.tipo;
            articleName.textContent = movimiento.articulo;
            articleCode.textContent = `${movimiento.codigo_articulo} · ${movimiento.categoria}`;
            quantityCell.className = "movement-quantity";
            quantityCell.textContent = `${movimiento.cantidad} ${movimiento.unidad}`;
            employeeCell.append(employeeName, username);
            articleCell.append(articleName, articleCode);
            typeCell.append(movementType);
            // Salida integrada: el equipo y cada parte muestran a qué salida pertenecen.
            if (movimiento.id_salida) {
                const integration = document.createElement("small");
                integration.textContent = movimiento.rol === "Principal"
                    ? `Equipo · ${movimiento.proceso} #${movimiento.id_salida}`
                    : `Integrada en ${movimiento.referencia} #${movimiento.id_salida}`;
                typeCell.append(integration);
                row.classList.add("movement-row--integrated");
            } else if (movimiento.origen && movimiento.origen !== "Manual") {
                const origin = document.createElement("small");
                origin.textContent = movimiento.origen;
                typeCell.append(origin);
            }
            if (movimiento.observaciones) {
                const notes = document.createElement("small");
                notes.className = "movement-notes";
                notes.textContent = movimiento.observaciones;
                articleCell.append(notes);
            }
            const sizfraCell = document.createElement("td");
            sizfraCell.className = "movement-sizfra";
            const sizfraParts = [
                movimiento.operacion_sizfra ? `Op. ${movimiento.operacion_sizfra}` : "",
                movimiento.formulario ? `Form. ${movimiento.formulario}` : "",
            ].filter(Boolean);
            sizfraCell.textContent = sizfraParts.join(" · ") || "—";
            row.append(dateCell, employeeCell, typeCell, articleCell, quantityCell, sizfraCell);
            movementTableBody.append(row);
        });

        movementHistoryMessage.hidden = true;
        movementTableWrap.hidden = false;
    };

    const loadMovementHistory = async () => {
        if (
            !(movementHistory instanceof HTMLDivElement) ||
            !(movementTableWrap instanceof HTMLDivElement) ||
            !(movementTableBody instanceof HTMLTableSectionElement) ||
            !(movementHistoryMessage instanceof HTMLParagraphElement) ||
            !(movementFilters instanceof HTMLDivElement)
        ) {
            return;
        }

        movementHistoryMessage.textContent = "Cargando movimientos...";
        movementHistoryMessage.hidden = false;
        movementTableWrap.hidden = true;
        movementFilters.hidden = true;

        try {
            const response = await fetch(movementHistory.dataset.movementsUrl);
            const result = await response.json();
            if (!response.ok) {
                throw new Error(result.error || "No se pudo cargar el historial.");
            }

            movementRecords = result.movimientos;
            if (movementCategoryFilter instanceof HTMLSelectElement) {
                movementCategoryFilter.replaceChildren(new Option("Todas las categorías", ""));
                result.categorias.forEach((categoria) => {
                    movementCategoryFilter.add(new Option(categoria, categoria));
                });
            }
            movementFilters.hidden = false;
            renderMovementHistory();
        } catch (error) {
            movementHistoryMessage.textContent = error.message || "No se pudo cargar el historial.";
            if (movementResultsCount) movementResultsCount.textContent = "";
        }
    };

    [movementSearchInput, movementCategoryFilter, movementDateInput].forEach((filter) => {
        if (filter instanceof HTMLInputElement || filter instanceof HTMLSelectElement) {
            const eventName = filter instanceof HTMLInputElement && filter.type === "search" ? "input" : "change";
            filter.addEventListener(eventName, renderMovementHistory);
        }
    });

    if (movementFilterReset instanceof HTMLButtonElement) {
        movementFilterReset.addEventListener("click", () => {
            if (movementSearchInput instanceof HTMLInputElement) movementSearchInput.value = "";
            if (movementCategoryFilter instanceof HTMLSelectElement) movementCategoryFilter.value = "";
            if (movementDateInput instanceof HTMLInputElement) movementDateInput.value = "";
            renderMovementHistory();
        });
    }

    // ==========================================
    // Reportes y conciliación con Sizfra
    // ==========================================
    const reportMessage = document.querySelector("#report-message");
    const reportSummary = document.querySelector("#report-summary");
    const reportTableWrap = document.querySelector("#report-table-wrap");
    const reportTableHead = document.querySelector("#report-table-head");
    const reportTableBody = document.querySelector("#report-table-body");
    const reportDate = new Intl.DateTimeFormat("es-CO", { dateStyle: "medium", timeStyle: "short" });
    const usd = (value) => (value === null || value === undefined
        ? ""
        : `USD ${Number(value).toLocaleString("es-CO", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`);

    // Columnas de cada reporte: [encabezado, función que saca el valor de la fila].
    const reportColumns = {
        inventario: [
            ["Código ZF", (f) => f.codigo],
            ["Descripción", (f) => f.nombre],
            ["Grupo", (f) => f.grupo || "—"],
            ["Ubicación", (f) => f.ubicacion],
            ["Stock", (f) => `${f.stock} ${f.unidad}`],
            ["Subpartida", (f) => f.subpartida || ""],
            ["Valor total", (f) => usd(f.valor_total_usd)],
        ],
        movimientos: [
            ["Fecha", (f) => reportDate.format(new Date(f.fecha_hora))],
            ["Tipo", (f) => f.tipo],
            ["Código", (f) => f.codigo_articulo],
            ["Artículo", (f) => f.articulo],
            ["Cantidad", (f) => `${f.cantidad} ${f.unidad}`],
            ["Sizfra", (f) => [f.operacion_sizfra && `Op. ${f.operacion_sizfra}`, f.formulario && `Form. ${f.formulario}`].filter(Boolean).join(" · ")],
            ["Empleado", (f) => f.empleado],
        ],
        salidas: [
            ["Salida", (f) => `#${f.salida}`],
            ["Fecha", (f) => reportDate.format(new Date(f.fecha_hora))],
            ["Proceso", (f) => f.proceso],
            ["Referencia", (f) => f.referencia],
            ["Rol", (f) => (f.rol === "Principal" ? "Equipo" : "Parte")],
            ["Artículo", (f) => `${f.codigo_articulo} · ${f.articulo}`],
            ["Cantidad", (f) => `${f.cantidad} ${f.unidad}`],
        ],
        remisiones: [
            ["Número", (f) => {
                const link = document.createElement("a");
                link.href = f.url;
                link.target = "_blank";
                link.rel = "noopener";
                link.textContent = f.numero;
                return link;
            }],
            ["Fecha", (f) => formatDate(f.fecha)],
            ["Cliente", (f) => `${f.cliente_nombre} · ${f.cliente_nit}`],
            ["Servicio", (f) => f.tipo_servicio || ""],
            ["Artículos", (f) => f.lineas.map((l) => `${l.cantidad} × ${l.codigo}`).join(", ")],
            ["Sizfra", (f) => [f.operacion_sizfra && `Op. ${f.operacion_sizfra}`, f.formulario && `Form. ${f.formulario}`].filter(Boolean).join(" · ")],
        ],
        conciliacion: [
            ["Estado", (f) => f.estado],
            ["Código", (f) => f.codigo],
            ["Artículo", (f) => f.nombre || "—"],
            ["Stock app", (f) => (f.stock_app ?? "—")],
            ["Saldo Sizfra", (f) => (f.saldo_sizfra ?? "—")],
            ["Diferencia", (f) => (f.diferencia ?? "—")],
        ],
    };

    const reportSummaryText = (report, result) => {
        if (report === "inventario") {
            return result.resumen.map((g) => `${g.grupo} · ${g.nombre}: ${g.articulos} artículos, ${g.unidades} unidades${g.valor_total_usd ? `, ${usd(g.valor_total_usd)}` : ""}`);
        }
        if (report === "movimientos") {
            const r = result.resumen;
            return [`${r.ingresos} ingresos (${r.unidades_ingresadas} unidades) y ${r.retiros} retiros (${r.unidades_retiradas} unidades).`];
        }
        if (report === "salidas") {
            return [`${result.total} salidas integradas.`];
        }
        if (report === "remisiones") {
            return [`${result.total} remisiones. Haz clic en el número para abrirla e imprimirla.`];
        }
        const r = result.resumen;
        return [
            `Columnas usadas del archivo: código "${result.columnas.codigo}", saldo "${result.columnas.saldo}".`,
            `${r.Coincide} coinciden, ${r.Diferencia} con diferencia, ${r["Solo en Sizfra"]} solo en Sizfra y ${r["Solo en la app"]} solo en la app.`,
        ];
    };

    const reportRows = (report, result) => {
        if (report === "salidas") {
            return result.salidas.flatMap((s) => s.movimientos.map((m) => ({ ...m, salida: s.id, proceso: s.proceso, referencia: s.referencia })));
        }
        if (report === "remisiones") {
            return result.remisiones;
        }
        return result.filas;
    };

    const showReportMessage = (text, state) => {
        reportMessage.textContent = text;
        reportMessage.dataset.state = state || "";
        reportMessage.hidden = false;
    };

    const reportQuery = (form) => {
        const params = new URLSearchParams();
        new FormData(form).forEach((value, key) => {
            if (typeof value === "string" && value.trim()) params.set(key, value.trim());
        });
        return params;
    };

    const fetchReport = (form, excel) => {
        const report = form.dataset.report;
        if (report === "conciliacion") {
            const body = new FormData(form);
            body.set("solo_zf", form.elements.solo_zf.checked ? "1" : "0");
            if (excel) body.set("formato", "xlsx");
            return fetch(form.dataset.reportUrl, { method: "POST", body });
        }
        const params = reportQuery(form);
        if (excel) params.set("formato", "xlsx");
        return fetch(`${form.dataset.reportUrl}?${params}`);
    };

    document.querySelectorAll(".report-card").forEach((form) => {
        const report = form.dataset.report;

        form.addEventListener("submit", async (event) => {
            event.preventDefault();
            showReportMessage("Cargando reporte...");
            reportSummary.hidden = true;
            reportTableWrap.hidden = true;
            try {
                const response = await fetchReport(form, false);
                const result = await response.json();
                if (!response.ok) throw new Error(result.error || "No se pudo generar el reporte.");

                const rows = reportRows(report, result);
                const columns = reportColumns[report];
                reportSummary.replaceChildren(...reportSummaryText(report, result).map((line) => {
                    const p = document.createElement("p");
                    p.textContent = line;
                    return p;
                }));
                reportSummary.hidden = false;
                if (!rows.length) {
                    showReportMessage("No hay registros con esos filtros.");
                    return;
                }
                const headRow = document.createElement("tr");
                headRow.append(...columns.map(([title]) => {
                    const th = document.createElement("th");
                    th.scope = "col";
                    th.textContent = title;
                    return th;
                }));
                reportTableHead.replaceChildren(headRow);
                reportTableBody.replaceChildren(...rows.map((row) => {
                    const tr = document.createElement("tr");
                    if (report === "conciliacion") {
                        tr.className = `report-row--${row.estado.toLowerCase().replace(/\s+/g, "-")}`;
                    }
                    tr.append(...columns.map(([, value]) => {
                        const td = document.createElement("td");
                        const content = value(row);
                        if (content instanceof Node) {
                            td.append(content);
                        } else {
                            td.textContent = content;
                        }
                        return td;
                    }));
                    return tr;
                }));
                reportMessage.hidden = true;
                reportTableWrap.hidden = false;
            } catch (error) {
                showReportMessage(error.message || "No se pudo conectar con el servidor.", "error");
            }
        });

        form.querySelector("[data-download]")?.addEventListener("click", async () => {
            if (!form.reportValidity()) return;
            try {
                const response = await fetchReport(form, true);
                if (!response.ok) {
                    const result = await response.json();
                    throw new Error(result.error || "No se pudo descargar el reporte.");
                }
                const disposition = response.headers.get("Content-Disposition") || "";
                const match = disposition.match(/filename="?([^";]+)"?/);
                const link = document.createElement("a");
                link.href = URL.createObjectURL(await response.blob());
                link.download = match ? match[1] : "reporte.xlsx";
                link.click();
                URL.revokeObjectURL(link.href);
            } catch (error) {
                showReportMessage(error.message || "No se pudo conectar con el servidor.", "error");
            }
        });
    });

    tabButtons.forEach((btn) => {
        btn.addEventListener("click", () => {
            const targetId = btn.dataset.target;
            switchTab(targetId);
            const tabHashes = {
                "section-users": "#usuarios",
                "section-movements": "#movimientos",
                "section-reports": "#reportes",
                "section-inventory": "#inventario",
            };
            window.location.hash = tabHashes[targetId] || "#inventario";
            if (targetId === "section-movements") loadMovementHistory();
        });
    });

    const initialTabs = {
        "#usuarios": "section-users",
        "#movimientos": "section-movements",
        "#reportes": "section-reports",
    };
    const initialTab = initialTabs[window.location.hash];
    if (initialTab) {
        switchTab(initialTab);
        if (initialTab === "section-movements") loadMovementHistory();
    }

    // ==========================================
    // Filtro y búsqueda de Usuarios y Empleados
    // ==========================================
    const usersSearchInput = document.querySelector("#users-search");
    const usersRoleFilter = document.querySelector("#users-role-filter");
    const userCards = [...document.querySelectorAll(".user-card")];
    const usersResultsCount = document.querySelector("#users-results-count");
    const emptyUsersSearch = document.querySelector("#empty-users-search");

    const applyUsersFilter = () => {
        const query = usersSearchInput instanceof HTMLInputElement ? usersSearchInput.value.trim().toLocaleLowerCase("es") : "";
        const role = usersRoleFilter instanceof HTMLSelectElement ? usersRoleFilter.value.trim().toLocaleLowerCase("es") : "";

        let visibleCount = 0;
        userCards.forEach((card) => {
            const username = (card.dataset.username || "").toLocaleLowerCase("es");
            const fullname = (card.dataset.fullname || "").toLocaleLowerCase("es");
            const email = (card.dataset.email || "").toLocaleLowerCase("es");
            const identity = (card.dataset.identity || "").toLocaleLowerCase("es");
            const phone = (card.dataset.phone || "").toLocaleLowerCase("es");
            const userRole = (card.dataset.role || "").toLocaleLowerCase("es");

            const content = `${username} ${fullname} ${email} ${identity} ${phone}`;
            const matchesQuery = !query || content.includes(query);
            const matchesRole = !role || userRole === role;

            const isVisible = matchesQuery && matchesRole;
            card.hidden = !isVisible;
            if (isVisible) visibleCount++;
        });

        if (usersResultsCount) {
            usersResultsCount.textContent = `${visibleCount} ${visibleCount === 1 ? "usuario" : "usuarios"}`;
        }
        if (emptyUsersSearch) {
            emptyUsersSearch.hidden = visibleCount > 0;
        }
    };

    if (usersSearchInput instanceof HTMLInputElement) {
        usersSearchInput.addEventListener("input", applyUsersFilter);
    }
    if (usersRoleFilter instanceof HTMLSelectElement) {
        usersRoleFilter.addEventListener("change", applyUsersFilter);
    }

    // ==========================================
    // Modal de Detalle de Usuario ("Ver más")
    // ==========================================
    const userDetailDialog = document.querySelector("#user-detail-dialog");
    const closeUserDetail = document.querySelector("#close-user-detail");
    const userDetailPhoto = document.querySelector("#user-detail-photo");
    const userDetailFallback = document.querySelector("#user-detail-fallback");
    const userDetailName = document.querySelector("#user-detail-name");
    const userDetailHandle = document.querySelector("#user-detail-handle");
    const userDetailBadge = document.querySelector("#user-detail-badge");
    const userDetailUsername = document.querySelector("#user-detail-username");
    const userDetailRoleDesc = document.querySelector("#user-detail-role-desc");
    const userDetailIdentity = document.querySelector("#user-detail-identity");
    const userDetailEmail = document.querySelector("#user-detail-email");
    const userDetailPhone = document.querySelector("#user-detail-phone");
    const userDetailAddress = document.querySelector("#user-detail-address");

    const openUserDetails = (card) => {
        if (!(userDetailDialog instanceof HTMLDialogElement) || !card) return;

        const {
            username,
            fullname,
            role,
            roleLabel,
            email,
            identity,
            phone,
            address,
            image,
        } = card.dataset;

        const displayName = fullname || username;
        if (userDetailName) userDetailName.textContent = displayName;
        if (userDetailHandle) userDetailHandle.textContent = `@${username}`;

        if (userDetailBadge) {
            userDetailBadge.textContent = roleLabel || (role === "admin" ? "Administrador" : "Empleado");
            userDetailBadge.className = `user-role-badge ${role === "admin" ? "user-role-badge--admin" : "user-role-badge--employee"}`;
        }

        if (userDetailUsername) userDetailUsername.textContent = username;
        if (userDetailRoleDesc) {
            userDetailRoleDesc.textContent = role === "admin" ? "Administrador general del sistema" : "Empleado / Personal operativo";
        }
        if (userDetailIdentity) userDetailIdentity.textContent = identity || "No especificado";
        if (userDetailEmail) userDetailEmail.textContent = email || "No especificado";
        if (userDetailPhone) userDetailPhone.textContent = phone || "No especificado";
        if (userDetailAddress) userDetailAddress.textContent = address || "No especificada";

        if (image) {
            if (userDetailPhoto) {
                userDetailPhoto.src = image;
                userDetailPhoto.alt = displayName;
                userDetailPhoto.hidden = false;
            }
            if (userDetailFallback) userDetailFallback.hidden = true;
        } else {
            if (userDetailPhoto) userDetailPhoto.hidden = true;
            if (userDetailFallback) {
                userDetailFallback.textContent = (displayName.charAt(0) || "U").toUpperCase();
                userDetailFallback.hidden = false;
            }
        }

        userDetailDialog.showModal();
    };

    document.querySelectorAll(".user-more-btn").forEach((button) => {
        button.addEventListener("click", () => {
            const card = button.closest(".user-card");
            if (card) openUserDetails(card);
        });
    });

    if (closeUserDetail instanceof HTMLButtonElement && userDetailDialog instanceof HTMLDialogElement) {
        closeUserDetail.addEventListener("click", () => userDetailDialog.close());
        userDetailDialog.addEventListener("click", (event) => {
            if (event.target === userDetailDialog) {
                userDetailDialog.close();
            }
        });
    }

    updateSummary();
    updateResultsCount();
})();