# Prompts para la web de El Chico Naturista (sincronizar con el Google Sheet)

Usar en orden, en la misma sesión de Claude Code abierta en el repositorio de la web.
Stack: Astro + Alpine (frontend), FastAPI + PostgreSQL (backend), panel de administración con JWT.

---

## Prompt 1. Diagnóstico (no cambia nada)

```
Contexto: esta es la tienda online El Chico Naturista (Astro + Alpine en el frontend, FastAPI + PostgreSQL en el backend, panel de administración con JWT para un único administrador). El negocio lleva sus costos, compras, caja y ganancias en un Google Sheet que se alimenta con una exportación de pedidos de esta web. La web es la fuente de verdad del catálogo, los precios, el stock y los pedidos.

Antes de cambiar nada, revisa el código y dame un informe corto con:
1. Modelos y tablas de Producto, Pedido e Ítem de pedido: campos que existen hoy.
2. Si el producto tiene un campo "codigo" (formato ECN-001) y si es único.
3. Estados de pedido que existen y dónde se cambian.
4. En qué momento se descuenta el stock hoy (al crear el pedido, al confirmarlo, nunca).
5. Si el pedido guarda costo de envío, subtotal y total, y cómo se calcula el envío.
6. Cómo funciona la importación de catálogo por TSV (si existe): si actualiza por código o por slug y si sobrescribe el stock.
7. Si existe alguna exportación de pedidos o productos.
No modifiques archivos. Al final, lista qué falta para cumplir con los prompts que te voy a pasar.
```

---

## Prompt 2. Código de producto fijo e importación segura

```
Necesito que el código de producto sea el identificador compartido entre la web y el Google Sheet.

1. Producto debe tener el campo "codigo" (texto, formato ECN-001, único, obligatorio). Si no existe, créalo con una migración y rellénalo para los productos actuales usando el mismo código que ya viene en el TSV de catálogo.
2. En el panel: mostrar el código en el listado y en el formulario. Al crear un producto, proponer automáticamente el siguiente código (ECN-027, ECN-028...). Una vez creado, el código no se puede editar (mostrarlo como solo lectura).
3. La importación del TSV de catálogo debe:
   - Buscar el producto por "codigo" (no por nombre ni por slug). Si existe, actualizarlo. Si no existe, crearlo.
   - NO modificar el stock de productos que ya existen. El stock del TSV solo se usa al crear un producto nuevo.
   - Mostrar al final un resumen: creados, actualizados, filas con error.
4. Agrega tests para: importación que actualiza sin tocar stock, importación que crea con stock inicial, código duplicado rechazado.
```

---

## Prompt 3. Estados del pedido, fecha de pago y stock

```
Quiero que el ciclo de un pedido sea claro y que el stock solo baje cuando el pago está confirmado.

1. Estados del pedido: pendiente, pagado, enviado, completado, cancelado. Si hoy existe "coordinado", reemplázalo por "pagado" con una migración de datos (los pedidos en "coordinado" pasan a "pagado").
2. Agregar al pedido el campo "fecha_pago" (fecha y hora, zona America/Lima). Se llena automáticamente cuando el administrador cambia el estado a "pagado". Debe poder editarse a mano desde el panel por si el pago fue otro día.
3. Stock:
   - Al crear el pedido (checkout) solo se valida que haya stock suficiente, no se descuenta.
   - Al pasar a "pagado" se descuenta el stock de cada ítem. Si en ese momento ya no alcanza el stock, mostrar un aviso claro al administrador y no permitir el cambio.
   - Si un pedido que ya estaba "pagado", "enviado" o "completado" pasa a "cancelado", se devuelve el stock.
   - Cancelar un pedido "pendiente" no toca el stock.
   - Todo esto en una transacción, para que el stock nunca quede a medias.
4. En el listado de pedidos del panel: filtro por estado y un aviso visual para pedidos pendientes con más de 48 horas (para que el administrador decida si cancelarlos).
5. Tests para cada transición de estado y su efecto en el stock.
```

---

## Prompt 4. Envío dentro del pedido

```
El envío se cobra dentro del pedido, pero es gratis desde cierto monto. Quiero que sea configurable y que quede guardado en cada pedido.

1. Crear una configuración editable desde el panel (tabla de ajustes):
   - Monto mínimo para envío gratis (valor inicial: 120 soles).
   - Tarifa de envío Lima y tarifa de envío provincia (valores a definir por el administrador).
2. En el checkout el cliente elige Lima o provincia. Calcular: subtotal de productos, costo de envío (0 si el subtotal es mayor o igual al mínimo) y total.
3. Guardar en el pedido: subtotal, costo_envio, total y zona_envio. El costo de envío queda congelado aunque luego cambie la configuración.
4. Mostrar el envío en el carrito, en el resumen del checkout, en el detalle del pedido del panel y en el mensaje de WhatsApp que se genera ("Envío: S/ 10.00" o "Envío: gratis").
5. Tests: subtotal bajo el mínimo cobra tarifa, subtotal en el mínimo o encima es gratis, cambiar la configuración no altera pedidos ya creados.
```

---

## Prompt 5. Botón "Exportar pedidos (CSV)"

