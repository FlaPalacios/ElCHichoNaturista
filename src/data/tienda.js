// Configuración de la tienda. Un solo lugar para los datos que se repiten.

export const tienda = {
  nombre: 'El Chico Naturista',
  lema: 'Productos naturales del Perú',
  // Número de WhatsApp en formato internacional, sin + ni espacios.
  whatsapp: '51946049689',
  whatsappVisible: '+51 946 049 689',
  correo: 'hola@elchiconaturista.pe',
  direccion: 'Las Camelias, Mz. K Lt. 17 – Los Olivos, Lima',
  horario: 'Lunes a sábado · 9:00 a 19:00',
  instagram: 'https://instagram.com/elchiconaturista',
  facebook: 'https://facebook.com/elchiconaturista',
  envioGratisDesde: 120,
  avisos: [
    'Envíos a todo el Perú · Delivery el mismo día en Lima',
    'Pedidos coordinados por WhatsApp, sin pasarela de pago',
    'Envío gratis en Lima desde S/ 120',
  ],
};

// Arma el enlace wa.me con un mensaje ya escrito.
export const waLink = (mensaje) =>
  `https://wa.me/${tienda.whatsapp}?text=${encodeURIComponent(mensaje)}`;
