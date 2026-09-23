# Backend — El Chico Naturista

API interna en FastAPI + PostgreSQL. Sirve el catálogo (etapas 3 y 4) y ya
puede crear y consultar pedidos (etapa 5). Administración (etapa 6) todavía no
tiene endpoints, pero su tabla ya está creada.

## Requisitos

- Python 3.11 o superior
- PostgreSQL 16/17 — con Docker o instalado en la máquina

## Puesta en marcha

### 1. Levantar PostgreSQL

**Opción A — Docker** (no hace falta instalar nada más):

```bash
cd backend
docker compose up -d          # postgres:16 en localhost:5432
docker compose ps             # comprobar que está "healthy"
```

Crea la base `elchiconaturista` con usuario `ecn` y clave `ecn`. Para apagarla,
`docker compose down`; para borrar además los datos, `docker compose down -v`.

**Opción B — PostgreSQL ya instalado** (es lo que hay en esta máquina). Crea una
vez el rol y la base, usando tu usuario administrador:

```bash
psql -U postgres -h localhost -c "CREATE ROLE ecn LOGIN PASSWORD 'ecn';"
psql -U postgres -h localhost -c "CREATE DATABASE elchiconaturista OWNER ecn ENCODING 'UTF8';"
```

Así la conexión queda igual que con Docker y no hay que tocar el `.env`.

