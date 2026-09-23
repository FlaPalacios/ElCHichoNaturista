# El Chico Naturista

E-commerce de productos naturales (Lima, Perú). Astro + Alpine.js por delante,
FastAPI + PostgreSQL por detrás. Sin pagos en línea: el pedido se cierra por
WhatsApp con un número de pedido generado en el checkout.

El sitio corre en **modo servidor (SSR)**: consulta la API en cada visita, así
los cambios de precio y stock se ven sin recompilar.

## Cómo correr

Hacen falta dos procesos. Primero el backend (instrucciones completas en
[backend/README.md](backend/README.md)):

```bash
cd backend
python -m app.instalar             # deja la base lista (la primera vez)
uvicorn app.main:app --reload      # http://127.0.0.1:8000
```

Y luego el sitio:

```bash
npm install
npm run dev                        # http://localhost:4321
npm run build                      # compila a dist/
node ./dist/server/entry.mjs       # sirve lo compilado
```

La URL de la API se configura en `.env` (`PUBLIC_API_URL`); por defecto apunta a
`http://127.0.0.1:8000/api/v1`. Si el backend no responde, el sitio no se cae:
muestra un aviso con el botón de WhatsApp.

## Publicarlo

Los pasos para dejarlo en línea están en [DESPLIEGUE.md](DESPLIEGUE.md).

## Estado según las etapas de CONTEXTO_PROYECTO.md

| Etapa | Estado |
|---|---|
| 1. Frontend visual con datos de prueba | hecha |
| 2. Carrito funcional sobre datos de prueba | hecha |
| 3. Backend FastAPI + PostgreSQL | hecha — ver [backend/README.md](backend/README.md) |
| 4. Conectar el frontend al backend | hecha — el sitio ya lee de la API |
| 5. Flujo de pedido completo | hecha — el checkout registra el pedido en el backend y abre WhatsApp |
| 6. Panel de administración | hecha — Pedidos, Productos, Categorías, Configuración, Resumen y Clientes |
| 7. Pulido visual según feedback | pendiente — nadie ha revisado el sitio en un navegador todavía |

El contexto completo del proyecto, al día, está en
[contexto y pasados/ahora/CONTEXTO_PROYECTO.md](contexto%20y%20pasados/ahora/CONTEXTO_PROYECTO.md).

## Páginas

| Ruta | Qué es |
|---|---|
| `/` | Portada de venta: banner de entrada, franja de beneficios, accesos por departamento y bloques de producto (destacados, más vendidos, ofertas y el resto del catálogo). Cada bloque aparece solo si tiene productos |
| `/catalogo` | El catálogo con búsqueda, filtros por categoría, subcategoría y marca, tope de precio, solo ofertas y 5 criterios de orden (el filtrado ocurre en el navegador, sin recargar) |
| `/producto/[slug]` | Ficha con descripción, beneficios, modo de uso, selector de cantidad y consulta directa por WhatsApp |
| `/carrito` | Revisión del pedido, cantidades, barra de envío gratis. El costo del envío no se sabe hasta elegir el distrito en el checkout |
| `/checkout` | Datos, dirección (departamento → provincia → distrito, todo el Perú) y nota → registra el pedido en el backend (`ECN-AAMMDD-NNNN` lo genera la API) y abre WhatsApp con el detalle escrito. Si el backend no responde, genera el número localmente y lo marca para sincronizar después |
| `/cuenta` | Consulta de un pedido por su número + último pedido guardado en el navegador |
| `/admin` | Panel interno, con su propio layout (sin encabezado, pie, carrito ni botón de WhatsApp). Pide usuario y contraseña |
| `/admin/productos` | Catálogo completo con filtros (categoría, subcategoría, marca, estado, poco stock y seis órdenes). Edición rápida de stock, activar/desactivar, ficha con todos los campos, fotos a Cloudinary, exportar e importar TSV |
| `/admin/categorias` | Categorías, subcategorías y marcas: crear, editar, reordenar y borrar |
| `/admin/configuracion` | Datos de la tienda, mensajes, envío gratis, umbral de stock y la tabla de costos de envío por zona |
| `/admin/resumen` | Pedidos por atender, ventas del mes, top 5 y lo que se está acabando |
| `/admin/clientes` | Clientes derivados de los pedidos, agrupados por teléfono |
| 404 | Página de rutas alternativas |

## Estructura

