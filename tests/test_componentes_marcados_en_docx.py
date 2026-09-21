# -*- coding: utf-8 -*-
"""El asesor pide el componente DESDE el DOCX: escribe su nombre como primera
línea de la caja ("Expander", "Tabs (uno al lado del otro)", "Flips cards…") y
le deja encima un comentario que solo dice "Maquetación".

Salido de auditar "Gestión del Riesgo y la Incertidumbre" (asesor Sebastián):
de 13 componentes pedidos así, las tabs no existían, las flip cards no se
reconocían por la 's' de más, y los expanders perdían el cuerpo entero cuando
venía en listas o en una tabla de datos anidada.
"""

import re

from maquetador.build.snippets import procesar_contenido


def _paneles(html: str) -> list:
    return re.findall(r'<h3 class="dp-panel-heading">([^<]*)</h3>', html)


# ---------------------------------------------------------------- expander --

EXPANDER_CON_LISTAS = (
    "<table><thead><tr><th>"
    "<p>Expander</p>"
    "<p><strong>Frente a las amenazas</strong></p>"
    "<ul><li>Evitar: se actúa para eliminar la amenaza.</li>"
    "<li>Escalar: hay consenso de que está fuera del alcance.</li></ul>"
    "<p><strong>Frente a las oportunidades</strong></p>"
    "<p>Estrategias que funcionan como espejo para agregar valor:</p>"
    "<ul><li>Aprovechar: actuar para asegurar que ocurra.</li></ul>"
    "</th></tr></thead></table>")


class TestExpander:

    def test_los_items_en_lista_no_se_pierden(self):
        """El cuerpo de cada panel venía en <ul> y el extractor solo miraba
        los <p>: el primer panel quedaba vacío y se perdían las 5 estrategias."""
        out = procesar_contenido(EXPANDER_CON_LISTAS)
        assert _paneles(out) == ["Frente a las amenazas",
                                 "Frente a las oportunidades"]
        assert "Evitar: se actúa para eliminar la amenaza." in out
        assert "Aprovechar: actuar para asegurar que ocurra." in out
        assert out.count("<ul>") == 2

    def test_la_instruccion_no_queda_a_la_vista(self):
        assert "<p>Expander</p>" not in procesar_contenido(EXPANDER_CON_LISTAS)

    def test_el_titulo_que_sigue_al_nombre_del_componente_se_conserva(self):
        """"Expander Cuatro preguntas para decidir": lo que va después del
        nombre del componente es el título del bloque, no la indicación."""
        html = EXPANDER_CON_LISTAS.replace(
            "<p>Expander</p>",
            "<p>Expander Cuatro preguntas para decidir en entornos cambiantes</p>")
        out = procesar_contenido(html)
        assert ('<p class="lead dp-text-bold">Cuatro preguntas para decidir '
                'en entornos cambiantes</p>') in out
        assert len(_paneles(out)) == 2


class TestExpanderConTablaAdentro:
    """El asesor mete una tabla de datos (con su epígrafe APA) dentro de un
    panel: el epígrafe va en negrita igual que los títulos de panel."""

    HTML = (
        "<table><thead><tr><th>"
        "<p>Expander</p>"
        "<p><strong>Valor monetario esperado (VME)</strong>. Se multiplica la "
        "probabilidad por el impacto.</p>"
        "<p><strong>Tabla 2</strong></p>"
        "<p><strong>Valor monetario esperado y exposición neta</strong></p>"
        "<table><thead><tr><th><p><strong>ID</strong></p></th>"
        "<th><p><strong>VME</strong></p></th></tr>"
        "<tr><th><p>R-017</p></th><th><p>-100000</p></th></tr></thead></table>"
        "<p><em>Nota. </em>Cálculo del VME.</p>"
        "<p><strong>Árboles de decisión</strong>. Representación gráfica de "
        "las decisiones y sus resultados.</p>"
        "</th></tr></thead></table>")

    def test_el_epigrafe_no_abre_un_panel(self):
        assert _paneles(procesar_contenido(self.HTML)) == [
            "Valor monetario esperado (VME)", "Árboles de decisión"]

    def test_la_tabla_anidada_sobrevive_y_queda_estilada(self):
        """Al reemplazar la tabla contenedora, las de adentro quedaban fuera
        del árbol: se publicaban sin estilo (o directamente aplastadas)."""
        out = procesar_contenido(self.HTML)
        assert "R-017" in out and "-100000" in out
        assert "ic-Table" in out       # la clase termina en el <figure> que
        assert "Cálculo del VME." in out   # arma la Nota como epígrafe


