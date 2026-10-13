"""Consultas a la base de datos. Las rutas no arman SQL: llaman a esto."""

import random
import re
from collections.abc import Sequence
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session, contains_eager, selectinload

from app.models import (
    Categoria,
    Distrito,
    EstadoPedido,
    Marca,
    Pedido,
    PedidoItem,
    Producto,
    Subcategoria,
    TarifaEnvio,
)


def listar_categorias(sesion: Session) -> list[Categoria]:
    """Categorías activas con sus subcategorías, dejando fuera las que no tienen
    ningún producto activo. Una categoría vacía no se muestra en la tienda, pero
    sigue en la base esperando que se cargue su mercadería."""
    tiene_productos = (
        select(Producto.id)
        .where(Producto.subcategoria_id == Subcategoria.id, Producto.activo.is_(True))
        .exists()
    )
    # contains_eager: `categoria.subcategorias` queda poblada solo con las filas
    # que trajo este join, que son justo las visibles.
    consulta = (
        select(Categoria)
        .join(Categoria.subcategorias)
        .where(
            Categoria.activo.is_(True),
            Subcategoria.activo.is_(True),
            tiene_productos,
        )
        .options(contains_eager(Categoria.subcategorias))
        .order_by(Categoria.orden, Categoria.nombre, Subcategoria.orden)
    )
    return list(sesion.scalars(consulta).unique())


def listar_marcas(sesion: Session) -> list[Marca]:
    """Solo las que tienen algún producto activo."""
    con_productos = select(Producto.id).where(
        Producto.marca_id == Marca.id, Producto.activo.is_(True)
    )
    consulta = (
        select(Marca).where(con_productos.exists()).order_by(Marca.orden, Marca.nombre)
    )
    return list(sesion.scalars(consulta))


def obtener_categoria_por_slug(sesion: Session, slug: str) -> Categoria | None:
    return sesion.scalar(
        select(Categoria).where(Categoria.slug == slug, Categoria.eliminado_en.is_(None))
    )


def _escapar_like(termino: str) -> str:
    """Neutraliza los comodines de LIKE para que el usuario busque texto literal."""
    return termino.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def listar_productos(
    sesion: Session,
    *,
    categoria: str | None = None,
    subcategoria: str | None = None,
    marca: str | None = None,
    precio_min: Decimal | None = None,
    precio_max: Decimal | None = None,
    q: str | None = None,
    destacado: bool | None = None,
    mas_vendido: bool | None = None,
    en_oferta: bool | None = None,
    solo_activos: bool = True,
) -> list[Producto]:
    consulta = select(Producto)

    if solo_activos:
        consulta = consulta.where(Producto.activo.is_(True))

    if categoria:
        consulta = consulta.where(
            Producto.subcategoria_id.in_(
                select(Subcategoria.id)
                .join(Subcategoria.categoria)
                .where(Categoria.slug == categoria)
            )
        )

    if subcategoria:
        consulta = consulta.where(
            Producto.subcategoria_id.in_(
                select(Subcategoria.id).where(Subcategoria.slug == subcategoria)
            )
        )

    if marca:
        consulta = consulta.where(
            Producto.marca_id.in_(select(Marca.id).where(Marca.slug == marca))
        )

    if precio_min is not None:
        consulta = consulta.where(Producto.precio >= precio_min)

    if precio_max is not None:
        consulta = consulta.where(Producto.precio <= precio_max)

    if q:
        patron = f"%{_escapar_like(q.strip())}%"
        consulta = consulta.where(
            Producto.nombre.ilike(patron, escape="\\")
            | Producto.descripcion_corta.ilike(patron, escape="\\")
        )

    if destacado is not None:
        consulta = consulta.where(Producto.destacado.is_(destacado))

    if mas_vendido is not None:
        consulta = consulta.where(Producto.mas_vendido.is_(mas_vendido))

    if en_oferta is not None:
        if en_oferta:
            consulta = consulta.where(Producto.precio_antes.is_not(None))
        else:
            consulta = consulta.where(Producto.precio_antes.is_(None))

    # Los destacados primero; dentro de cada grupo, por nombre.
    consulta = consulta.order_by(Producto.destacado.desc(), Producto.nombre)

    return list(sesion.scalars(consulta).unique())


def obtener_producto_por_slug(
    sesion: Session, slug: str, *, solo_activos: bool = True
) -> Producto | None:
    consulta = select(Producto).where(Producto.slug == slug)
    if solo_activos:
        consulta = consulta.where(Producto.activo.is_(True))
    return sesion.scalars(consulta).unique().one_or_none()


