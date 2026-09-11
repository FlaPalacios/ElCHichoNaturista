# El Chico Naturista

E-commerce de productos naturales (Lima, Perú). Astro + Alpine.js, sin pagos en
línea: el pedido se cierra por WhatsApp con un número de pedido generado en el
checkout.

## Cómo correr

```bash
npm install
npm run dev      # http://localhost:4321
npm run build    # sitio estático en dist/
npm run preview  # sirve dist/
```

## Estado según las etapas de CONTEXTO_PROYECTO.md

| Etapa | Estado |
|---|---|
| 1. Frontend visual con datos de prueba | hecha |
| 2. Carrito funcional sobre datos de prueba | hecha |
| 3. Backend FastAPI + PostgreSQL | pendiente |
| 4. Conectar el frontend al backend | pendiente |
| 5. Flujo de pedido completo | hecha en el front (número de pedido + `wa.me`); falta persistirlo en el backend |
| 6. Panel de administración | maqueta visual, sin datos reales ni autenticación |
| 7. Pulido visual según feedback | esperando tu revisión |

## Páginas

| Ruta | Qué es |
|---|---|
| `/` | Portada de venta: banner de entrada, franja de beneficios, accesos por departamento y cinco bloques de producto (más vendidos, ofertas, Henna Colors, aceites, superalimentos) |
| `/catalogo` | 25 productos con búsqueda, filtro por departamento, tope de precio, solo ofertas y 5 criterios de orden (todo en el navegador, sin recargar) |
| `/producto/[slug]` | Ficha con descripción, beneficios, modo de uso, selector de cantidad y consulta directa por WhatsApp |
| `/carrito` | Revisión del pedido, cantidades, barra de envío gratis |
| `/checkout` | Datos, entrega, forma de pago → genera `ECN-AAMMDD-NNNN` y abre WhatsApp con el detalle escrito |
| `/cuenta` | Ingresar / crear cuenta (maqueta) + último pedido guardado en el navegador |
| `/admin` | Tablero interno: métricas, pedidos e inventario (maqueta) |
| 404 | Página de rutas alternativas |

## Estructura

```
src/
  alpine.js              Stores de Alpine: carrito y pedido (localStorage)
  data/
    productos.js         25 productos y 4 categorías de prueba + helpers
    tienda.js            WhatsApp, dirección, horario, avisos, envío gratis
  layouts/Base.astro     Head, fuentes, header, footer, panel de carrito, botón flotante
  components/
    Header.astro         Cintillo rotativo, mega-menú por departamentos, buscador
    Footer.astro         Navegación, datos de contacto, aviso legal
    ProductoCard.astro   Ficha de producto reutilizable
    CarritoPanel.astro   Panel lateral del carrito
    Etiqueta.astro       Imagen de producto dibujada en SVG (ver abajo)
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

**Carrito y pedido.** Viven en `localStorage` (`ecn.carrito.v1`,
`ecn.pedidos.v1`) y se sincronizan entre pestañas. El checkout arma el mensaje
de WhatsApp con el detalle, el total y los datos de entrega. En la etapa 3 el
número de pedido debe pasar a generarlo la API.

**Tipografía y layout.** Fraunces (titulares) y Karla (texto), reglas finas en
vez de sombras, composiciones asimétricas y numeradas. La idea es que parezca
un negocio con identidad propia, no una plantilla.

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
- Reemplazar los productos de prueba por el catálogo real (precios, stock y
  origen).
- Cambiar `site` en `astro.config.mjs` por el dominio definitivo.
