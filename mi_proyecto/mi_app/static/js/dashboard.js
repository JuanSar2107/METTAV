(() => {
    const logoutButton = document.querySelector("#logout-button");
    const searchInput = document.querySelector("#inventory-search");
    const categoryFilter = document.querySelector("#category-filter");
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
            const content = normalizeSearchText(`${card.dataset.name || ""} ${card.dataset.code || ""} ${card.dataset.category || ""}`);
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

    tabButtons.forEach((btn) => {
        btn.addEventListener("click", () => {
            const targetId = btn.dataset.target;
            switchTab(targetId);
            window.location.hash = targetId === "section-users" ? "#usuarios" : "#inventario";
        });
    });

    if (window.location.hash === "#usuarios") {
        switchTab("section-users");
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