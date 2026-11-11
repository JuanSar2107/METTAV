// Traducción de la interfaz al inglés. Solo cambia textos conocidos de la aplicación:
// los datos escritos por los usuarios y las descargas (Excel, PDF) siguen en español.
(() => {
    const STORAGE_KEY = "mettav-idioma";
    const readLanguage = () => {
        try {
            return window.localStorage.getItem(STORAGE_KEY) === "en" ? "en" : "es";
        } catch {
            return "es";
        }
    };
    const language = readLanguage();
    window.METTAV_IDIOMA = language;
    window.METTAV_LOCALE = language === "en" ? "en-US" : "es-CO";

    const dictionary = {
        "(ANULADO)": "(VOIDED)",
        "+ Agregar artículo": "+ Add item",
        "+ Agregar parte": "+ Add part",
        "1. Información del cliente": "1. Customer information",
        "2. Mercancía": "2. Goods",
        "ADMINISTRACIÓN": "ADMINISTRATION",
        "ADMINISTRACIÓN DE PERSONAL": "STAFF MANAGEMENT",
        "AUDITORÍA DE ZONA FRANCA": "FREE TRADE ZONE AUDIT",
        "Abre esta pestaña para consultar los movimientos registrados.": "Open this tab to see the recorded movements.",
        "Activos oficina METTAV": "METTAV office assets",
        "Actualizar por importación": "Updated by import",
        "Actualizar servicio": "Update service",
        "Administración": "Administration",
        "Administrador": "Administrator",
        "Administrador general del sistema": "General system administrator",
        "Administradores": "Administrators",
        "Agrega al menos un artículo a la remisión.": "Add at least one item to the delivery note.",
        "Agrega al menos una parte integrada.": "Add at least one integrated part.",
        "Agregar artículo": "Add item",
        "Agregar categoría nueva": "Add new category",
        "Agregar usuario nuevo": "Add new user",
        "Alerta de Stock Bajo": "Low Stock Alert",
        "Alguno de los artículos ya no existe. Recarga la página.": "One of the items no longer exists. Reload the page.",
        "Alta de artículo": "New item",
        "Anulación registrada.": "Void recorded.",
        "Anulada": "Voided",
        "Anulado": "Voided",
        "Anular": "Void",
        "Anular movimiento": "Void movement",
        "Apartamento": "Apartment",
        "Archivo Excel (.xlsx)": "Excel file (.xlsx)",
        "Artículo": "Item",
        "Artículo dado de baja. Su historial se conserva.": "Item written off. Its history is kept.",
        "Artículo eliminado.": "Item deleted.",
        "Artículo reactivado.": "Item reactivated.",
        "Artículo: código o nombre": "Item: code or name",
        "Artículos": "Items",
        "Artículos Totales": "Total Items",
        "Artículos dados de baja": "Written-off items",
        "Artículos del inventario": "Inventory items",
        "Asistente IA": "AI Assistant",
        "Asistente METTAV": "METTAV Assistant",
        "Asistente con IA": "AI assistant",
        "Auxiliar de inventarios": "Inventory assistant",
        "Auxiliares de inventarios": "Inventory assistants",
        "Bodega": "Warehouse",
        "Busca el artículo aunque no recuerdes el código, elígelo y súbele la existencia. Así no se repiten códigos.": "Find the item even if you don't remember its code, select it and add stock. This avoids duplicate codes.",
        "Busca y elige el artículo al que le vas a subir la existencia.": "Find and select the item you want to add stock to.",
        "Buscar artículo o categoría": "Search item or category",
        "Buscar empleado, artículo, formulario o referencia": "Search employee, item, form or reference",
        "Buscar por código o nombre, p. ej. ZF-MAQ-CO-001": "Search by code or name, e.g. ZF-MAQ-CO-001",
        "Buscar por nombre o código": "Search by name or code",
        "Buscar por nombre, usuario, correo, cédula o teléfono": "Search by name, username, email, ID or phone",
        "CC/ID:": "ID:",
        "CUENTA PERSONAL": "PERSONAL ACCOUNT",
        "Cada imagen puede pesar máximo 5 MB.": "Each image can be 5 MB at most.",
        "Cada línea debe indicar el artículo.": "Each line must specify the item.",
        "Cada línea debe tener una cantidad entera mayor que cero.": "Each line must have a whole quantity greater than zero.",
        "Cambiar": "Change",
        "Cancelado": "Cancelled",
        "Cancelar": "Cancel",
        "Cantidad": "Quantity",
        "Cantidad de la parte": "Part quantity",
        "Cantidad del equipo": "Equipment quantity",
        "Cargando movimientos...": "Loading movements...",
        "Cargando reporte...": "Loading report...",
        "Cargando trazabilidad...": "Loading traceability...",
        "Categoría": "Category",
        "Categoría creada con éxito.": "Category created successfully.",
        "Categoría del código": "Code category",
        "Cerrar": "Close",
        "Cerrar asistente": "Close assistant",
        "Cerrar detalle": "Close details",
        "Cerrar formulario": "Close form",
        "Cerrar perfil": "Close profile",
        "Cerrar sesión": "Log out",
        "Cerrar trazabilidad": "Close traceability",
        "Cerrar ventana": "Close window",
        "Cliente": "Customer",
        "Cliente o NIT": "Customer or tax ID",
        "Cliente y estado del servicio": "Customer and service status",
        "Coincide": "Matches",
        "Columnas que reconoce: Código interno, Código ZF, Categoría, Ubicación, Tipo, Consecutivo, Descripción y Marca. Opcionales: Grupo, Subpartida, valor USD, Procedencia, Estado, Cantidad, Unidad, Serial, Responsable, Fecha de ingreso, Documento soporte, Fecha de retiro y razón del retiro.": "Recognized columns: Código interno, Código ZF, Categoría, Ubicación, Tipo, Consecutivo, Descripción and Marca. Optional: Grupo, Subpartida, valor USD, Procedencia, Estado, Cantidad, Unidad, Serial, Responsable, Fecha de ingreso, Documento soporte, Fecha de retiro and razón del retiro.",
        "Comedor": "Cafeteria",
        "Comparar": "Compare",
        "Comparar solo artículos con código ZF": "Compare only items with a ZF code",
        "Con IA de Gemini · consulta el inventario": "Powered by Gemini AI · check the inventory",
        "Conciliación con Sizfra": "Sizfra reconciliation",
        "Confirma tu contraseña en 'contrasena' para eliminar la cuenta.": "Confirm your password to delete the account.",
        "Consulta o descarga en Excel el inventario y los movimientos, y concilia contra Sizfra.": "View or download the inventory and movements in Excel, and reconcile against Sizfra.",
        "Contacto": "Contact",
        "Contraseña": "Password",
        "Copia de seguridad": "Backup",
        "Correo electrónico": "Email",
        "Crear artículo": "Create item",
        "Crear remisión": "Create delivery note",
        "Crear usuario": "Create user",
        "Cuenta": "Account",
        "Cuenta eliminada.": "Account deleted.",
        "Código": "Code",
        "Código ZF": "ZF code",
        "Código consecutivo": "Sequential code",
        "Código interno": "Internal code",
        "Código o nombre": "Code or name",
        "Da de baja en un solo registro el equipo y las partes que se le integraron. Si a alguna línea le falta stock, no se descuenta nada.": "Writes off the equipment and its integrated parts in a single record. If any line is short of stock, nothing is deducted.",
        "Dar de baja": "Write off",
        "Datos de Sizfra del movimiento": "Sizfra data for this movement",
        "Datos de la salida": "Exit details",
        "Datos de zona franca": "Free trade zone data",
        "Datos de zona franca (opcionales)": "Free trade zone data (optional)",
        "Debe tener una columna de código y otra de saldo o cantidad.": "It must have a code column and a balance or quantity column.",
        "Debes enviar usuario y contraseña.": "You must provide a username and password.",
        "Debes indicar el motivo de la anulación.": "You must give a reason for voiding.",
        "Debes iniciar sesión.": "You must log in.",
        "Demasiados intentos fallidos.": "Too many failed attempts.",
        "Descarga toda la información: datos, documentos e imágenes. Guárdala fuera del servidor y en un lugar seguro, porque contiene información sensible.": "Downloads all information: data, documents and images. Store it off the server in a safe place, because it contains sensitive information.",
        "Descargar Excel": "Download Excel",
        "Descargar PDF": "Download PDF",
        "Descargar copia": "Download backup",
        "Descargar copia de seguridad": "Download backup",
        "Descargar el manual de usuario": "Download the user manual",
        "Descripción": "Description",
        "Desde": "From",
        "Diferencia": "Difference",
        "Dirección": "Address",
        "Dirección de residencia": "Home address",
        "Directorio de usuarios registrados y colaboradores del sistema METTAV.": "Directory of registered users and staff of the METTAV system.",
        "Documento de entrega": "Delivery document",
        "Documento de ingreso": "Entry document",
        "Documento de retiro": "Withdrawal document",
        "Documento soporte": "Supporting document",
        "Día": "Day",
        "ENTRADA DE MERCANCÍA": "GOODS RECEIPT",
        "ENTREGA A CLIENTE": "CUSTOMER DELIVERY",
        "Editar artículo": "Edit item",
        "Editar mi perfil": "Edit my profile",
        "El archivo debe ser un Excel .xlsx.": "The file must be an Excel .xlsx.",
        "El archivo no es un Excel (.xlsx) válido.": "The file is not a valid Excel (.xlsx).",
        "El archivo no es una imagen válida.": "The file is not a valid image.",
        "El archivo no tiene filas con código y saldo.": "The file has no rows with code and balance.",
        "El archivo supera el límite de 5 MB. Elige otro.": "The file exceeds the 5 MB limit. Choose another one.",
        "El artículo no está dado de baja.": "The item is not written off.",
        "El artículo no existe.": "The item does not exist.",
        "El asistente no está configurado: falta GEMINI_API_KEY.": "The assistant is not configured: GEMINI_API_KEY is missing.",
        "El campo 'usuario' es obligatorio.": "The username field is required.",
        "El campo 'usuario' no puede estar vacío.": "The username field cannot be empty.",
        "El cliente no puede superar 160 caracteres.": "The customer cannot exceed 160 characters.",
        "El correo del cliente no es válido.": "The customer's email is not valid.",
        "El correo o número de identidad ya está en uso.": "The email or ID number is already in use.",
        "El código ZF solo admite letras, números y guiones (máximo 24).": "The ZF code only allows letters, numbers and hyphens (24 max).",
        "El código interno solo admite letras, números y guiones (máximo 32).": "The internal code only allows letters, numbers and hyphens (32 max).",
        "El código se genera solo y sube de 1 en 1. Puedes cambiarlo; si lo borras, vuelve al automático. La categoría y el grupo se toman de aquí.": "The code is generated automatically and goes up by 1. You can change it; if you clear it, the automatic code returns. The category and group are taken from here.",
        "El documento soporte debe ser un PDF o una imagen (JPG, PNG o WEBP).": "The supporting document must be a PDF or an image (JPG, PNG or WEBP).",
        "El empleado ingresa y retira artículos. El auxiliar de inventarios además ve el historial, la trazabilidad y los reportes. Solo el administrador crea códigos de inventario y usuarios.": "Employees add and withdraw items. Inventory assistants can also see the history, traceability and reports. Only administrators create inventory codes and users.",
        "El envío es demasiado grande. Cada archivo puede pesar máximo 5 MB.": "The upload is too large. Each file can be 5 MB at most.",
        "El equipo principal no es válido.": "The main equipment is not valid.",
        "El estado no puede superar 40 caracteres.": "The condition cannot exceed 40 characters.",
        "El formulario de Sizfra solo admite letras, números y guiones (máximo 24).": "The Sizfra form only allows letters, numbers and hyphens (24 max).",
        "El grupo de inventario debe ser 001, 002, 003 o 004.": "The inventory group must be 001, 002, 003 or 004.",
        "El motivo no puede superar 500 caracteres.": "The reason cannot exceed 500 characters.",
        "El movimiento no existe.": "The movement does not exist.",
        "El movimiento no tiene documento soporte.": "The movement has no supporting document.",
        "El nombre de la categoría es obligatorio.": "The category name is required.",
        "El nombre de la categoría no puede superar los 60 caracteres.": "The category name cannot exceed 60 characters.",
        "El nombre es obligatorio y no puede superar 120 caracteres.": "The name is required and cannot exceed 120 characters.",
        "El nombre o correo supera el largo permitido.": "The name or email is too long.",
        "El reporte de Sizfra debe ser un archivo .xlsx o .csv.": "The Sizfra report must be an .xlsx or .csv file.",
        "El rol debe ser empleado o auxiliar de inventarios.": "The role must be employee or inventory assistant.",
        "El stock debe ser un número entero igual o mayor que cero.": "Stock must be a whole number equal to or greater than zero.",
        "El stock no puede ser negativo.": "Stock cannot be negative.",
        "El tipo no puede superar 8 caracteres.": "The type cannot exceed 8 characters.",
        "El valor FOB debe ser un número en dólares, por ejemplo 1200 o 1200,50.": "The FOB value must be a number in dollars, for example 1200 or 1200.50.",
        "El valor FOB debe ser un número positivo.": "The FOB value must be a positive number.",
        "Electrodomésticos": "Appliances",
        "Elegir": "Choose",
        "Elige la categoría, la ubicación y el tipo del código.": "Choose the code's category, location and type.",
        "Elige un reporte para verlo aquí.": "Choose a report to see it here.",
        "Eliminar": "Delete",
        "Eliminar artículo": "Delete item",
        "Empleado": "Employee",
        "Empleado / Personal operativo": "Employee / Operations staff",
        "Empleados / Usuarios": "Employees / Users",
        "En servicio": "In service",
        "Entregado": "Delivered",
        "Enviar": "Send",
        "Enviar pregunta": "Send question",
        "Envía la consulta en formato JSON.": "Send the query as JSON.",
        "Envía los datos de la remisión en formato JSON.": "Send the delivery note data as JSON.",
        "Envía los datos de la salida en formato JSON.": "Send the exit data as JSON.",
        "Envía los datos del servicio en formato JSON.": "Send the service data as JSON.",
        "Envía un objeto JSON válido.": "Send a valid JSON object.",
        "Equipo": "Equipment",
        "Equipo (opcional)": "Equipment (optional)",
        "Equipo principal": "Main equipment",
        "Equipos": "Equipment",
        "Equipos de bodega": "Warehouse equipment",
        "Equipos operativos bodega": "Warehouse operating equipment",
        "Error al conectar con el servidor.": "Error connecting to the server.",
        "Escribe tu pregunta...": "Type your question...",
        "Escribe un correo electrónico válido.": "Enter a valid email address.",
        "Escribe una pregunta.": "Type a question.",
        "Ese correo ya está en uso.": "That email is already in use.",
        "Ese número de identidad ya está en uso.": "That ID number is already in use.",
        "Ese usuario ya está registrado.": "That username is already registered.",
        "Estado": "Status",
        "Estado de la mercancía": "Goods condition",
        "Estado de servicio": "Service status",
        "Estado del servicio": "Service status",
        "Este movimiento ya está anulado.": "This movement is already voided.",
        "Extranjera": "Foreign",
        "Fabricación": "Manufacturing",
        "Fecha": "Date",
        "Fecha de ingreso": "Entry date",
        "Fecha de retiro": "Withdrawal date",
        "Filtrar movimientos por categoría": "Filter movements by category",
        "Filtrar por categoría": "Filter by category",
        "Filtrar por rol": "Filter by role",
        "Formulario": "Form",
        "Foto de perfil": "Profile photo",
        "GESTIÓN DE BODEGA": "WAREHOUSE MANAGEMENT",
        "GESTIÓN DE CATEGORÍAS": "CATEGORY MANAGEMENT",
        "Gemini devolvió una respuesta no válida.": "Gemini returned an invalid response.",
        "Gemini no devolvió una respuesta. Intenta reformular la pregunta.": "Gemini did not return an answer. Try rephrasing the question.",
        "Generando...": "Generating...",
        "Grupo": "Group",
        "Grupo Sizfra": "Sizfra group",
        "Grupo de Sizfra": "Sizfra group",
        "Grupo de inventario": "Inventory group",
        "Guardar": "Save",
        "Guardar artículo": "Save item",
        "Guardar cambios": "Save changes",
        "Guardar categoría": "Save category",
        "Guardar perfil": "Save profile",
        "Has hecho muchas consultas seguidas.": "You have made many queries in a row.",
        "Hasta": "To",
        "Herramienta / artículo": "Tool / item",
        "Herramientas": "Tools",
        "Herramientas eléctricas": "Power tools",
        "Herramientas manuales": "Hand tools",
        "Historial": "History",
        "Historial de movimientos": "Movement history",
        "Historial de movimientos de inventario": "Inventory movement history",
        "INFORMACIÓN PERSONAL": "PERSONAL INFORMATION",
        "INICIAR SESIÓN": "LOG IN",
        "INTEGRACIÓN DE PARTES": "PARTS INTEGRATION",
        "Imagen": "Image",
        "Imagen actual.": "Current image.",
        "Importación Excel": "Excel import",
        "Importar": "Import",
        "Importar Excel": "Import Excel",
        "Importar inventario desde Excel": "Import inventory from Excel",
        "Imágenes del artículo (opcionales, hasta 3)": "Item images (optional, up to 3)",
        "Indica 'usuario' o 'contrasena' para actualizar.": "Provide a username or password to update.",
        "Indica el NIT o la cédula del cliente, por ejemplo 900.059.427-0.": "Enter the customer's tax ID, for example 900.059.427-0.",
        "Indica el motivo de la anulación.": "Give a reason for voiding.",
        "Indica el nombre del cliente.": "Enter the customer's name.",
        "Indica la referencia del equipo al que se integran las partes.": "Enter the reference of the equipment the parts are integrated into.",
        "Indica una cantidad entera mayor que cero.": "Enter a whole quantity greater than zero.",
        "Indica una cantidad válida dentro del stock disponible.": "Enter a valid quantity within the available stock.",
        "Ingresar": "Add",
        "Ingresar existencias": "Add stock",
        "Ingresar objeto": "Add item",
        "Ingreso": "Entry",
        "Ingresos y retiros": "Entries and withdrawals",
        "Ingresos y retiros de herramientas y materiales.": "Entries and withdrawals of tools and materials.",
        "Iniciar sesión | METTAV Group SAS": "Log in | METTAV Group SAS",
        "Inventario": "Inventory",
        "Inventario actual": "Current inventory",
        "JPEG, PNG o WEBP; máximo 5 MB cada una. Si no eliges una, se conserva la actual.": "JPEG, PNG or WEBP; 5 MB max each. If you don't choose one, the current one is kept.",
        "JPEG, PNG o WEBP; máximo 5 MB cada una. Sin imágenes se usa la de la bodega.": "JPEG, PNG or WEBP; 5 MB max each. Without images, the warehouse image is used.",
        "JPEG, PNG o WEBP; máximo 5 MB.": "JPEG, PNG or WEBP; 5 MB max.",
        "La cantidad supera el límite original del artículo.": "The quantity exceeds the item's original limit.",
        "La carpeta de imágenes no está permitida.": "That image folder is not allowed.",
        "La categoría, unidad o ubicación supera el largo permitido.": "The category, unit or location is too long.",
        "La descripción es obligatoria y no puede superar 4000 caracteres.": "The description is required and cannot exceed 4000 characters.",
        "La fecha 'desde' no puede ser posterior a 'hasta'.": "The 'from' date cannot be after the 'to' date.",
        "La fecha debe tener el formato AAAA-MM-DD.": "The date must use the YYYY-MM-DD format.",
        "La identidad, teléfono o dirección supera el largo permitido.": "The ID, phone or address is too long.",
        "La imagen debe ser JPEG, PNG o WEBP.": "The image must be JPEG, PNG or WEBP.",
        "La imagen supera el límite de 5 MB.": "The image exceeds the 5 MB limit.",
        "La imagen tiene dimensiones demasiado grandes.": "The image dimensions are too large.",
        "La marca no puede superar 80 caracteres.": "The brand cannot exceed 80 characters.",
        "La operación de Sizfra debe ser un número, por ejemplo 420.": "The Sizfra operation must be a number, for example 420.",
        "La procedencia debe ser Nacional o Extranjera.": "The origin must be Domestic or Foreign.",
        "La salida no existe.": "The exit does not exist.",
        "La subpartida arancelaria debe tener el formato 8413.30.10.00.": "The tariff code must use the format 8413.30.10.00.",
        "Las observaciones no pueden superar 2000 caracteres.": "Notes cannot exceed 2000 characters.",
        "Limpiar": "Clear",
        "Limpiar filtros": "Clear filters",
        "Los artículos se identifican por el código ZF. Si un código ya existe se actualizan sus datos, pero no su stock.": "Items are identified by ZF code. If a code already exists, its data is updated but not its stock.",
        "METTAV, panel de control": "METTAV, control panel",
        "Mantenimiento": "Maintenance",
        "Manual de usuario": "User manual",
        "Maquinaria": "Machinery",
        "Maquinaria pesada": "Heavy machinery",
        "Marca": "Brand",
        "Materia prima": "Raw material",
        "Mercancía de clientes (opcional)": "Customer goods (optional)",
        "Mercancía que ingresa para la prestación de un servicio": "Goods received to provide a service",
        "Mi perfil": "My profile",
        "Mobiliario": "Furniture",
        "Mostrar contraseña": "Show password",
        "Motivo": "Reason",
        "Movimiento": "Movement",
        "Movimientos": "Movements",
        "NIT / CC": "Tax ID",
        "Nacional": "Domestic",
        "No especificada": "Not specified",
        "No especificado": "Not specified",
        "No había cambios.": "There were no changes.",
        "No hay artículos que coincidan con la búsqueda.": "No items match the search.",
        "No hay movimientos que coincidan con los filtros.": "No movements match the filters.",
        "No hay registros con esos filtros.": "No records match those filters.",
        "No hay registros para ese código.": "There are no records for that code.",
        "No hay suficientes unidades en stock.": "There are not enough units in stock.",
        "No puedes eliminar al único administrador.": "You can't delete the only administrator.",
        "No se encontraron usuarios que coincidan con la búsqueda.": "No users match the search.",
        "No se encontró el archivo del documento soporte.": "The supporting document file was not found.",
        "No se encontró ningún artículo. Si es nuevo, un administrador debe crear su código con \"Agregar artículo\".": "No item found. If it is new, an administrator must create its code with \"Add item\".",
        "No se pudo anular el movimiento.": "The movement could not be voided.",
        "No se pudo calcular el código siguiente.": "The next code could not be calculated.",
        "No se pudo cargar el historial.": "The history could not be loaded.",
        "No se pudo cargar la trazabilidad.": "Traceability could not be loaded.",
        "No se pudo completar la solicitud.": "The request could not be completed.",
        "No se pudo conectar con Gemini. Revisa la conexión a internet.": "Could not connect to Gemini. Check the internet connection.",
        "No se pudo conectar con el servidor.": "Could not connect to the server.",
        "No se pudo conectar con el servidor. Inténtalo de nuevo.": "Could not connect to the server. Try again.",
        "No se pudo crear el usuario.": "The user could not be created.",
        "No se pudo crear la categoría.": "The category could not be created.",
        "No se pudo crear la copia de seguridad.": "The backup could not be created.",
        "No se pudo crear la remisión.": "The delivery note could not be created.",
        "No se pudo descargar el reporte.": "The report could not be downloaded.",
        "No se pudo eliminar el artículo.": "The item could not be deleted.",
        "No se pudo generar el archivo.": "The file could not be generated.",
        "No se pudo generar el reporte.": "The report could not be generated.",
        "No se pudo guardar el artículo.": "The item could not be saved.",
        "No se pudo guardar el artículo. Inténtalo de nuevo.": "The item could not be saved. Try again.",
        "No se pudo guardar el perfil.": "The profile could not be saved.",
        "No se pudo guardar el servicio.": "The service could not be saved.",
        "No se pudo guardar la categoría.": "The category could not be saved.",
        "No se pudo guardar la importación. Inténtalo de nuevo.": "The import could not be saved. Try again.",
        "No se pudo importar el archivo.": "The file could not be imported.",
        "No se pudo ingresar el artículo.": "The item could not be added.",
        "No se pudo ingresar la existencia.": "The stock could not be added.",
        "No se pudo inicializar el formulario de autenticación.": "The login form could not be initialized.",
        "No se pudo obtener una respuesta.": "An answer could not be obtained.",
        "No se pudo reactivar el artículo.": "The item could not be reactivated.",
        "No se pudo registrar la salida.": "The exit could not be recorded.",
        "No se pudo retirar el artículo.": "The item could not be withdrawn.",
        "No tienes permiso para cambiar el servicio.": "You don't have permission to change the service.",
        "No tienes permiso para ver el historial de movimientos.": "You don't have permission to see the movement history.",
        "No tienes permiso para ver la trazabilidad.": "You don't have permission to see traceability.",
        "No tienes permiso para ver los documentos soporte.": "You don't have permission to see supporting documents.",
        "No tienes permiso para ver los reportes.": "You don't have permission to see reports.",
        "Nombre": "Name",
        "Nombre completo": "Full name",
        "Nombre de Usuario": "Username",
        "Nombre de la categoría": "Category name",
        "Nombre de usuario": "Username",
        "Nueva conversación": "New conversation",
        "N° de Identificación": "ID number",
        "Número": "Number",
        "Número de identidad": "ID number",
        "Observaciones": "Notes",
        "Observaciones o razón": "Notes or reason",
        "Ocultar contraseña": "Hide password",
        "Opcionales. Se guardan con el ingreso o el retiro para cruzarlo con Sizfra.": "Optional. Saved with the entry or withdrawal to cross-check against Sizfra.",
        "Operación Sizfra": "Sizfra operation",
        "Operativa": "Operations",
        "Operativos": "Operations",
        "Otra remisión se guardó al mismo tiempo. Inténtalo de nuevo.": "Another delivery note was saved at the same time. Try again.",
        "Otro": "Other",
        "Otros": "Other",
        "PDF o imagen; máximo 5 MB.": "PDF or image; 5 MB max.",
        "Panel de control | METTAV Group SAS": "Control panel | METTAV Group SAS",
        "Para cambiar la contraseña indica la actual en 'contrasena_actual'.": "To change your password, enter your current one.",
        "Para no repetir códigos, súbele la existencia a uno de estos:": "To avoid duplicate codes, add stock to one of these:",
        "Para reparación": "For repair",
        "Parte": "Part",
        "Parte integrada": "Integrated part",
        "Parte: código o nombre": "Part: code or name",
        "Partes integradas": "Integrated parts",
        "Pensando...": "Thinking...",
        "Perfil": "Profile",
        "Petición rechazada: origen no permitido.": "Request rejected: origin not allowed.",
        "Pregunta para el asistente": "Question for the assistant",
        "Procedencia": "Origin",
        "Proceso": "Process",
        "Protección personal": "Personal protection",
        "Quitar": "Remove",
        "Quitar esta imagen": "Remove this image",
        "Quitar parte": "Remove part",
        "Qué partes se integraron a cada equipo, cuándo y con qué formulario.": "Which parts were integrated into each piece of equipment, when and with which form.",
        "REGISTRO DE BODEGA": "WAREHOUSE LOG",
        "Razón del retiro": "Withdrawal reason",
        "Reactivar": "Reactivate",
        "Reactivar artículo": "Reactivate item",
        "Recibido": "Received",
        "Referencia": "Reference",
        "Referencia del equipo": "Equipment reference",
        "Registrada": "Recorded",
        "Registrar salida": "Record exit",
        "Remisiones de salida": "Delivery notes",
        "Remisión": "Delivery note",
        "Remisión No 0001": "Delivery note No 0001",
        "Remisión de salida": "Delivery note",
        "Reparación": "Repair",
        "Reporte exportado de Sizfra (.xlsx o .csv)": "Report exported from Sizfra (.xlsx or .csv)",
        "Reportes": "Reports",
        "Requiere reabastecimiento": "Needs restocking",
        "Responsable": "Person in charge",
        "Resumen de usuarios": "User summary",
        "Resumen del inventario": "Inventory summary",
        "Retirar objeto": "Withdraw item",
        "Retiro": "Withdrawal",
        "Rol": "Role",
        "Rol de acceso": "Access role",
        "Saldo Sizfra": "Sizfra balance",
        "Salida": "Exit",
        "Salida integrada": "Integrated exit",
        "Salidas integradas": "Integrated exits",
        "Salieron del inventario, pero conservan su código y su historial. Desde aquí se pueden reactivar.": "They left the inventory but keep their code and history. They can be reactivated from here.",
        "Se anulará TODA la remisión, con todas sus líneas.": "The ENTIRE delivery note will be voided, with all its lines.",
        "Se define con el primer ingreso": "Set by the first entry",
        "Se descuenta del stock cada artículo, queda en el historial y se abre la remisión para imprimirla o guardarla como PDF.": "Each item is deducted from stock and logged in the history, and the delivery note opens to print or save as PDF.",
        "Se quitará al guardar.": "Will be removed when saved.",
        "Se retira para mantenimiento del banco": "Withdrawn for bench maintenance",
        "Secciones del panel": "Panel sections",
        "Selecciona el archivo Excel (.xlsx) del inventario.": "Select the inventory Excel file (.xlsx).",
        "Selecciona el reporte de inventario exportado de Sizfra (.xlsx o .csv).": "Select the inventory report exported from Sizfra (.xlsx or .csv).",
        "Selecciona una imagen.": "Select an image.",
        "Servicio": "Service",
        "Servicio actualizado.": "Service updated.",
        "Sesión cerrada.": "Logged out.",
        "Si eliges una imagen, aquí verás cuál es antes de guardar.": "If you choose an image, you'll see it here before saving.",
        "Si se deja vacía, se usa el equipo": "If left empty, the equipment is used",
        "Sin consecutivo: escribe el código a mano más abajo.": "No sequence: type the code manually below.",
        "Sin código consecutivo": "No sequential code",
        "Sin estado": "No status",
        "Sin grupo": "No group",
        "Sin grupo de Sizfra": "No Sizfra group",
        "Sin imagen.": "No image.",
        "Sin indicar": "Not specified",
        "Sin servicio": "No service",
        "Solo en Sizfra": "Only in Sizfra",
        "Solo en la app": "Only in the app",
        "Solo ingresos": "Entries only",
        "Solo retiros": "Withdrawals only",
        "Solo un administrador puede crear usuarios.": "Only an administrator can create users.",
        "Solo un administrador puede descargar copias de seguridad.": "Only an administrator can download backups.",
        "Solo un administrador puede gestionar los artículos.": "Only an administrator can manage items.",
        "Solo un administrador puede ver la lista de usuarios.": "Only an administrator can see the user list.",
        "Stock actual": "Current stock",
        "Stock app": "App stock",
        "Stock inicial": "Initial stock",
        "Stock más alto": "Highest stock",
        "Subpartida": "Tariff code",
        "Subpartida arancelaria": "Tariff code",
        "TRAZABILIDAD": "TRACEABILITY",
        "Teléfono": "Phone",
        "Teléfono de contacto": "Contact phone",
        "Terminado": "Finished",
        "Tipo": "Type",
        "Tipo de servicio": "Service type",
        "Todas": "All",
        "Todas las categorías": "All categories",
        "Todavía no hay movimientos registrados.": "There are no recorded movements yet.",
        "Todo en orden": "All good",
        "Todos": "All",
        "Todos los roles": "All roles",
        "Total en stock": "Total in stock",
        "Total registrados": "Total registered",
        "Ubicación": "Location",
        "Ubicación del código": "Code location",
        "Un mismo artículo no puede aparecer dos veces en la remisión.": "The same item can't appear twice in the delivery note.",
        "Un mismo artículo no puede aparecer dos veces en la salida.": "The same item can't appear twice in the exit.",
        "Una remisión admite máximo 100 líneas.": "A delivery note allows 100 lines at most.",
        "Una salida admite máximo 50 partes integradas.": "An exit allows 50 integrated parts at most.",
        "Unidad": "Unit",
        "Unidades Disponibles": "Available Units",
        "Unidades a ingresar": "Units to add",
        "Unidades a retirar": "Units to withdraw",
        "Usuario": "User",
        "Usuario o contraseña incorrectos.": "Incorrect username or password.",
        "Usuarios y Empleados": "Users and Employees",
        "Valor FOB": "FOB value",
        "Valor FOB (USD)": "FOB value (USD)",
        "Valor total": "Total value",
        "Ver": "View",
        "Ver más": "See more",
        "Ver trazabilidad completa": "View full traceability",
        "Vigente": "Active",
        "Vista previa de la imagen": "Image preview",
        "Vista previa del documento": "Document preview",
        "artículos": "items",
        "categorías": "categories",
        "disponibles": "available",
        "unidades": "units",
        "usuarios": "users",
        "¿Ya existe?": "Already exists?",
        "➕ Agregar categoría nueva...": "➕ Add new category...",
    };

    const compact = (text) => text.replace(/\s+/g, " ").trim();

    // Textos con datos variables. Los datos capturados se dejan tal cual, salvo cuando pasan por t().
    const patterns = [
        [/^Bienvenido, (.+)\. Consulta y administra tus artículos\.$/, "Welcome, $1. View and manage your items."],
        [/^Hola, (.+)\. Puedo ayudarte con preguntas sobre el inventario, por ejemplo: "¿Qué artículos tienen stock bajo\?" o "¿Dónde están los guantes\?"\.$/, 'Hello, $1. I can help you with questions about the inventory, for example: "Which items are low on stock?" or "Where are the gloves?".'],
        [/^Ej\. (.+)$/, (_m, value) => `E.g. ${t(value)}`],
        [/^Imagen (\d) \(principal\)$/, "Image $1 (main)"],
        [/^Imagen (\d)$/, "Image $1"],
        [/^Vista previa de la imagen (\d)$/, "Preview of image $1"],
        [/^Ver imagen (\d+) de (\d+)$/, "See image $1 of $2"],
        [/^Vas a subir: (.+)$/, "You will upload: $1"],
        [/^Ver más sobre (.+)$/, (_m, name) => `See more about ${t(name)}`],
        [/^Eliminar (.+)$/, (_m, name) => `Delete ${t(name)}`],
        [/^1 (unidades|unidad)$/, "1 unit"],
        [/^(\d+) (unidades|unidad)$/, "$1 units"],
        [/^(\d+) categorías?$/, (_m, n) => `${n} ${n === "1" ? "category" : "categories"}`],
        [/^(\d+) artículos?$/, (_m, n) => `${n} ${n === "1" ? "item" : "items"}`],
        [/^(\d+) usuarios?$/, (_m, n) => `${n} ${n === "1" ? "user" : "users"}`],
        [/^(.+) disponibles$/, (_m, unit) => `${t(unit)} available`],
        [/^(.+) · existencia actual: (\S+) (.+)$/, (_m, code, stock, unit) => `${code} · current stock: ${stock} ${t(unit)}`],
        [/^(Ingreso|Retiro) de (\d+) (.+?)( \(ANULADO\))?$/, (_m, type, qty, unit, voided) => `${t(type)} of ${qty} ${t(unit)}${voided ? " (VOIDED)" : ""}`],
        [/^"(.+)" no es un artículo del inventario\. Elígelo de la lista\.$/, '"$1" is not an inventory item. Choose it from the list.'],
        [/^Se anulará TODA la salida integrada #(\d+), con todas sus líneas\.$/, "The ENTIRE integrated exit #$1 will be voided, with all its lines."],
        [/^Se anulará: (Ingreso|Retiro) de (\d+) (.+?) de (.+)\.$/, (_m, type, qty, unit, item) => `To be voided: ${t(type)} of ${qty} ${t(unit)} of ${t(item)}.`],
        [/^El stock se corrige solo y el registro queda visible como anulado\.$/, "Stock is corrected automatically and the record stays visible as voided."],
        [/^Motivo de la anulación:$/, "Reason for voiding:"],
        [/^¿Quitar "(.+)" del inventario\?$/, (_m, name) => `Remove "${t(name)}" from the inventory?`],
        [/^Si tiene movimientos no se borra: queda dado de baja, conserva su historial y se puede reactivar desde Reportes\.$/, "If it has movements it isn't deleted: it is written off, keeps its history and can be reactivated from Reports."],
        [/^Motivo \(opcional\):$/, "Reason (optional):"],
        [/^¿Devolver (\S+) al inventario con (\S+) (.+)\?$/, (_m, code, stock, unit) => `Return ${code} to the inventory with ${stock} ${t(unit)}?`],
        [/^Motivo: (.+) \(@(.+)\)$/, (_m, reason, user) => `Reason: ${t(reason)} (@${user})`],
        [/^Anulado por @(.+?): (.+)$/, (_m, user, reason) => `Voided by @${user}: ${t(reason)}`],
        [/^Mostrando (\d+) de (\d+) movimientos$/, "Showing $1 of $2 movements"],
        [/^Mostrando (\d+) de (\d+) (artículos|usuarios)$/, (_m, a, b, kind) => `Showing ${a} of ${b} ${t(kind)}`],
        [/^(\d+) registros, del más reciente al más antiguo\.$/, "$1 records, from newest to oldest."],
        [/^(\d+) artículos dados de baja\.$/, "$1 written-off items."],
        [/^(\d+) remisiones\. Haz clic en el número para abrirla e imprimirla\.$/, "$1 delivery notes. Click the number to open and print it."],
        [/^(\d+) salidas integradas\.$/, "$1 integrated exits."],
        [/^(\d+) coinciden, (\d+) con diferencia, (\d+) solo en Sizfra y (\d+) solo en la app\.$/, "$1 match, $2 differ, $3 only in Sizfra and $4 only in the app."],
        [/^(\d+) ingresos \((\d+) unidades\) y (\d+) retiros \((\d+) unidades\)\.(?: (\d+) anulados, no incluidos en estos totales\.)?$/, (_m, a, b, c, d, voided) => `${a} entries (${b} units) and ${c} withdrawals (${d} units).${voided ? ` ${voided} voided, not included in these totals.` : ""}`],
        [/^(.+): (\d+) artículos, (\d+) unidades(, USD .+)?$/, (_m, group, items, units, value) => `${t(group)}: ${items} items, ${units} units${value || ""}`],
        [/^Columnas usadas del archivo: código "(.+)", saldo "(.+)"\.$/, 'Columns used from the file: code "$1", balance "$2".'],
        [/^Categoría "(.+)" guardada correctamente\.$/, 'Category "$1" saved successfully.'],
        [/^Código (\S+)\. El código y el stock no se cambian aquí\.$/, "Code $1. The code and stock are not changed here."],
        [/^Código cambiado a mano\. Si lo borras, vuelve al automático: (.+)\.$/, "Code changed manually. If you clear it, the automatic code returns: $1."],
        [/^Este artículo quedará con el código (.+)\. Se genera solo y sube de 1 en 1; puedes cambiarlo\.$/, "This item will get code $1. It is generated automatically and goes up by 1; you can change it."],
        [/^Documento soporte: (.+)$/, "Supporting document: $1"],
        [/^Observaciones: (.+)$/, (_m, notes) => `Notes: ${t(notes)}`],
        [/^Origen: (.+)$/, (_m, origin) => `Origin: ${t(origin)}`],
        [/^Sizfra: (.+)$/, (_m, parts) => `Sizfra: ${parts.replace(/operación/g, "operation").replace(/formulario/g, "form")}`],
        [/^Equipo de la salida integrada #(\d+) \((.+)\)$/, (_m, id, process) => `Equipment of integrated exit #${id} (${t(process)})`],
        [/^Integrada en (.+) · salida #(\d+) \((.+)\)$/, (_m, ref, id, process) => `Integrated into ${t(ref)} · exit #${id} (${t(process)})`],
        [/^Integrada en (.+) #(\d+)$/, (_m, ref, id) => `Integrated into ${t(ref)} #${id}`],
        [/^(.+) #(\d+)$/, (_m, name, id) => `${t(name)} #${id}`],
        [/^Importación lista: (\d+) creados, (\d+) actualizados(?:, (\d+) filas con error)?(?:, (\d+) avisos)?\.$/, (_m, a, b, c, d) => `Import finished: ${a} created, ${b} updated${c ? `, ${c} rows with errors` : ""}${d ? `, ${d} warnings` : ""}.`],
        [/^Fila (\d+)(.*): aviso, (.+)$/, "Row $1$2: warning, $3"],
        [/^Fila (\d+)(.*): (.+)$/, (_m, row, code, message) => `Row ${row}${code}: ${t(message)}`],
        [/^Indica una cantidad entre 1 y (\d+) para (.+)\.$/, "Enter a quantity between 1 and $1 for $2."],
        [/^Indica una cantidad válida para (.+)\.$/, "Enter a valid quantity for $1."],
        [/^Solo hay (\d+) (.+) de (.+)\.$/, (_m, qty, unit, code) => `There are only ${qty} ${t(unit)} of ${code}.`],
        [/^Ingresaste 1 unidad de (.+)\.$/, (_m, name) => `You added 1 unit of ${t(name)}.`],
        [/^Ingresaste (\d+) unidades de (.+)\.$/, (_m, qty, name) => `You added ${qty} units of ${t(name)}.`],
        [/^Retiraste 1 unidad de (.+)\.$/, (_m, name) => `You withdrew 1 unit of ${t(name)}.`],
        [/^Retiraste (\d+) unidades de (.+)\.$/, (_m, qty, name) => `You withdrew ${qty} units of ${t(name)}.`],
        [/^Código ZF repetido en (\d+) filas del archivo; no se importó\.$/, "ZF code repeated in $1 rows of the file; not imported."],
        [/^Ese código está dado de baja; reactívalo en Reportes si debe volver al inventario\.$/, "That code is written off; reactivate it in Reports if it should return to the inventory."],
        [/^El campo (.+) no puede superar (\d+) caracteres\.$/, "The field $1 cannot exceed $2 characters."],
        [/^El código se salta el consecutivo: el siguiente es (.+)\.$/, "The code skips the sequence: the next one is $1."],
        [/^El estado del servicio debe ser: (.+)\.$/, "The service status must be: $1."],
        [/^El tipo de servicio debe ser: (.+)\.$/, "The service type must be: $1."],
        [/^Elige el proceso: (.+)\.$/, "Choose the process: $1."],
        [/^La categoría '(.+)' ya existe\.$/, "The category '$1' already exists."],
        [/^La fecha '(.+)' debe tener el formato AAAA-MM-DD\.$/, "The date '$1' must use the YYYY-MM-DD format."],
        [/^La fecha '(.+)' no es válida\..*$/, "The date '$1' is not valid. Use 08/05/2026."],
        [/^La pregunta no puede superar (\d+) caracteres\.$/, "The question cannot exceed $1 characters."],
        [/^No hay suficientes unidades de (.+) \(disponibles: (\d+)\)\. No se descontó nada\.$/, "There are not enough units of $1 (available: $2). Nothing was deducted."],
        [/^Ya existe un artículo con el código (.+)\.$/, "An item with code $1 already exists."],
        [/^No se puede anular el ingreso de (.+): se necesitan (\d+) unidades y solo quedan (\d+)\. Anula primero las salidas que las usaron\.$/, "The entry of $1 can't be voided: $2 units are needed and only $3 remain. Void the exits that used them first."],
        [/^El artículo (.+) ya no existe; no se puede devolver su stock\.$/, "Item $1 no longer exists; its stock can't be returned."],
        [/^El artículo (.+) está dado de baja\. Reactívalo antes de anular\.$/, "Item $1 is written off. Reactivate it before voiding."],
        [/^(.+) Inténtalo de nuevo en (\d+) minuto\(s\)\.$/, (_m, message, minutes) => `${t(message)} Try again in ${minutes} minute(s).`],
        // "12 juegos": cantidad con una unidad de los datos del inventario.
        [/^(\d+) (.+)$/, (_m, qty, unit) => `${qty} ${t(unit)}`],
    ];

    function t(text) {
        const key = compact(text);
        if (!key) return text;
        if (Object.prototype.hasOwnProperty.call(dictionary, key)) return dictionary[key];
        for (const [regex, replacement] of patterns) {
            if (regex.test(key)) return key.replace(regex, replacement);
        }
        // "EQ · Equipos", "Equipo · Reparación #1": se traduce cada parte conocida.
        if (key.includes(" · ")) {
            const parts = key.split(" · ").map(t);
            const joined = parts.join(" · ");
            if (joined !== key) return joined;
        }
        return text;
    }

    const translate = (text) => {
        if (text.includes("\n") && text.trim().includes("\n")) {
            return text.split("\n").map((line) => t(line)).join("\n");
        }
        const translated = t(text);
        if (translated === text) return text;
        const [, before, , after] = text.match(/^(\s*)([\s\S]*?)(\s*)$/);
        return `${before}${translated}${after}`;
    };

    const ATTRIBUTES = ["placeholder", "title", "aria-label", "alt"];
    const SKIP = "script, style, textarea, [data-no-translate]";
    const textStates = new WeakMap();
    const attributeStates = new WeakMap();

    const translateTextNode = (node) => {
        if (node.parentElement?.closest(SKIP)) return;
        // Se traduce siempre desde el texto original: los datos pueden llegar después.
        const state = textStates.get(node);
        const source = state && state.output === node.data ? state.source : node.data;
        const output = translate(source);
        textStates.set(node, { source, output });
        if (output !== node.data) node.data = output;
    };
    const translateAttributes = (element) => {
        if (element.closest("[data-no-translate]")) return;
        ATTRIBUTES.forEach((name) => {
            const value = element.getAttribute(name);
            if (!value) return;
            const states = attributeStates.get(element) || {};
            const source = states[name]?.output === value ? states[name].source : value;
            const output = translate(source);
            states[name] = { source, output };
            attributeStates.set(element, states);
            if (output !== value) element.setAttribute(name, output);
        });
    };
    const translateTree = (root) => {
        if (root.nodeType === Node.TEXT_NODE) {
            translateTextNode(root);
            return;
        }
        if (root.nodeType !== Node.ELEMENT_NODE) return;
        translateAttributes(root);
        root.querySelectorAll("*").forEach(translateAttributes);
        const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
        while (walker.nextNode()) translateTextNode(walker.currentNode);
    };

    // Datos del inventario (nombres, descripciones, unidades...): llegan traducidos por lotes.
    const loadDataTranslations = async () => {
        const url = document.querySelector("[data-translations-url]")?.dataset.translationsUrl;
        if (!url) return;
        for (let round = 0; round < 25; round += 1) {
            let result;
            try {
                const response = await fetch(url, { method: "POST" });
                if (!response.ok) return;
                result = await response.json();
            } catch {
                return;
            }
            Object.entries(result.traducciones).forEach(([spanish, english]) => {
                if (!Object.prototype.hasOwnProperty.call(dictionary, spanish)) dictionary[spanish] = english;
            });
            translateTree(document.body);
            // Para que el buscador también encuentre los artículos escribiendo en inglés.
            document.querySelectorAll(".inventory-card").forEach((card) => {
                card.dataset.translated = `${t(card.dataset.name || "")} ${t(card.dataset.category || "")}`;
            });
            if (!result.pendientes || !result.disponible) return;
        }
    };

    const setupToggle = () => {
        const button = document.querySelector("#language-toggle");
        if (!button) return;
        const label = language === "en" ? "Español" : "English";
        button.querySelector("span").textContent = label;
        button.setAttribute("aria-label", language === "en" ? "Cambiar a español" : "Switch to English");
        button.title = button.getAttribute("aria-label");
        button.addEventListener("click", () => {
            try {
                window.localStorage.setItem(STORAGE_KEY, language === "en" ? "es" : "en");
            } catch {
                return;
            }
            window.location.reload();
        });
    };

    if (language === "en") {
        ["alert", "confirm", "prompt"].forEach((name) => {
            const original = window[name].bind(window);
            window[name] = (message, ...rest) => original(translate(String(message ?? "")), ...rest);
        });
    }

    // Después de los demás scripts: así guardan sus textos originales en español
    // y los vuelven a poner; el observador los traduce cada vez.
    document.addEventListener("DOMContentLoaded", () => {
        setupToggle();
        if (language !== "en") return;
        document.documentElement.lang = "en";
        document.title = translate(document.title);
        translateTree(document.body);
        new MutationObserver((records) => {
            records.forEach((record) => {
                if (record.type === "characterData") {
                    translateTextNode(record.target);
                } else if (record.type === "attributes") {
                    translateAttributes(record.target);
                } else {
                    record.addedNodes.forEach(translateTree);
                }
            });
        }).observe(document.body, {
            subtree: true,
            childList: true,
            characterData: true,
            attributes: true,
            attributeFilter: ATTRIBUTES,
        });
        loadDataTranslations();
    });
})();
