# -*- coding: utf-8 -*-
"""Segunda revisión en Canvas de "Neurociencia Aplicada I".

El equipo maquetó sobre el paquete y volvió a anotar, página por página, lo
que hubo que arreglar. Cada test reproduce el markup real que fallaba,
verificado contra la exportación corregida del aula.
"""

import pytest
from bs4 import BeautifulSoup

from maquetador.build.snippets import (procesar_contenido, _texto_de_acceso,
                                       bloque_video_studio,
                                       enlazar_lecturas_con_bibliografia,
                                       indexar_figuras_diseno,
                                       reemplazar_figuras_diseno)
from maquetador.build.bibliography import indice_de_obras


class TestElAireTieneQueOcuparAlto:
    """Un <p> vacío de verdad, o con un espacio común, no ocupa alto: el
    renglón se come y los bloques quedan pegados. El aire del aula es
    siempre &nbsp;. Pasó debajo de "Ejemplos que iluminan" (1.3.2), entre
    los dos recuadros de 1.3.4 y al final de 2.3.2."""

    @pytest.mark.parametrize("vacio", ["<p></p>", "<p> </p>", "<p>\n</p>"])
    def test_el_parrafo_vacio_pasa_a_ser_aire(self, vacio):
        out = procesar_contenido(f"<p>Antes.</p>{vacio}<h3>Después</h3>")
        s = BeautifulSoup(out, "html.parser")
        sin_texto = [p for p in s.find_all("p") if not p.get_text().strip()]
        assert sin_texto, "desapareció el renglón de aire"
        assert all(p.get_text() == "\xa0" for p in sin_texto), \
            "el renglón de aire se publicó sin &nbsp;: no ocupa alto"

    def test_un_parrafo_con_imagen_no_se_toca(self):
        out = procesar_contenido('<p><img src="__MEDIA__/x.png"></p>')
        assert "<img" in out


class TestElIconoDelBloqueDeVideo:
    """El <i> de Font Awesome está vacío por definición: lo dibuja la
    fuente. La limpieza del marcado vacío de Word lo desenvolvía y el
    separador del bloque de video salía sin ícono, con "Video" como texto
    suelto."""

    def test_el_icono_sobrevive_a_procesar_contenido(self):
        out = procesar_contenido(bloque_video_studio(referencia="NAO - V_M1"))
        s = BeautifulSoup(out, "html.parser")
        icono = s.find("i", class_="fa-youtube")
        assert icono is not None
        assert "dp-icon" in icono.get("class")

    def test_el_marcado_vacio_de_word_se_sigue_limpiando(self):
        """Sin clase, un <strong> vacío es basura de Word y se saca."""
        out = procesar_contenido("<p><strong> </strong>Texto del párrafo.</p>")
        assert "<strong>" not in out


class TestLaUrlQueWordParteEnDos:
    """Al retocar el hipervínculo, Word deja la "h" de "https" afuera del
    <a>. Se publicaba una "h" huérfana, el link con el texto roto, y como
    no se reconocía la URL cruda tampoco se renombraba."""

    CAJA = ('<table><thead><tr><th><p><strong>Descubrí leyendo</strong></p>'
            "</th></tr><tr><th>"
            "<p>Para profundizar, recomendamos la lectura del siguiente "
            'artículo: <u>h</u><a href="https://www.ejemplo.com/nota.html">'
            "<u>ttps://www.ejemplo.com/nota.html</u></a></p>"
            "</th></tr></thead></table>")

    def test_el_enlace_se_rearma_entero(self):
        s = BeautifulSoup(procesar_contenido(self.CAJA), "html.parser")
        a = s.find("a", href="https://www.ejemplo.com/nota.html")
        assert a is not None
        assert "ttps://" not in s.get_text()

    def test_y_queda_renombrado(self):
        out = procesar_contenido(self.CAJA)
        assert "Acceso al documento" in out


class TestDosTextosDeEnlaceYNadaMas:
    """El aula usa "Ver video" y "Acceso al documento". No hay "Acceso al
    artículo" ni "Escuchar el podcast", aunque la cita hable de eso."""

    @pytest.mark.parametrize("contexto", [
        "Para profundizar, recomendamos la lectura del siguiente artículo",
        "Un episodio del podcast sobre liderazgo",
        "Revisá el capítulo 2 del manual",
    ])
    def test_todo_lo_que_no_es_video_es_documento(self, contexto):
        assert _texto_de_acceso(contexto) == "Acceso al documento"

    def test_el_video_si_tiene_el_suyo(self):
        assert _texto_de_acceso("Dos neuronas [Video]. YouTube.") == "Ver video"