# ── Pedidos ──────────────────────────────────────────────────────────


class ErrorPedido(Exception):
    """Error de negocio al crear un pedido. La ruta lo traduce a HTTPException."""


class ProductoNoDisponible(ErrorPedido):
    def __init__(self, producto_id: int):
        super().__init__(f"El producto {producto_id} no existe o no está disponible.")
        self.producto_id = producto_id


class StockInsuficiente(ErrorPedido):
    def __init__(self, producto_id: int, nombre: str, disponible: int, solicitado: int):
        super().__init__(
            f"Stock insuficiente para '{nombre}': quedan {disponible}, se pidieron {solicitado}."
        )
        self.producto_id = producto_id
        self.disponible = disponible
        self.solicitado = solicitado


LIMA = timezone(timedelta(hours=-5))  # sin horario de verano


def _numero_candidato(prefijo: str, dia: date) -> str:
    azar = random.randint(1000, 9999)
    return f"{prefijo}-{dia:%y%m%d}-{azar}"


def generar_numero_pedido(
    sesion: Session, *, prefijo: str = "ECN", dia: date | None = None, intentos: int = 20
) -> str:
    """ECN-AAMMDD-NNNN en la web; ECN-M-AAMMDD-NNNN en las ventas manuales.

    La parte al azar hace que no se pueda adivinar el código de otro pedido:
    la consulta pública de un pedido solo pide este número."""
    dia = dia or date.today()
    for _ in range(intentos):
        candidato = _numero_candidato(prefijo, dia)
        existe = sesion.scalar(select(Pedido.id).where(Pedido.numero_pedido == candidato))
        if existe is None:
            return candidato
    raise ErrorPedido("No se pudo generar un número de pedido único.")


class DestinoNoValido(ErrorPedido):
    def __init__(self, ubigeo: str):
        super().__init__(f"El distrito '{ubigeo}' no existe en el padrón del INEI.")


def obtener_distrito(sesion: Session, ubigeo: str) -> Distrito | None:
    return sesion.get(Distrito, ubigeo)


def costo_envio(sesion: Session, distrito: Distrito) -> Decimal:
    """Tarifa de la provincia si está afinada; si no, la del departamento."""
    provincia = distrito.provincia
    tarifas = sesion.scalars(
        select(TarifaEnvio).where(
            TarifaEnvio.departamento_codigo == provincia.departamento_codigo
        )
    ).all()

    por_provincia = next(
        (t for t in tarifas if t.provincia_codigo == provincia.codigo), None
    )
    if por_provincia is not None:
        return por_provincia.costo

    base = next((t for t in tarifas if t.provincia_codigo is None), None)
    if base is None:
        raise ErrorPedido(
            f"No hay tarifa de envío para {provincia.departamento.nombre}."
        )
    return base.costo


def crear_pedido(
    sesion: Session,
    *,
    nombre_contacto: str,
    telefono_contacto: str,
    correo: str | None,
    direccion: str,
    ubigeo: str,
    referencia: str | None,
    nota: str | None,
    items: Sequence[tuple[int, int]],  # (producto_id, cantidad)
    envio_gratis_desde: Decimal,
) -> Pedido:
    """Valida stock y arma el pedido con precios y envío reales de la base.

    No hace commit: eso lo decide quien llama, igual que en seed.py.
    """
    distrito = obtener_distrito(sesion, ubigeo)
    if distrito is None:
        raise DestinoNoValido(ubigeo)

    ids = [producto_id for producto_id, _ in items]
    productos = {
        p.id: p for p in sesion.scalars(select(Producto).where(Producto.id.in_(ids)))
    }

    subtotal = Decimal("0.00")
    for producto_id, cantidad in items:
        producto = productos.get(producto_id)
        if producto is None or not producto.activo:
            raise ProductoNoDisponible(producto_id)
        if producto.stock < cantidad:
            raise StockInsuficiente(producto_id, producto.nombre, producto.stock, cantidad)
        subtotal += producto.precio * cantidad

    envio = (
        Decimal("0.00")
        if subtotal >= envio_gratis_desde
        else costo_envio(sesion, distrito)
    )

    provincia = distrito.provincia
    pedido = Pedido(
        numero_pedido=generar_numero_pedido(sesion),
        nombre_contacto=nombre_contacto,
        telefono_contacto=telefono_contacto,
        email_contacto=correo,
        direccion_envio=direccion,
        departamento=provincia.departamento.nombre,
        provincia=provincia.nombre,
        distrito=distrito.nombre,
        ubigeo=distrito.codigo,
        referencia=referencia,
        nota=nota,
        envio=envio,
        total=subtotal + envio,
    )
    sesion.add(pedido)
    sesion.flush()  # asigna pedido.id

    for producto_id, cantidad in items:
        sesion.add(
            PedidoItem(
                pedido_id=pedido.id,
                producto_id=producto_id,
                cantidad=cantidad,
                precio_unitario=productos[producto_id].precio,
            )
        )
    sesion.flush()
    return pedido


