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
uvicorn app.main:app --reload      # http://127.0.0.1:8000
```

Y luego el sitio:

```bash
npm install
npm run dev                        # http://localhost:4321
npm run build                      # compila a dist/
node ./dist/server/entry.mjs       # sirve lo compilado
```

La URL de la API se configura en `.env` (`API_URL`); por defecto apunta a
`http://127.0.0.1:8000/api/v1`. Si el backend no responde, el sitio no se cae:
muestra un aviso con el botón de WhatsApp.

## Estado según las etapas de CONTEXTO_PROYECTO.md

| Etapa | Estado |
|---|---|
| 1. Frontend visual con datos de prueba | hecha |
| 2. Carrito funcional sobre datos de prueba | hecha |
| 3. Backend FastAPI + PostgreSQL | hecha — ver [backend/README.md](backend/README.md) |
| 4. Conectar el frontend al backend | hecha — el sitio ya lee de la API |
| 5. Flujo de pedido completo | hecha — el checkout registra el pedido en el backend y abre WhatsApp |
| 6. Panel de administración | maqueta visual, sin datos reales ni autenticación |
| 7. Pulido visual según feedback | esperando tu revisión |

## Páginas

| Ruta | Qué es |
|---|---|
| `/` | Portada de venta: banner de entrada, franja de beneficios, accesos por departamento y cinco bloques de producto (más vendidos, ofertas, Henna Colors, aceites, superalimentos) |
| `/catalogo` | El catálogo con búsqueda, filtro por departamento, tope de precio, solo ofertas y 5 criterios de orden (el filtrado ocurre en el navegador, sin recargar) |
| `/producto/[slug]` | Ficha con descripción, beneficios, modo de uso, selector de cantidad y consulta directa por WhatsApp |
| `/carrito` | Revisión del pedido, cantidades, barra de envío gratis |
| `/checkout` | Datos, entrega, forma de pago → registra el pedido en el backend (`ECN-AAMMDD-NNNN` lo genera la API) y abre WhatsApp con el detalle escrito. Si el backend no responde, genera el número localmente y lo marca para sincronizar después |
| `/cuenta` | Ingresar / crear cuenta (maqueta) + último pedido guardado en el navegador |
| `/admin` | Tablero interno: inventario y métricas reales de la base; los pedidos y el acceso siguen siendo maqueta |
| 404 | Página de rutas alternativas |

## Estructura

```
src/
  alpine.js              Stores de Alpine: carrito y pedido (localStorage)
  lib/api.js             Único punto de contacto con la API de FastAPI
  data/
    tienda.js            WhatsApp, dirección, horario, avisos, envío gratis
  layouts/Base.astro     Head, fuentes, header, footer, panel de carrito, botón flotante
  components/
    Header.astro         Cintillo rotativo, mega-menú por departamentos, buscador
    Footer.astro         Navegación, datos de contacto, aviso legal
    ProductoCard.astro   Ficha de producto reutilizable
    CarritoPanel.astro   Panel lateral del carrito
    Etiqueta.astro       Imagen de producto dibujada en SVG (ver abajo)
    ApiCaida.astro       Aviso cuando la API no responde
    Greca.astro          Divisor con la greca del sello
  pages/                 Una por ruta
  styles/global.css      Tokens de marca, tipografía, botones, formularios
```

## Decisiones que conviene conocer

**Imágenes de producto.** Todavía no hay fotos, así que cada producto se dibuja
con `Etiqueta.astro`: un envase deducido de su presentación (sobre, frasco
ámbar, bolsa, botella…) sobre el paisaje del sello, con una gama de color por
departamento y tonos propios para los tintes de henna. Cuando existan fotos
reales, se cambia ese componente por un `<img>` y nada más se toca.

**De dónde salen los productos.** De la API, vía [src/lib/api.js](src/lib/api.js),
que además traduce los nombres de campo de la API a los que usan los
componentes. No queda catálogo escrito en el frontend.

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

**Verde jade `#7A9B87` en las superficies grandes.** El encabezado del sitio,
la banda de cierre de la portada, y las cajas de resumen del carrito, checkout
y cuenta usan jade (`--jade`) como fondo, con texto e íconos en tonos oscuros
(`--cafe`, `--salvia-osc`, o esos mismos a media opacidad) para que se sigan
leyendo — jade es un verde claro, así que ahí va texto oscuro, no claro.

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

**Categorías de la portada.** Cuatro botones-píldora redondeados con una
insignia circular numerada (01–04) a la izquierda; el círculo ya está listo
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
- Reemplazar los productos de ejemplo de la base por el catálogo real (el seed
  está en `backend/app/datos_semilla.json`).
- Cambiar `site` en `astro.config.mjs` por el dominio definitivo.
