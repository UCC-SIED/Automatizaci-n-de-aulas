# -*- coding: utf-8 -*-
"""«Maquetación: enlazar actividad».

El asesor escribe "Para acceder a la consigna, hacé clic aquí" y anota al pie
del recuadro el DOCX al que apunta ("EP - AFI.docx"). Ese texto tiene que ser
el link al assignment, y el nombre del archivo es una nota para maquetación
que no va publicada.

Salido de auditar "Gestión del Riesgo y la Incertidumbre": los cuatro enlaces
quedaban como texto plano y los cuatro nombres de archivo se publicaban en la
página del estudiante.
"""

from bs4 import BeautifulSoup

from maquetador.build.snippets import procesar_contenido
from maquetador.ingest.docx_comments import _clasificar, aplicar_comentarios


CAJA_EP = (
    "<table><thead><tr><th><p><strong>¿Cómo vengo hasta acá?</strong></p></th>"
    "</tr><tr><th>"
    "<p>Te sugiero completar una entrega preparatoria del proyecto troncal, "
    "que luego desarrollarás en la segunda actividad obligatoria.</p>"
    "<p>Para acceder a las consignas, hacé clic aquí.</p>"
    '<p><a href="https://docs.google.com/document/d/1H">EP - AFI.docx</a></p>'
    "</th></tr></thead></table>")


def _aplicar(html, instruccion, anclado):
    soup = BeautifulSoup(html, "html.parser")
    coment = [{"instruccion": instruccion, "anclado": anclado,
               "accion": _clasificar(instruccion, anclado), "autor": ""}]
    aplicar_comentarios(soup, coment)
    return soup, coment[0]


class TestClasificacion:

    def test_enlazar_actividad(self):
        assert _clasificar("Maquetación: enlazar actividad") == "enlazar_actividad"

    def test_con_la_aclaracion_del_buzon(self):
        assert _clasificar("Maquetación: enlazar actividad; el buzón debe ser "
                           "el mismo que se abrió en el módulo 2") \
            == "enlazar_actividad"

    def test_no_se_confunde_con_otros_pedidos(self):
        assert _clasificar("Maquetación: subtítulo") == "subtitulo"


class TestMarcaEnElHtml:

    def test_el_texto_anclado_se_vuelve_link(self):
        soup, c = _aplicar(CAJA_EP, "Maquetación: enlazar actividad",
                           "Para acceder a las consignas, hacé clic aquí.")
        a = soup.find("a", class_="dp-course-link")
        assert c["_aplicado"] is True
        assert a is not None
        assert a.get_text(strip=True) == "Para acceder a las consignas, hacé clic aquí."

    def test_anota_el_docx_al_que_apunta(self):
        """Es el dato exacto: la prosa nombra la entrega preparatoria Y la
        obligatoria en el mismo párrafo, así que adivinar por el texto falla."""
        soup, _c = _aplicar(CAJA_EP, "Maquetación: enlazar actividad",
                            "Para acceder a las consignas, hacé clic aquí.")
        a = soup.find("a", class_="dp-course-link")
        assert a["data-actividad-archivo"] == "EP - AFI.docx"

    def test_la_entrega_preparatoria_es_la_sugerida(self):
        soup, _c = _aplicar(CAJA_EP, "Maquetación: enlazar actividad",
                            "Para acceder a las consignas, hacé clic aquí.")
        assert soup.find("a", class_="dp-course-link")["data-actividad"] \
            == "sugerida"

    def test_el_modulo_que_nombra_el_asesor_queda_en_la_marca(self):
        """"el buzón debe ser el mismo que se abrió en el módulo 2": sin esto
        el módulo 3 abría su propio buzón para la misma entrega."""
        soup, _c = _aplicar(
            CAJA_EP,
            "Maquetación: enlazar actividad; el buzón debe ser el mismo que se "
            "abrió en el módulo 2",
            "Para acceder a las consignas, hacé clic aquí.")
        assert soup.find("a", class_="dp-course-link")["data-actividad"] \
            == "sugerida:2"

    def test_una_caja_de_obligatoria_apunta_a_la_obligatoria(self):
        html = CAJA_EP.replace(
            "Te sugiero completar una entrega preparatoria del proyecto "
            "troncal, que luego desarrollarás en la segunda actividad "
            "obligatoria.",
            "Con estas herramientas estás en condiciones de realizar la primera "
            "actividad obligatoria.")
        soup, _c = _aplicar(html, "Maquetación: enlazar actividad",
                            "Para acceder a las consignas, hacé clic aquí.")
        assert soup.find("a", class_="dp-course-link")["data-actividad"] \
            == "obligatoria"


