import { tienda } from './data/tienda.js';

const CLAVE = 'ecn.carrito.v1';
const CLAVE_PEDIDOS = 'ecn.pedidos.v1';
const COSTO_ENVIO_LIMA = 12;

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
      return this.subtotal >= tienda.envioGratisDesde;
    },

    get envio() {
      if (this.vacio) return 0;
      return this.envioGratis ? 0 : COSTO_ENVIO_LIMA;
    },

    get faltaParaEnvioGratis() {
      return Math.max(0, tienda.envioGratisDesde - this.subtotal);
    },

    get total() {
      return this.subtotal + this.envio;
    },

    soles(n) {
      return 'S/ ' + Number(n).toFixed(2);
    },
  });

  // Estado del checkout: genera el número de pedido y arma el mensaje de
  // WhatsApp. En la etapa 5 el número lo devolverá la API.
  Alpine.store('pedido', {
    ultimo: null,

    init() {
      this.ultimo = leer(CLAVE_PEDIDOS, null);
    },

    generarNumero() {
      const d = new Date();
      const yy = String(d.getFullYear()).slice(2);
      const mm = String(d.getMonth() + 1).padStart(2, '0');
      const dd = String(d.getDate()).padStart(2, '0');
      const azar = Math.floor(1000 + Math.random() * 9000);
      return `ECN-${yy}${mm}${dd}-${azar}`;
    },

    registrar(datos, carrito) {
      const pedido = {
        numero: this.generarNumero(),
        fecha: new Date().toISOString(),
        estado: 'pendiente',
        cliente: datos,
        items: carrito.items.map((i) => ({
          producto_id: i.id,
          nombre: i.nombre,
          cantidad: i.cantidad,
          precio_unitario: i.precio,
        })),
        subtotal: carrito.subtotal,
        envio: carrito.envio,
        total: carrito.total,
      };
      this.ultimo = pedido;
      guardar(CLAVE_PEDIDOS, pedido);
      return pedido;
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
        `Entrega: ${pedido.cliente.entrega === 'tienda' ? 'Recojo en tienda' : pedido.cliente.direccion + ', ' + pedido.cliente.distrito}`,
      ];
      if (pedido.cliente.nota) lineas.push(`Nota: ${pedido.cliente.nota}`);
      return `https://wa.me/${tienda.whatsapp}?text=${encodeURIComponent(lineas.join('\n'))}`;
    },
  });
};
