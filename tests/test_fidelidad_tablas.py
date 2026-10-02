# -*- coding: utf-8 -*-
"""Tablas de datos del DOCX con el estilo institucional.

El generador las dejaba peladas (<table border="1">): sin barra de encabezado,
sin filas alternadas y sin contenedor, así que en pantalla chica rompían el
ancho de la página. El aula corregida a mano usa ic-Table dentro de
dp-table-scroll.

Ver docs/auditoria-fidelidad-gestion-calidad-2026-09-10.md
"""

import pytest
from bs4 import BeautifulSoup

from maquetador.build.snippets import procesar_contenido, CABECERA_TABLA_POR_TEMA

TABLA = ("<table><tr><td>Criterio</td><td>Descripción</td></tr>"
         "<tr><td>Exactitud técnica</td><td>Precisión en el cálculo.</td></tr>"
         "<tr><td>Aplicación</td><td>Capacidad de justificar.</td></tr></table>")


class TestEstiloInstitucional:
    def test_usa_ic_table(self):
        out = procesar_contenido(TABLA, "posgrado")
        assert "ic-Table" in out
        assert "ic-Table--striped" in out
        assert 'border="1"' not in out

    def test_va_dentro_del_contenedor_con_scroll(self):
        out = procesar_contenido(TABLA, "posgrado")
        soup = BeautifulSoup(out, "html.parser")
        assert soup.find("table").find_parent(class_="dp-table-scroll") is not None

    def test_la_primera_fila_pasa_a_encabezado(self):
        soup = BeautifulSoup(procesar_contenido(TABLA, "posgrado"), "html.parser")
        thead = soup.find("thead")
        assert thead is not None
        ths = thead.find_all("th")
        assert [t.get_text(strip=True) for t in ths] == ["Criterio", "Descripción"]
        assert all(t.get("scope") == "col" for t in ths)

    def test_filas_alternadas(self):
        soup = BeautifulSoup(procesar_contenido(TABLA, "posgrado"), "html.parser")
        cuerpo = [tr for tr in soup.find_all("tr")
                  if tr.find_parent("thead") is None]
        assert "#ffffff" in cuerpo[0]["style"]
        assert "#f4f7fa" in cuerpo[1]["style"]


class TestColorDeCabeceraPorTema:
    def test_los_dos_colores(self):
        assert CABECERA_TABLA_POR_TEMA["educacion"] == "#004a80"
        assert CABECERA_TABLA_POR_TEMA["posgrado"] == "#1b1e31"

    @pytest.mark.parametrize("tema,color", [("educacion", "#004a80"),
                                            ("posgrado", "#1b1e31")])
    def test_la_cabecera_usa_el_color_del_aula(self, tema, color):
        soup = BeautifulSoup(procesar_contenido(TABLA, tema), "html.parser")
        assert color in soup.find("thead").find("tr")["style"]

    def test_la_cabecera_de_tabla_no_es_el_acento_del_recuadro(self):
        """En educación el recuadro va #003087 pero la tabla #004a80."""
        assert CABECERA_TABLA_POR_TEMA["educacion"] != "#003087"


class TestNoRompeLoQueYaAndaba:
    def test_la_tabla_de_una_columna_sigue_siendo_recuadro(self):
        una = ("<table><tr><td>Video</td></tr>"
               "<tr><td>Mirá este video.</td></tr></table>")
        out = procesar_contenido(una, "posgrado")
        assert "dp-callout" in out
        assert "ic-Table" not in out
