# -*- coding: utf-8 -*-
"""Lo que dejó la revisión de Metodología II (16-10-2026).

La corrección que más se repitió: el maquetador armaba componentes que la
asesora no había pedido, deduciéndolos del texto. *"Todo esto está bien
interpretado, pero lamentablemente si no me lo pide el asesor no puedo
marcarlo, así que la próxima dejalo texto plano."*

Los componentes salen SOLO cuando hay un pedido explícito: un comentario en
el DOCX, una tabla del asesor, o un marcador escrito en el documento.
"""

import pytest
from bs4 import BeautifulSoup

from maquetador.build.componentes_asesor import aplicar_cita
from maquetador.build.snippets import procesar_contenido


class TestNoSeInventanComponentes:
    """Las cuatro frases que armaban un recuadro sin que nadie lo pidiera."""

    @pytest.mark.parametrize("parrafo,componente", [
        # "No pases de largo" sobre un párrafo que arranca así.
        ("Es importante señalar que hay un mundo que nos preexiste, con su "
         "lenguaje, sus normas y un conjunto de instituciones que lo "
         "conforman, en el que los sujetos se vinculan intersubjetivamente.",
         "No pases de largo"),
        # "Descubrí leyendo".
        ("Te invito a leer el texto de Guevara Patiño que aborda el estado "
         "del arte en la investigación según los distintos paradigmas.",
         "Descubrí leyendo"),
        # Bloque de video, sin marcador ni enlace.
        ("Te propongo visualizar el material que acompaña este recorrido "
         "para seguir pensando la propuesta del módulo.",
         "data-title=\"Video\""),
        # "Miralo con lupa".
        ("Te propongo observar la imagen con atención y registrar qué "
         "elementos reconocés antes de seguir leyendo el apartado.",
         "Miralo con lupa"),
    ])
    def test_el_texto_solo_no_alcanza(self, parrafo, componente):
        out = procesar_contenido(f"<p>{parrafo}</p>")
        assert componente not in out
        assert "dp-callout" not in out

    def test_el_texto_sigue_estando(self):
        """No se arma el recuadro, pero el contenido no se pierde."""
        out = procesar_contenido(
            "<p>Es importante señalar que hay un mundo que nos preexiste, "
            "con su lenguaje y sus normas.</p>")
        assert "un mundo que nos preexiste" in out

    def test_con_el_comentario_del_asesor_si_se_arma(self):
        """La contracara: cuando lo pide, sale."""
        from maquetador.ingest.docx_comments import aplicar_comentarios
        soup = BeautifulSoup(
            "<p>Es importante señalar que hay un mundo que nos preexiste.</p>",
            "html.parser")
        aplicar_comentarios(soup, [{
            "accion": "recuadro_simple",
            "instruccion": "Para maquetación: mantener recuadro destacado",
            "anclado": "Es importante señalar que hay un mundo que nos preexiste.",
        }])
        assert "dp-callout" in str(soup)


class TestElVideoSaleConSuMarcador:
    """Apagar la deducción por prosa no puede llevarse por delante el video
    que el asesor sí marca."""

    def test_el_marcador_pegado_al_final(self):
        out = procesar_contenido(
            "<p>Antes de profundizar en cada una de estas herramientas, te "
            "proponemos mirar el siguiente video conceptual. VIDEO M2.</p>")
        assert 'data-title="Video"' in out

    def test_el_marcador_en_su_propio_parrafo(self):
        out = procesar_contenido(
            "<p>Te invitamos a ver el video conceptual del módulo.</p>"
            "<p>VIDEO M1.</p>")
        assert 'data-title="Video"' in out

    def test_el_marcador_no_se_publica(self):
        out = procesar_contenido(
            "<p>Te proponemos mirar el siguiente video. VIDEO M2.</p>")
        assert "VIDEO M2" not in out

    def test_un_enlace_externo_sigue_siendo_cta(self):
        """El enlace a YouTube está escrito en el documento: tampoco es una
        deducción de la prosa."""
        out = procesar_contenido(
            "<p>Te invito a ver el video sobre narrativas transmedia.</p>"
            '<p><a href="https://youtu.be/abc123">https://youtu.be/abc123</a></p>')
        assert "Auriculares on" in out

    def test_sin_marcador_ni_enlace_no_hay_bloque(self):
        out = procesar_contenido(
            "<p>Luego de ver el video, te propongo pensar en tu "
            "institución.</p>")
        assert 'data-title="Video"' not in out


class TestLaCitaDeWordEsUnaCita:
    """El estilo "Cita" de Word llegaba como <blockquote> y se publicaba
    encuadrado. Es una cita: va sangrada y sin caja."""

    FRASE = ("Esta actitud metodológica lleva necesariamente a sustituir la "
             "relación ingenua entre el individuo y la sociedad. (p. 18)")

    def test_queda_sangrada(self):
        out = procesar_contenido(f"<blockquote><p>{self.FRASE}</p></blockquote>")
        assert "margin-left: 80px" in out

    def test_no_queda_encuadrada(self):
        out = procesar_contenido(f"<blockquote><p>{self.FRASE}</p></blockquote>")
        assert "dp-callout" not in out

    def test_no_se_pierde_el_blockquote_sin_parrafos(self):
        out = procesar_contenido(f"<blockquote>{self.FRASE}</blockquote>")
        assert "sustituir la relación ingenua" in out
        assert "<blockquote" not in out


class TestLaSangriaDeLaCita:
    """Seis veces en la misma revisión: "le falta aumentar la sangría una
    vez más"."""

    def test_ochenta_a_la_izquierda(self):
        p = BeautifulSoup("<p>Una cita textual larga.</p>", "html.parser").p
        aplicar_cita(p)
        assert "margin-left: 80px" in p["style"]

    def test_cuarenta_a_la_derecha(self):
        """El margen derecho queda: sin él la cita se lee como un párrafo
        corrido con un margen cualquiera."""
        p = BeautifulSoup("<p>Una cita textual larga.</p>", "html.parser").p
        aplicar_cita(p)
        assert "margin-right: 40px" in p["style"]

    def test_respeta_el_estilo_que_ya_tenia(self):
        p = BeautifulSoup('<p style="text-align: justify;">Cita.</p>',
                          "html.parser").p
        aplicar_cita(p)
        assert "text-align: justify" in p["style"]
        assert "margin-left: 80px" in p["style"]