```
Necesito exportar los pedidos para importarlos en Google Sheets. El formato tiene que ser exactamente este, porque el Sheet lee las columnas por posición.

1. Endpoint protegido (solo administrador): GET /api/admin/export/pedidos.csv
   - Exporta el HISTORIAL COMPLETO de pedidos (todos los estados), ordenado por fecha y número de pedido.
   - Opcional: parámetros desde y hasta (fechas) para filtrar.
2. Formato del archivo:
   - UTF-8 con BOM, separado por comas, texto entre comillas cuando tenga comas.
   - Primera fila exacta: N° pedido,Fecha pedido,Fecha pago,Estado,Cliente,Código,Producto,Cantidad,Precio unitario
   - Una fila por cada ítem del pedido. Un pedido con 3 productos ocupa 3 filas con el mismo N° pedido.
   - Si el pedido tiene costo de envío (aunque sea 0), agregar una fila más con Código = ENVIO, Producto = Envío, Cantidad = 1, Precio unitario = costo de envío cobrado.
   - Fechas en formato AAAA-MM-DD, zona America/Lima. Fecha pago vacía si no hay.
   - Estado en minúsculas: pendiente, pagado, enviado, completado, cancelado.
   - Precio unitario = precio cobrado en ese pedido (el guardado en el ítem), no el precio actual del producto. Decimales con punto, sin símbolo de moneda.
   - Cliente = solo el nombre. No incluir teléfono, correo ni dirección.
   - Código = código ECN del producto.
3. En el panel, en la página de pedidos, un botón "Exportar pedidos (CSV)" que descarga el archivo con el nombre pedidos-AAAA-MM-DD.csv.
4. Tests: un pedido con 2 ítems y envío genera 3 filas, el encabezado es exacto, los estados salen en minúsculas, un pedido cancelado también aparece.
```

---

## Prompt 6. Cargar las 18 ventas antiguas

```
Antes de la web hubo 18 líneas de venta (7 pedidos, V-001 a V-007) que se hicieron sin la web. Están en el archivo ventas-antiguas-para-cargar-en-web.csv con el mismo formato de la exportación.

1. Crear un script de carga única (por ejemplo backend/scripts/cargar_ventas_antiguas.py) que lea ese CSV y cree los pedidos con:
   - número de pedido igual al del archivo (V-001...),
   - estado completado, origen "manual",
   - las fechas del archivo (si vienen vacías, usar la fecha que yo indique por parámetro),
   - precio unitario del archivo.
2. Muy importante: estos pedidos NO deben descontar stock (el stock actual ya considera esas ventas).
3. El script debe ser idempotente: si se corre dos veces no duplica pedidos.
4. Si es simple, agrega también en el panel la opción "Registrar venta manual" para ventas fuera de la web (mismo comportamiento que un pedido normal, que sí descuenta stock al marcarlo pagado).
```

---

## Prompt 7 (opcional). Exportar productos y alerta de stock bajo

```
1. Endpoint protegido GET /api/admin/export/productos.csv y botón "Exportar productos (CSV)" en el panel, con columnas: Código,Producto,Precio,Stock,Activo (mismo formato UTF-8 con BOM, decimales con punto, Activo = si/no). Sirve para comparar el stock y los precios con el Google Sheet.
2. Agregar a Producto el campo "stock_minimo" (entero, por defecto 2). En el listado de productos del panel, marcar en amarillo los que tengan stock menor o igual al mínimo y en rojo los que estén en 0.
```

---

## Prompt 8 (más adelante). Que el Sheet lea los pedidos solo

```
Quiero que Google Sheets lea la exportación de pedidos sin descargar el archivo a mano.

1. Crear un endpoint GET /api/export/pedidos.csv?token=XXXX que devuelva exactamente el mismo CSV del prompt 5, protegido por un token largo y aleatorio guardado en una variable de entorno (EXPORT_TOKEN), sin login.
2. Si el token no coincide, responder 404 (no 401), para no revelar que la ruta existe.
3. Limitar a 30 solicitudes por hora por IP.
4. Documentar en el README cómo rotar el token.
Después en el Sheet, en la celda A1 de "Importar pedidos", se usará =IMPORTDATA("https://dominio/api/export/pedidos.csv?token=XXXX").
```
Advertencia del prompt 8: cualquier persona con acceso al Sheet puede ver el token y leer los nombres de clientes. Mantener el Sheet compartido solo con Fernando y contigo.

---

## Campos compartidos entre la web y el Sheet

| En la web | En el Sheet | Regla |
|---|---|---|
| producto.codigo | Productos: Código / Ventas: Código | ECN-001, único, nunca se cambia |
| producto.nombre | Productos: Producto | Mismo nombre en ambos |
| producto.precio | Productos: Precio en la web | Se cambia en la web y se copia al Sheet |
| producto.stock | (solo control en Inventario) | Manda la web |
| pedido.numero | Importar pedidos: N° pedido | Lo genera la web |
| pedido.estado | Importar pedidos: Estado | pendiente, pagado, enviado, completado, cancelado |
| pedido.fecha_pago | Importar pedidos: Fecha pago | Se llena al marcar pagado |
| pedido.costo_envio | Fila con código ENVIO | 0 si es envío gratis |
| item.precio_unitario | Importar pedidos: Precio unitario | Precio cobrado en ese momento |
