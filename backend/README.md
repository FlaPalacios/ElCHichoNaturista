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

### 4. Crear las tablas

```bash
alembic upgrade head
```

Tres migraciones: `0001` crea las seis tablas y el tipo `estado_pedido`, `0002`
añade el contenido de la ficha de producto, y `0003` añade a `pedidos` los
datos del checkout. Para revertir todo: `alembic downgrade base`.

### 5. Cargar el catálogo de ejemplo

```bash
python -m app.seed              # crea o actualiza; se puede correr las veces que quieras
python -m app.seed --reset      # borra el catálogo y lo vuelve a cargar
```

Carga las 4 categorías y los 25 productos del catálogo de ejemplo, con toda su
ficha: presentación, origen, descripción, modo de uso y beneficios.

### 6. Levantar la API

```bash
uvicorn app.main:app --reload   # http://127.0.0.1:8000
```

- Documentación interactiva: http://127.0.0.1:8000/docs
- Comprobación rápida: http://127.0.0.1:8000/api/v1/salud

## Endpoints

| Método | Ruta | Qué hace |
|---|---|---|
| GET | `/api/v1/categorias` | Las categorías, en su orden de menú |
| GET | `/api/v1/productos` | Lista con filtros (ver abajo) |
| GET | `/api/v1/productos/{slug}` | Detalle de un producto |
| POST | `/api/v1/pedidos` | Crea un pedido con sus items, devuelve `201` |
| GET | `/api/v1/pedidos/{numero_pedido}` | Consulta un pedido por su número |
| GET | `/api/v1/salud` | Estado de la API y de la base |

Filtros de `GET /api/v1/productos`:

| Parámetro | Ejemplo | Nota |
|---|---|---|
| `categoria` | `?categoria=aceites` | Slug de la categoría; 404 si no existe |
| `precio_min` | `?precio_min=20` | En soles, no negativo |
| `precio_max` | `?precio_max=30` | 422 si es menor que `precio_min` |
| `q` | `?q=henna` | Busca en nombre y descripción corta |
| `destacado` | `?destacado=true` | Solo los destacados |
| `mas_vendido` | `?mas_vendido=true` | Solo los más vendidos |
| `en_oferta` | `?en_oferta=true` | Solo los que tienen precio anterior |

Se combinan entre sí: `?categoria=superalimentos&q=cacao&precio_max=30`.

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
  "entrega": "delivery",
  "direccion": "Av. Siempre Viva 123",
  "distrito": "Miraflores",
  "referencia": "Frente al parque",
  "metodo_pago": "yape",
  "nota": "Entregar en la tarde",
  "items": [{ "producto_id": 4, "cantidad": 2 }]
}
```

`entrega` es `"delivery"` o `"tienda"`; si es `"delivery"`, `direccion` y
`distrito` son obligatorios. `metodo_pago` es `"yape"`, `"transferencia"` o
`"contraentrega"`. `correo`, `referencia` y `nota` son opcionales.

Errores:

| Caso | Código | Detalle |
|---|---|---|
| Producto inexistente o inactivo | 422 | menciona el `producto_id` |
| Stock insuficiente | 422 | "quedan N, se pidieron M" |
| Carrito vacío (`items: []`) | 422 | validación de Pydantic |
| `entrega: "delivery"` sin dirección/distrito | 422 | "Para delivery hace falta dirección y distrito." |

Al crear el pedido **se valida el stock pero no se descuenta**: no hay aún un
flujo de cancelación que lo revierta (eso es etapa 6).

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
    models.py           Las seis tablas
    schemas.py          Lo que la API recibe y devuelve (Pydantic)
    crud.py             Las consultas y la lógica de crear pedidos
    seed.py             Carga del catálogo de ejemplo
    datos_semilla.json  Catálogo de ejemplo (fuente del seed)
    api/v1/             categorias.py, productos.py, pedidos.py, router.py
  alembic/versions/     Migraciones 0001, 0002 y 0003
  plantilla_catalogo.tsv  Plantilla para cargar tu catálogo real (ver abajo)
  docker-compose.yml    PostgreSQL para desarrollo
  requirements.txt
```

## Migraciones

| Revisión | Qué hace |
|---|---|
| `0001` | Esquema completo: las seis tablas y el tipo `estado_pedido` |
| `0002` | Añade a `productos` el contenido de la ficha: `presentacion`, `origen`, `descripcion_larga`, `modo_uso`, `beneficios` (array de texto), `precio_antes` y `mas_vendido` |
| `0003` | Añade a `pedidos` los datos que ya recoge el checkout: `distrito`, `referencia`, `email_contacto`, `nota` y `metodo_pago` (enum `metodo_pago_pedido`) |

La `0002` también pone un CHECK que impide guardar un `precio_antes` que no sea
mayor que el precio vigente: un precio tachado menor no sería una oferta.

## Cargar tu catálogo real

`plantilla_catalogo.tsv` tiene las mismas 16 columnas que lee `app/seed.py`
desde `datos_semilla.json`, con 3 filas de ejemplo ya llenas. No se carga
automáticamente: es una plantilla para cuando tengas tu catálogo real.

Formato de cada columna:

- `precio` / `precio_antes`: número con punto decimal (`28.50`). `precio_antes`
  vacío = no está en oferta; si se llena, debe ser mayor que `precio`.
- `beneficios`: varios ítems separados por `|` (pipe), sin `|` al final.
- `activo` / `destacado` / `mas_vendido`: `true` o `false`, en minúscula.
- `imagen_url`: vacío por ahora (ver "A tener en cuenta" abajo).
- `stock`: número entero.

Convertir este TSV a `datos_semilla.json` (o a inserts directos) para cargarlo
con `python -m app.seed` es un paso manual, fuera de esta etapa.

## A tener en cuenta

**Las imágenes vienen vacías.** `imagen_url` se sembró como `null` porque
todavía no hay fotos; el frontend dibuja su ilustración cuando no hay imagen.
Cuando existan las fotos, basta con llenar esa columna.

**La API pública solo devuelve productos activos.** Por eso el panel de
administración todavía no puede ver los desactivados: eso llega con los
endpoints `/api/v1/admin/...` de la etapa 6.
