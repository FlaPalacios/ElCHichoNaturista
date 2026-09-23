// Único punto de contacto con la API de FastAPI.
// Las páginas no llaman a fetch: piden los datos a estas funciones.

import { ESPERA } from './entorno.js';

// PUBLIC_ porque este archivo también corre en el navegador (checkout y
// carrito): Astro solo expone al cliente las variables con ese prefijo.
const BASE = (
  import.meta.env.PUBLIC_API_URL || 'http://127.0.0.1:8000/api/v1'
).replace(/\/$/, '');

/** Error de la API con el estado HTTP, para distinguir un 404 de una caída. */
export class ErrorApi extends Error {
  constructor(mensaje, estado, ruta) {
    super(mensaje);
    this.name = 'ErrorApi';
    this.estado = estado;
    this.ruta = ruta;
  }

  /** true cuando la API respondió "no existe", no cuando está caída. */
  get noEncontrado() {
    return this.estado === 404;
  }
}

/** Hace el fetch de verdad y traduce cualquier fallo a ErrorApi. Común a GET y POST. */
async function _solicitar(url, ruta, opciones) {
  let respuesta;
  try {
    respuesta = await fetch(url, { signal: AbortSignal.timeout(ESPERA), ...opciones });
  } catch (causa) {
    // La API no respondió: apagada, red caída o timeout.
    throw new ErrorApi(
      `No se pudo conectar con la API en ${BASE}. ¿Está levantado el backend?`,
      0,
      ruta
    );
  }

  if (!respuesta.ok) {
    let detalle = respuesta.statusText;
    try {
      const cuerpo = await respuesta.json();
      if (cuerpo?.detail) {
        // FastAPI a veces manda detail como lista de errores de validación.
        detalle = typeof cuerpo.detail === 'string' ? cuerpo.detail : JSON.stringify(cuerpo.detail);
      }
    } catch {
      /* la respuesta no traía JSON; nos quedamos con el statusText */
    }
    throw new ErrorApi(detalle, respuesta.status, ruta);
  }

  return respuesta.json();
}

async function pedir(ruta, parametros = {}) {
  const url = new URL(BASE + ruta);
  for (const [clave, valor] of Object.entries(parametros)) {
    if (valor !== undefined && valor !== null && valor !== '') {
      url.searchParams.set(clave, String(valor));
    }
  }
  return _solicitar(url, ruta, { headers: { Accept: 'application/json' } });
}

/** POST con body JSON. Usada por los endpoints que crean algo (pedidos). */
async function enviarJson(ruta, cuerpo) {
  const url = new URL(BASE + ruta);
  return _solicitar(url, ruta, {
    method: 'POST',
    headers: { Accept: 'application/json', 'Content-Type': 'application/json' },
    body: JSON.stringify(cuerpo),
  });
}

/**
 * Traduce un producto de la API (snake_case, categoría anidada) a la forma
 * que ya usan los componentes del sitio.
 */
function adaptarProducto(p) {
  return {
    id: p.id,
    nombre: p.nombre,
    slug: p.slug,
    categoria: p.subcategoria.categoria.slug,
    categoriaNombre: p.subcategoria.categoria.nombre,
    subcategoria: p.subcategoria.slug,
    subcategoriaNombre: p.subcategoria.nombre,
    marca: p.marca.slug,
    marcaNombre: p.marca.nombre,
    precio: Number(p.precio),
    precioAntes: p.precio_antes != null ? Number(p.precio_antes) : undefined,
    presentacion: p.presentacion ?? '',
    descripcionCorta: p.descripcion_corta ?? '',
    descripcion: p.descripcion_larga ?? '',
    modoUso: p.modo_uso ?? '',
    beneficios: p.beneficios ?? [],
    codigo: p.codigo,
    // Ya ordenadas por la API; la primera (orden 1) es la principal.
    imagenes: (p.imagenes ?? []).map((i) => ({ url: i.url, tipo: i.tipo })),
    stock: p.stock,
    activo: p.activo,
    destacado: p.destacado,
    masVendido: p.mas_vendido,
  };
}

