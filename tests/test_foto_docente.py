# -*- coding: utf-8 -*-
"""El aviso cuando la foto del docente llega con pocos píxeles."""
from pathlib import Path

import pytest

from maquetador.build.imscc_builder import GeneradorAula
from maquetador.models import CourseSpec, Severidad


def _generador(tmp_path):
    spec = CourseSpec(nombre="Materia")
    spec.tema = "educacion"
    g = GeneradorAula(spec, {}, tmp_path)
    g.working = tmp_path
    return g


def _imagen(ruta, lado):
    from PIL import Image
    Image.new("RGB", (lado, lado), "white").save(ruta)
    return ruta


class TestFotoChica:
    """La ficha muestra la foto a 150x150 y las pantallas de hoy piden el
    doble de píxeles reales: por debajo de eso se ve borrosa."""

    def test_avisa_cuando_el_recorte_queda_chico(self, tmp_path):
        g = _generador(tmp_path)
        recorte = _imagen(tmp_path / "chica.png", 180)
        g._avisar_si_la_foto_es_chica(recorte, Path("Foto docente.jpg"))
        assert any("borrosa" in i.mensaje for i in g.spec.issues)
        assert any("180x180" in i.mensaje for i in g.spec.issues)

    def test_no_avisa_con_una_foto_grande(self, tmp_path):
        g = _generador(tmp_path)
        recorte = _imagen(tmp_path / "grande.png", 2428)
        g._avisar_si_la_foto_es_chica(recorte, Path("Foto docente.jpg"))
        assert g.spec.issues == []

    def test_el_limite_es_el_doble_de_lo_que_muestra_la_ficha(self, tmp_path):
        g = _generador(tmp_path)
        g._avisar_si_la_foto_es_chica(
            _imagen(tmp_path / "justa.png", 300), Path("f.jpg"))
        assert g.spec.issues == []

    def test_nombra_el_archivo_original(self, tmp_path):
        g = _generador(tmp_path)
        g._avisar_si_la_foto_es_chica(
            _imagen(tmp_path / "c.png", 100), Path("EVELIN PINEDA.jpg"))
        assert any("EVELIN PINEDA.jpg" in i.mensaje for i in g.spec.issues)

    def test_un_archivo_ilegible_no_rompe(self, tmp_path):
        g = _generador(tmp_path)
        rota = tmp_path / "rota.png"
        rota.write_bytes(b"no soy una imagen")
        g._avisar_si_la_foto_es_chica(rota, Path("f.jpg"))
        assert g.spec.issues == []
