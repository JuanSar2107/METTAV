# Requerimientos de la reunión del 27/10/2026

Fuente: grabación de pantalla de la reunión por Teams (17 min). Se mostraron Sizfra 2.0
(sistema de la zona franca Intexzona), el Excel `Inventario_Consecutivo_Por_Categoria EQUIPOS METTAV`
y el Excel `Remision_METTAV INGRESOS POR SERVICIOS`.

---

## 1. Glosario técnico

| Término | Qué significa en este contexto |
|---|---|
| **Sizfra** ("cifra" / "sisma" en el audio) | Software oficial de la Zona Franca Intexzona. Ahí se registran todos los ingresos y salidas de mercancía. Es la fuente de verdad ante la zona franca. |
| **Zona Franca (ZF)** | Área con régimen aduanero especial. Todo lo que entra o sale queda registrado ante el usuario operador y se audita. |
| **Usuario operador** | Personal de la zona franca que revisa y aprueba los formularios y deja observaciones. |
| **Formulario** | Registro de una operación en Sizfra (p. ej. formulario 1383926). Guarda trazabilidad: hora de inicio, hora de fin, revisión del operador y observaciones. |
| **Operación** | Tipo de movimiento aduanero, identificado por un código. En el video aparecen la **420** (*salida al territorio nacional de maquinaria que ingresó temporalmente para prestar un servicio*), la **50** (*salida definitiva por ventas*) y la **101** (*ingreso desde el resto del mundo de maquinaria y repuestos*). |
| **Afectar un código** | Indicar qué código de inventario sube o baja en una operación. En el reporte se ve la columna `AFECTA = SUMA / RESTA`. |
| **Dar de baja** | Descontar unidades del inventario. Ejemplo: hay 3 bancos y sale 1, entonces quedan 2. |
| **Subpartida arancelaria** | Código de clasificación aduanera del producto (p. ej. `8413.30.10.00`, `8412.90.00.00`). |
| **Valor FOB (USD)** | *Free On Board*: valor de la mercancía en dólares. En la zona franca todo se valora en USD. |
| **TRM** | Tasa Representativa del Mercado, para convertir USD a COP. Sizfra la muestra arriba (p. ej. 3.185,01). |
| **Kit / Integración de partes / Producto elaborado** | Cuando se fabrica o repara un equipo usando ítems del inventario. Esos ítems se "integran" al producto y salen del inventario. En el reporte de Sizfra aparecen las columnas *TIPO MOV* (`MISMO_ESTADO`) y *PRODUCTO ELABORADO*. |
| **Materia prima / Consumibles** | Insumos que rotan constantemente y se usan para el objeto social (fabricar o reparar). |
| **Overhaul** | Reparación mayor o reacondicionamiento completo de un equipo. |
| **Comodato** | Préstamo de maquinaria. Hay una carpeta "REMISION SALIDA DE MAQUINARIA COMODATO". |
| **Remisión de salida** | Documento de entrega al cliente. Tiene consecutivo (`REM-0001`), datos del cliente (NIT, contacto, tipo de servicio) y una tabla de mercancía. |
| **Estado de la mercancía** | Con qué condición ingresa: *para reparación, nuevo, con avería, otro, para fabricar*. |
| **Estado del servicio** | En qué punto va el trabajo: *en servicio, terminado, entregado, cancelado*. |
| **Auditoría / conciliación de inventario** | La zona franca audita constantemente. Hay que cruzar el reporte de Sizfra con el reporte interno y encontrar diferencias. |
| **Software contable** | Integración futura: exportar movimientos al sistema de contabilidad. |

## 2. Estructura de códigos (Excel de inventario)

Cada ítem tiene **dos códigos**:

- **Código interno** (columna morada): uso interno de METTAV. Ejemplos: `MAQ-BOD-CO-001`, `EQ-ADM-CO-004`.
  Fórmula: `Categoría-Ubicación-Tipo-Consecutivo`.
- **Código ZF** (columna azul): **el que se registra en Sizfra y el que se da de baja**. Ejemplos: `ZF-MAQ-CO-001`, `ZF-OT-PR-001`.
  Fórmula: `"ZF-" & Categoría & "-" & Tipo & "-" & TEXTO(consecutivo; "000")`.

Columnas del Excel: Código interno, Código ZF, **Categoría** (`EQ` equipo, `MAQ` maquinaria,
`EL` electrodoméstico, `MO` mobiliario, `HE` herramienta, `OT` otro), **Ubicación** (`ADM` administración,
`BOD` bodega, `COM` comedor, `M/OP` operativa, `APT` apartamento), **Tipo** (`PR`, `CO`, …),
Consecutivo (automático), Descripción y Marca. Hay más de 200 ítems.