# -------------------------------------------------------------- flip cards --

class TestFlipCards:

    HTML = (
        "<table><thead><tr><th>"
        "<p>Flips cards (una al lado de la otra)</p>"
        "<p><strong>Sector privado</strong>. Una desarrolladora detecta que un "
        "competidor libera un módulo con licencia abierta.</p>"
        "<p><strong>Sector público</strong>. Un municipio enfrenta demoras por "
        "trámites ambientales.</p>"
        "</th></tr></thead></table>")

    def test_flips_cards_con_la_ese_de_mas_igual_se_reconoce(self):
        """El asesor escribe "Flips cards": con la lista de palabras vieja la
        caja salía como recuadro, con la instrucción a la vista."""
        out = procesar_contenido(self.HTML)
        assert "dp-flip-card" in out
        assert "Flips cards" not in out

    def test_frente_y_dorso(self):
        out = procesar_contenido(self.HTML)
        assert "<strong>Sector privado</strong>" in out
        assert "Un municipio enfrenta demoras por trámites ambientales." in out


# -------------------------------------------------------------------- tabs --

class TestTabsHorizontales:

    HTML = (
        "<table><thead><tr><th>"
        "<p>Tabs (uno al lado del otro)</p>"
        "<p><strong>Amenaza</strong>.<strong> </strong>Riesgo con impacto "
        "potencialmente perjudicial.</p>"
        "<p><strong>Oportunidad</strong>.<strong> </strong>Riesgo de impacto "
        "potencialmente positivo.</p>"
        "</th></tr></thead></table>")

    def test_se_arman_las_solapas(self):
        out = procesar_contenido(self.HTML)
        assert "dp-tabs-buttons" in out
        assert _paneles(out) == ["Amenaza", "Oportunidad"]

    def test_las_solapas_horizontales_van_a_ancho_completo(self):
        assert "dp-panel-tab-width-fill" in procesar_contenido(self.HTML)

    def test_la_instruccion_no_queda_a_la_vista(self):
        assert "uno al lado del otro" not in procesar_contenido(self.HTML)

    def test_el_resaltado_vacio_de_word_no_ensucia_el_cuerpo(self):
        """"<strong>Amenaza</strong>.<strong> </strong>Riesgo…" dejaba un
        <strong> con un solo espacio al principio de cada panel."""
        assert "<strong> </strong>" not in procesar_contenido(self.HTML)


class TestTabsVerticalesSobreTablaDeDatos:
    """La otra forma de pedirlas: el asesor escribe la tabla y arriba anota
    "Tabs verticales; al hacer clic en cada zona se abren las columnas"."""

    HTML = (
        "<table><thead><tr><th>"
        "<p>Tabs verticales; al hacer clic en cada “zona”, se abren las "
        "columnas correspondientes. Respetar colores.</p>"
        "<table><thead>"
        "<tr><th><p><strong>Zona</strong></p></th>"
        "<th><p><strong>Qué exige</strong></p></th>"
        "<th><p><strong>Qué se documenta</strong></p></th></tr>"
        "<tr><th><p>Roja</p></th><th><p>Respuesta obligatoria.</p></th>"
        "<th><p>Plan de respuesta completo.</p></th></tr>"
        "<tr><th><p>Verde</p></th><th><p>Monitoreo.</p></th>"
        "<th><p>Lista de observación.</p></th></tr>"
        "</thead></table>"
        "</th></tr></thead></table>")

    def test_una_solapa_por_fila(self):
        assert _paneles(procesar_contenido(self.HTML)) == ["Roja", "Verde"]

    def test_la_variante_vertical_la_dice_el_asesor(self):
        out = procesar_contenido(self.HTML)
        assert "dp-tabs-buttons-vertical" in out
        assert "dp-panel-tab-width-fill" not in out

    def test_el_encabezado_de_columna_va_pegado_al_texto(self):
        """Suelto en su propio párrafo en negrita lo agarraba el paso de
        subtítulos y una columna quedaba con estilo de subtítulo y la otra no."""
        out = procesar_contenido(self.HTML)
        assert "<strong>Qué exige.</strong> Respuesta obligatoria." in out
        assert "lead dp-text-bold" not in out

    def test_la_indicacion_no_queda_a_la_vista(self):
        out = procesar_contenido(self.HTML)
        assert "Respetar colores" not in out
        assert "al hacer clic" not in out


