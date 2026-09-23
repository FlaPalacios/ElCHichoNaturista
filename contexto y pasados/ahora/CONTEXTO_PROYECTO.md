# El Chico Naturista — Contexto del proyecto

Actualizado el 22 de septiembre de 2026, al terminar la Etapa 6.

E-commerce de productos naturales (Lima, Perú). Este documento dice **cómo está
el proyecto hoy**, no cómo se planeó: donde el plan original y lo construido no
coinciden, manda lo construido y se explica por qué.

Los contextos anteriores están en `contexto y pasados/pasados/`, numerados en
el orden en que se usaron.

---

## 1. Qué es

Una tienda en línea donde el cliente arma su pedido y lo cierra por WhatsApp.
**No se cobra en línea**: al confirmar, el sitio genera un número de pedido
(`ECN-AAMMDD-NNNN`) y abre WhatsApp con el detalle ya escrito. El pago se
acuerda en el chat.

Hay **un solo administrador** (Fernando), con su propio panel interno.

## 2. Stack

- **Frontend**: Astro en modo servidor (SSR) + Alpine.js para la interacción.
- **Backend**: FastAPI + PostgreSQL, con migraciones en Alembic.
- **Fotos**: Cloudinary. Se suben desde el panel; las credenciales van en
  `backend/.env`.
- **Sesión del panel**: JWT en una cookie `httpOnly`.

El sitio consulta la API en cada visita, así un cambio de precio o de stock se
ve sin recompilar. Si la API no responde, el sitio no se cae: muestra un aviso
con el botón de WhatsApp.

## 3. Identidad de marca

- Verde salvia `#2F5D50`, verde jade `#7A9B87`, fondo `#F7F7F7`, café `#211E1E`.
- Tipografías Hind (titulares) y Amulya (texto), servidas desde el propio
  sitio.
- **Todos los colores salen de `:root` en `src/styles/global.css`.** Fuera de
  ahí no hay ninguno escrito a mano, salvo el `<meta name="theme-color">`, que
  no acepta variables CSS.
- Objetivo de diseño: que no parezca una web genérica. Reglas finas en vez de
  sombras, composiciones deliberadas, nada de grillas por defecto.

## 4. Cómo está organizado el catálogo

Dos niveles más la marca:

**Categoría → Subcategoría**, y cada producto además pertenece a una **marca**.

| Categoría | Subcategorías |
|---|---|
| Frescos | Bebidas frescas · Bebidas probióticas |
| Abarrotes | Café y cacao · Aceites vegetales · Mermeladas y mieles · Proteínas y suplementos |
| Cuidado Personal | Cuidado de cabello · Cuidado corporal |

Marcas: Green House / HIRI, Henna Colors, Algarrobos Orgánicos, Fit Rex.

La categoría del producto **no se guarda aparte**: sale de su subcategoría, así
no pueden contradecirse. Lo que no tiene productos activos no se muestra en la
tienda, pero sigue en la base.

**Convención de borrador**: un producto sin precio confirmado se carga con
`precio 0.00` y `activo=false`. Existe en la base pero no aparece en la tienda
hasta que se complete desde el panel. Hoy están así las 4 galletas Fit Rex, las
2 algarrobinas y las 2 macas.

## 5. Envío

| Zona | Costo |
|---|---|
| Los 43 distritos de la provincia de Lima y los 7 del Callao | S/ 10 |
| Todo el resto del Perú, incluido el resto del departamento de Lima | S/ 15 |

Desde **S/ 120 el envío es gratis en todo el país**.

El costo sale de la tabla `tarifas_envio` (una fila por departamento, más filas
por provincia para afinar casos como Lima capital) y se edita desde el panel.
El checkout pide **departamento → provincia → distrito** con el padrón del INEI
2022 (25 / 196 / 1891).

**No hay recojo en tienda ni elección de método de pago**: todo pedido es
delivery, y el pago (Yape, Plin o transferencia) se coordina por WhatsApp. En
el checkout es solo un texto informativo.

## 6. Estados del pedido

```
nuevo → pago_confirmado → preparando → enviado → entregado
                                   ↘ cancelado | no_concretado
```

`cancelado` es para un pedido que iba en serio y se cayó; `no_concretado`, para
el cliente que nunca llegó a confirmar.

