import { tienda as porDefecto } from './data/tienda.js';
import { urlCloudinary } from './lib/cloudinary.js';
import {
  consultarEnvio,
  crearPedido,
  obtenerDistritos,
  obtenerPedido,
  obtenerProvincias,
} from './lib/api.js';

// Los ajustes reales los inyecta el layout; el archivo es el respaldo.
const tienda = { ...porDefecto, ...(globalThis.window?.__tienda ?? {}) };

const CLAVE = 'ecn.carrito.v1';
const CLAVE_PEDIDOS = 'ecn.pedidos.v1';

// Cómo se le cuenta al cliente en qué va su pedido.
const ESTADOS = {
  nuevo: 'Recibido',
  pago_confirmado: 'Pago confirmado',
  preparando: 'Preparando',
  enviado: 'En camino',
  entregado: 'Entregado',
  cancelado: 'Cancelado',
  no_concretado: 'Sin confirmar',
};


/** Llama al panel a través de /api/admin, que es quien lleva el token. */
async function peticionAdmin(ruta, metodo = 'GET', cuerpo = null, detallado = false) {
  try {
    const respuesta = await fetch(`/api/admin${ruta}`, {
      method: metodo,
      headers: cuerpo ? { 'Content-Type': 'application/json' } : {},
      body: cuerpo ? JSON.stringify(cuerpo) : undefined,
    });
    const datos = await respuesta.json().catch(() => ({}));
    if (!respuesta.ok) {
      const error = datos.detail ?? 'No se pudo guardar.';
      return detallado ? { ok: false, error: String(error) } : null;
    }
    return detallado ? { ok: true, datos } : datos;
  } catch {
    return detallado ? { ok: false, error: 'Sin conexión con el servidor.' } : null;
  }
}

const leer = (clave, porDefecto) => {
  try {
    const crudo = localStorage.getItem(clave);
    return crudo ? JSON.parse(crudo) : porDefecto;
  } catch {
    return porDefecto;
  }
};

const guardar = (clave, valor) => {
  try {
    localStorage.setItem(clave, JSON.stringify(valor));
  } catch {
    /* modo privado o almacenamiento lleno: el carrito sigue en memoria */
  }
};

