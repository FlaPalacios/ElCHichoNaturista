"""Carga el ubigeo del Perú y las tarifas de envío.

    python -m app.ubigeo          # crea o actualiza las tres tablas

Los datos salen de `app/datos/ubigeo.csv`, el padrón del INEI 2022 (25
departamentos, 196 provincias, 1891 distritos).

El padrón viene TODO EN MAYÚSCULAS Y SIN TILDES ("SAN MARTIN DE PORRES"). Se
guarda con mayúscula y minúscula, y con las tildes puestas donde se pueden
poner con certeza: los 25 departamentos y los distritos de Lima y Callao, que
son los que el cliente va a elegir casi siempre. El resto queda tal como lo
publica el INEI.
"""

import argparse
import csv
from decimal import Decimal
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import SesionLocal
from app.models import Departamento, Distrito, Provincia, TarifaEnvio

ARCHIVO = Path(__file__).parent / "datos" / "ubigeo.csv"

# Costos de envío vigentes. Se cargan una vez; después se editan desde el panel.
COSTO_LIMA = Decimal("10.00")
COSTO_PROVINCIA = Decimal("15.00")
COD_LIMA_DEPARTAMENTO = "15"
COD_LIMA_PROVINCIA = "1501"
COD_CALLAO = "07"

# Palabras que en un nombre propio van en minúscula.
MINUSCULAS = {"de", "del", "la", "las", "los", "y", "en"}

TILDES = {
    # Departamentos
    "ANCASH": "Áncash",
    "APURIMAC": "Apurímac",
    "HUANUCO": "Huánuco",
    "JUNIN": "Junín",
    "SAN MARTIN": "San Martín",
    # Distritos de Lima y Callao
    "JESUS MARIA": "Jesús María",
    "SAN MARTIN DE PORRES": "San Martín de Porres",
    "SANTA MARIA DEL MAR": "Santa María del Mar",
    "VILLA MARIA DEL TRIUNFO": "Villa María del Triunfo",
    "RIMAC": "Rímac",
    "LURIN": "Lurín",
    "ANCON": "Ancón",
    "PUCUSANA": "Pucusana",
    "SAN JUAN DE LURIGANCHO": "San Juan de Lurigancho",
    "SAN JUAN DE MIRAFLORES": "San Juan de Miraflores",
    "CARMEN DE LA LEGUA REYNOSO": "Carmen de la Legua Reynoso",
    "MI PERU": "Mi Perú",
}


def bonito(nombre: str) -> str:
    """MAYÚSCULAS DEL INEI → forma legible, con tilde si la conocemos."""
    nombre = nombre.strip()
    if nombre in TILDES:
        return TILDES[nombre]
    palabras = [
        palabra.lower() if i and palabra.lower() in MINUSCULAS else palabra.capitalize()
        for i, palabra in enumerate(nombre.split())
    ]
    return " ".join(palabras)


def cargar_ubigeo(sesion: Session) -> None:
    if not ARCHIVO.exists():
        raise SystemExit(f"Falta el padrón del INEI en {ARCHIVO}.")

    with ARCHIVO.open(encoding="utf-8-sig", newline="") as f:
        filas = list(csv.DictReader(f))

    departamentos: dict[str, str] = {}
    provincias: dict[str, tuple[str, str]] = {}
    distritos: dict[str, tuple[str, str]] = {}
    for fila in filas:
        departamentos[fila["cod_departamento"]] = bonito(fila["departamento"])
        provincias[fila["cod_provincia"]] = (
            fila["cod_departamento"],
            bonito(fila["provincia"]),
        )
        distritos[fila["ubigeo"]] = (fila["cod_provincia"], bonito(fila["distrito"]))

    # Solo se agrega lo que falta y se corrigen los nombres. Borrar y recargar
    # arrastraría en cascada las tarifas de envío, que sí son datos del
    # negocio: los códigos del INEI son estables, así que esto alcanza.
    nuevos = 0
    for modelo, filas in (
        (Departamento, [(c, {"nombre": n}) for c, n in departamentos.items()]),
        (
            Provincia,
            [
                (c, {"nombre": n, "departamento_codigo": d})
                for c, (d, n) in provincias.items()
            ],
        ),
        (
            Distrito,
            [
                (c, {"nombre": n, "provincia_codigo": p})
                for c, (p, n) in distritos.items()
            ],
        ),
    ):
        existentes = {fila.codigo: fila for fila in sesion.scalars(select(modelo))}
        for codigo, campos in filas:
            fila = existentes.get(codigo)
            if fila is None:
                sesion.add(modelo(codigo=codigo, **campos))
                nuevos += 1
            else:
                for campo, valor in campos.items():
                    setattr(fila, campo, valor)
        sesion.flush()

    print(
        f"  ubigeo: {len(departamentos)} departamentos, {len(provincias)} provincias, "
        f"{len(distritos)} distritos ({nuevos} nuevos)"
    )


def cargar_tarifas(sesion: Session) -> None:
    """Tarifa base por departamento, más la excepción de Lima capital.

    Solo se crean las que falten: si ya editaste un costo desde el panel, esta
    carga no te lo pisa.
    """
    existentes = {
        (t.departamento_codigo, t.provincia_codigo)
        for t in sesion.scalars(select(TarifaEnvio))
    }
    nuevas = 0

    for codigo in sesion.scalars(select(Departamento.codigo)):
        if (codigo, None) in existentes:
            continue
        costo = COSTO_LIMA if codigo == COD_CALLAO else COSTO_PROVINCIA
        sesion.add(TarifaEnvio(departamento_codigo=codigo, costo=costo))
        nuevas += 1

    # Lima capital paga como Lima; el resto del departamento, como provincia.
    if (COD_LIMA_DEPARTAMENTO, COD_LIMA_PROVINCIA) not in existentes:
        sesion.add(
            TarifaEnvio(
                departamento_codigo=COD_LIMA_DEPARTAMENTO,
                provincia_codigo=COD_LIMA_PROVINCIA,
                costo=COSTO_LIMA,
            )
        )
        nuevas += 1

    sesion.flush()
    total = sesion.scalar(select(func.count()).select_from(TarifaEnvio))
    print(f"  tarifas: {total} zonas ({nuevas} nuevas)")


def main() -> None:
    argparse.ArgumentParser(description="Carga el ubigeo y las tarifas.").parse_args()
    print("Cargando ubigeo del Perú…")
    with SesionLocal() as sesion:
        cargar_ubigeo(sesion)
        cargar_tarifas(sesion)
        sesion.commit()
    print("Listo.")


if __name__ == "__main__":
    main()