```
src/
  alpine.js              Stores de Alpine: carrito y pedido (localStorage)
  middleware.js          Carga los datos de la tienda una vez por visita
  lib/
    api.js               Único punto de contacto con la API pública
    admin.js             Sesión del panel (cookie httpOnly) y llamadas con token
    tienda.js            Datos de la tienda desde la API, con respaldo local
    cloudinary.js        Arma la URL de cada foto al tamaño que hace falta
  data/
    tienda.js            WhatsApp, dirección, horario, avisos, envío gratis
  layouts/
    Base.astro           Head, fuentes, header, footer, panel de carrito, botón flotante
    Admin.astro          Layout del panel: solo menú lateral y contenido
  components/
    Header.astro         Cintillo rotativo, mega-menú por departamentos, buscador
    Footer.astro         Navegación, datos de contacto, aviso legal
    ProductoCard.astro   Ficha de producto reutilizable
    CarritoPanel.astro   Panel lateral del carrito
    FotoProducto.astro   Foto de Cloudinary, o marco con el sello si no hay foto
    ApiCaida.astro       Aviso cuando la API no responde
  pages/                 Una por ruta
  styles/global.css      Tokens de marca, tipografía, botones, formularios
```

## Decisiones que conviene conocer

**Imágenes de producto.** Fotos alojadas en Cloudinary (tabla `product_images`).
La de orden 1 es la principal en tarjetas; la ficha muestra todas con
miniaturas. [src/lib/cloudinary.js](src/lib/cloudinary.js) pide cada foto al
ancho que hace falta, así el navegador no baja el original.

**Cómo está organizado el catálogo.** Dos niveles: categoría (Frescos,
Abarrotes, Cuidado Personal) → subcategoría, más la marca del producto
(Green House / HIRI, Henna Colors, Fit Rex, Algarrobos Orgánicos). El menú y
la portada muestran las categorías; el catálogo filtra por los tres. Las
categorías, subcategorías y marcas sin productos activos no se muestran.

**De dónde salen los productos.** De la API, vía [src/lib/api.js](src/lib/api.js),
que además traduce los nombres de campo de la API a los que usan los
componentes. No queda catálogo escrito en el frontend.

**Envío.** S/ 10 a los 43 distritos de la provincia de Lima y a los 7 del
Callao, S/ 15 al resto del Perú, y gratis en todo el país desde S/ 120. El
costo sale de una tabla en la base editable desde el panel, no del código. El
checkout pide departamento, provincia y distrito con el padrón del INEI (1891
distritos), y el carrito no muestra costo de envío hasta ese momento porque
depende del destino.

**Sin recojo en tienda ni método de pago.** Todo pedido es delivery. El pago se
coordina por WhatsApp (Yape, Plin o transferencia); en el checkout es solo una
nota informativa.

**La sesión del panel vive en una cookie httpOnly.** El token JWT nunca queda
al alcance del JavaScript de la página: las pantallas del panel piden los datos
desde el servidor, y los cambios (estado de un pedido, nota interna) pasan por
`/api/admin/…`, un puente que reenvía a FastAPI poniendo el token. Ese puente
solo alcanza rutas bajo `/admin` de la API.

**Los datos de la tienda se editan desde el panel.** El WhatsApp, la
dirección, las redes, los avisos del cintillo y el monto de envío gratis salen
de la base. [src/middleware.js](src/middleware.js) los carga una vez por visita
y los deja en `Astro.locals.tienda`, así ningún componente los pide por su
cuenta. Si la API no responde se usan los de
[src/data/tienda.js](src/data/tienda.js) y el sitio sigue mostrando algo
sensato.

**El catálogo se edita desde el panel.** La base manda; la planilla
`backend/app/datos/catalogo.tsv` quedó como carga inicial. Desde el panel se
exporta el catálogo a TSV (abre en Excel) y se vuelve a importar editado.

**Carrito y pedido.** El carrito vive en `localStorage` (`ecn.carrito.v1`) y se
sincroniza entre pestañas. El pedido se crea en el backend (`POST
/api/v1/pedidos`, que recalcula precios y envío desde la base) y también se
guarda en `localStorage` (`ecn.pedidos.v1`) para el historial de `/cuenta`. Si
la API no responde, el checkout genera el número localmente como respaldo,
abre WhatsApp igual (nunca se pierde una venta), y lo marca como "guardado en
este dispositivo" hasta poder sincronizarlo. El checkout arma el mensaje de
WhatsApp con el detalle, el total y los datos de entrega.

**Tipografía y layout.** Hind en bold para titulares y Amulya regular para el
texto, ambas servidas desde `public/fonts` (sin llamadas a Google ni Fontshare).
Reglas finas en vez de sombras, composiciones asimétricas y numeradas. La idea
es que parezca un negocio con identidad propia, no una plantilla. Ninguna de las
dos tiene ejes variables por CDN, así que se cargan los pesos que se usan:
400/500/600/700 de Hind y 400/500/700 de Amulya. Detalles y licencias en
`public/fonts/LEEME.txt`.

