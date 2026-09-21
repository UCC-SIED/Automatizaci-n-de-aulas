# -*- coding: utf-8 -*-
"""Genially y demás recursos incrustados.

El pedido de Genially es un encargo para el diseñador ("Para diseño: … -->
Genially, pantalla principal con 7 botones…"), que después entrega el div para
incrustar en Canvas. La descripción NO es contenido de la página: lo que va es
el hueco donde se pega el recurso.

Ver docs/auditoria-fidelidad-gestion-calidad-2026-09-10.md
"""

import pytest

from maquetador.build.snippets import (procesar_contenido, _PAT_GENIALLY_URL,
                                       bloque_recurso_incrustado)

URL_VISTA = "https://view.genially.com/6a8869e899d6db519fae8e99"


class TestDominios:
    @pytest.mark.parametrize("url", [
        URL_VISTA,
        "https://genial.ly/abc123",
        "https://genially.com/xyz",
    ])
    def test_reconoce_las_dos_formas_de_url(self, url):
        """Las aulas usan view.genially.com; el patrón solo cubría genial.ly."""
        assert _PAT_GENIALLY_URL.search(url)


class TestConUrl:
    def test_incrusta_el_iframe(self):
        out = procesar_contenido(f"<p>Ver el recurso: {URL_VISTA}</p>")
        assert "<iframe" in out
        assert "6a8869e899d6db519fae8e99" in out

    def test_usa_el_contenedor_responsivo(self):
        out = procesar_contenido(f"<p>Ver el recurso: {URL_VISTA}</p>")
        assert "padding-bottom: 56.25%" in out
        assert "dp-embed-wrapper" in out


class TestSinUrl:
    DESCRIPCION = "<p>Recurso tipo Genially: pantalla con 7 botones.</p>"

    def test_deja_el_hueco_para_el_diseniador(self):
        out = procesar_contenido(self.DESCRIPCION)
        assert "dp-embed-wrapper" in out
        assert "padding-bottom: 56.25%" in out

    def test_no_es_un_recuadro_de_atencion(self):
        """Antes salía como un recuadro rojo; es un encargo, no una alerta."""
        out = procesar_contenido(self.DESCRIPCION)
        assert "dp-callout-color-danger" not in out

    def test_la_descripcion_no_se_publica(self):
        out = procesar_contenido(self.DESCRIPCION)
        assert "7 botones" not in out


class TestContenedor:
    def test_vacio_trae_la_marca_de_donde_va(self):
        html = bloque_recurso_incrustado(titulo="Genially")
        assert "Incrustar aquí" in html
        assert "Genially" in html