def obtener_pedido_por_numero(sesion: Session, numero_pedido: str) -> Pedido | None:
    consulta = (
        select(Pedido)
        .options(selectinload(Pedido.items).joinedload(PedidoItem.producto))
        .where(Pedido.numero_pedido == numero_pedido)
    )
    return sesion.scalars(consulta).unique().one_or_none()


# ── Panel: pedidos ───────────────────────────────────────────────────

# Estados en los que la mercadería ya está comprometida y el stock debe estar
# descontado. Fuera de ellos, el stock vuelve al almacén.
ESTADOS_CON_STOCK_TOMADO = frozenset(
    {
        EstadoPedido.pagado,
        EstadoPedido.enviado,
        EstadoPedido.completado,
    }
)


def listar_pedidos(
    sesion: Session,
    *,
    estado: EstadoPedido | None = None,
    desde: date | None = None,
    hasta: date | None = None,
    q: str | None = None,
) -> list[Pedido]:
    """Los pedidos del panel, del más nuevo al más viejo."""
    consulta = select(Pedido).options(
        selectinload(Pedido.items).joinedload(PedidoItem.producto)
    )

    if estado is not None:
        consulta = consulta.where(Pedido.estado == estado)
    if desde is not None:
        consulta = consulta.where(Pedido.creado_en >= desde)
    if hasta is not None:
        # `hasta` es un día completo, así que se compara contra el siguiente.
        consulta = consulta.where(Pedido.creado_en < hasta + timedelta(days=1))
    if q:
        patron = f"%{_escapar_like(q.strip())}%"
        condicion = (
            Pedido.numero_pedido.ilike(patron, escape="\\")
            | Pedido.telefono_contacto.ilike(patron, escape="\\")
            | Pedido.nombre_contacto.ilike(patron, escape="\\")
        )
        # "V-14" o "v-014": el número de venta del Sheet.
        if venta := re.fullmatch(r"v-?(\d+)", q.strip(), flags=re.I):
            condicion = condicion | (Pedido.correlativo == int(venta.group(1)))
        consulta = consulta.where(condicion)

    # A igual fecha (ventas cargadas del mismo día), el número de venta manda.
    consulta = consulta.order_by(Pedido.creado_en.desc(), Pedido.correlativo.desc())
    return list(sesion.scalars(consulta).unique())


def _cantidades_por_producto(pedido: Pedido) -> dict[int, int]:
    """Unidades que pide el pedido de cada producto (una línea repetida suma)."""
    cantidades: dict[int, int] = {}
    for item in pedido.items:
        cantidades[item.producto_id] = cantidades.get(item.producto_id, 0) + item.cantidad
    return cantidades


def _bloquear_productos(sesion: Session, ids: list[int]) -> dict[int, Producto]:
    """Los productos con su fila bloqueada hasta el commit.

    Dos cambios de estado simultáneos sobre el mismo producto esperan uno al
    otro en vez de leer el mismo stock. Se piden siempre ordenados por id para
    que dos pedidos con los mismos productos no se bloqueen entre sí."""
    consulta = (
        select(Producto)
        .where(Producto.id.in_(sorted(ids)))
        .order_by(Producto.id)
        # `of`: las relaciones joined (marca, subcategoría) no se bloquean.
        .with_for_update(of=Producto)
        .execution_options(populate_existing=True)
    )
    return {p.id: p for p in sesion.scalars(consulta).unique()}


