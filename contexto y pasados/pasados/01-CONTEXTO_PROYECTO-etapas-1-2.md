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

## Modelo de datos (referencia para cuando se construya el backend)

- **Producto**: id, nombre, slug, descripción corta, categoría, precio,
  imagen(es), stock, activo/inactivo, destacado
- **Categoría**: id, nombre, slug
- **Pedido**: id, número de pedido, fecha, estado, total
- **PedidoItem**: pedido_id, producto_id, cantidad, precio unitario
- **Cliente** (opcional): id, nombre, email, teléfono, contraseña (hash)
- **Admin**: usuario único (Fernando)

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

1. Frontend visual con datos de prueba (ETAPA ACTUAL)
2. Carrito funcional sobre datos de prueba
3. Backend real: modelo de datos + API FastAPI
4. Conectar frontend al backend real
5. Flujo de pedido completo (checkout + número de pedido + WhatsApp)
6. Panel de administración
7. Pulido visual según feedback de Fernando

## Fuera de alcance en esta versión

Pagos en línea, apps móviles nativas, logística de envío automatizada,
múltiples administradores, lácteos/kéfires frescos, contenido extenso por
producto.