**Grupos de inventario en Sizfra** (deben existir igual en la app):

| Código | Grupo | Corresponde en el Excel a |
|---|---|---|
| 001 | Activos oficina METTAV | `MO-ADM`, `EQ-ADM`, `EL-ADM` |
| 002 | Equipos de bodega | `MAQ-BOD` |
| 003 | Equipos operativos bodega | `OT-OP` (ítems resaltados en amarillo) |
| 004 | Mercancía que ingresa para la prestación de un servicio | Ítems de clientes (p. ej. los de la remisión) |

## 3. Requerimientos

### R1. Importar el inventario desde el Excel
Cargar los más de 200 ítems con código interno, código ZF, categoría, ubicación, tipo, consecutivo,
descripción, marca y grupo. Los códigos no los genera la app: vienen del Excel y se ingresan tal cual.
*(En el audio se pregunta si la app puede generar los códigos. La respuesta fue que no, que se ingresan.)*

### R2. Campos aduaneros por ítem
Agregar subpartida arancelaria, valor FOB en USD, procedencia (nacional o extranjera), unidad de medida
y estado de la mercancía.

### R3. Bajas consistentes con Sizfra
Cada salida descuenta stock (3 − 1 = 2) y queda asociada a la operación y al formulario de Sizfra,
para que las cantidades de la app coincidan con las de Sizfra y no haya que contar a mano.

### R4. Salida con integración de partes (lo más importante)
En un **solo registro**: sacar un producto (p. ej. un banco) y, a la vez, dar de baja los ítems que se
le integraron (kit de accesorios, repuestos). Debe quedar qué se integró, a qué equipo, con qué
referencia y en qué fecha. Hoy en el inventario les toca hacerlo código por código.

### R5. Estado del servicio para la mercancía de clientes
Al ingresar: tipo de servicio (mantenimiento, reparación, overhaul, fabricación, materia prima).
Al dar salida: estado (*en servicio, terminado, entregado, servicio cancelado*).

### R6. Trazabilidad / bitácora de auditoría
Por cada operación: quién la hizo, desde dónde, qué ingresó o sacó, hora de inicio, hora de fin
y observaciones. En el futuro habrá una persona dedicada solo a inventarios.

### R7. Reportes
- Por grupo de inventario y por código (como el catálogo de informes de Sizfra).
- De movimientos: "el 27/10 a las 10:00 se retiró un banco y se le integraron 5 ítems por una fabricación".
- **Reporte de conciliación**: cruzar el inventario de Sizfra con el de la app y marcar los ítems que no
  coinciden (p. ej. se retiró en Sizfra pero no en la app).

### R8. Remisión de salida
Generar el documento de remisión (consecutivo `REM-xxxx`, cliente, NIT, contacto, tipo de servicio y
tabla de mercancía con código, descripción, unidad, procedencia, estado, subpartida, valor FOB,
cantidad y estado de servicio). Hoy se hace en Excel.

### R9. A futuro
- Integración o exportación hacia el software contable.
- Se trabajará de forma iterativa: irán surgiendo más necesidades cuando llegue la operación fuerte.
- Valoran que la app sea **en línea** (accesible desde cualquier lugar).

## 4. Qué tiene hoy la app y qué falta

| Hoy en `mi_app/models/inventory.py` | Falta |
|---|---|
| `ArticuloInventario`: código, nombre, categoría, descripción, stock, ubicación, imagen | Código ZF y código interno por separado, grupo, tipo, marca, subpartida, valor FOB, procedencia, estado (R1, R2) |
| `MovimientoInventario`: un artículo por movimiento, tipo `Retiro` | Movimiento con varias líneas (producto + partes integradas), operación y formulario Sizfra, tipo de servicio, estado del servicio, observaciones, hora de inicio y fin (R3–R6) |
| `Categoria` (solo nombre) | Grupos de inventario 001–004 (sección 2) |
| — | Clientes y remisiones (R8), reportes y conciliación (R7), importación desde Excel (R1) |

## 5. Preguntas abiertas para aclarar

1. ¿Qué significan exactamente los valores de la columna **Tipo** (`PR`, `CO`, …)?
2. ¿Sizfra permite exportar su inventario (Excel o CSV) para automatizar la conciliación?
3. ¿Cuál software contable usan, para planear la integración?
4. ¿La remisión debe salir en PDF con el formato actual del Excel?
