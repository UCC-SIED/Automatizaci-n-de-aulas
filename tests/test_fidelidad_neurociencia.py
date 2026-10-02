# -*- coding: utf-8 -*-
"""Convenciones nuevas que trajo "Neurociencia Aplicada a las Organizaciones I".

Cada asesor arma la carpeta y la planilla a su manera. Los tests de acá
reproducen lo que traía esta materia y que el generador no sabía leer: sin
esto, las 26 páginas de contenido salían vacías y el plan llegaba con cuatro
bloqueantes.
"""

import pytest

from maquetador.ingest.folder_scanner import escanear
from maquetador.build.snippets import contenido_declara_video
from maquetador.ingest.docx_comments import _clasificar


class TestCarpetaPorEtapasConLetra:
    """La materia guarda los tres DOCX modulares SUELTOS en la etapa
    ("b- ETAPA 2_ Material_/M1 Luis Roldán - ….docx"), sin la subcarpeta
    "Material Multimedia" que traían las anteriores. El escáner pedía que la
    carpeta lo confirmara, así que ninguno entraba como desarrollo teórico."""

    def _curso(self, tmp_path):
        raiz = tmp_path / "Neurociencia"
        etapa = raiz / "b- ETAPA 2_ Material_"
        etapa.mkdir(parents=True)
        for n in ("M1 Luis Roldán - Neurociencia Aplicada I .docx",
                  "M2 - Luis Roldán - Neurociencia aplicada.docx",
                  "M3 Luis Roldán Neurociencia aplicada.docx"):
            (etapa / n).write_text("x", encoding="utf-8")
        return raiz

    def test_el_docx_que_abre_con_el_modulo_es_el_desarrollo_teorico(self, tmp_path):
        inv = escanear(self._curso(tmp_path))
        assert sorted(inv.docx_modulos) == [1, 2, 3]
        assert inv.docx_modulos[2].name.startswith("M2 -")

    def test_no_se_lleva_los_guiones_de_video(self, tmp_path):
        raiz = self._curso(tmp_path)
        (raiz / "b- ETAPA 2_ Material_"
         / "Guion Video Módulo 1 (Luis Roldán).docx").write_text("x", encoding="utf-8")
        inv = escanear(raiz)
        assert sorted(inv.docx_modulos) == [1, 2, 3]
        assert [p.name for _n, p in inv.guiones_video] == [
            "Guion Video Módulo 1 (Luis Roldán).docx"]


class TestCarpetaBioYFoto:
    """La foto y la titulación del docente vienen en "Bio y Foto", y el DOCX
    se llama con el nombre del docente y nada más. Los dos salían "sin
    fuente" aunque estuvieran en la carpeta."""

    def _curso(self, tmp_path):
        from PIL import Image
        raiz = tmp_path / "Neurociencia"
        bio = raiz / "a- ETAPA 1_ Programa" / "Bio y Foto"
        bio.mkdir(parents=True)
        # Una segunda etapa, como en la carpeta real: si no, el escáner toma
        # "Bio y Foto" por la raíz del curso y la ruta relativa queda vacía.
        (raiz / "b- ETAPA 2_ Material_").mkdir()
        Image.new("RGB", (400, 400)).save(bio / "81583.jpg")
        (bio / "LUIS ROLDÁN GONZÁLEZ DE LAS CUEVAS.docx").write_text(
            "x", encoding="utf-8")
        return raiz

    def test_la_foto_sin_nombre_descriptivo_es_la_del_docente(self, tmp_path):
        inv = escanear(self._curso(tmp_path))
        assert [p.name for p in inv.fotos_docente] == ["81583.jpg"]

    def test_el_docx_de_la_carpeta_bio_es_la_titulacion(self, tmp_path):
        inv = escanear(self._curso(tmp_path))
        assert [p.name for p in inv.biografia] == [
            "LUIS ROLDÁN GONZÁLEZ DE LAS CUEVAS.docx"]


class TestHerramientaHtmlSuelta:
    """La AFI llega como un .html autónomo hecho con IA ("el alumno tiene a
    su disposición un instrumento de aplicación que deberá utilizar"). No es
    una página del aula: es un recurso que se publica y se incrusta."""

    def test_el_html_entra_como_recurso(self, tmp_path):
        raiz = tmp_path / "Neurociencia"
        act = raiz / "b- ETAPA 2_ Material_" / "Actividades y AFI"
        act.mkdir(parents=True)
        (act / "AFI_PiramideDelNeurolider_2.html").write_text(
            "<html></html>", encoding="utf-8")
        inv = escanear(raiz)
        assert [p.name for _n, p in inv.recursos_html] == [
            "AFI_PiramideDelNeurolider_2.html"]
        assert not inv.otros


class TestFilasNoAplica:
    """La planilla trae la grilla completa de ítems posibles y el asesor
    marca "No Aplica" los que la materia no usa. Tomándolas por ítems, el
    aula salía con una decena de actividades y foros vacíos."""

    def _fila(self, estado):
        from maquetador.ingest.xlsx_parser import FilaPlanilla
        return FilaPlanilla(bloque="", item="Tarea", estado=estado)

    def test_la_fila_marcada_no_aplica_no_es_un_item(self):
        from maquetador.ingest.folder_scanner import normalizar
        assert "no aplica" in normalizar(self._fila("⚫ No Aplica").estado)
        assert "no aplica" not in normalizar(
            self._fila("🔵 Listo para Maquetar").estado)


class TestComentariosDeEsteAsesor:
    """Formas nuevas de escribir el mismo pedido."""

    @pytest.mark.parametrize("texto", [
        "para maquetación quick chek",
        "para maquetación: quick chek",
        "quic check",
        "quick check",
    ])
    def test_quick_check_con_cualquier_errata(self, texto):
        assert _clasificar(texto) == "quiz"

    def test_cita_a_secas(self):
        """El asesor nombra el componente, no arma una frase."""
        assert _clasificar("para maquetación: cita") == "cita"
        assert _clasificar("esto es una cita") == "cita"

    def test_tabs_vertical_con_la_palabra_recurso_adelante(self):
        assert _clasificar("para maquetación recurso tabs vertical") \
            == "tabs_vertical"
        assert _clasificar("para maquetación: recurso expander") == "expander"


class TestElVideoNoSeDuplica:
    """La planilla declara un "Video conceptual" por módulo y el hueco va en
    la Introducción. Pero si el DOCX ya dice dónde va, ese hueco ya está
    puesto: agregar otro deja el módulo con dos bloques de video."""

    @pytest.mark.parametrize("html", [
        "<p>Embeber video: GRyI - V_M1</p>",
        "<p>VIDEO M2.</p>",
        "<p>Te invito a ver el siguiente video antes de seguir.</p>",
    ])
    def test_reconoce_que_el_contenido_ya_lo_marca(self, html):
        assert contenido_declara_video(html) is True

    @pytest.mark.parametrize("html", [
        "",
        "<p>La neurociencia estudia el sistema nervioso.</p>",
        # Un CTA a un video externo no es el video propio del módulo.
        '<p>Mirá el video en <a href="https://youtu.be/x">YouTube</a>.</p>',
    ])
    def test_sin_marca_el_hueco_hace_falta(self, html):
        assert contenido_declara_video(html) is False
