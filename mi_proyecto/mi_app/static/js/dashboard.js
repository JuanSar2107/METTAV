(() => {
    const logoutButton = document.querySelector("#logout-button");
    const searchInput = document.querySelector("#inventory-search");
    let cards = [...document.querySelectorAll(".inventory-card")];
    const resultsCount = document.querySelector("#results-count");
    const emptySearch = document.querySelector("#empty-search");
    const dialog = document.querySelector("#item-dialog");
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
        document.querySelector("#summary-items").textContent = cards.length;
        document.querySelector("#summary-units").textContent = totalUnits;
        document.querySelector("#summary-low-stock").textContent = lowStock;
    };

    const updateResultsCount = () => {
        const visibleCount = cards.filter((card) => !card.hidden).length;
        resultsCount.textContent = `${visibleCount} ${visibleCount === 1 ? "artículo" : "artículos"}`;
        emptySearch.hidden = visibleCount > 0;
    };

    if (searchInput instanceof HTMLInputElement) {
        searchInput.addEventListener("input", () => {
            const query = searchInput.value.trim().toLocaleLowerCase("es");
            cards.forEach((card) => {
                const content = `${card.dataset.name} ${card.dataset.code} ${card.dataset.category}`.toLocaleLowerCase("es");
                card.hidden = !content.includes(query);
            });
            updateResultsCount();
        });
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
                showToast(`Usuario ${createdUsername} creado con rol normal.`);
            } catch (error) {
                createUserMessage.textContent = error.message || "No se pudo conectar con el servidor.";
                createUserMessage.dataset.state = "error";
                createUserMessage.hidden = false;
            } finally {
                createUserButton.disabled = false;
            }
        });
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
        quantityInput.max = card.dataset.stock;
        quantityInput.value = Number(card.dataset.stock) > 0 ? "1" : "";
        quantityInput.disabled = Number(card.dataset.stock) === 0;
        withdrawButton.disabled = Number(card.dataset.stock) === 0;
        message.hidden = true;
        dialog.showModal();
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

    if (withdrawForm instanceof HTMLFormElement) {
        withdrawForm.addEventListener("submit", async (event) => {
            event.preventDefault();
            if (!selectedCard) {
                return;
            }

            const quantity = Number(quantityInput.value);
            const available = Number(selectedCard.dataset.stock);
            if (!Number.isInteger(quantity) || quantity < 1 || quantity > available) {
                showMessage("Indica una cantidad válida dentro del stock disponible.", "error");
                return;
            }

            withdrawButton.disabled = true;
            try {
                const response = await fetch(selectedCard.dataset.withdrawUrl, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ cantidad: quantity }),
                });
                const result = await response.json();
                if (!response.ok) {
                    throw new Error(result.error || "No se pudo retirar el artículo.");
                }

                selectedCard.dataset.stock = result.articulo.stock;
                const stockLabel = selectedCard.querySelector(".stock-label");
                selectedCard.querySelector(".stock-value").textContent = result.articulo.stock;
                selectedCard.querySelector(".stock-unit").textContent = `${selectedCard.dataset.unit} disponibles`;
                stockLabel.classList.toggle("is-low", result.articulo.stock <= 5);
                detailStock.textContent = `${result.articulo.stock} ${result.articulo.unidad}`;
                quantityInput.max = result.articulo.stock;
                quantityInput.value = result.articulo.stock > 0 ? "1" : "";
                quantityInput.disabled = result.articulo.stock === 0;
                updateSummary();
                dialog.close();
                showToast(`Retiraste ${quantity} ${quantity === 1 ? "unidad" : "unidades"} de ${selectedCard.dataset.name}.`);
            } catch (error) {
                showMessage(error.message || "No se pudo conectar con el servidor.", "error");
            } finally {
                withdrawButton.disabled = Number(selectedCard.dataset.stock) === 0;
            }
        });
    }

    updateSummary();
    updateResultsCount();
})();