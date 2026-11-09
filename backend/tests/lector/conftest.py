"""Fixtures del lector. Los PDF reales son locales (Silabos/ no se versiona)."""
import re
from pathlib import Path

import pytest

from app.agentes.facultades import normalizar

RAIZ = Path(__file__).resolve().parents[3]
PDFS = {
    "datos": RAIZ / "Silabos/Software/AnalisisDatos-Ingenieria/silabo_Datos_Software-signed.pdf",
    "tic": RAIZ / "Silabos/Software/TIC-Ingenieria/TIC-Ingenieria.pdf",
}
_ROTULO_NOMBRE = "NOMBRES Y APELLIDOS"
_CONTACTO = re.compile(r"[\w.+-]+@[\w.-]+|\d{4}-\d{4}-\d{4}-\d{3}[\dX]|\d{9,}")


@pytest.fixture
def pdf_real():
    def cargar(nombre: str) -> bytes:
        ruta = PDFS[nombre]
        if not ruta.exists():
            pytest.skip("PDF real no disponible en Silabos/ (no se versiona)")
        return ruta.read_bytes()
    return cargar


def datos_personales(datos: bytes) -> set[str]:
    """Firmas inequívocas de la sección I: pares de palabras del nombre completo,
    correos, teléfonos (≥9 dígitos) e identificadores ORCID.

    Un apellido suelto no cuenta: puede coincidir con un autor de la bibliografía.
    Nunca imprime nada: quien la usa solo debe informar cuántas fugas hubo.
    """
    from app.silabo.lector.entrada import abrir, seccion_privada

    firmas: set[str] = set()
    with abrir(datos) as pdf:
        for parte in seccion_privada(pdf, "I"):
            texto = normalizar(parte.extract_text() or "")
            firmas.update(m.replace(" ", "") for m in _CONTACTO.findall(texto))
            for tabla in parte.extract_tables():
                for fila in tabla:
                    celdas = [normalizar(c) for c in fila if c]
                    if celdas and celdas[0].startswith(_ROTULO_NOMBRE):
                        valor = " ".join(celdas[1:]) or celdas[0].removeprefix(_ROTULO_NOMBRE)
                        palabras = re.findall(r"[A-ZÑ]{2,}", valor)
                        firmas.update(f"{a} {b}" for a, b in zip(palabras, palabras[1:]))
    return firmas


def fugas(texto: str, personales: set[str]) -> int:
    """Cuántas firmas personales aparecen en el texto."""
    plano = " ".join(normalizar(texto).split())
    compacto = re.sub(r"[\s-]", "", plano)
    return sum(1 for f in personales if f in plano or ("@" not in f and " " not in f and f in compacto))