def cambiar_estado(sesion: Session, pedido: Pedido, nuevo: EstadoPedido) -> Pedido:
    """Mueve el pedido de estado y ajusta el stock en consecuencia.

    El stock se descuenta al entrar a un estado pagado y vuelve si el pedido se
    cancela. Cancelar un pedido pendiente no toca el stock. Comparar "estaba
    tomado" con "debe estar tomado" hace que la operación sea segura aunque se
    repita o se salten estados.

    No hace commit: si algo falla (por ejemplo, no alcanza el stock) quien
    llama hace rollback y nada queda a medias.
    """
    # Se relee el estado con la fila bloqueada: si otra petición lo cambió un
    # instante antes, se decide con el estado de verdad.
    sesion.refresh(pedido, ["estado"], with_for_update=True)
    if pedido.estado == nuevo:
        return pedido

    estaba_tomado = pedido.estado in ESTADOS_CON_STOCK_TOMADO
    debe_estar_tomado = nuevo in ESTADOS_CON_STOCK_TOMADO

    if estaba_tomado != debe_estar_tomado:
        cantidades = _cantidades_por_producto(pedido)
        productos = _bloquear_productos(sesion, list(cantidades))
        signo = -1 if debe_estar_tomado else +1

        if debe_estar_tomado:
            for producto_id, cantidad in cantidades.items():
                producto = productos[producto_id]
                if producto.stock < cantidad:
                    raise StockInsuficiente(
                        producto.id, producto.nombre, producto.stock, cantidad
                    )
        for producto_id, cantidad in cantidades.items():
            productos[producto_id].stock += signo * cantidad

        # El dinero entra al pasar a un estado pagado; si ya tenía fecha (por
        # ejemplo, se reactiva un pedido cancelado) se respeta.
        if debe_estar_tomado and pedido.fecha_pago is None:
            pedido.fecha_pago = datetime.now(timezone.utc)

    if nuevo == EstadoPedido.pendiente:
        pedido.fecha_pago = None

    pedido.estado = nuevo
    sesion.flush()
    return pedido


def cambiar_fecha_pago(
    sesion: Session, pedido: Pedido, fecha_pago: datetime | None
) -> Pedido:
    """Corrige a mano cuándo se pagó. Un pedido pendiente no tiene fecha de pago."""
    if pedido.estado == EstadoPedido.pendiente and fecha_pago is not None:
        raise ErrorPedido("El pedido todavía está pendiente: primero márcalo como pagado.")
    pedido.fecha_pago = fecha_pago
    sesion.flush()
    return pedido


def crear_venta_manual(
    sesion: Session,
    *,
    nombre_contacto: str,
    telefono_contacto: str | None,
    fecha: date | None,
    items: Sequence[tuple[int, int, Decimal | None]],  # (producto_id, cantidad, precio)
    envio: Decimal,
    pagado: bool,
    nota_interna: str | None,
) -> Pedido:
    """Una venta cerrada fuera de la web (WhatsApp, en persona).

    Se comporta como un pedido normal: nace pendiente y el stock baja al
    marcarla pagada. Con `pagado` se marca en el acto, con la fecha de la venta
    como fecha de pago. Acepta productos inactivos y un precio distinto al de
    lista (un descuento, por ejemplo). No hace commit."""
    ids = [producto_id for producto_id, _, _ in items]
    productos = {
        p.id: p for p in sesion.scalars(select(Producto).where(Producto.id.in_(ids)))
    }
    pedidas: dict[int, int] = {}
    for producto_id, cantidad, _ in items:
        if producto_id not in productos:
            raise ProductoNoDisponible(producto_id)
        pedidas[producto_id] = pedidas.get(producto_id, 0) + cantidad
    for producto_id, cantidad in pedidas.items():
        producto = productos[producto_id]
        if producto.stock < cantidad:
            raise StockInsuficiente(producto_id, producto.nombre, producto.stock, cantidad)

    hoy = datetime.now(LIMA).date()
    if fecha is not None and fecha > hoy:
        raise ErrorPedido("La fecha de la venta no puede ser futura.")
    # Una venta de otro día se fecha a mediodía, para que no cambie de día.
    momento = (
        datetime.now(timezone.utc)
        if fecha is None or fecha == hoy
        else datetime.combine(fecha, time(12, 0), tzinfo=LIMA)
    )

    lineas = [
        (pid, cantidad, precio if precio is not None else productos[pid].precio)
        for pid, cantidad, precio in items
    ]
    subtotal = sum((c * p for _, c, p in lineas), Decimal("0.00"))
    pedido = Pedido(
        numero_pedido=generar_numero_pedido(sesion, prefijo="ECN-M", dia=fecha or hoy),
        origen="manual",
        nombre_contacto=nombre_contacto,
        telefono_contacto=telefono_contacto,
        envio=envio,
        total=subtotal + envio,
        nota_interna=nota_interna,
        creado_en=momento,
    )
    for producto_id, cantidad, precio in lineas:
        pedido.items.append(
            PedidoItem(producto_id=producto_id, cantidad=cantidad, precio_unitario=precio)
        )
    sesion.add(pedido)
    sesion.flush()

    if pagado:
        cambiar_estado(sesion, pedido, EstadoPedido.pagado)
        pedido.fecha_pago = momento
        sesion.flush()
    return pedido