### 2. Instalar dependencias

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate          # Windows;  en Linux/Mac: source .venv/bin/activate
pip install -r requirements.txt
```

### 3. Configurar el entorno

```bash
copy .env.example .env          # Windows;  en Linux/Mac: cp .env.example .env
```

El valor por defecto ya apunta a la base de arriba:

```
DATABASE_URL=postgresql+psycopg://ecn:ecn@localhost:5432/elchiconaturista
```

### 4. Dejar la base lista

```bash
python -m app.instalar
```

Un solo comando hace, en orden, lo que si no habría que recordar por partes:

1. aplica las migraciones,
2. carga el ubigeo del Perú y las tarifas de envío,
3. carga el catálogo desde las planillas de `app/datos`,
4. crea el usuario del panel con la clave del `.env`.

Es seguro correrlo las veces que quieras: **solo agrega lo que falta**. No pisa
un producto que ya esté en la base ni una tarifa que hayas editado desde el
panel.

Para empezar de cero —al pasar de las pruebas a los datos de verdad— está
`--reset`, que borra pedidos, catálogo, ajustes y tarifas antes de cargar:

```bash
python -m app.instalar --reset
```

Pide escribir `borrar` para continuar, y dice cuántos pedidos y productos se
van a perder. **No se puede deshacer.** El padrón del INEI no se toca, porque
no son datos del negocio. Para automatizarlo, `--si` salta la pregunta.

Si prefieres los pasos por separado, siguen existiendo: `alembic upgrade head`,
`python -m app.ubigeo`, `python -m app.seed` y `python -m app.crear_admin`.

### 5. Levantar la API

```bash
uvicorn app.main:app --reload   # http://127.0.0.1:8000
```

- Documentación interactiva: http://127.0.0.1:8000/docs
- Comprobación rápida: http://127.0.0.1:8000/api/v1/salud

## Endpoints

| Método | Ruta | Qué hace |
|---|---|---|
| GET | `/api/v1/categorias` | Las categorías con algún producto activo, cada una con sus subcategorías |
| GET | `/api/v1/marcas` | Las marcas con algún producto activo |
| GET | `/api/v1/productos` | Lista con filtros (ver abajo) |
| GET | `/api/v1/productos/{slug}` | Detalle de un producto |
| POST | `/api/v1/pedidos` | Crea un pedido con sus items, devuelve `201` |
| GET | `/api/v1/pedidos/{numero_pedido}` | Consulta un pedido por su número |
| GET | `/api/v1/ubigeo/departamentos` | Los 25 departamentos |
| GET | `/api/v1/ubigeo/departamentos/{codigo}/provincias` | Provincias de un departamento |
| GET | `/api/v1/ubigeo/provincias/{codigo}/distritos` | Distritos de una provincia |
| GET | `/api/v1/envio?ubigeo=150122` | Cuánto cuesta enviar a ese distrito |
| GET | `/api/v1/salud` | Estado de la API y de la base |
| POST | `/api/v1/admin/login` | Entra al panel, devuelve el token |
| GET | `/api/v1/admin/yo` | Comprueba que el token sirve |
| GET | `/api/v1/admin/pedidos` | Lista pedidos (filtros: `estado`, `desde`, `hasta`, `q`) |
| GET | `/api/v1/admin/pedidos/{numero}` | Detalle de un pedido |
| PATCH | `/api/v1/admin/pedidos/{numero}/estado` | Cambia el estado (y courier/seguimiento) |
| PATCH | `/api/v1/admin/pedidos/{numero}/nota` | Guarda la nota interna |
| GET | `/api/v1/admin/productos` | Todo el catálogo, activos e inactivos |
| POST | `/api/v1/admin/productos` | Crea un producto |
| PUT | `/api/v1/admin/productos/{codigo}` | Edita un producto |
| PATCH | `/api/v1/admin/productos/{codigo}/stock` | Cambia solo el stock |
| PATCH | `/api/v1/admin/productos/{codigo}/activo` | Activa o desactiva |
| GET | `/api/v1/admin/productos/exportar` | Descarga el catálogo en TSV |
| POST | `/api/v1/admin/productos/importar` | Carga productos desde un TSV |
| POST | `/api/v1/admin/productos/{codigo}/imagenes` | Sube una foto a Cloudinary |
| DELETE | `/api/v1/admin/productos/{codigo}/imagenes/{id}` | Borra una foto |
| PATCH | `/api/v1/admin/productos/{codigo}/imagenes/orden` | Reordena las fotos |
| GET | `/api/v1/admin/clasificacion` | Categorías con sus subcategorías, y las marcas |
| POST/PUT/DELETE | `/api/v1/admin/categorias` · `/subcategorias` · `/marcas` | CRUD de la clasificación |
| GET | `/api/v1/admin/resumen` | Cifras del mes, stock bajo y top 5 |
| GET | `/api/v1/admin/clientes` | Clientes derivados de los pedidos |
| GET/PUT | `/api/v1/admin/configuracion` | Ajustes de la tienda |
| GET/PATCH | `/api/v1/admin/tarifas` | Costos de envío por zona |
| GET | `/api/v1/tienda` | Datos y avisos de la tienda (público) |

Filtros de `GET /api/v1/productos`:

| Parámetro | Ejemplo | Nota |
|---|---|---|
| `categoria` | `?categoria=abarrotes` | Slug de la categoría; 404 si no existe |
| `subcategoria` | `?subcategoria=cafe-y-cacao` | Slug de la subcategoría |
| `marca` | `?marca=henna-colors` | Slug de la marca |
| `precio_min` | `?precio_min=20` | En soles, no negativo |
| `precio_max` | `?precio_max=30` | 422 si es menor que `precio_min` |
| `q` | `?q=henna` | Busca en nombre y descripción corta |
| `destacado` | `?destacado=true` | Solo los destacados |
| `mas_vendido` | `?mas_vendido=true` | Solo los más vendidos |
| `en_oferta` | `?en_oferta=true` | Solo los que tienen precio anterior |

Se combinan entre sí: `?categoria=abarrotes&q=cacao&precio_max=30`.

**La lista solo devuelve productos activos**, y el detalle de un producto
inactivo responde 404: los productos desactivados desde el panel desaparecen de
la tienda sin borrarse de la base.

### `POST /api/v1/pedidos`

Recalcula precios, stock y envío desde la base de datos: **nunca confía en lo
que mande el cliente**. Devuelve `201` con el pedido completo.

Payload de entrada:

```json
{
  "nombre_contacto": "Ana Torres",
  "telefono_contacto": "987654321",
  "correo": "ana@example.com",
  "direccion": "Av. Siempre Viva 123",
  "ubigeo": "150122",
  "referencia": "Frente al parque",
  "nota": "Entregar en la tarde",
  "items": [{ "producto_id": 4, "cantidad": 2 }]
}
```

`ubigeo` es el código INEI del distrito de entrega (6 dígitos); de ahí salen el
departamento, la provincia y el costo del envío. `correo`, `referencia` y `nota`
son opcionales. Todo pedido es delivery: el recojo en tienda se retiró, igual
que el método de pago (ahora es informativo, se coordina por WhatsApp).

Errores:

| Caso | Código | Detalle |
|---|---|---|
| Producto inexistente o inactivo | 422 | menciona el `producto_id` |
| Stock insuficiente | 422 | "quedan N, se pidieron M" |
| Carrito vacío (`items: []`) | 422 | validación de Pydantic |
| Ubigeo que no existe | 422 | "El distrito 'X' no existe en el padrón del INEI." |

Al crear el pedido **se valida el stock pero no se descuenta**: eso ocurre al
pasarlo a `pago_confirmado` desde el panel (etapa 6).

### Estados del pedido

`nuevo` → `pago_confirmado` → `preparando` → `enviado` → `entregado`, más
`cancelado` y `no_concretado`, que son finales. El cliente solo ve una etiqueta
legible ("Recibido", "En camino"…); los nombres internos están en
`EstadoPedido` (`app/models.py`).

### Envío

El costo sale de la tabla `tarifas_envio`: una fila por departamento, y filas
opcionales por provincia que afinan un caso concreto. Hoy quedan así:

| Zona | Costo |
|---|---|
| Provincia de Lima (43 distritos) y Callao | S/ 10 |
| Todo el resto del país, incluido el resto del departamento de Lima | S/ 15 |

Desde `envio_gratis_desde` (S/ 120 por defecto, en `.env`) el envío es gratis en
todo el Perú. Las tarifas se cargan una vez con `python -m app.ubigeo` y después
se editan desde el panel sin tocar código.

### `GET /api/v1/pedidos/{numero_pedido}`

Devuelve el mismo objeto que el POST. Es público solo con el número de pedido
— no pide teléfono ni ningún otro dato adicional. Quien tenga el número (por
ejemplo, si un chat de WhatsApp se reenvía) puede ver nombre, teléfono y
dirección de ese pedido; es un trade-off de privacidad aceptado
deliberadamente por ahora. `404` si el número no existe.

**Limitaciones conocidas** (aceptables para el volumen de este negocio, no
bloquean la etapa): no hay `SELECT ... FOR UPDATE` sobre `stock`, así que dos
compras simultáneas de la última unidad podrían ambas pasar la validación; y
una colisión de `numero_pedido` entre dos pedidos del mismo día es
teóricamente posible (y rarísima) sin que se reintente a nivel de `commit()`.

## Estructura

```
backend/
  app/
    main.py             App de FastAPI, CORS y rutas
    config.py           Ajustes desde .env (incluye envío/envío gratis)
    database.py         Motor, sesiones y Base declarativa
    models.py           Las catorce tablas
    schemas.py          Lo que la API recibe y devuelve (Pydantic)
    crud.py             Las consultas y la lógica de crear pedidos
    seed.py             Carga el catálogo desde las planillas de datos/
    ubigeo.py           Carga el padrón del INEI y las tarifas de envío
    seguridad.py        Contraseñas (bcrypt) y tokens (JWT) del panel
    fotos.py            Sube y borra fotos en Cloudinary
    tienda.py           Ajustes editables: valores por defecto y lectura
    crear_admin.py      Siembra el usuario del panel desde el .env
    datos/              marcas, categorias, subcategorias, catalogo, imagenes (.tsv)
                        ubigeo.csv (padrón INEI 2022)
    api/v1/             categorias, marcas, productos, pedidos, ubigeo, envio, router
    api/v1/admin/       auth, pedidos, productos, clasificacion, resumen,
                        configuracion (todo menos el login pide token)
  alembic/versions/     Migraciones 0001 a 0008
  docker-compose.yml    PostgreSQL para desarrollo
  requirements.txt