**El stock se descuenta al entrar a `pago_confirmado`** y vuelve al almacén si
el pedido pasa a `cancelado` o `no_concretado`. Al crear el pedido solo se
valida, no se descuenta. El cliente ve etiquetas legibles ("Recibido", "En
camino"), no estos nombres.

## 7. Base de datos

Catorce tablas. Las que importan:

- **marcas**, **categorias**, **subcategorias** — la clasificación.
- **productos** — con `codigo` (ECN-001), el identificador del negocio, que es
  también lo que relaciona las fotos.
- **product_images** — fotos de Cloudinary, relacionadas por `codigo`. La de
  `orden` 1 es la principal.
- **pedidos** / **pedido_items** — el pedido guarda su destino completo y una
  copia del precio de cada producto, para que el histórico no cambie si suben
  los precios.
- **departamentos** / **provincias** / **distritos** — el padrón del INEI.
- **tarifas_envio** — costos por zona.
- **configuracion** — clave-valor con los ajustes editables desde el panel.
- **admin** — el usuario del panel, con la contraseña hasheada (bcrypt).

**La tabla `clientes` se eliminó del alcance**: se compra como invitado y los
clientes se derivan de los pedidos, agrupados por teléfono.

## 8. Páginas

**Tienda**: portada, catálogo (con filtros por categoría, subcategoría, marca,
precio y ofertas), ficha de producto, carrito, checkout, consulta de pedido y
404.

**Panel** (`/admin`, con su propio layout: sin encabezado, pie, carrito ni
botón de WhatsApp):

| Sección | Qué hace |
|---|---|
| Pedidos | Lista con filtros, detalle, cambio de estado, courier y código de seguimiento, nota interna y botón de WhatsApp al cliente |
| Productos | Filtros (categoría, subcategoría, marca, estado, poco stock, seis órdenes), edición rápida de stock, activar/desactivar, ficha completa, fotos a Cloudinary, exportar e importar TSV |
| Categorías | Categorías, subcategorías y marcas: crear, editar y borrar |
| Configuración | Datos de la tienda, mensajes, envío gratis, umbral de stock y costos de envío por zona |
| Resumen | Pedidos por atender, ventas del mes, top 5 y lo que se está acabando |
| Clientes | Derivados de los pedidos, agrupados por teléfono |

## 9. Decisiones que conviene recordar

**El panel manda sobre el catálogo.** La base es la fuente de verdad.
`python -m app.seed` solo crea lo que falta y nunca pisa lo que se editó desde
el panel. Para cargar cambios masivos está Importar TSV; para ver el catálogo
en Excel, Exportar TSV. Las planillas de `backend/app/datos/` quedaron como
carga inicial.

**Nada se borra si tiene historia.** Los productos se desactivan, no se borran.
Una categoría con subcategorías, una subcategoría con productos o una marca con
productos no se pueden borrar: la API explica qué hay que mover primero.

**La sesión del panel no está al alcance del JavaScript.** El token vive en una
cookie `httpOnly`; las pantallas piden los datos desde el servidor y los
cambios pasan por `/api/admin/…`, un puente que solo alcanza rutas del panel.

**Los datos de la tienda no están en el código.** WhatsApp, dirección, redes,
avisos del cintillo y montos salen de la base. `src/middleware.js` los carga
una vez por visita; si la API falla, se usan los de `src/data/tienda.js`.

**El checkout nunca pierde una venta.** Si la API no responde al confirmar, el
pedido se guarda en el navegador con un número generado localmente, se abre
WhatsApp igual, y queda marcado como "guardado en este dispositivo".

## 10. Etapas

| Etapa | Estado |
|---|---|
| 1. Frontend visual con datos de prueba | Completa |
| 2. Carrito funcional | Completa |
| 3. Backend: modelo de datos + API | Completa |
| 4. Conectar el frontend al backend | Completa |
| 5. Flujo de pedido completo | Completa |
| 6. Panel de administración | Completa |
| **7. Pulido visual según feedback de Fernando** | **Pendiente** |

## 11. Qué falta antes de publicar

1. **Nadie ha revisado esto en un navegador todavía.** Todo se verificó con
   peticiones a la API, no con clics. Es lo primero que toca hacer.
2. **Completar los 8 borradores**: precio, descripción y stock de las galletas,
   las algarrobinas y las macas.
3. **Confirmar los datos de contacto**: el correo y los enlaces de Instagram y
   Facebook siguen siendo los de ejemplo (el WhatsApp y la dirección ya son
   reales). Se editan desde Configuración.
4. **El banner de la portada** repite la misma foto tres veces; faltan dos
   fotos más.
5. **El dominio definitivo** en `astro.config.mjs` (`site`).
6. **Rotar las credenciales de Cloudinary**, que se compartieron por chat.
7. **Poner la base en limpio**: `python -m app.instalar --reset` borra los datos
   de prueba y deja el catálogo real cargado.

## 12. Fuera de alcance en esta versión

Pagos en línea, apps móviles, logística automatizada, varios administradores,
cuentas de cliente con registro y contraseña.
