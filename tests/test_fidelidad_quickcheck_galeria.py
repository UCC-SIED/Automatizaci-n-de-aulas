# -*- coding: utf-8 -*-
"""Quick Check y Galería de figuras.

Dos componentes que el asesor pide por comentario y que antes salían como
texto plano: la lista de verdadero/falso quedaba como un párrafo numerado y
las figuras, una debajo de otra a lo largo de media página. El markup de
referencia es el del aula corregida de "Neurociencia Aplicada I".
"""

from bs4 import BeautifulSoup

from maquetador.build.snippets import (quick_check, galeria_de_figuras,
                                       preguntas_de_verdadero_o_falso,
                                       procesar_contenido)
from maquetador.ingest.docx_comments import aplicar_comentarios


class TestArmarLasPreguntas:
    """Word parte los renglones largos: la respuesta ("Falso") cae en un
    párrafo aparte del enunciado y hay que volver a unirlos."""

    def test_junta_el_enunciado_con_su_respuesta_partida(self):
        preguntas = preguntas_de_verdadero_o_falso([
            "1. Las neuronas se unen sólidamente.", "Falso",
            "2. La transmisión es química.", "Verdadero"])
        assert preguntas == [("Las neuronas se unen sólidamente.", "Falso"),
                             ("La transmisión es química.", "Verdadero")]

    def test_la_respuesta_en_el_mismo_renglon(self):
        preguntas = preguntas_de_verdadero_o_falso([
            "1. El cerebro consume glucosa. (Verdadero)",
            "2. La corteza es blanca. (Falso)"])
        assert [p[1] for p in preguntas] == ["Verdadero", "Falso"]

    def test_el_numero_no_queda_en_el_enunciado(self):
        preguntas = preguntas_de_verdadero_o_falso(
            ["1. El cerebro consume glucosa. Verdadero"])
        assert preguntas[0][0] == "El cerebro consume glucosa."


class TestLaGrillaDelQuickCheck:
    PREGUNTAS = [("Una.", "Verdadero"), ("Dos.", "Falso"),
                 ("Tres.", "Verdadero")]

    def test_cada_pregunta_es_una_tarjeta(self):
        s = BeautifulSoup(quick_check(self.PREGUNTAS), "html.parser")
        assert len(s.find_all(attrs={"data-interactive-id": True})) == 3

    def test_la_impar_ocupa_el_ancho_entero(self):
        """De a dos por fila, la última de una cantidad impar quedaría
        colgando a la izquierda con medio renglón vacío al lado."""
        out = quick_check(self.PREGUNTAS)
        assert out.count("col-lg-6 col-md-6 col-sm-12") == 2
        assert "col-12" in out

    def test_con_cantidad_par_no_hay_ninguna_entera(self):
        out = quick_check(self.PREGUNTAS[:2])
        assert out.count("col-lg-6 col-md-6 col-sm-12") == 2
        assert "col-12" not in out

    def test_cada_tarjeta_tiene_su_propio_id(self):
        s = BeautifulSoup(quick_check(self.PREGUNTAS), "html.parser")
        ids = [d["data-interactive-id"]
               for d in s.find_all(attrs={"data-interactive-id": True})]
        assert len(set(ids)) == len(ids)

    def test_el_titulo_oficial(self):
        assert "Compruebe su comprensión" in quick_check(self.PREGUNTAS)


class TestElQuickCheckDesdeElComentario:
    """El asesor marca la tabla con las preguntas y pide el componente."""

    HTML = ("<table><tbody>"
            "<tr><td><p>Marcá verdadero o falso.</p>"
            "<p>1. Las neuronas se unen sólidamente. Falso</p>"
            "<p>2. La transmisión es química. Verdadero</p>"
            "<p>3. La corteza hace posible el lenguaje. Verdadero</p>"
            "</td></tr></tbody></table>")

    def _aplicar(self, html):
        s = BeautifulSoup(html, "html.parser")
        aplicar_comentarios(s, [{
            "accion": "quiz",
            "instruccion": "para maquetación: quick check",
            "anclado": "Las neuronas se unen sólidamente."}])
        return str(s)

    def test_la_tabla_se_vuelve_la_grilla(self):
        out = self._aplicar(self.HTML)
        assert "Compruebe su comprensión" in out
        assert "<table" not in out

    def test_el_rotulo_de_la_caja_no_entra_como_pregunta(self):
        """"Marcá verdadero o falso" termina en "falso": sin cortar desde el
        primer ítem numerado se colaba como la pregunta 1."""
        out = self._aplicar(self.HTML)
        tarjetas = BeautifulSoup(out, "html.parser").find_all(
            attrs={"data-interactive-id": True})
        assert len(tarjetas) == 3
        assert "Marcá verdadero o falso" not in out

    def test_con_una_sola_pregunta_no_arma_nada(self):
        """Mejor el texto como venía que una grilla de una sola tarjeta."""
        out = self._aplicar("<table><tbody><tr><td>"
                            "<p>1. Única. Verdadero</p></td></tr></tbody></table>")
        assert "Compruebe su comprensión" not in out


class TestLaGaleriaDeFiguras:
    FIGURAS = [("3", "Nivel 1 - Fundamento neurobiológico",
                '<img src="__MEDIA__/f3.png">', "Nota. Elaboración propia."),
               ("4", "Nivel 2 - Hábitos estoicos",
                '<img src="__MEDIA__/f4.png">', ""),
               ("5", "Nivel 3 - Equipos",
                '<img src="__MEDIA__/f5.png">', "")]

    def test_arma_la_grilla_con_una_tarjeta_por_figura(self):
        s = BeautifulSoup(galeria_de_figuras(self.FIGURAS), "html.parser")
        assert s.find(class_="dp-popup-gallery") is not None
        assert len(s.find_all("img")) == 3

    def test_la_imagen_pierde_el_ancho_fijo_del_docx(self):
        """Con el width: 700px que trae Word, la figura se sale de su celda
        y rompe la grilla."""
        out = galeria_de_figuras([("3", "T", '<img style="width: 700px;" '
                                   'src="__MEDIA__/f3.png">', "")])
        assert "700px" not in out
        assert "object-fit: contain" in out

    def test_el_titulo_de_cada_tarjeta_no_se_vuelve_un_h3(self):
        """El promotor de negritas a <h3> convertía el título de cada
        tarjeta en un encabezado de sección: aparecían en el índice de la
        página y con el estilo del tema encima de la grilla. El único h3 que
        queda es el de la galería entera."""
        s = BeautifulSoup(procesar_contenido(galeria_de_figuras(self.FIGURAS)),
                          "html.parser")
        encabezados = [h.get_text(strip=True) for h in s.find_all("h3")]
        assert encabezados == ["Galería de Figuras"]
        assert "Nivel 1 - Fundamento neurobiológico" in str(s)

    def test_el_titulo_oficial(self):
        assert "Galería de Figuras" in galeria_de_figuras(self.FIGURAS)