# ── Panel: catálogo ──────────────────────────────────────────────────


class ErrorCatalogo(Exception):
    """Error de negocio al editar el catálogo. La ruta lo traduce a HTTP."""


class ValorRepetido(ErrorCatalogo):
    def __init__(self, campo: str, valor: str):
        super().__init__(f"Ya existe un producto con {campo} '{valor}'.")


ORDENES_CATALOGO = {
    "codigo": (Producto.codigo,),
    "nuevos": (Producto.creado_en.desc(), Producto.codigo.desc()),
    "editados": (Producto.actualizado_en.desc().nullslast(), Producto.codigo),
    "nombre": (Producto.nombre,),
    "stock": (Producto.stock,),
    "precio": (Producto.precio.desc(),),
}


def listar_productos_admin(
    sesion: Session,
    *,
    q: str | None = None,
    categoria_id: int | None = None,
    subcategoria_id: int | None = None,
    marca_id: int | None = None,
    activo: bool | None = None,
    stock_bajo_de: int | None = None,
    orden: str = "codigo",
) -> list[Producto]:
    """Todo el catálogo, activos e inactivos, con los filtros del panel."""
    consulta = select(Producto)

    if q:
        patron = f"%{_escapar_like(q.strip())}%"
        consulta = consulta.where(
            Producto.nombre.ilike(patron, escape="\\")
            | Producto.codigo.ilike(patron, escape="\\")
        )
    if categoria_id is not None:
        consulta = consulta.where(
            Producto.subcategoria_id.in_(
                select(Subcategoria.id).where(Subcategoria.categoria_id == categoria_id)
            )
        )
    if subcategoria_id is not None:
        consulta = consulta.where(Producto.subcategoria_id == subcategoria_id)
    if marca_id is not None:
        consulta = consulta.where(Producto.marca_id == marca_id)
    if activo is not None:
        consulta = consulta.where(Producto.activo.is_(activo))
    if stock_bajo_de is not None:
        consulta = consulta.where(Producto.stock <= stock_bajo_de)

    consulta = consulta.order_by(*ORDENES_CATALOGO.get(orden, ORDENES_CATALOGO["codigo"]))
    return list(sesion.scalars(consulta).unique())


def obtener_producto_admin(sesion: Session, codigo: str) -> Producto | None:
    consulta = select(Producto).where(Producto.codigo == codigo)
    return sesion.scalars(consulta).unique().one_or_none()


def siguiente_codigo(sesion: Session) -> str:
    """El siguiente ECN-NNN libre, mirando los que ya existen."""
    codigos = sesion.scalars(select(Producto.codigo)).all()
    numeros = [
        int(c.split("-")[1])
        for c in codigos
        if c.startswith("ECN-") and c.split("-")[1].isdigit()
    ]
    return f"ECN-{(max(numeros) + 1) if numeros else 1:03d}"


def guardar_producto(
    sesion: Session, datos: dict, *, producto: Producto | None = None
) -> Producto:
    """Crea o actualiza un producto. `datos` ya viene validado por Pydantic."""
    nuevo = producto is None

    # Código y slug identifican al producto en la tienda: no pueden chocar.
    for campo in ("codigo", "slug"):
        valor = datos.get(campo)
        if valor is None:
            continue
        choque = sesion.scalar(
            select(Producto).where(getattr(Producto, campo) == valor)
        )
        if choque is not None and (nuevo or choque.id != producto.id):
            raise ValorRepetido(campo, valor)

    if nuevo:
        producto = Producto(codigo=datos["codigo"])
        sesion.add(producto)
    else:
        # El código identifica al producto y lo relaciona con sus fotos: una
        # vez creado, no se cambia.
        datos.pop("codigo", None)

    for campo, valor in datos.items():
        setattr(producto, campo, valor)

    sesion.flush()
    return producto