export default (Alpine) => {
  Alpine.store('carrito', {
    items: [],
    abierto: false,
    aviso: '',
    _avisoTimer: null,
    listo: false,

    init() {
      this.items = leer(CLAVE, []);
      this.listo = true;
      // Sincroniza entre pestañas abiertas.
      window.addEventListener('storage', (e) => {
        if (e.key === CLAVE) this.items = leer(CLAVE, []);
      });
    },

    persistir() {
      guardar(CLAVE, this.items);
    },

    agregar(producto, cantidad = 1) {
      const existente = this.items.find((i) => i.id === producto.id);
      const tope = producto.stock ?? 99;
      if (existente) {
        existente.cantidad = Math.min(existente.cantidad + cantidad, tope);
      } else {
        this.items.push({
          id: producto.id,
          slug: producto.slug,
          nombre: producto.nombre,
          precio: producto.precio,
          presentacion: producto.presentacion,
          categoria: producto.categoria,
          stock: tope,
          cantidad: Math.min(cantidad, tope),
        });
      }
      this.persistir();
      this.mostrarAviso(`${producto.nombre} · agregado`);
      this.abierto = true;
    },

    quitar(id) {
      this.items = this.items.filter((i) => i.id !== id);
      this.persistir();
    },

    cambiarCantidad(id, delta) {
      const item = this.items.find((i) => i.id === id);
      if (!item) return;
      const nueva = item.cantidad + delta;
      if (nueva < 1) {
        this.quitar(id);
        return;
      }
      item.cantidad = Math.min(nueva, item.stock ?? 99);
      this.persistir();
    },

    fijarCantidad(id, valor) {
      const item = this.items.find((i) => i.id === id);
      if (!item) return;
      const n = parseInt(valor, 10);
      item.cantidad = Number.isNaN(n) || n < 1 ? 1 : Math.min(n, item.stock ?? 99);
      this.persistir();
    },

    vaciar() {
      this.items = [];
      this.persistir();
    },

    cantidadDe(id) {
      const item = this.items.find((i) => i.id === id);
      return item ? item.cantidad : 0;
    },

    mostrarAviso(texto) {
      this.aviso = texto;
      clearTimeout(this._avisoTimer);
      this._avisoTimer = setTimeout(() => (this.aviso = ''), 2600);
    },

    get unidades() {
      return this.items.reduce((n, i) => n + i.cantidad, 0);
    },

    get vacio() {
      return this.items.length === 0;
    },

    get subtotal() {
      return this.items.reduce((n, i) => n + i.precio * i.cantidad, 0);
    },

    get envioGratis() {
      return !this.vacio && this.subtotal >= tienda.envioGratisDesde;
    },

    get faltaParaEnvioGratis() {
      return Math.max(0, tienda.envioGratisDesde - this.subtotal);
    },

    // El costo del envío depende del distrito, así que hasta el checkout no se
    // conoce: solo se sabe seguro cuando el subtotal ya lo hace gratis.
    get envio() {
      return this.envioGratis ? 0 : null;
    },

    get total() {
      return this.subtotal + (this.envio ?? 0);
    },

    soles(n) {
      return 'S/ ' + Number(n).toFixed(2);
    },
  });

  // Una fila de la lista de pedidos del panel. Guarda los cambios pasando por
  // /api/admin, que es quien tiene el token de la sesión.
  Alpine.data('pedidoAdmin', (inicial) => ({
    ...inicial,
    abierto: false,
    mensaje: '',

    nombreEstado() {
      return ESTADOS[this.estado] ?? this.estado;
    },

    async _guardar(ruta, cuerpo, aviso) {
      this.mensaje = 'Guardando…';
      try {
        const respuesta = await fetch(`/api/admin/pedidos/${this.numero}/${ruta}`, {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(cuerpo),
        });
        if (!respuesta.ok) {
          const datos = await respuesta.json().catch(() => ({}));
          this.mensaje = datos.detail ?? 'No se pudo guardar.';
          return false;
        }
        const pedido = await respuesta.json();
        this.estado = pedido.estado;
        this.mensaje = aviso;
        setTimeout(() => (this.mensaje = ''), 2500);
        return true;
      } catch {
        this.mensaje = 'Sin conexión con el servidor.';
        return false;
      }
    },

    guardarEstado() {
      return this._guardar(
        'estado',
        {
          estado: this.estado,
          courier: this.courier || null,
          codigo_seguimiento: this.seguimiento || null,
        },
        'Estado guardado'
      );
    },

    guardarNota() {
      return this._guardar('nota', { nota_interna: this.nota || null }, 'Nota guardada');
    },
  }));

  // Una fila de la tabla de productos: stock rápido y activar/desactivar.
  Alpine.data('filaProducto', (inicial) => ({
    ...inicial,

    async guardarStock() {
      await peticionAdmin(`/productos/${this.codigo}/stock`, 'PATCH', {
        stock: Number(this.stock),
      });
    },

    async alternarActivo() {
      const p = await peticionAdmin(`/productos/${this.codigo}/activo`, 'PATCH', {
        activo: !this.activo,
      });
      if (p) this.activo = p.activo;
    },
  }));

  // La pantalla de productos: buscar, importar/exportar y la ficha lateral.
  Alpine.data('catalogoAdmin', ({ marcas, categorias, subcategorias }) => ({
    marcas,
    categorias,
    subcategorias,
    abierto: false,
    nuevo: true,
    guardando: false,
    subiendo: false,
    importando: false,
    mensaje: '',
    error: false,
    mensajeFicha: '',
    errorFicha: false,
    fotos: [],
    form: {},
    beneficiosTexto: '',

    _vacio() {
      return {
        codigo: '',
        nombre: '',
        slug: '',
        marca_id: '',
        categoria_id: '',
        subcategoria_id: '',
        precio: '',
        precio_antes: '',
        stock: 0,
        activo: true,
        destacado: false,
        mas_vendido: false,
        presentacion: '',
        descripcion_corta: '',
        descripcion_larga: '',
        modo_uso: '',
      };
    },


    /** Las subcategorías de la categoría elegida. */
    subcategoriasDe(categoriaId) {
      return this.subcategorias.filter((s) => s.categoria_id === categoriaId);
    },

    /** Pide un nombre y crea la categoría, subcategoría o marca al vuelo. */
    async _crearAlVuelo(tipo, extra = {}) {
      const etiquetas = {
        categorias: 'la nueva categoría',
        subcategorias: 'la nueva subcategoría',
        marcas: 'la nueva marca',
      };
      const nombre = prompt(`Nombre de ${etiquetas[tipo]}:`);
      if (!nombre || !nombre.trim()) return null;

      const respuesta = await peticionAdmin(
        `/${tipo}`,
        'POST',
        { nombre: nombre.trim(), orden: 99, ...extra },
        true
      );
      if (!respuesta.ok) {
        this.errorFicha = true;
        this.mensajeFicha = respuesta.error;
        return null;
      }
      this.errorFicha = false;
      this.mensajeFicha = `"${respuesta.datos.nombre}" creada`;
      return respuesta.datos;
    },

    async cambiarCategoria() {
      if (this.form.categoria_id !== 'nueva') {
        this.form.subcategoria_id = '';
        return;
      }
      this.form.categoria_id = '';
      const creada = await this._crearAlVuelo('categorias');
      if (!creada) return;
      this.categorias = [...this.categorias, { id: creada.id, nombre: creada.nombre }];
      this.form.categoria_id = creada.id;
      this.form.subcategoria_id = '';
    },

    async cambiarSubcategoria() {
      if (this.form.subcategoria_id !== 'nueva') return;
      this.form.subcategoria_id = '';
      const creada = await this._crearAlVuelo('subcategorias', {
        categoria_id: this.form.categoria_id,
      });
      if (!creada) return;
      const categoria = this.categorias.find((c) => c.id === this.form.categoria_id);
      this.subcategorias = [
        ...this.subcategorias,
        {
          id: creada.id,
          nombre: creada.nombre,
          categoria_id: this.form.categoria_id,
          categoria: categoria?.nombre ?? '',
        },
      ];
      this.form.subcategoria_id = creada.id;
    },

    async cambiarMarca() {
      if (this.form.marca_id !== 'nueva') return;
      this.form.marca_id = '';
      const creada = await this._crearAlVuelo('marcas');
      if (!creada) return;
      this.marcas = [...this.marcas, { id: creada.id, nombre: creada.nombre }];
      this.form.marca_id = creada.id;
    },

    miniatura(url) {
      return urlCloudinary(url, 140);
    },

    async abrirNuevo() {
      this.form = this._vacio();
      this.beneficiosTexto = '';
      this.fotos = [];
      this.nuevo = true;
      this.mensajeFicha = '';
      this.abierto = true;
      const datos = await peticionAdmin('/productos/siguiente-codigo');
      if (datos) this.form.codigo = datos.codigo;
    },

    async abrirEdicion(codigo) {
      const p = await peticionAdmin(`/productos/${codigo}`);
      if (!p) return;
      this.form = {
        codigo: p.codigo,
        nombre: p.nombre,
        slug: p.slug,
        marca_id: p.marca.id,
        categoria_id: p.subcategoria.categoria.id,
        subcategoria_id: p.subcategoria.id,
        precio: p.precio,
        precio_antes: p.precio_antes ?? '',
        stock: p.stock,
        activo: p.activo,
        destacado: p.destacado,
        mas_vendido: p.mas_vendido,
        presentacion: p.presentacion ?? '',
        descripcion_corta: p.descripcion_corta ?? '',
        descripcion_larga: p.descripcion_larga ?? '',
        modo_uso: p.modo_uso ?? '',
      };
      this.beneficiosTexto = (p.beneficios ?? []).join('\n');
      this.fotos = p.imagenes ?? [];
      this.nuevo = false;
      this.mensajeFicha = '';
      this.abierto = true;
    },

    cerrar() {
      this.abierto = false;
    },

    /** Del nombre sale el slug, mientras el producto sea nuevo. */
    sugerirSlug() {
      if (!this.nuevo) return;
      this.form.slug = this.form.nombre
        .toLowerCase()
        .normalize('NFD')
        .replace(/[̀-ͯ]/g, '')
        .replace(/[^a-z0-9]+/g, '-')
        .replace(/(^-|-$)/g, '');
    },

    async guardar() {
      this.guardando = true;
      this.mensajeFicha = '';
      this.errorFicha = false;
      const cuerpo = {
        ...this.form,
        precio_antes: this.form.precio_antes === '' ? null : this.form.precio_antes,
        beneficios: this.beneficiosTexto
          .split('\n')
          .map((b) => b.trim())
          .filter(Boolean),
      };
      if (!this.nuevo) delete cuerpo.codigo;
      // La categoria solo sirve para filtrar el menu: la API la saca de la
      // subcategoria elegida.
      delete cuerpo.categoria_id;

      const respuesta = await peticionAdmin(
        this.nuevo ? '/productos' : `/productos/${this.form.codigo}`,
        this.nuevo ? 'POST' : 'PUT',
        cuerpo,
        true
      );
      this.guardando = false;

      if (respuesta.ok) {
        location.reload();
        return;
      }
      this.errorFicha = true;
      this.mensajeFicha = respuesta.error;
    },

    async subirFoto(evento) {
      const archivo = evento.target.files?.[0];
      if (!archivo) return;
      this.subiendo = true;
      this.mensajeFicha = '';
      this.errorFicha = false;

      const datos = new FormData();
      datos.append('archivo', archivo);
      const respuesta = await fetch(
        `/api/admin/productos/${this.form.codigo}/imagenes`,
        { method: 'POST', body: datos }
      );
      this.subiendo = false;
      evento.target.value = '';

      const cuerpo = await respuesta.json().catch(() => ({}));
      if (!respuesta.ok) {
        this.errorFicha = true;
        this.mensajeFicha = cuerpo.detail ?? 'No se pudo subir la foto.';
        return;
      }
      this.fotos = cuerpo.imagenes ?? [];
      this.mensajeFicha = 'Foto subida';
    },

    async borrarFoto(id) {
      if (!confirm('Se borra también de Cloudinary y no se puede deshacer. ¿Continuar?')) return;
      const p = await peticionAdmin(
        `/productos/${this.form.codigo}/imagenes/${id}`,
        'DELETE'
      );
      if (p) this.fotos = p.imagenes ?? [];
    },

    async moverFoto(indice, salto) {
      const orden = [...this.fotos];
      const destino = indice + salto;
      if (destino < 0 || destino >= orden.length) return;
      [orden[indice], orden[destino]] = [orden[destino], orden[indice]];
      this.fotos = orden;
      const p = await peticionAdmin(
        `/productos/${this.form.codigo}/imagenes/orden`,
        'PATCH',
        { ids: orden.map((f) => f.id) }
      );
      if (p) this.fotos = p.imagenes ?? [];
    },

    // Importar va en dos pasos: primero se simula (valida todo sin guardar) y
    // solo si no hay errores se ofrece confirmar. El archivo queda en memoria
    // entre ambos pasos.
    previa: null,
    archivoImport: null,

    async _enviarPlanilla(simular) {
      const datos = new FormData();
      datos.append('archivo', this.archivoImport);
      const respuesta = await fetch(
        `/api/admin/productos/importar${simular ? '?simular=true' : ''}`,
        { method: 'POST', body: datos }
      );
      const cuerpo = await respuesta.json().catch(() => ({}));
      if (!respuesta.ok) {
        throw new Error(
          typeof cuerpo.detail === 'string' ? cuerpo.detail : 'No se pudo leer la planilla.'
        );
      }
      return cuerpo;
    },

    async importar(evento) {
      const archivo = evento.target.files?.[0];
      evento.target.value = '';
      if (!archivo) return;
      this.archivoImport = archivo;
      this.previa = null;
      this.mensaje = '';
      this.error = false;
      this.importando = true;
      try {
        this.previa = await this._enviarPlanilla(true);
      } catch (e) {
        this.error = true;
        this.mensaje = e.message || 'No se pudo conectar con el servidor.';
        this.archivoImport = null;
      } finally {
        this.importando = false;
      }
    },

    cancelarImport() {
      this.previa = null;
      this.archivoImport = null;
    },

    async confirmarImport() {
      this.importando = true;
      try {
        const r = await this._enviarPlanilla(false);
        if (!r.aplicado) {
          this.previa = r;
          return;
        }
        this.previa = null;
        this.archivoImport = null;
        this.mensaje = `Listo: ${r.creados} creados y ${r.actualizados} actualizados.`;
        setTimeout(() => location.reload(), 1200);
      } catch (e) {
        this.error = true;
        this.mensaje = e.message || 'No se pudo conectar con el servidor.';
      } finally {
        this.importando = false;
      }
    },
  }));

  // Categorías, subcategorías y marcas del panel. Un solo formulario sirve a
  // los tres porque comparten nombre, orden y visibilidad.
  Alpine.data('clasificacionAdmin', (inicial) => ({
    categorias: inicial.categorias,
    marcas: inicial.marcas,
    papelera: inicial.papelera ?? { categorias: [], subcategorias: [], marcas: [] },
    verPapelera: false,
    form: null,
    guardando: false,
    errorForm: '',
    mensaje: '',
    error: false,

    tituloForm() {
      if (!this.form) return '';
      const que = { categoria: 'categoría', subcategoria: 'subcategoría', marca: 'marca' }[
        this.form.tipo
      ];
      return this.form.id ? `Editar ${que}` : `Nueva ${que}`;
    },

    _abrir(form) {
      this.form = form;
      this.errorForm = '';
      this.$nextTick(() => this.$refs.primero?.focus());
    },

    nuevaCategoria() {
      this._abrir({ tipo: 'categoria', nombre: '', orden: this.categorias.length + 1, activo: true });
    },

    editarCategoria(c) {
      this._abrir({ tipo: 'categoria', id: c.id, nombre: c.nombre, orden: c.orden, activo: c.activo });
    },

    nuevaSubcategoria(c) {
      this._abrir({
        tipo: 'subcategoria',
        nombre: '',
        categoria_id: c.id,
        orden: c.subcategorias.length + 1,
        activo: true,
      });
    },

    editarSubcategoria(s, c) {
      this._abrir({
        tipo: 'subcategoria',
        id: s.id,
        nombre: s.nombre,
        categoria_id: c.id,
        orden: s.orden,
        activo: s.activo,
      });
    },

    nuevaMarca() {
      this._abrir({ tipo: 'marca', nombre: '', orden: this.marcas.length + 1, activo: true });
    },

    editarMarca(m) {
      this._abrir({ tipo: 'marca', id: m.id, nombre: m.nombre, orden: m.orden, activo: true });
    },

    cerrar() {
      this.form = null;
    },

    async guardar() {
      const f = this.form;
      const rutas = { categoria: '/categorias', subcategoria: '/subcategorias', marca: '/marcas' };
      const cuerpo = { nombre: f.nombre, orden: f.orden };
      if (f.tipo !== 'marca') cuerpo.activo = f.activo;
      if (f.tipo === 'subcategoria') cuerpo.categoria_id = f.categoria_id;

      this.guardando = true;
      this.errorForm = '';
      const respuesta = await peticionAdmin(
        f.id ? `${rutas[f.tipo]}/${f.id}` : rutas[f.tipo],
        f.id ? 'PUT' : 'POST',
        cuerpo,
        true
      );
      this.guardando = false;

      if (!respuesta.ok) {
        this.errorForm = respuesta.error;
        return;
      }
      this.cerrar();
      await this.recargar();
    },

    // Borrar manda a la papelera: se puede deshacer, así que no pide confirmación.
    async borrarCategoria(c) {
      await this._borrar(`/categorias/${c.id}`, `«${c.nombre}» está en la papelera.`);
    },

    async borrarSubcategoria(s) {
      await this._borrar(`/subcategorias/${s.id}`, `«${s.nombre}» está en la papelera.`);
    },

    async borrarMarca(m) {
      await this._borrar(`/marcas/${m.id}`, `«${m.nombre}» está en la papelera.`);
    },

    async _borrar(ruta, aviso) {
      const respuesta = await peticionAdmin(ruta, 'DELETE', null, true);
      if (!respuesta.ok) {
        this.error = true;
        this.mensaje = respuesta.error;
        return;
      }
      this.error = false;
      this.mensaje = aviso;
      this.verPapelera = true;
      await this.recargar();
    },

    // ── Papelera ──
    async restaurar(tipo, x) {
      const respuesta = await peticionAdmin(
        `/papelera/${tipo}/${x.id}/restaurar`,
        'POST',
        {},
        true
      );
      this.error = !respuesta.ok;
      this.mensaje = respuesta.ok ? `«${x.nombre}» volvió a su lugar.` : respuesta.error;
      await this.recargar();
    },

    async eliminarSiempre(tipo, x) {
      if (!confirm(`Se elimina «${x.nombre}» para siempre y no se puede recuperar. ¿Continuar?`)) {
        return;
      }
      const respuesta = await peticionAdmin(`/papelera/${tipo}/${x.id}`, 'DELETE', null, true);
      this.error = !respuesta.ok;
      this.mensaje = respuesta.ok ? 'Eliminado para siempre.' : respuesta.error;
      await this.recargar();
    },

    get enPapelera() {
      const p = this.papelera;
      return p.categorias.length + p.subcategorias.length + p.marcas.length;
    },

    async recargar() {
      const [datos, papelera] = await Promise.all([
        peticionAdmin('/clasificacion'),
        peticionAdmin('/papelera'),
      ]);
      if (datos) {
        this.categorias = datos.categorias;
        this.marcas = datos.marcas;
      }
      if (papelera) this.papelera = papelera;
      setTimeout(() => (this.mensaje = ''), 4000);
    },
  }));

  // Buscador del encabezado: productos, categorías y secciones de la tienda.
  // Sin escribir muestra atajos; escribiendo, mezcla lo que coincida. Enter sin
  // elegir nada manda la búsqueda al catálogo.
  Alpine.data('buscadorGlobal', ({ productos, categorias, paginas }) => {
    const limpio = (t) =>
      String(t ?? '')
        .normalize('NFD')
        .replace(/\p{M}/gu, '')
        .toLowerCase()
        .trim();
    const preparar = (lista, campos) =>
      lista.map((x) => ({ ...x, _h: limpio(campos.map((c) => x[c]).join(' ')) }));
    const prods = preparar(productos, ['n', 'm', 'c']);
    const cats = preparar(categorias, ['t', 'p']);
    const pags = preparar(paginas, ['t', 'k']);
    const coinciden = (lista, palabras) => lista.filter((x) => palabras.every((w) => x._h.includes(w)));

    return {
      q: '',
      abierto: false,
      activo: -1,

      get items() {
        const texto = this.q.trim();
        const palabras = limpio(texto).split(/\s+/).filter(Boolean);
        if (!palabras.length) {
          return pags.slice(0, 5).map((p) => ({ grupo: 'Ir a', t: p.t, sub: '', h: p.h }));
        }
        return [
          ...coinciden(prods, palabras)
            .slice(0, 5)
            .map((p) => ({ grupo: 'Productos', t: p.n, sub: p.c, h: '/producto/' + p.s })),
          ...coinciden(cats, palabras)
            .slice(0, 4)
            .map((c) => ({ grupo: 'Categorías', t: c.t, sub: c.p ? 'en ' + c.p : '', h: c.h })),
          ...coinciden(pags, palabras)
            .slice(0, 3)
            .map((p) => ({ grupo: 'Secciones', t: p.t, sub: '', h: p.h })),
          {
            grupo: 'Buscar',
            t: `Buscar «${texto}» en el catálogo`,
            sub: '',
            h: '/catalogo?q=' + encodeURIComponent(texto),
          },
        ];
      },

      mover(paso) {
        const n = this.items.length;
        if (!n) return;
        this.abierto = true;
        if (this.activo < 0) this.activo = paso > 0 ? 0 : n - 1;
        else this.activo = (this.activo + paso + n) % n;
      },

      entrar(evento) {
        const elegido = this.items[this.activo];
        if (!elegido) return; // sin elegir nada: se envía el formulario al catálogo
        evento.preventDefault();
        location.href = elegido.h;
      },

      cerrar() {
        this.abierto = false;
        this.activo = -1;
      },
    };
  });

  // Ventas e ingresos entre fechas. Los gráficos se dibujan a mano (un SVG para
  // la serie y barras HTML para los rankings): son pocos y así no se suma
  // ninguna librería al panel.
  Alpine.data('ventasAdmin', () => {
    const W = 760;
    const H = 260;
    const M = { i: 58, d: 8, s: 12, b: 28 }; // márgenes: izquierda, derecha, arriba, abajo
    const ZONA = 'America/Lima';

    const hoyLima = () => new Date().toLocaleDateString('en-CA', { timeZone: ZONA });
    const sumarDias = (iso, dias) => {
      const d = new Date(iso + 'T12:00:00Z');
      d.setUTCDate(d.getUTCDate() + dias);
      return d.toISOString().slice(0, 10);
    };
    const numero = (n, dec = 0) =>
      Number(n).toLocaleString('es-PE', { minimumFractionDigits: dec, maximumFractionDigits: dec });

    // Un máximo "redondo" para el eje: 1, 2, 5 o 10 por una potencia de diez.
    const eje = (maximo) => {
      const crudo = Math.max(maximo, 1) / 4;
      const pot = 10 ** Math.floor(Math.log10(crudo));
      const f = crudo / pot;
      const paso = (f <= 1 ? 1 : f <= 2 ? 2 : f <= 5 ? 5 : 10) * pot;
      return { paso, tope: Math.ceil(Math.max(maximo, 1) / paso) * paso };
    };

    return {
      desde: '',
      hasta: '',
      agrupar: 'auto',
      estado: 'pagados',
      comparar: true,
      preset: '30d',
      datos: null,
      cargando: false,
      error: '',
      tabla: false,
      tip: null,
      _pedido: 0,

      PRESETS: [
        ['7d', '7 días'],
        ['30d', '30 días'],
        ['90d', '90 días'],
        ['mes', 'Este mes'],
        ['mes_pasado', 'Mes pasado'],
        ['anio', 'Este año'],
      ],
      ESTADOS: {
        nuevo: 'Nuevo',
        pago_confirmado: 'Pago confirmado',
        preparando: 'Preparando',
        enviado: 'Enviado',
        entregado: 'Entregado',
        cancelado: 'Cancelado',
        no_concretado: 'No concretado',
      },

      init() {
        this.usarPreset('30d');
      },

      usarPreset(p) {
        const hoy = hoyLima();
        const [a, m] = hoy.split('-').map(Number);
        const primero = (anio, mes) => `${anio}-${String(mes).padStart(2, '0')}-01`;
        this.preset = p;
        if (p === '7d') [this.desde, this.hasta] = [sumarDias(hoy, -6), hoy];
        if (p === '30d') [this.desde, this.hasta] = [sumarDias(hoy, -29), hoy];
        if (p === '90d') [this.desde, this.hasta] = [sumarDias(hoy, -89), hoy];
        if (p === 'mes') [this.desde, this.hasta] = [primero(a, m), hoy];
        if (p === 'mes_pasado') {
          const este = primero(a, m);
          const ant = m === 1 ? primero(a - 1, 12) : primero(a, m - 1);
          [this.desde, this.hasta] = [ant, sumarDias(este, -1)];
        }
        if (p === 'anio') [this.desde, this.hasta] = [primero(a, 1), hoy];
        this.cargar();
      },

      fechasCambiaron() {
        this.preset = 'custom';
        this.cargar();
      },

      get urlExportar() {
        const q = new URLSearchParams({ desde: this.desde, hasta: this.hasta, estado: this.estado });
        return `/api/admin/ventas/exportar?${q}`;
      },

      async cargar() {
        if (!this.desde || !this.hasta) return;
        if (this.hasta < this.desde) {
          this.error = 'La fecha final no puede ser anterior a la inicial.';
          return;
        }
        const turno = ++this._pedido;
        this.cargando = true;
        this.error = '';
        const q = new URLSearchParams({
          desde: this.desde,
          hasta: this.hasta,
          agrupar: this.agrupar,
          estado: this.estado,
          comparar: this.comparar,
        });
        const r = await peticionAdmin(`/ventas?${q}`, 'GET', null, true);
        if (turno !== this._pedido) return; // llegó una respuesta más nueva
        this.cargando = false;
        if (!r.ok) {
          this.error = r.error;
          return;
        }
        this.tip = null;
        this.datos = r.datos;
      },

      // ── Formatos ──
      soles: (n) => 'S/ ' + numero(n, 2),
      entero: (n) => numero(n),
      corto: (n) => (n >= 1000 ? numero(n / 1000, 1) + ' k' : numero(n)),

      etiqueta(periodo, largo = false) {
        const d = new Date(periodo + 'T12:00:00Z');
        const unidad = this.datos?.rango.agrupar;
        if (unidad === 'mes') {
          return d.toLocaleDateString('es-PE', { month: 'short', year: '2-digit', timeZone: 'UTC' });
        }
        const dia = d.toLocaleDateString('es-PE', { day: 'numeric', month: 'short', timeZone: 'UTC' });
        return unidad === 'semana' ? (largo ? 'Semana del ' : 'Sem. ') + dia : dia;
      },

      fechaLarga(iso) {
        return new Date(iso + 'T12:00:00Z').toLocaleDateString('es-PE', {
          day: 'numeric',
          month: 'short',
          year: 'numeric',
          timeZone: 'UTC',
        });
      },

      // Variación frente al periodo anterior, con flecha y texto (nunca solo color).
      delta(clave) {
        const previo = this.datos?.previo;
        if (!previo) return null;
        const a = this.datos.cifras[clave];
        const p = previo.cifras[clave];
        if (!p) return a ? { texto: 'Sin datos antes', clase: '' } : null;
        const pct = ((a - p) / p) * 100;
        if (Math.abs(pct) < 0.5) return { texto: '= igual que antes', clase: '' };
        return {
          texto: `${pct > 0 ? '▲' : '▼'} ${numero(Math.abs(pct))}% vs. periodo anterior`,
          clase: pct > 0 ? 'sube' : 'baja',
        };
      },

      get sinVentas() {
        return this.datos && this.datos.cifras.pedidos === 0;
      },

      // ── Gráfico de la serie ──
      get grafico() {
        const d = this.datos;
        if (!d) return { svg: '', n: 0 };
        const serie = d.serie;
        const previa = d.previo?.serie ?? [];
        const n = serie.length;
        const { paso, tope } = eje(Math.max(...serie.map((s) => s.ventas), ...previa.map((s) => s.ventas)));
        const alto = H - M.s - M.b;
        const y = (v) => M.s + alto * (1 - v / tope);
        const banda = (W - M.i - M.d) / n;
        const ancho = Math.min(banda * 0.66, 34);
        const x = (i) => M.i + banda * i + (banda - ancho) / 2;

        let s = '';
        for (let v = 0; v <= tope + 1e-9; v += paso) {
          s += `<line x1="${M.i}" x2="${W - M.d}" y1="${y(v)}" y2="${y(v)}" stroke="var(--linea)" stroke-width="1"/>`;
          s += `<text x="${M.i - 8}" y="${y(v) + 4}" text-anchor="end" font-size="11" fill="var(--tinta-suave)">${this.corto(v)}</text>`;
        }
        serie.forEach((p, i) => {
          if (p.ventas <= 0) return;
          const top = y(p.ventas);
          s += `<rect x="${x(i)}" y="${top}" width="${ancho}" height="${Math.max(y(0) - top, 2)}" rx="2" fill="var(--salvia)"/>`;
        });
        if (previa.length) {
          const pts = previa
            .slice(0, n)
            .map((p, i) => `${M.i + banda * (i + 0.5)},${y(p.ventas)}`)
            .join(' ');
          s += `<polyline points="${pts}" fill="none" stroke="var(--tinta-suave)" stroke-width="2" stroke-dasharray="5 4" stroke-linejoin="round" opacity="0.85"/>`;
        }
        // Etiquetas del eje x: unas ocho, repartidas.
        const cada = Math.max(1, Math.ceil(n / 8));
        serie.forEach((p, i) => {
          if (i % cada !== 0) return;
          s += `<text x="${M.i + banda * (i + 0.5)}" y="${H - 8}" text-anchor="middle" font-size="11" fill="var(--tinta-suave)">${this.etiqueta(p.periodo)}</text>`;
        });
        return {
          n,
          banda,
          svg: `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Ventas por ${d.rango.agrupar}" preserveAspectRatio="xMidYMid meet">${s}</svg>`,
        };
      },

      get zonaSensible() {
        const p = (v, t) => `${(v / t) * 100}%`;
        return `left:${p(M.i, W)};right:${p(M.d, W)};top:${p(M.s, H)};bottom:${p(M.b, H)}`;
      },

      get tooltip() {
        if (this.tip === null || !this.datos) return null;
        const p = this.datos.serie[this.tip];
        const previo = this.datos.previo?.serie[this.tip];
        const centro = (M.i + this.grafico.banda * (this.tip + 0.5)) / W;
        return {
          estilo: `left:${centro * 100}%;${centro > 0.62 ? 'transform:translateX(-102%)' : 'transform:translateX(2%)'}`,
          titulo: this.etiqueta(p.periodo, true),
          ventas: this.soles(p.ventas),
          pedidos: p.pedidos,
          previo: previo ? this.soles(previo.ventas) : null,
          previoEt: previo ? this.etiqueta(previo.periodo, true) : '',
        };
      },

      // Ancho de la barra de un ranking, en %, respecto al mayor de la lista.
      ancho(valor, lista, campo = 'importe') {
        const mayor = Math.max(...lista.map((f) => f[campo]), 1);
        return Math.max((valor / mayor) * 100, valor > 0 ? 2 : 0);
      },
    };
  });

  // Ajustes de la tienda.
  Alpine.data('configuracionAdmin', (iniciales) => ({
    valores: { ...iniciales },
    guardando: false,
    mensaje: '',
    error: false,

    async guardar() {
      this.guardando = true;
      this.mensaje = '';
      const respuesta = await peticionAdmin('/configuracion', 'PUT', this.valores, true);
      this.guardando = false;
      this.error = !respuesta.ok;
      this.mensaje = respuesta.ok ? 'Guardado' : respuesta.error;
      if (respuesta.ok) setTimeout(() => (this.mensaje = ''), 2500);
    },
  }));

  // Una fila de la tabla de costos de envío.
  Alpine.data('tarifaFila', (inicial) => ({
    ...inicial,
    guardado: false,

    async guardar() {
      const datos = await peticionAdmin(`/tarifas/${this.id}`, 'PATCH', {
        costo: this.costo,
      });
      if (!datos) return;
      this.costo = Number(datos.costo);
      this.guardado = true;
      setTimeout(() => (this.guardado = false), 1800);
    },
  }));

  // Consulta de un pedido por su número, en /cuenta.
  Alpine.data('consultaPedido', () => ({
    numero: '',
    buscando: false,
    pedido: null,
    error: '',

    async buscar() {
      const numero = this.numero.trim().toUpperCase();
      this.pedido = null;
      this.error = '';
      if (!numero) return;

      this.buscando = true;
      try {
        const encontrado = await obtenerPedido(numero);
        if (encontrado) this.pedido = encontrado;
        else this.error = `No encontramos el pedido ${numero}. Revisa el número.`;
      } catch {
        this.error = 'No pudimos consultar ahora. Intenta de nuevo en un momento.';
      } finally {
        this.buscando = false;
      }
    },
  }));

  // El formulario de checkout. Vive acá y no en la página porque necesita
  // llamar a la API (provincias, distritos y costo de envío) y las
  // expresiones x-data de Astro no pueden importar módulos.
  // `departamentos` llega ya renderizado desde el servidor, así el primer
  // menú está lleno aunque el JavaScript tarde.
  Alpine.data('checkout', (departamentos = []) => ({
    hecho: null,
    enlaceWa: '',
    intento: false,
    enviando: false,
    departamentos,
    provincias: [],
    distritos: [],
    // Lo que respondió la API para el distrito elegido.
    envio: null,
    cargando: '',
    datos: {
      nombre: '',
      telefono: '',
      correo: '',
      direccion: '',
      departamento: '',
      provincia: '',
      distrito: '',
      referencia: '',
      nota: '',
      departamentoNombre: '',
      provinciaNombre: '',
      distritoNombre: '',
    },

    get errores() {
      const e = {};
      const d = this.datos;
      // Los topes van iguales que en backend/app/schemas.py (PedidoCrear).
      if (d.nombre.trim().length < 3) e.nombre = 'Escribe tu nombre completo';
      else if (d.nombre.length > 40) e.nombre = 'Máximo 40 caracteres';
      if (!/^[0-9\s+]{9,15}$/.test(d.telefono.trim())) e.telefono = 'Un número de 9 dígitos';
      if (d.correo && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(d.correo.trim())) e.correo = 'Correo inválido';
      else if (d.correo.length > 80) e.correo = 'Máximo 80 caracteres';
      if (d.direccion.trim().length < 5) e.direccion = 'Calle y número';
      else if (d.direccion.length > 100) e.direccion = 'Máximo 100 caracteres';
      if (!d.departamento) e.departamento = 'Elige tu departamento';
      else if (!d.provincia) e.provincia = 'Elige tu provincia';
      else if (!d.distrito) e.distrito = 'Elige tu distrito';
      return e;
    },

    get valido() {
      return Object.keys(this.errores).length === 0;
    },

    /** Envío ya decidido: gratis por monto, o lo que dijo la API. */
    get costoEnvio() {
      if (this.$store.carrito.envioGratis) return 0;
      return this.envio ? this.envio.costo : null;
    },

    get total() {
      return this.$store.carrito.subtotal + (this.costoEnvio ?? 0);
    },

    async cambiarDepartamento() {
      const d = this.datos;
      Object.assign(d, { provincia: '', distrito: '', provinciaNombre: '', distritoNombre: '' });
      this.provincias = [];
      this.distritos = [];
      this.envio = null;
      if (!d.departamento) return;

      d.departamentoNombre = this.departamentos.find((x) => x.codigo === d.departamento)?.nombre ?? '';
      this.cargando = 'provincias';
      try {
        this.provincias = await obtenerProvincias(d.departamento);
      } finally {
        this.cargando = '';
      }
    },

    async cambiarProvincia() {
      const d = this.datos;
      d.distrito = '';
      d.distritoNombre = '';
      this.distritos = [];
      this.envio = null;
      if (!d.provincia) return;

      d.provinciaNombre = this.provincias.find((x) => x.codigo === d.provincia)?.nombre ?? '';
      this.cargando = 'distritos';
      try {
        this.distritos = await obtenerDistritos(d.provincia);
      } finally {
        this.cargando = '';
      }
    },

    async cambiarDistrito() {
      const d = this.datos;
      this.envio = null;
      if (!d.distrito) return;

      d.distritoNombre = this.distritos.find((x) => x.codigo === d.distrito)?.nombre ?? '';
      this.cargando = 'envio';
      try {
        this.envio = await consultarEnvio(d.distrito);
      } catch {
        // Si falla, el checkout sigue: el costo real lo pone el backend al
        // crear el pedido.
        this.envio = null;
      } finally {
        this.cargando = '';
      }
    },

    async confirmar() {
      this.intento = true;
      if (!this.valido || this.$store.carrito.vacio || this.enviando) return;
      this.enviando = true;
      try {
        const pedido = await this.$store.pedido.registrar(
          { ...this.datos },
          this.$store.carrito,
          this.costoEnvio ?? 0
        );
        this.enlaceWa = this.$store.pedido.mensajeWhatsApp(pedido);
        this.hecho = pedido;
        this.$store.carrito.vaciar();
        window.open(this.enlaceWa, '_blank', 'noopener');
        window.scrollTo({ top: 0, behavior: 'smooth' });
      } finally {
        this.enviando = false;
      }
    },
  }));

  // Estado del checkout: registra el pedido en el backend y arma el mensaje
  // de WhatsApp. Si la API no responde, genera el número localmente como
  // respaldo — nunca se pierde una venta por una caída del servidor.
  Alpine.store('pedido', {
    ultimo: null,
    sincronizando: false,

    init() {
      this.ultimo = leer(CLAVE_PEDIDOS, null);
    },

    etiquetaEstado(estado) {
      return ESTADOS[estado] ?? estado;
    },

    // Se usa solo como respaldo si crearPedido() falla; en el camino normal
    // el número lo pone la API.
    generarNumero() {
      const d = new Date();
      const yy = String(d.getFullYear()).slice(2);
      const mm = String(d.getMonth() + 1).padStart(2, '0');
      const dd = String(d.getDate()).padStart(2, '0');
      const azar = Math.floor(1000 + Math.random() * 9000);
      return `ECN-${yy}${mm}${dd}-${azar}`;
    },

    // Cuerpo del POST /pedidos, en snake_case tal como lo espera la API.
    _payloadApi(datos, carrito) {
      return {
        nombre_contacto: datos.nombre,
        telefono_contacto: datos.telefono,
        correo: datos.correo || null,
        direccion: datos.direccion,
        ubigeo: datos.distrito,
        referencia: datos.referencia || null,
        nota: datos.nota || null,
        items: carrito.items.map((i) => ({ producto_id: i.id, cantidad: i.cantidad })),
      };
    },

    // Pedido de respaldo si la API no responde. `envio` es el que ya calculó
    // la API al elegir el distrito, o 0 si el subtotal lo hizo gratis.
    _pedidoLocal(datos, carrito, numero, envio) {
      return {
        numero,
        fecha: new Date().toISOString(),
        estado: 'nuevo',
        cliente: datos,
        items: carrito.items.map((i) => ({
          producto_id: i.id,
          nombre: i.nombre,
          cantidad: i.cantidad,
          precio_unitario: i.precio,
        })),
        subtotal: carrito.subtotal,
        envio,
        total: carrito.subtotal + envio,
        sincronizado: false,
      };
    },

    async registrar(datos, carrito, envio = 0) {
      this.sincronizando = true;
      const local = this._pedidoLocal(datos, carrito, this.generarNumero(), envio);
      try {
        const api = await crearPedido(this._payloadApi(datos, carrito));
        const pedido = {
          ...local,
          numero: api.numero,
          fecha: api.fecha,
          estado: api.estado,
          subtotal: api.subtotal,
          envio: api.envio,
          total: api.total,
          sincronizado: true,
        };
        this.ultimo = pedido;
        guardar(CLAVE_PEDIDOS, pedido);
        return pedido;
      } catch (error) {
        // Red caída, timeout o el backend falló: no se pierde el pedido, se
        // guarda local y se marca para sincronizar después.
        this.ultimo = local;
        guardar(CLAVE_PEDIDOS, local);
        return local;
      } finally {
        this.sincronizando = false;
      }
    },

    mensajeWhatsApp(pedido) {
      const soles = (n) => 'S/ ' + Number(n).toFixed(2);
      const lineas = [
        `Hola ${tienda.nombre}, quiero confirmar mi pedido ${pedido.numero}.`,
        '',
        ...pedido.items.map(
          (i) => `• ${i.cantidad} × ${i.nombre} — ${soles(i.precio_unitario * i.cantidad)}`
        ),
        '',
        `Subtotal: ${soles(pedido.subtotal)}`,
        `Envío: ${pedido.envio === 0 ? 'gratis' : soles(pedido.envio)}`,
        `Total: ${soles(pedido.total)}`,
        '',
        `Nombre: ${pedido.cliente.nombre}`,
        `Teléfono: ${pedido.cliente.telefono}`,
        `Entrega: ${pedido.cliente.direccion}`,
        `Distrito: ${pedido.cliente.distritoNombre}, ${pedido.cliente.provinciaNombre}, ${pedido.cliente.departamentoNombre}`,
      ];
      if (pedido.cliente.referencia) lineas.push(`Referencia: ${pedido.cliente.referencia}`);
      if (pedido.cliente.nota) lineas.push(`Nota: ${pedido.cliente.nota}`);
      return `https://wa.me/${tienda.whatsapp}?text=${encodeURIComponent(lineas.join('\n'))}`;
    },
  });
};
