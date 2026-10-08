# -*- coding: utf-8 -*-
"""Los tres pedidos del asesor que quedaban sin resolverse solos.

Salían como aviso en cada corrida de Neurociencia y había que armarlos a
mano en Canvas.
"""

from pathlib import Path

from bs4 import BeautifulSoup

from maquetador.build.componentes_asesor import pares_de_texto
from maquetador.ingest.docx_comments import aplicar_comentarios, _clasificar, _AUTO


class TestTituloEnNegritaDentroDeUnaLista:
    """El asesor marca el término en negrita y sigue con lo que tenga a
    mano: coma ("<b>Hipotálamo</b>, que participa en…") o punto
    ("<b>Privacidad mental</b>. ¿Quién podrá…"). Exigir dos puntos dejaba
    sin armar los dos pedidos de tabs verticales de Neurociencia."""

    def _items(self, html):
        return BeautifulSoup(html, "html.parser").find_all("li")

    def test_con_coma(self):
        pares = pares_de_texto(self._items(
            "<ul><li><strong>Hipotálamo</strong>, que participa en el control "
            "del hambre y la sed.</li>"
            "<li><strong>Tálamo</strong>, estación del procesamiento "
            "sensorial hacia la corteza.</li></ul>"))
        assert [p[0] for p in pares] == ["Hipotálamo", "Tálamo"]
        assert pares[0][1].startswith("que participa")

    def test_con_punto(self):
        pares = pares_de_texto(self._items(
            "<ul><li><strong>Privacidad mental</strong>. ¿Quién podrá acceder "
            "a la información de las neuroimágenes?</li>"
            "<li><strong>Autonomía personal</strong>. ¿Hasta qué punto una "
            "intervención puede coartar la libertad?</li></ul>"))
        assert [p[0] for p in pares] == ["Privacidad mental", "Autonomía personal"]

    def test_un_item_sin_negrita_corta_la_serie(self):
        pares = pares_de_texto(self._items(
            "<ul><li><strong>Hipotálamo</strong>, controla el hambre y la sed.</li>"
            "<li>Un ítem cualquiera, sin término en negrita adelante.</li></ul>"))
        assert len(pares) == 1

    def test_la_negrita_larga_no_es_un_titulo(self):
        """Un ítem entero en negrita es énfasis, no un rótulo."""
        pares = pares_de_texto(self._items(
            "<ul><li><strong>Todo este ítem está en negrita porque el asesor "
            "quiso destacarlo entero, no porque sea un título</strong></li>"
            "<li><strong>Otro igual, también entero en negrita y bien "
            "largo para que no pase por rótulo</strong></li></ul>"))
        assert pares == []


class TestTabsVerticalesDesdeLaLista:
    HTML = ("<p>Entre ellas se destacan:</p>"
            "<ul><li><strong>Hipotálamo</strong>, controla el hambre y la sed.</li>"
            "<li><strong>Tálamo</strong>, procesa la información sensorial.</li>"
            "<li><strong>Hipocampo</strong>, consolida los recuerdos nuevos.</li>"
            "</ul>")

    def test_se_arma_el_componente(self):
        s = BeautifulSoup(self.HTML, "html.parser")
        aplicar_comentarios(s, [{
            "accion": "tabs_vertical",
            "instruccion": "para maquetación: recurso tabs vertical",
            "anclado": "Hipotálamo, controla el hambre y la sed."}])
        sopa = BeautifulSoup(str(s), "html.parser")
        panel = sopa.find(class_="dp-panels-wrapper")
        assert panel is not None
        assert "dp-tabs-buttons-vertical" in panel.get("class")
        assert [h.get_text(" ", strip=True)
                for h in sopa.find_all(class_="dp-panel-heading")] == [
            "Hipotálamo", "Tálamo", "Hipocampo"]


class TestReemplazarPorLaFiguraDeDiseno:
    """"Reemplazar esta figura por la que está en carpeta diseño" es lo que
    el generador hace solo cuando diseño mandó la figura con ese número:
    avisarlo era una falsa alarma en cada corrida."""

    def test_se_reconoce_y_no_avisa(self):
        accion = _clasificar(
            "para maquetación: reemplazar eta figura por la que está en "
            "carpeta diseño", "Nota. Figura creada con Claude.")
        assert accion == "figura_de_diseno"
        assert accion in _AUTO

    def test_un_pedido_vago_sigue_avisando(self):
        assert _clasificar("maquetación", "Un texto cualquiera.") == "revisar"


class TestAvisoDeFiguraDeDisenoSinUbicar:
    """Si el epígrafe no coincide con el número del archivo, la figura se
    perdía en silencio. Ahora se avisa."""

    def test_avisa_la_que_no_se_uso(self, tmp_path):
        from maquetador.build.imscc_builder import GeneradorAula
        from maquetador.models import CourseSpec
        spec = CourseSpec(nombre="x")
        gen = GeneradorAula(spec, {}, tmp_path)
        gen.indice_diseno = {(2, "figura", 3): Path("M_2 fig 3.jpg"),
                             (2, "figura", 4): Path("M_2 fig 4.jpg")}
        gen.figuras_usadas = {Path("M_2 fig 4.jpg")}
        gen._avisar_figuras_de_diseno_sin_usar()
        textos = [i.mensaje for i in spec.issues]
        assert any("M_2 fig 3.jpg" in t for t in textos)
        assert not any("M_2 fig 4.jpg" in t for t in textos)
