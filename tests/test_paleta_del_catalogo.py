# -*- coding: utf-8 -*-
"""Los colores que publicamos salen del catálogo UCC.

"Tratá de respetar los colores de los nuevos snippets siempre" (21-10-2026).
El catálogo (`Snipped utilizados.html`) trae los 72 componentes con sus
colores, y los mismos componentes existen en dos variantes: Educación usa
el azul institucional #003087 y Posgrado el azul oscuro #1b1e31.

Este test existe porque ya se me escapó una vez: el bloque de código salió
con dos grises de GitHub (#f6f8fa, #e1e4e8) que no están en ningún snippet.
"""

import re
from pathlib import Path

import pytest

from maquetador.build.componentes_asesor import (construir_panels,
                                                 construir_flipcards,
                                                 construir_tooltip)
from maquetador.build.snippets import (procesar_contenido, resaltado_simple,
                                       resaltado_profundizacion,
                                       resaltado_atencion, resaltado_ejemplo,
                                       resaltado_laboratorio_ideas,
                                       cta_titulo, ICONOS, galeria_de_figuras,
                                       fila_de_figuras, bloque_video_studio)

_CATALOGO = Path(__file__).resolve().parent.parent / "Snipped utilizados.html"
_AULA_BASE = Path(__file__).resolve().parent.parent / "Aula base-Educacion.imscc"

pytestmark = pytest.mark.skipif(
    not _CATALOGO.exists(), reason="falta el catálogo de snippets")


def _colores(texto: str) -> set:
    return {c.lower() for c in re.findall(r"#[0-9a-fA-F]{6}", texto or "")}


def _permitidos() -> set:
    """Los del catálogo más los que el aula base ya trae puestos.

    El aula base aporta los suyos (el gris del popover, el de la fila
    "Sección 1"): no los elegimos nosotros y no tiene sentido prohibirlos.
    """
    permitidos = _colores(_CATALOGO.read_text(encoding="utf-8", errors="replace"))
    if _AULA_BASE.exists():
        import zipfile
        with zipfile.ZipFile(_AULA_BASE) as z:
            for nombre in z.namelist():
                if nombre.endswith((".html", ".xml")):
                    permitidos |= _colores(
                        z.read(nombre).decode("utf-8", "replace"))
    return permitidos


@pytest.fixture(scope="module")
def permitidos():
    return _permitidos()


class TestElCatalogoTraeLosDosTemas:
    def test_educacion_usa_el_azul_institucional(self, permitidos):
        assert "#003087" in permitidos

    def test_posgrado_usa_el_azul_oscuro(self, permitidos):
        assert "#1b1e31" in permitidos


class TestLosComponentesQueArmamos:
    """Cada componente, con los dos temas, contra la paleta del catálogo."""

    @pytest.mark.parametrize("tema", ["educacion", "posgrado"])
    @pytest.mark.parametrize("nombre,fabrica", [
        ("resaltado simple", lambda: resaltado_simple("<p>Un texto.</p>")),
        ("profundización", lambda: resaltado_profundizacion(
            "Profundización", "<p>Un texto.</p>")),
        ("atención", lambda: resaltado_atencion("<p>Un texto.</p>")),
        ("ejemplos", lambda: resaltado_ejemplo("<p>Un texto.</p>")),
        ("laboratorio", lambda: resaltado_laboratorio_ideas("<p>Un texto.</p>")),
        ("cta lectura", lambda: cta_titulo(
            "Descubrí leyendo", "<p>Un texto.</p>", ICONOS["lectura"])),
        ("cta video", lambda: cta_titulo(
            "Auriculares on", "<p>Un texto.</p>", ICONOS["video"])),
        ("bloque de video", lambda: bloque_video_studio()),
        ("tooltip", lambda: construir_tooltip("DUA", "Diseño Universal", 0)),
        ("panels", lambda: construir_panels(
            [("Uno", "<p>a</p>"), ("Dos", "<p>b</p>")], "dp-tabs-buttons")),
        ("flip cards", lambda: construir_flipcards(
            [("Frente", "<p>Dorso</p>"), ("Otro", "<p>Dorso</p>")])),
        ("galería", lambda: galeria_de_figuras(
            [("1", "Una", '<img src="a.jpg"/>', "Nota.")])),
        ("fila de figuras", lambda: fila_de_figuras(
            [("1", "Una", '<img src="a.jpg"/>', ""),
             ("2", "Otra", '<img src="b.jpg"/>', "")])),
    ])
    def test_sin_colores_fuera_del_catalogo(self, nombre, fabrica, tema,
                                            permitidos):
        fuera = sorted(_colores(procesar_contenido(fabrica(), tema))
                       - permitidos)
        assert not fuera, f"{nombre} ({tema}) usa {fuera}"


class TestElBloqueDeCodigo:
    """El caso que motivó el test: sali� con dos grises de GitHub."""

    CODIGO = ("<p># Creación de un diccionario</p>"
              "<p>estudiante = {</p>"
              '<p>    "nombre": "Juan",</p>'
              "<p>}</p>")

    @pytest.mark.parametrize("tema", ["educacion", "posgrado"])
    def test_sin_colores_fuera_del_catalogo(self, tema, permitidos):
        fuera = sorted(_colores(procesar_contenido(self.CODIGO, tema))
                       - permitidos)
        assert not fuera, f"el bloque de código ({tema}) usa {fuera}"

    def test_los_grises_de_github_no_vuelven(self):
        salida = procesar_contenido(self.CODIGO, "posgrado")
        assert "#f6f8fa" not in salida
        assert "#e1e4e8" not in salida
