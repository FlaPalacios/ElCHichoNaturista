# Publicar el sitio en Render

Guía para dejar la tienda en línea **como muestra**, para que otros la vean y
opinen. No es un montaje de producción: se usa el plan gratuito de Render, que
tiene límites que conviene conocer antes de compartir el enlace.

Lo que se publica son **tres cosas**: la base de datos, la API y el sitio.
En ese orden, porque cada una necesita la anterior.

---

## Antes de empezar

1. **Rotar las credenciales de Cloudinary.** Las actuales se escribieron en un
   chat, así que hay que darlas por perdidas. En el panel de Cloudinary se
   genera un par nuevo y el viejo se desactiva.
2. **Subir el proyecto a GitHub.** Render despliega desde un repositorio. El
   repositorio puede ser privado.
3. **Comprobar que `.env` no esté en GitHub.** Ya está en `.gitignore`, pero
   vale la pena mirarlo: ahí están la clave del panel y la de Cloudinary.

---

## Lo que el plan gratuito hace y conviene saber

| Qué pasa | Por qué importa |
|---|---|
| El servidor **se apaga tras ~15 minutos sin visitas** | La primera visita después de una pausa tarda cerca de un minuto en cargar. Es normal, no está roto |
| Render **borra las bases de datos gratuitas al cabo de unos 30 días** | Si la muestra va a durar más, hay que rehacerla. **Avisa por correo antes**: no lo ignores |
| Hay un tope de horas de servidor al mes | Con dos servicios que duermen casi todo el día no se llega, pero no dejes pestañas abiertas recargando |

El código ya está preparado para lo primero: espera hasta 55 segundos a que la
API despierte antes de darla por caída. Sin eso el sitio mostraría
"tienda no disponible" en cada primera visita.

**Avísale a quien le compartas el enlace** que la primera carga es lenta. Si no,
la primera impresión va a ser que el sitio no funciona.

---

## 1. La base de datos

En Render: **New → Postgres**. Plan **Free**.

Cuando termine de crearse, copia la **Internal Database URL**. Se ve así:

```
postgresql://usuario:clave@host/nombre_base
```

No hace falta cambiarle nada: la API traduce sola ese formato al driver que
usa (`postgresql+psycopg://`).

## 2. La API

**New → Web Service**, apuntando al repositorio.

| Campo | Valor |
|---|---|
| Root Directory | `backend` |
| Runtime | Python 3 |
| Build Command | `pip install -r requirements.txt && python -m app.instalar` |
| Start Command | `uvicorn app.main:app --host 0.0.0.0 --port $PORT` |
| Plan | Free |

El `python -m app.instalar` del build es lo que deja la base lista: aplica las
migraciones, carga el ubigeo, el catálogo y el usuario del panel. Se puede
correr en cada despliegue sin miedo porque **solo agrega lo que falta**: no
pisa un producto editado desde el panel ni una tarifa cambiada.

Variables de entorno:

| Variable | Valor |
|---|---|
| `DATABASE_URL` | la Internal Database URL del paso 1 |
| `ENTORNO` | `produccion` |
| `JWT_SECRETO` | una cadena larga al azar, distinta a la de tu máquina |
| `ADMIN_USUARIO` | `NatuAdmin` |
| `ADMIN_PASSWORD` | la clave del panel |
| `CLOUDINARY_CLOUD_NAME` | el de la cuenta |
| `CLOUDINARY_API_KEY` | la clave **nueva** |
| `CLOUDINARY_API_SECRET` | el secreto **nuevo** |
| `ORIGENES_CORS` | se llena en el paso 4, cuando exista la dirección del sitio |

Con `ENTORNO=produccion` la documentación de la API (`/docs`, `/redoc`) queda
cerrada. En tu máquina sigue abierta, porque ahí la variable no está puesta.

Al terminar, anota la dirección que te da Render. Va a ser algo como
`https://ecn-api.onrender.com`.

## 3. El sitio

**New → Web Service**, mismo repositorio.

| Campo | Valor |
|---|---|
| Root Directory | *(vacío: la raíz)* |
| Runtime | Node |
| Build Command | `npm install && npm run build` |
| Start Command | `npm start` |
| Plan | Free |

Variables de entorno:

| Variable | Valor |
|---|---|
| `PUBLIC_API_URL` | la dirección de la API del paso 2, **con `/api/v1` al final** |
| `HOST` | `0.0.0.0` |
| `SITIO_DEMO` | `true` |
| `SITIO_URL` | la dirección que Render le dé a este servicio |

`PORT` lo pone Render solo; no lo escribas.

`SITIO_DEMO=true` le pide a los buscadores que no indexen el sitio: el catálogo
está a medias y los precios no son definitivos, y una página que Google ya
guardó cuesta semanas de sacar. **Cuando el sitio sea el de verdad, borra esta
variable** — no hay que tocar código.

> **Ojo con `PUBLIC_API_URL`.** Se incrusta al compilar, no se lee al arrancar.
> Si la cambias, hay que volver a desplegar (*Manual Deploy → Clear build cache
> & deploy*), no basta con reiniciar.

## 4. Cerrar el círculo del CORS

Vuelve al servicio de la **API** y pon:

| Variable | Valor |
|---|---|
| `ORIGENES_CORS` | la dirección del sitio, por ejemplo `https://ecn.onrender.com` |

Sin barra al final. Si algún día hay más de una dirección, se separan con
comas.

Esto hace falta porque el navegador del cliente llama a la API directamente en
el carrito y el checkout, no solo el servidor. Si falta, el catálogo se ve pero
al confirmar un pedido no pasa nada.

Guarda, espera a que reinicie, y listo.

---

## Comprobar que quedó bien

Con la dirección del sitio en la mano:

1. **La API responde**: abre `…/api/v1/salud` en el servicio de la API. Debe
   decir `"base_de_datos": "conectada"`.
2. **La documentación está cerrada**: `…/docs` debe dar 404.
3. **Los buscadores están bloqueados**: `…/robots.txt` en el sitio debe decir
   `Disallow: /`.
4. **El catálogo carga**: la portada muestra productos con foto.
5. **El pedido llega hasta el final**: agrega algo, elige un destino, confirma,
   y comprueba que aparezca en el panel.
6. **El panel entra**: `…/admin` con el usuario y la clave.

El punto 5 es el que de verdad importa: es el único que prueba que la base, la
API y el sitio se hablan entre sí.

---

## Cuando esto deje de ser una muestra

- Borrar `SITIO_DEMO` del sitio, para que los buscadores puedan entrar.
- Poner el dominio propio en Render y en `SITIO_URL`, y agregarlo a
  `ORIGENES_CORS`.
- Pasar la base a un plan que no se borre, y el sitio a uno que no se duerma.
- Dejar la base en limpio antes de cargar datos reales:
  `python -m app.instalar --reset`.