class TestLaFiguraQueReemplazaUnaTabla:
    """En 2.2 el epígrafe trae debajo el título de la figura y el texto
    alternativo, así que la tabla queda a tres hermanos de distancia: no se
    la encontraba y la figura se publicaba ADEMÁS de la tabla, con los
    mismos datos dos veces."""

    HTML = ("<p><strong>Figura 1 </strong></p>"
            "<p><strong>Diferencia entre gestor, líder y neurolíder</strong></p>"
            "<p>texto alternativo: Gestor controla tareas; líder inspira.</p>"
            "<table><thead><tr><th><p><strong>Gestor</strong></p></th>"
            "<th><p><strong>Líder</strong></p></th></tr>"
            "<tr><th><p>Basado en el control</p></th>"
            "<th><p>Basado en la influencia</p></th></tr></thead></table>"
            "<p><em>Nota. </em>Tabla elaborada con base en el libro.</p>"
            "<p>En pocas palabras:</p>")

    def _salida(self, tmp_path):
        fig = tmp_path / "M_2 fig 1.jpg"
        fig.write_bytes(b"x")
        return reemplazar_figuras_diseno(
            self.HTML, 2, indexar_figuras_diseno([fig]), set())

    def test_la_tabla_no_se_publica_dos_veces(self, tmp_path):
        out = self._salida(tmp_path)
        assert "__DISENO__/M_2 fig 1.jpg" in out
        assert "<table" not in out
        assert "Basado en el control" not in out

    def test_lo_que_sigue_a_la_figura_se_queda(self, tmp_path):
        out = self._salida(tmp_path)
        assert "En pocas palabras" in out
        assert "Tabla elaborada con base en el libro" in out

    def test_la_figura_de_una_tabla_se_puede_ampliar(self, tmp_path):
        """Resume varias filas en una imagen: sin poder ampliarla no se
        lee."""
        assert "dp-popup-image" in self._salida(tmp_path)


class TestElLinkDelRecuadroDeLectura:
    """"Descubrí leyendo" manda a leer un capítulo de un libro que está en
    la bibliografía del módulo, con su enlace. El recuadro salía sin link y
    el alumno no tenía de dónde bajar el material."""

    REFS = ("<p><em>Bibliografía obligatoria</em></p>"
            "<p>Roldán González de las Cuevas, L. (2025). <em>Neurociencia "
            "empresarial. Potencie negocios con la ciencia del cerebro</em>. "
            'Autoedición <a href="https://drive.google.com/file/d/1gl/view">'
            "https://drive.google.com/file/d/1gl/view</a></p>")

    CAJA = ('<div class="dp-callout card"><div class="card-body">'
            '<p class="card-title">Descubrí leyendo</p>'
            "<p>En el libro<em> Neurociencia empresarial</em>, de Roldán "
            "(2025), revisá el capítulo 2.</p></div></div>")

    def test_el_indice_sale_de_la_cursiva_de_la_cita(self):
        indice = indice_de_obras(self.REFS)
        assert any(t.startswith("neurociencia empresarial") for t in indice)
        assert list(indice.values())[0] == "https://drive.google.com/file/d/1gl/view"

    def test_el_recuadro_recibe_el_enlace(self):
        out = enlazar_lecturas_con_bibliografia(
            self.CAJA, indice_de_obras(self.REFS))
        s = BeautifulSoup(out, "html.parser")
        a = s.find("a", href=True)
        assert a is not None
        assert a.get_text(strip=True) == "Acceso al documento"
        assert a["href"] == "https://drive.google.com/file/d/1gl/view"

    def test_si_ya_tiene_enlace_no_se_agrega_otro(self):
        caja = self.CAJA.replace("</div></div>",
                                 '<p><a href="https://x/y">Acceso al documento'
                                 "</a></p></div></div>")
        out = enlazar_lecturas_con_bibliografia(caja, indice_de_obras(self.REFS))
        assert out.count("Acceso al documento") == 1

    def test_otros_recuadros_no_se_tocan(self):
        """En "Auriculares on" una cursiva es el título de un video: con el
        enlace del libro mandaría a otro lado."""
        caja = ('<div class="dp-callout card"><div class="card-body">'
                '<p class="card-title">Auriculares on</p>'
                "<p>Mirá <em>Neurociencia empresarial</em> en YouTube.</p>"
                "</div></div>")
        out = enlazar_lecturas_con_bibliografia(caja, indice_de_obras(self.REFS))
        assert "Acceso al documento" not in out


class TestUnEncabezadoNoEsUnaOracion:
    """El asesor usa el estilo de título de Word para destacar una frase
    larga. En 2.4 la página abría con un <h3> de 196 caracteres en vez del
    párrafo de entrada."""

    def test_la_oracion_larga_baja_a_parrafo(self):
        frase = ("Sin duda, el éxito de un líder depende de muchos factores. "
                 "Entre ellos, podemos seleccionar al menos dos que son "
                 "básicos e indispensables: a) inteligencia emocional; y b) "
                 "capacidad de persuasión.")
        s = BeautifulSoup(procesar_contenido(f"<h3>{frase}</h3>"), "html.parser")
        assert s.find("h3") is None
        assert frase[:30] in s.get_text()

    def test_un_subtitulo_de_verdad_se_queda(self):
        out = procesar_contenido("<h3>Persuasión e inteligencia emocional</h3>")
        assert "<h3>" in out

    def test_el_encabezado_de_un_panel_no_se_toca(self):
        """Dentro de un componente el h3 es del panel, no del documento."""
        largo = ("Esta es una frase larguísima que el asesor puso como título "
                 "de un panel del expander y que termina con punto.")
        html = (f'<div class="dp-panels-wrapper"><div class="dp-panel-group">'
                f'<h3 class="dp-panel-heading">{largo}</h3>'
                f'<div class="dp-panel-content"><p>Cuerpo.</p></div>'
                f"</div></div>")
        s = BeautifulSoup(procesar_contenido(html), "html.parser")
        assert s.find("h3", class_="dp-panel-heading") is not None