class TestNombreDeArchivoSuelto:
    """El pie "EP - AFI.docx" es la nota del asesor sobre qué entregable
    corresponde: se publicaba tal cual, con el link al Drive de asesoría."""

    def test_no_se_publica(self):
        out = procesar_contenido(CAJA_EP)
        assert "EP - AFI.docx" not in out
        assert "docs.google.com" not in out

    def test_el_resto_del_recuadro_se_conserva(self):
        out = procesar_contenido(CAJA_EP)
        assert "Para acceder a las consignas, hacé clic aquí." in out
        assert "entrega preparatoria del proyecto troncal" in out

    def test_sin_link_tampoco(self):
        out = procesar_contenido("<p>Texto.</p><p>AEO 1 - GRyI.docx</p>")
        assert "AEO 1 - GRyI.docx" not in out
        assert "Texto." in out

    def test_un_archivo_subido_al_aula_si_se_publica(self):
        """El descargable real apunta al archivo del propio paquete: ese es
        contenido, no una nota."""
        html = ('<p>Texto.</p><p><a href="$IMS-CC-FILEBASE$/Multimedia%20'
                'cargada/Plantilla.docx">Plantilla.docx</a></p>')
        assert "Plantilla.docx" in procesar_contenido(html)

    def test_una_frase_que_menciona_un_archivo_no_se_borra(self):
        html = ("<p>Descargá la plantilla Registro.xlsx y completala con los "
                "riesgos de tu proyecto.</p>")
        assert "Registro.xlsx" in procesar_contenido(html)


class TestDestacarTramo:
    """«Maquetación: en cursiva u otra forma de destacado» sobre el prompt de
    IA que el estudiante copia y pega. Son varios párrafos seguidos, no uno:
    con el recuadro simple (que encuadra un solo elemento) el bloque quedaba
    partido y se confundía con el cuerpo de la página."""

    PROMPT = (
        "<p>Adaptá a tu necesidad el siguiente texto, copialo y pegalo:</p>"
        "<p>[Prompt]<em> Actúa como analista de gestión de riesgos.</em></p>"
        "<p><em>Necesito una planilla de cálculo simple.</em></p>"
        "<p><em>Mi proyecto: </em>[escribirlo en una o dos líneas]</p>"
        "<p>Después de copiarlo, revisá el resultado.</p>")

    ANCLA = ("[Prompt] Actúa como analista de gestión de riesgos. Necesito una "
             "planilla de cálculo simple. Mi proyecto: [escribirlo en una o "
             "dos líneas]")

    def _out(self):
        soup, c = _aplicar(self.PROMPT,
                           "Maquetación: en cursiva u otra forma de destacado",
                           self.ANCLA)
        return str(soup), c

    def test_se_clasifica(self):
        assert _clasificar("Maquetación: en cursiva u otra forma de destacado") \
            == "destacar_tramo"

    def test_el_tramo_entero_queda_en_una_sola_caja(self):
        out, c = self._out()
        assert c["_aplicado"] is True
        soup = BeautifulSoup(out, "html.parser")
        assert len(soup.find_all(class_="dp-callout")) == 1
        caja = soup.find(class_="dp-callout")
        assert "Actúa como analista" in caja.get_text()
        assert "Mi proyecto:" in caja.get_text()

    def test_se_completa_la_cursiva_que_falta(self):
        """El asesor escribió en cursiva casi todo, pero no el rótulo ni los
        campos que el estudiante completa."""
        caja = BeautifulSoup(self._out()[0], "html.parser").find(class_="dp-callout")
        sueltos = [t for t in caja.find_all(string=True) if t.strip()
                   and not any(p.name in ("em", "i") for p in t.parents)]
        assert sueltos == []

    def test_no_se_lleva_lo_que_esta_fuera_del_tramo(self):
        caja = BeautifulSoup(self._out()[0], "html.parser").find(class_="dp-callout")
        assert "copialo y pegalo" not in caja.get_text()
        assert "revisá el resultado" not in caja.get_text()

    def test_el_texto_de_alrededor_sigue_en_la_pagina(self):
        out, _c = self._out()
        assert "copialo y pegalo" in out
        assert "revisá el resultado" in out