**Todos los colores salen de `:root` en
[src/styles/global.css](src/styles/global.css).** Fuera de ahí no hay colores
escritos a mano (la única excepción es el `<meta name="theme-color">` de
`Base.astro`, que no acepta variables). Para cambiar la paleta se tocan esas
variables y listo. Los tres tonos atenuados del café (`--cafe-texto`,
`--cafe-suave`, `--cafe-linea`) se calculan a partir de `--cafe` con
`color-mix`, así que cambiando el café cambian los tres. Lo mismo del lado
claro con `--sobre-salvia` y `--linea-salvia`.

**Verde jade `#7A9B87` en las superficies grandes.** El encabezado del sitio
y las cajas de resumen del carrito, checkout y cuenta usan jade (`--jade`) como
fondo, con texto e íconos en tonos oscuros (`--cafe-texto`, `--cafe-suave`)
para que se sigan leyendo — jade es un verde claro, así que ahí va texto
oscuro, no claro.

**Café `#211E1E` solo en detalles pequeños.** El color oscuro (`--cafe`) se
quedó a propósito nada más en botones y puntos concretos que no ocupan mucho
espacio: el botón «agregar al carrito» (tarjetas y ficha de producto), el
contador de unidades del carrito, el aviso flotante al agregar un producto
("brindis"), y el texto de los títulos en toda la web. No se usa como fondo de
ninguna sección ni panel grande. Los botones llevan una curva ligera de 5px
(`--radio`).

**Sin líneas divisorias.** Se quitaron dos elementos puramente decorativos: la
greca en zigzag que estaba arriba del footer, y la línea horizontal que unía
cada título de sección con su enlace "ver más" (ahora ese espacio lo resuelve
`justify-content: space-between`). Los separadores punteados entre productos
de una misma lista (carrito, resumen del pedido) se mantuvieron, porque
cumplen una función distinta: distinguir una fila de la siguiente, no dividir
partes de la página.

**Imágenes con esquinas redondeadas.** La ilustración de cada producto
(tarjetas del catálogo/portada y la imagen grande de la ficha) tiene ahora
`border-radius` (14–16px) en vez de esquinas rectas.

**Footer más compacto.** Menos margen antes de empezar, logo más chico
(76px en vez de 104px), y menos espaciado entre los bloques de enlaces.

**Botón "quitar" del carrito.** Es un ícono de basurero (antes decía
"Quitar" en texto), con hover en `--rojo` (`#C0392B`), en el panel lateral y en
`/carrito`.

**Botones de WhatsApp.** Pasaron de un verde WhatsApp saturado (`#1F7A4D`) al
verde jade de la marca (`--jade`, con hover en `--salvia`). Es una decisión de
marca deliberada; el texto blanco sobre jade tiene algo menos de contraste que
antes (~3.1:1 frente al mínimo de 4.5:1 de WCAG AA para texto normal) — si en
algún momento se quiere más legibilidad ahí, la forma más simple es oscurecer
el texto del botón en vez de aclarar el fondo.

**Categorías de la portada.** Botones-píldora redondeados con una insignia
circular numerada a la izquierda (solo las categorías con productos activos); el círculo ya está listo
para reemplazarse por una foto de categoría más adelante (`overflow: hidden`).
Sin conteo de productos, a propósito: minimalista.

**Hero de la portada.** Carrusel de 3 fotos (hoy las 3 son la misma imagen;
falta un par de fotos más para diferenciarlas) y más corto que antes
(`clamp(300px, 34vw, 420px)` en vez de `420–620px`), para que la fila de
categorías quede visible sin bajar mucho.

**Logo.** `logo-1.png` en la raíz venía con un damero gris de fondo en lugar de
transparencia; `public/logo-1.png` es la versión con fondo transparente, que es
la que usa el sitio.

**Banner de la portada.** El original es `img-paginaprincipal.png` (2,1 MB) en
la raíz. El sitio carga las versiones optimizadas de `public/`: `hero-1672.webp`
(189 KB), `hero-1200.webp`, `hero-760.webp` y `hero.jpg` como respaldo. Si
cambias la foto, vuelve a generar esas cuatro.

**La portada no cuenta la historia de la marca.** Es una vitrina: banner,
beneficios y producto tras producto, siguiendo la estructura de mundoverde.com.pe.

## Antes de publicar

- `src/data/tienda.js`: el WhatsApp (`51946049689`) y la dirección ya son los
  reales. Falta confirmar el correo y los enlaces de Instagram y Facebook.
- Completar los 8 borradores del catálogo (galletas, algarrobina y maca: sin
  precio ni descripción) desde el panel.
- Dejar la base en limpio con `python -m app.instalar --reset`, que borra los
  datos de prueba y carga el catálogo real.
- Rotar las credenciales de Cloudinary, que se compartieron por chat.
- Cambiar `site` en `astro.config.mjs` por el dominio definitivo.