/** Categorías del menú, cada una con sus subcategorías. */
export async function obtenerCategorias() {
  const datos = await pedir('/categorias');
  return datos.map((c) => ({
    id: c.id,
    nombre: c.nombre,
    slug: c.slug,
    orden: c.orden,
    subcategorias: (c.subcategorias ?? []).map((s) => ({
      id: s.id,
      nombre: s.nombre,
      slug: s.slug,
    })),
  }));
}

/** Marcas con productos a la venta, para el filtro del catálogo. */
export async function obtenerMarcas() {
  const datos = await pedir('/marcas');
  return datos.map((m) => ({ id: m.id, nombre: m.nombre, slug: m.slug }));
}

/**
 * Lista productos activos.
 * Filtros: categoria, subcategoria, marca, precioMin, precioMax, q, destacado,
 * masVendido, enOferta.
 */
export async function obtenerProductos(filtros = {}) {
  const datos = await pedir('/productos', {
    categoria: filtros.categoria,
    subcategoria: filtros.subcategoria,
    marca: filtros.marca,
    precio_min: filtros.precioMin,
    precio_max: filtros.precioMax,
    q: filtros.q,
    destacado: filtros.destacado,
    mas_vendido: filtros.masVendido,
    en_oferta: filtros.enOferta,
  });
  return datos.map(adaptarProducto);
}

/** Devuelve el producto o null si no existe o está inactivo. */
export async function obtenerProducto(slug) {
  try {
    return adaptarProducto(await pedir(`/productos/${encodeURIComponent(slug)}`));
  } catch (error) {
    if (error instanceof ErrorApi && error.noEncontrado) return null;
    throw error;
  }
}

export async function comprobarSalud() {
  return pedir('/salud');
}

/**
 * Traduce un pedido de la API a la forma que ya consumen checkout.astro,
 * cuenta.astro y mensajeWhatsApp: items en snake_case
 * ({producto_id, nombre, cantidad, precio_unitario}), igual que el pedido que
 * antes se armaba solo en localStorage.
 */
function adaptarPedido(p) {
  return {
    numero: p.numero_pedido,
    fecha: p.creado_en,
    estado: p.estado,
    direccionEnvio: p.direccion_envio,
    departamento: p.departamento,
    provincia: p.provincia,
    distrito: p.distrito,
    referencia: p.referencia,
    nota: p.nota,
    correo: p.email_contacto,
    items: p.items.map((i) => ({
      producto_id: i.producto.id,
      nombre: i.producto.nombre,
      cantidad: i.cantidad,
      precio_unitario: Number(i.precio_unitario),
    })),
    subtotal: Number(p.subtotal),
    envio: Number(p.envio),
    total: Number(p.total),
  };
}

/** payload ya en snake_case (lo arma el store `pedido` de src/alpine.js). */
export async function crearPedido(payload) {
  return adaptarPedido(await enviarJson('/pedidos', payload));
}

/** Devuelve el pedido o null si no existe. */
export async function obtenerPedido(numero) {
  try {
    return adaptarPedido(await pedir(`/pedidos/${encodeURIComponent(numero)}`));
  } catch (error) {
    if (error instanceof ErrorApi && error.noEncontrado) return null;
    throw error;
  }
}

// ── Ubigeo y envío ──────────────────────────────────────────────────

/** Los 25 departamentos del Perú. */
export async function obtenerDepartamentos() {
  return pedir('/ubigeo/departamentos');
}

export async function obtenerProvincias(codigoDepartamento) {
  return pedir(`/ubigeo/departamentos/${encodeURIComponent(codigoDepartamento)}/provincias`);
}

export async function obtenerDistritos(codigoProvincia) {
  return pedir(`/ubigeo/provincias/${encodeURIComponent(codigoProvincia)}/distritos`);
}

/** Cuánto cuesta enviar a ese distrito. El pedido lo recalcula igual. */
export async function consultarEnvio(ubigeo) {
  const datos = await pedir('/envio', { ubigeo });
  return { ...datos, costo: Number(datos.costo) };
}

/** Precio en soles, con el formato que usa toda la tienda. */
export const soles = (n) => 'S/ ' + Number(n).toFixed(2);