class TestElPedidoPorComentarioNoSeVaDeLaCaja:
    """El asesor ancla el comentario sobre la caja ("Tabs (uno al lado de
    otro)") y `pares_de_tabla` no ve pares ahí: hay una sola celda. El armado
    seguía de largo por los HERMANOS de la tabla y montaba las solapas con lo
    que venía DESPUÉS —el epígrafe "Tabla 1" y su tabla de escalas, que
    además desaparecían de la página— mientras la caja real quedaba cruda."""

    HTML = (
        "<table><thead><tr><th>"
        "<p>Tabs (uno al lado de otro)</p>"
        "<p><strong>Zona roja</strong>. Concentra los riesgos de alto impacto.</p>"
        "<p><strong>Zona verde</strong>. Riesgos de bajo impacto.</p>"
        "</th></tr></thead></table>"
        "<p>Las escalas no se improvisan durante la evaluación.</p>"
        "<p><strong>Tabla 1</strong></p>"
        "<p><strong>Escalas de probabilidad e impacto por objetivo</strong></p>"
        "<table><thead><tr><th><p>Nivel</p></th><th><p>Probabilidad</p></th></tr>"
        "<tr><th><p>Alto</p></th><th><p>70 %</p></th></tr></thead></table>")

    COMENTARIO = [{"instruccion": "Maquetación: ver la posibilidad de agregar "
                                  "colores en los tabs",
                   "anclado": "Tabs (uno al lado de otro)",
                   "accion": "tabs", "autor": ""}]

    def _aplicado(self):
        from bs4 import BeautifulSoup
        from maquetador.ingest.docx_comments import aplicar_comentarios
        soup = BeautifulSoup(self.HTML, "html.parser")
        aplicar_comentarios(soup, [dict(c) for c in self.COMENTARIO])
        return str(soup)

    def test_las_solapas_salen_de_la_caja_anclada(self):
        assert _paneles(self._aplicado()) == ["Zona roja", "Zona verde"]

    def test_lo_que_sigue_a_la_caja_queda_intacto(self):
        out = self._aplicado()
        assert "Las escalas no se improvisan durante la evaluación." in out
        assert "<strong>Tabla 1</strong>" in out
        assert "Escalas de probabilidad e impacto por objetivo" in out
        assert "Probabilidad" in out and "70 %" in out


class TestBriefDeFiguraParaDiseno:
    """Caja de una celda con el epígrafe arriba y, abajo, la descripción de lo
    que tiene que dibujar Diseño. Cuando la figura llega hecha, ese texto ya
    está DENTRO de la imagen: dejarlo publica lo mismo dos veces."""

    HTML = (
        "<table><thead><tr><th>"
        "<p><strong>Figura 4. </strong>Toma de decisiones</p>"
        "<p>Imagen, tipo check list</p>"
        "<p><strong>Mantener opciones y flexibilidad</strong>. Evitar "
        "comprometer recursos de forma irreversible.</p>"
        "<p><strong>Avanzar en pasos reversibles</strong>. Priorizar una "
        "prueba piloto a un despliegue total.</p>"
        "</th></tr></thead></table>")

    def _con_diseno(self, tmp_path):
        from maquetador.build.snippets import (indexar_figuras_diseno,
                                               reemplazar_figuras_diseno)
        fig = tmp_path / "M_3 fig 4.jpg"
        fig.write_bytes(b"x")
        indice = indexar_figuras_diseno([fig])
        return reemplazar_figuras_diseno(self.HTML, 3, indice, set())

    def test_la_figura_de_diseno_reemplaza_al_pedido(self, tmp_path):
        out = self._con_diseno(tmp_path)
        assert "__DISENO__/M_3 fig 4.jpg" in out
        assert "Figura 4. Toma de decisiones" in out

    def test_el_pedido_a_diseno_no_se_publica(self, tmp_path):
        out = self._con_diseno(tmp_path)
        assert "Imagen, tipo check list" not in out
        assert "Mantener opciones y flexibilidad" not in out
        assert "Avanzar en pasos reversibles" not in out

    def test_sin_figura_de_diseno_no_se_borra_nada(self):
        """Si la imagen no llegó, el texto es lo único que hay: se publica."""
        from maquetador.build.snippets import reemplazar_figuras_diseno
        out = reemplazar_figuras_diseno(self.HTML, 3, {}, set())
        assert "Mantener opciones y flexibilidad" in out

    def test_la_nota_al_pie_sobrevive(self, tmp_path):
        from maquetador.build.snippets import (indexar_figuras_diseno,
                                               reemplazar_figuras_diseno)
        fig = tmp_path / "M_3 fig 4.jpg"
        fig.write_bytes(b"x")
        html = self.HTML.replace(
            "</th></tr></thead></table>",
            "<p><em>Nota. </em>Elaboración propia.</p></th></tr></thead></table>")
        out = reemplazar_figuras_diseno(html, 3, indexar_figuras_diseno([fig]), set())
        assert "Elaboración propia." in out

    def test_una_figura_suelta_en_el_texto_no_arrastra_lo_que_sigue(self, tmp_path):
        """Fuera de una caja no hay pedido a Diseño que borrar: lo que sigue al
        epígrafe es el cuerpo de la página."""
        from maquetador.build.snippets import (indexar_figuras_diseno,
                                               reemplazar_figuras_diseno)
        fig = tmp_path / "M_3 fig 4.jpg"
        fig.write_bytes(b"x")
        html = ("<p><strong>Figura 4. </strong>Toma de decisiones</p>"
                "<p>El párrafo que explica la figura y sigue la lectura.</p>")
        out = reemplazar_figuras_diseno(html, 3, indexar_figuras_diseno([fig]), set())
        assert "El párrafo que explica la figura y sigue la lectura." in out