```

## Migraciones

| Revisión | Qué hace |
|---|---|
| `0001` | Esquema completo: las seis tablas y el tipo `estado_pedido` |
| `0002` | Añade a `productos` el contenido de la ficha: `presentacion`, `origen`, `descripcion_larga`, `modo_uso`, `beneficios` (array de texto), `precio_antes` y `mas_vendido` |
| `0003` | Añade a `pedidos` los datos que ya recoge el checkout: `distrito`, `referencia`, `email_contacto`, `nota` y `metodo_pago` (enum `metodo_pago_pedido`) |
| `0004` | Añade `productos.codigo` (ECN-001), crea `product_images` (fotos de Cloudinary, relacionadas por `codigo`) y retira `productos.imagen_url`, que nunca se usó |
| `0006` | Crea `departamentos`, `provincias`, `distritos` (ubigeo INEI) y `tarifas_envio`. El pedido pierde el recojo en tienda y el método de pago, y gana destino completo, `envio`, `courier`, `codigo_seguimiento` y `nota_interna`. Cambian los estados |
| `0005` | Crea `marcas` y `subcategorias`; el producto pasa a clasificarse por subcategoría (su categoría es la de ella) y por marca. Retira `productos.categoria_id` y `productos.origen`. **Vacía el catálogo**: se recarga con el seed |

| `0007` | Guarda en cada foto el `public_id` que le da Cloudinary |
| `0008` | Crea `configuracion`: los ajustes de la tienda que antes estaban en el código |

La `0002` también pone un CHECK que impide guardar un `precio_antes` que no sea
mayor que el precio vigente: un precio tachado menor no sería una oferta.

## El catálogo

El catálogo vive en tres planillas TSV dentro de `app/datos/`. Se editan en
Excel o Google Sheets (exportar como "valores separados por tabulaciones") y se
cargan con `python -m app.seed`.

El catálogo tiene dos niveles: **categoría** (Frescos, Abarrotes, Cuidado
Personal) → **subcategoría**, y además cada producto es de una **marca**.

**`marcas.tsv`** — `slug`, `nombre`, `orden`.

**`categorias.tsv`** — `slug`, `nombre`, `orden` (posición en el menú), `activo`.

**`subcategorias.tsv`** — `slug`, `nombre`, `categoria_slug` (de qué categoría
cuelga), `orden`, `activo`. El `slug` es único en toda la tienda.

**`catalogo.tsv`** — un producto por fila, identificado por `codigo`:

- `codigo`: `ECN-001`, único. Es lo que relaciona el producto con sus fotos.
- `marca_slug`: tiene que existir en `marcas.tsv`.
- `subcategoria_slug`: tiene que existir en `subcategorias.tsv`. La categoría
  del producto sale de ahí; la columna `categoria_slug` de la planilla es solo
  una ayuda visual para quien la edita y el seed la ignora.
- `precio` / `precio_antes`: número con punto decimal (`28.50`). `precio_antes`
  vacío = no está en oferta; si se llena, debe ser mayor que `precio`.
- `beneficios`: varios ítems separados por `|` (pipe), sin `|` al final.
- `activo` / `destacado` / `mas_vendido`: `true` o `false`, en minúscula.
- `stock`: número entero.

Un producto sin datos completos se carga como **borrador**: `precio 0.00` y
`activo=false`. Queda en la base pero no aparece en la tienda.

**`imagenes.tsv`** — `id_producto` (el `codigo`), `url` de Cloudinary, `orden`
(1 = foto principal) y `tipo` (`frente`, `posterior`, `lateral`, `detalle`,
`uso`). Cada carga reemplaza todas las fotos por las de la planilla.

Si una fila tiene más o menos columnas que la cabecera, el seed se detiene y
dice en qué línea está el problema.

## A tener en cuenta

**La API pública solo muestra lo activo.** La lista de productos solo devuelve
productos activos; la de categorías, solo las que tienen algún producto activo,
y recorta las subcategorías vacías; la de marcas, igual. Hoy quedan fuera
`proteinas-y-suplementos`, Fit Rex y Algarrobos Orgánicos, porque todos sus
productos son borradores. El panel de administración
verá todo con los endpoints `/api/v1/admin/...` de la etapa 6.

**Tamaños de foto.** La base guarda la URL original de Cloudinary; el frontend
pide cada foto al ancho que necesita insertando transformaciones en la URL
(`f_auto,q_auto,w_500`), ver `src/lib/cloudinary.js`.

## El panel de administración

Un solo administrador, sin roles: quien tiene un token válido puede hacer todo.

**Entrar.** `POST /api/v1/admin/login` con `username` y `password` como
formulario devuelve un JWT que dura `JWT_HORAS` (12 por defecto). Todas las
demás rutas de `/admin` piden ese token en `Authorization: Bearer …`. Un
usuario que no existe y una contraseña equivocada dan el mismo error, para no
confirmarle a nadie que acertó el usuario.

**Variables del `.env`:**

| Variable | Para qué |
|---|---|
| `JWT_SECRETO` | Firma los tokens. Si cambia, todas las sesiones se cierran |
| `JWT_HORAS` | Cuánto dura una sesión (12) |
| `ADMIN_USUARIO` / `ADMIN_PASSWORD` | Solo los lee `python -m app.crear_admin` |
| `CLOUDINARY_*` | Subida de fotos desde el panel |
| `STOCK_BAJO` | Valor inicial del umbral de stock bajo; después se edita en el panel |

**Stock y estados.** El stock se descuenta al entrar a `pago_confirmado` y
vuelve al almacén si el pedido pasa a `cancelado` o `no_concretado`. En vez de
guardar una bandera, se compara si el estado viejo y el nuevo están dentro del
grupo de estados que retienen mercadería (`ESTADOS_CON_STOCK_TOMADO` en
`crud.py`), así la operación es segura aunque se repita o se salten estados. Si
al confirmar no alcanza el stock, responde 422 y no cambia nada.

**El catálogo se edita en el panel, no en la planilla.** La base es la fuente
de verdad. `python -m app.seed` solo crea lo que falta: si un producto ya está
en la base no lo toca, así una recarga no pisa lo que se editó. Para reemplazar
todo a propósito está `--reset`.

**Exportar e importar.** El panel descarga el catálogo como TSV con las mismas
columnas que `app/datos/catalogo.tsv`, con BOM para que Excel respete las
tildes. Ese mismo archivo se puede editar y volver a subir: los productos se
emparejan por `codigo`, se crean los que falten y se actualizan los demás. Si
alguna fila trae una marca o subcategoría que no existe, **no se guarda nada**
y responde con las líneas que fallaron.

**Fotos.** Se suben a Cloudinary, a la carpeta `elchiconaturista/productos`,
con el nombre `<codigo>-<orden>-<azar>`. Se guarda el `public_id` que devuelve
Cloudinary para poder borrarlas después; las que entraron por planilla no lo
tienen y se deduce de la URL. Al borrar una foto se elimina también de
Cloudinary (con `invalidate`, para que el CDN deje de servirla) y las que
quedan se renumeran para que siempre haya una foto en la posición 1.

**Los ajustes de la tienda viven en la base.** El número de WhatsApp, la
dirección, las redes, los avisos del cintillo, el texto de formas de pago, el
monto de envío gratis y el umbral de stock bajo están en la tabla
`configuracion` (clave-valor) y se editan desde el panel. Los valores por
defecto y el tipo de cada clave están en `app/tienda.py`; la tabla solo guarda
lo que se cambió. El sitio los pide en `GET /api/v1/tienda`.

**Nada se borra si tiene historia.** Una categoría con subcategorías, una
subcategoría con productos o una marca con productos no se pueden borrar:
responden 422 explicando qué hay que mover primero. Los productos tampoco se
borran, se desactivan.

**La nota interna no sale del panel.** `nota_interna` solo existe en
`PedidoAdminOut`; el `GET /api/v1/pedidos/{numero}` que puede ver un cliente no
la incluye.
