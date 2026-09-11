# El Chico Naturista — Contexto del proyecto

E-commerce de productos naturales (Perú). Primera versión de la marca.

## Identidad de marca

- Verde salvia: `#2F5D50`
- Verde jade: `#7A9B87`
- Fondo: `#F7F7F7`
- Objetivo de diseño: NO debe verse como una web genérica hecha con IA. Evitar
  grillas de tarjetas por defecto, tipografía del sistema, espaciados
  automáticos sin criterio. Usar tipografía con carácter y layout deliberado.

## Stack

- Frontend: Astro + Alpine.js
- Backend: FastAPI (Python) — aún no se construye, ver etapas
- Base de datos: PostgreSQL — aún no se construye, ver etapas
- Autenticación: JWT — aún no se construye
- Sin pagos en línea. El pedido se coordina por WhatsApp vía enlace `wa.me`.

## Catálogo (categorías del MVP)

- Cosmética capilar (línea Henna Colors: tintes naturales, aceites, accesorios)
- Suplementos naturales (cápsulas)
- Aceites esenciales y naturales
- Alimentos y superalimentos secos (cacao, harinas, endulzantes, etc.)

No se venden lácteos/kéfires frescos en esta versión (requieren cadena de frío).

## Modelo de datos (esquema completo)

### categorias
| Campo | Tipo | Notas |
|---|---|---|
| id | serial PK | |
| nombre | varchar(100) | |
| slug | varchar(100) unique | |
| orden | int | orden de aparición en menú |

### productos
| Campo | Tipo | Notas |
|---|---|---|
| id | serial PK | |
| nombre | varchar(150) | |
| slug | varchar(150) unique | |
| descripcion_corta | text | |
| categoria_id | int FK → categorias.id | |
| precio | numeric(10,2) | |
| imagen_url | text | una imagen principal en esta versión |
| stock | int default 0 | |
| activo | boolean default true | |
| destacado | boolean default false | |
| creado_en | timestamp default now() | |
| actualizado_en | timestamp | |

### clientes (opcional — compra como invitado si no existe registro)
| Campo | Tipo | Notas |
|---|---|---|
| id | serial PK | |
| nombre | varchar(150) | |
| email | varchar(150) unique | |
| telefono | varchar(20) | |
| password_hash | varchar(255) nullable | |
| creado_en | timestamp default now() | |

### pedidos
| Campo | Tipo | Notas |
|---|---|---|
| id | serial PK | |
| numero_pedido | varchar(20) unique | ej. ECN-0001, autogenerado |
| cliente_id | int FK → clientes.id, nullable | null si compra invitado |
| nombre_contacto | varchar(150) | |
| telefono_contacto | varchar(20) | |
| direccion_envio | text | |
| departamento | varchar(100) | para envíos a nivel nacional |
| estado | enum(pendiente, coordinado, enviado, completado, cancelado) | default pendiente |
| total | numeric(10,2) | |
| creado_en | timestamp default now() | |

### pedido_items
| Campo | Tipo | Notas |
|---|---|---|
| id | serial PK | |
| pedido_id | int FK → pedidos.id | |
| producto_id | int FK → productos.id | |
| cantidad | int | |
| precio_unitario | numeric(10,2) | snapshot del precio al momento de compra |

### admin
| Campo | Tipo | Notas |
|---|---|---|
| id | serial PK | |
| usuario | varchar(100) unique | |
| password_hash | varchar(255) | |

Relaciones: categorias 1→N productos · clientes 1→N pedidos (opcional) ·
pedidos 1→N pedido_items · productos 1→N pedido_items.

## Diseño de la API (interna, versionada `/api/v1`)

Etapa 3 (ahora) — solo productos y categorías, lectura:
- `GET /api/v1/categorias`
- `GET /api/v1/productos` (query params: `categoria`, `precio_min`, `precio_max`, `q`, `destacado`)
- `GET /api/v1/productos/{slug}`

Etapa 5 (flujo de pedido) — se agrega después:
- `POST /api/v1/pedidos` (crea pedido + items, devuelve `numero_pedido`)
- `GET /api/v1/pedidos/{numero_pedido}`

Etapa 6 (panel admin) — se agrega después:
- `POST /api/v1/auth/login` (admin)
- `POST /api/v1/admin/productos`, `PUT .../{id}`, `DELETE .../{id}`
- `GET /api/v1/admin/pedidos`
- `PATCH /api/v1/admin/pedidos/{id}/estado`

Nota: el esquema completo de base de datos se crea de una vez (una sola
migración), pero los endpoints se construyen de forma incremental por etapa.

## Referencias de diseño (solo estructura/interacción, NO estética a copiar)

- https://www.lasanahoria.com/ — bio-market peruano real. Rescatar: mega-menú
  organizado por departamentos, carrusel de destacados en el hero, secciones
  de categorías con fotografía de producto grande y cálida, sensación de
  negocio establecido y confiable.
- Referencia tipo Shopify simple (Vita Eco) — rescatar: tarjetas de producto
  limpias, checkout ligero, botón de WhatsApp visible.
- NO copiar la estética de ninguna (colores, tipografía, layout exacto).
  El Chico Naturista usa su propia paleta e identidad definida arriba.

## Páginas del sitio

1. Inicio — hero de marca, categorías destacadas, productos más vendidos
2. Catálogo — grid con búsqueda y filtros (categoría, precio)
3. Detalle de producto
4. Carrito
5. Checkout — genera número de pedido, botón WhatsApp (`wa.me`)
6. Cuenta (login/registro opcional, historial de pedidos)
7. Panel de administración (protegido, solo Fernando)

## Orden de desarrollo (etapas)

1. Frontend visual con datos de prueba — COMPLETO
2. Carrito funcional sobre datos de prueba — COMPLETO
3. Backend real: modelo de datos + API FastAPI (productos/categorías) — ETAPA ACTUAL
4. Conectar frontend al backend real
5. Flujo de pedido completo (checkout + número de pedido + WhatsApp)
6. Panel de administración
7. Pulido visual según feedback de Fernando

## Fuera de alcance en esta versión

Pagos en línea, apps móviles nativas, logística de envío automatizada,
múltiples administradores, lácteos/kéfires frescos, contenido extenso por
producto.
