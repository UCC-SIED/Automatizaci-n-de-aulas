# -*- coding: utf-8 -*-
"""Recuadros: anidamiento y centrado de frases cortas.

Salido de comparar el aula generada contra la corregida a mano: en el curso
de prueba había 25 recuadros contra 19, y dos de los que sobraban eran en
realidad un recuadro DENTRO de otro (se veía como "el recuadro puesto doble").

Ver docs/auditoria-fidelidad-gestion-calidad-2026-09-10.md
"""

from bs4 import BeautifulSoup

from maquetador.build.snippets import procesar_contenido, resaltado_simple
from maquetador.ingest.docx_comments import aplicar_comentarios

FRASE = "La participación temprana de stakeholders ayuda a evitar problemas."


class TestNoAnida:
    """El texto llega como cita (blockquote) Y con un comentario que pide
    recuadro: se encuadraba dos veces, una adentro de la otra."""

    def test_blockquote_con_recuadro_adentro_no_se_vuelve_a_encuadrar(self):
        html = ('<blockquote><div class="dp-callout dp-callout-color-lg-tip card">'
                f'<div class="card-body"><em>{FRASE}</em></div></div></blockquote>')
        out = procesar_contenido(html)
        assert out.count('class="dp-callout') == 1
        assert "<blockquote" not in out

    def test_la_cita_sin_recuadro_previo_si_se_encuadra(self):
        out = procesar_contenido(f"<blockquote><p>{FRASE}</p></blockquote>")
        assert out.count('class="dp-callout') == 1

    def test_el_comentario_no_encuadra_lo_que_ya_esta_encuadrado(self):
        soup = BeautifulSoup(
            f'<div class="dp-callout"><div class="card-body"><p>{FRASE}</p>'
            '</div></div>', "html.parser")
        coment = [{"instruccion": "Para maquetación: texto resaltado",
                   "anclado": FRASE, "accion": "recuadro_simple", "autor": ""}]
        aplicar_comentarios(soup, coment)
        assert str(soup).count('class="dp-callout') == 1


class TestFraseCortaCentrada:
    """'si la frase es chica centrala' — anotación de la revisión manual."""

    def test_frase_corta_va_centrada(self):
        html = resaltado_simple(f"<p><em>{FRASE}</em></p>")
        assert 'style="text-align: center;"' in html
        assert "card-text" in html

    def test_texto_largo_no_se_centra(self):
        largo = "<p>" + ("palabra " * 60) + "</p>"
        assert "text-align: center" not in resaltado_simple(largo)

    def test_respeta_una_alineacion_ya_puesta(self):
        html = resaltado_simple(f'<p style="text-align: right;">{FRASE}</p>')
        assert "text-align: right" in html
        assert "text-align: center" not in html

    def test_envuelve_el_contenido_suelto(self):
        html = resaltado_simple(f"<em>{FRASE}</em>")
        assert '<p class="card-text" style="text-align: center;">' in html


class TestCitaLargaSinEnvoltorio:
    """aplicar_comentarios pasa el contenido INTERNO del párrafo anclado
    ("".join(children), no el <p> que lo envolvía) a resaltado_simple. Con
    una cita corta no importa (se re-envuelve en el <p class="card-text">
    centrado), pero con una cita larga (>220, la rama que NO centra) el
    <em>/texto suelto quedaba como hijo directo de card-body, sin ningún
    <p> — a merced de cómo arme el navegador la caja anónima para ese
    contenido inline. Regresión real: módulo 1.4 de Gestión de la Calidad,
    "La participación temprana de stakeholders…" (233 caracteres)."""

    LARGA = ("La participación temprana de stakeholders ayuda a evitar uno "
             "de los problemas más frecuentes en proyectos: entregar algo "
             "técnicamente correcto que no responde a las expectativas "
             "reales de quienes deben usarlo, aprobarlo o sostenerlo.")

    def test_queda_envuelta_en_p(self):
        html = resaltado_simple(f"<em>{self.LARGA}</em>")
        assert f"<p><em>{self.LARGA}</em></p>" in html

    def test_no_se_centra_por_ser_larga(self):
        html = resaltado_simple(f"<em>{self.LARGA}</em>")
        assert "text-align: center" not in html
        assert "card-text" not in html

    def test_una_cita_larga_que_ya_trae_p_no_se_duplica(self):
        html = resaltado_simple(f"<p>{self.LARGA}</p>")
        assert html.count("<p>") == 1


class TestEspaciadoDelRecuadroSimple:
    """El recuadro simple (sin título) llevaba el aire corto solo ARRIBA:
    _espaciar_recuadros nunca llamaba a _aire_corto_despues en esa rama.
    Regresión real: '¿Estamos creando las condiciones para que el entregable
    sea correcto, útil y aceptado?' (1.1/1.2) quedaba pegado al párrafo
    siguiente. El pedido explícito es aire arriba Y abajo, el espaciado
    chico."""

    def test_lleva_aire_corto_arriba_y_abajo(self):
        html = ('<p>En términos prácticos, esto significa pasar de preguntar '
                'también:</p>'
                f'{resaltado_simple(f"<p><em>{FRASE}</em></p>")}'
                '<p>Esta diferencia es central para la dirección de '
                'proyectos.</p>')
        out = procesar_contenido(html)
        assert "<br/></p><div" in out
        assert "</div>\n</div><p><br/>" in out


class TestAireCortoEsUnParrafoPropio:
    """El "espacio chico" que arriba se pegaba como <br> al FINAL del
    párrafo anterior: se confirmó en Canvas que ESE <br>, pegado justo
    antes de un <div> (el recuadro), no siempre se ve como espacio —
    persistía el reclamo de '¿Estamos creando las condiciones…?' incluso
    ya con el fix de arriba/abajo. Ahora es un <p><br></p> propio, un
    bloque real con un único salto de línea adentro, no la cola de otro
    párrafo."""

    def test_no_se_cuelga_del_parrafo_anterior(self):
        html = ('<p>Antes.</p>'
                f'{resaltado_simple(f"<p><em>{FRASE}</em></p>")}'
                '<p>Después.</p>')
        out = procesar_contenido(html)
        assert "<p>Antes.</p><p><br/></p><div" in out
        assert "Antes.<br" not in out

    def test_dos_vecinos_no_duplican_el_espaciador(self):
        """Si ya hay un <p><br></p> (u otro espaciador) puesto, no se agrega
        uno encima — no queda "<p><br/></p><p><br/></p>" apilado."""
        html = ('<p>Antes.</p><p><br></p>'
                f'{resaltado_simple(f"<p><em>{FRASE}</em></p>")}'
                '<p>Después.</p>')
        out = procesar_contenido(html)
        assert "<p><br/></p><p><br/></p>" not in out
        assert "<p>Antes.</p><p><br/></p><div" in out