class TestAnchoRealDeLaTabla:

    def test_una_caja_con_tabla_adentro_no_es_una_tabla_de_datos(self):
        """Contar las celdas con find_all mezclaba las de la tabla anidada:
        una caja de 1 celda daba "13 columnas" y se maquetaba como tabla de
        datos, con una tabla metida adentro del <th> de otra."""
        html = ("<table><thead><tr><th><p>Una pausa para reflexionar</p>"
                "<table><thead>"
                "<tr><th><p>A</p></th><th><p>B</p></th><th><p>C</p></th></tr>"
                "<tr><th><p>1</p></th><th><p>2</p></th><th><p>3</p></th></tr>"
                "</thead></table></th></tr></thead></table>")
        out = procesar_contenido(html)
        assert "dp-callout" in out
        assert out.count('class="ic-Table') == 1


class TestElGloboSoloSenalaElComponente:
    """Con este asesor el globo dice solo "Maquetación": el pedido está en el
    texto marcado, que es el nombre del componente escrito como primera línea
    de la caja. Esos comentarios llenaban el informe de avisos "revisar
    pedido" aunque el componente ya saliera bien."""

    def test_no_queda_como_pedido_pendiente(self):
        from maquetador.ingest.docx_comments import _clasificar
        for ancla in ("Expander", "Tabs (uno al lado del otro)",
                      "Tabs verticales; al hacer clic en cada zona",
                      "Flips cards (una al lado de la otra)"):
            assert _clasificar("Maquetación", ancla) == "componente_en_el_texto", ancla

    def test_un_pedido_de_verdad_sigue_avisando(self):
        from maquetador.ingest.docx_comments import _clasificar
        assert _clasificar("Maquetación: plantilla descargable",
                           "La herramienta más adecuada es la más simple") \
            == "revisar"

    def test_el_componente_lo_sigue_armando_la_caja(self):
        """No se enruta al armador por comentario a propósito: el que sale de
        la caja entiende listas y tablas adentro de cada panel."""
        from bs4 import BeautifulSoup
        from maquetador.ingest.docx_comments import aplicar_comentarios
        soup = BeautifulSoup(EXPANDER_CON_LISTAS, "html.parser")
        coment = [{"instruccion": "Maquetación", "anclado": "Expander",
                   "accion": "componente_en_el_texto", "autor": ""}]
        aplicar_comentarios(soup, coment)
        assert coment[0]["_aplicado"] is True
        assert soup.find("table") is not None     # la caja llega intacta
        assert _paneles(procesar_contenido(str(soup))) == [
            "Frente a las amenazas", "Frente a las oportunidades"]
