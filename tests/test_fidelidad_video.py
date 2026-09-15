# -*- coding: utf-8 -*-
"""Video propio (Canvas Studio) vs CTA a una plataforma externa.

Los videos de desarrollo / introducción / conceptuales son de la UCC: se suben
a Canvas Studio y se incrustan, NO son un llamado a la acción que manda a
YouTube. El generador los trataba a todos como CTA y dejaba el marcador
"VIDEO M2." publicado como texto.

El id del video recién existe cuando alguien lo sube, después de generar el
aula, así que el bloque queda armado y vacío listo para pegar el embed.

Ver docs/auditoria-fidelidad-gestion-calidad-2026-09-10.md
"""

from maquetador.build.snippets import procesar_contenido, bloque_video_studio

PROPIO = ("<p>Antes de profundizar en cada una de estas herramientas, te "
          "proponemos mirar el siguiente video conceptual. VIDEO M2.</p>")
EXTERNO = ('<p>Te invito a ver el video sobre calidad.</p>'
           '<p><a href="https://youtu.be/abc123">https://youtu.be/abc123</a></p>')


class TestVideoPropio:
    def test_arma_el_bloque_de_canvas_studio(self):
        out = procesar_contenido(PROPIO)
        assert 'data-title="Video"' in out
        assert 'data-category="+UCC"' in out

    def test_no_es_un_cta(self):
        assert "Auriculares on" not in procesar_contenido(PROPIO)

    def test_deja_el_hueco_para_el_embed(self):
        out = procesar_contenido(PROPIO)
        assert "dp-embed-wrapper" in out
        assert "Canvas Studio" in out

    def test_el_divisor_queda_en_h2(self):
        """El h2 con ícono es el divisor de sección: no se degrada a h3."""
        out = procesar_contenido(PROPIO)
        assert '<h2 class="dp-has-icon">' in out

    def test_no_publica_el_marcador(self):
        out = procesar_contenido(PROPIO)
        assert "VIDEO M2" not in out
        assert "video conceptual" in out

    def test_el_marcador_suelto_tampoco_se_publica(self):
        out = procesar_contenido("<p>Te invito a ver el video.</p><p>VIDEO 2</p>")
        assert "VIDEO 2" not in out


class TestMarcadorConNombreDeModulo:
    """El asesor también marca el video como "VIDEO MÓDULO 1" (no solo
    "VIDEO 2"/"VIDEO M2."), y a veces lo deja separado de la invitación por un
    párrafo de aire (&nbsp;): igual debe quedar adentro del mismo bloque, sin
    duplicar el hueco del embed ni publicarse como título suelto."""

    CON_AIRE = ("<p>Te invito a ver el siguiente video sobre calidad.</p>"
                "<p>&nbsp;</p><p><strong>VIDEO MÓDULO 1</strong></p>")

    def test_no_publica_el_marcador_con_modulo(self):
        out = procesar_contenido(self.CON_AIRE)
        assert "VIDEO MÓDULO" not in out.upper()

    def test_un_solo_bloque_de_video(self):
        out = procesar_contenido(self.CON_AIRE)
        assert out.count('data-title="Video"') == 1

    def test_suelto_separado_por_aire_no_publica_titulo(self):
        out = procesar_contenido(
            "<p>Te invito a ver el video.</p><p>&nbsp;</p><p>VIDEO MÓDULO 2</p>")
        assert "VIDEO MÓDULO" not in out.upper()
        assert out.count('data-title="Video"') == 1


class TestVideoExterno:
    def test_con_enlace_sigue_siendo_cta(self):
        out = procesar_contenido(EXTERNO)
        assert "Auriculares on" in out

    def test_no_arma_bloque_de_studio(self):
        assert 'data-title="Video"' not in procesar_contenido(EXTERNO)


class TestBloqueSuelto:
    def test_sin_intro_arma_igual_el_bloque(self):
        html = bloque_video_studio()
        assert "dp-embed-wrapper" in html
        assert '<h2 class="dp-has-icon">' in html
