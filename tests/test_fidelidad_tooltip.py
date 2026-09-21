# -*- coding: utf-8 -*-
"""Tooltip: qué palabra lo dispara y con qué markup.

La automatización convertía el PÁRRAFO ENTERO en el disparador, y además
armaba un popover en vez de un tooltip. En el aula corregida a mano solo la
sigla ("SGC") abre el globo.

Ver docs/auditoria-fidelidad-gestion-calidad-2026-09-10.md
"""

import pytest
from bs4 import BeautifulSoup

from maquetador.build.componentes_asesor import (sigla_de, disparador_tooltip,
                                                 construir_tooltip)
from maquetador.ingest.docx_comments import aplicar_comentarios

PARRAFO = ("La norma ISO 9001 es un estándar internacional que establece los "
           "requisitos para implementar un SGC eficaz, basado en los "
           "principios ya mencionados en 1.2.")
TERMINO = "Sistema de Gestión de la Calidad"


class TestSigla:
    def test_arma_la_sigla_salteando_preposiciones(self):
        assert sigla_de(TERMINO) == "SGC"

    def test_otra_sigla(self):
        assert sigla_de("Actividad Final Integradora") == "AFI"


class TestDisparador:
    def test_prefiere_la_sigla_presente_en_el_texto(self):
        assert disparador_tooltip(PARRAFO, TERMINO) == "SGC"

    def test_si_no_hay_sigla_usa_el_termino_completo(self):
        assert disparador_tooltip("Hablamos de mejora continua acá.",
                                  "mejora continua") == "mejora continua"

    def test_no_marca_nada_si_el_termino_no_aparece(self):
        """Antes marcaba el párrafo entero, que quedaba hecho un link."""
        assert disparador_tooltip("Un texto cualquiera.", "Otra Cosa") == ""

    def test_la_sigla_tiene_que_ser_palabra_entera(self):
        assert disparador_tooltip("Un SGCX raro.", TERMINO) == ""


class TestMarkup:
    def test_es_tooltip_y_no_popover(self):
        html = construir_tooltip("SGC", TERMINO, 0)
        assert "dp-tooltip-container" in html
        assert "dp-tooltip-trigger" in html
        assert "dp-tooltip-content" in html
        assert "dp-popover-trigger" not in html

    def test_el_contenido_va_dentro_del_contenedor(self):
        soup = BeautifulSoup(construir_tooltip("SGC", TERMINO, 0), "html.parser")
        cont = soup.find(class_="dp-tooltip-container")
        assert cont.find(class_="dp-tooltip-content") is not None


class TestAplicadoAlParrafo:
    def _aplicar(self):
        soup = BeautifulSoup(f"<div><p>{PARRAFO}</p></div>", "html.parser")
        coment = [{"instruccion": f"Para maquetación: tooltip --> {TERMINO}",
                   "anclado": PARRAFO, "accion": "tooltip", "autor": ""}]
        aplicar_comentarios(soup, coment)
        return str(soup), coment[0]

    def test_se_aplica(self):
        _, c = self._aplicar()
        assert c.get("_aplicado") is True

    def test_solo_la_sigla_queda_como_disparador(self):
        out, _ = self._aplicar()
        assert ">SGC</a>" in out

    def test_el_parrafo_no_se_convierte_en_un_link(self):
        out, _ = self._aplicar()
        soup = BeautifulSoup(out, "html.parser")
        assert len(soup.find("a").get_text(strip=True)) < 10
        assert "La norma ISO 9001 es un estándar" in out
