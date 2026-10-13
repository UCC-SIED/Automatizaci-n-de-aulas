# -*- coding: utf-8 -*-
"""Incrustado de los videos de Canvas Studio.

La colección de Studio se comparte recién cuando la maquetación está por
cerrarse, así que al generar el paquete los ids todavía no existen y el
bloque sale con el hueco comentado. Cuando los ids llegan se vuelven a
pasar y el mismo paquete sale con los videos puestos: antes había que
pegar los cuatro embeds a mano, y al regenerar se perdían.

Los ids de estos tests son los de la exportación corregida de
"Neurociencia Aplicada a las Organizaciones I".
"""

import pytest

from maquetador.build.snippets import (media_id_de_studio, embed_de_studio,
                                       bloque_video_studio)

ID_INICIO = "571e42c5-6345-42f6-830b-6973a6a168ae-1446"
ID_141 = "6b047ed4-2206-4dce-b2f5-505793f02230-1449"


class TestLeerElIdDelMedio:
    """El id es el UUID del medio y, pegado con guion, su número. Puede
    llegar pelado o dentro del iframe entero copiado desde Canvas."""

    def test_desde_el_iframe_copiado(self):
        iframe = ('<iframe class="lti-embed" src="$CANVAS_COURSE_REFERENCE$'
                  "/external_tools/retrieve?display=borderless&amp;url=https"
                  "%3A%2F%2Fuccor.instructuremedia.com%2Flti%2Flaunch%3F"
                  "custom_arc_launch_type%3Dlearn_embed%26custom_arc_media_id"
                  f"%3D{ID_INICIO}%26custom_arc_start_at%3D0\"></iframe>")
        assert media_id_de_studio(iframe) == ID_INICIO

    def test_desde_el_id_pelado(self):
        assert media_id_de_studio(ID_INICIO) == ID_INICIO

    def test_el_enlace_de_edicion_no_sirve(self):
        """Lo que trae la planilla es el enlace de edición del subtitulado.
        Su token no es el id del reproductor: el UUID no se puede deducir de
        ahí, y adivinarlo publicaría un video roto."""
        url = ("https://uccor.instructuremedia.com/collections/user/"
               "perspectives/u2Ebsi80p4GHX6Z6RT79pQ/caption/edit/1446")
        assert media_id_de_studio(url) == ""

    def test_sin_nada_reconocible(self):
        assert media_id_de_studio("") == ""
        assert media_id_de_studio("Pendiente") == ""


class TestElEmbed:
    """Mismo iframe que genera Canvas al incrustar desde Studio."""

    def test_lleva_el_id_escapado_en_la_url_de_lanzamiento(self):
        out = embed_de_studio(ID_INICIO)
        assert f"custom_arc_media_id%3D{ID_INICIO}" in out
        assert "custom_arc_launch_type%3Dlearn_embed" in out
        assert "custom_arc_transcript_downloadable%3Dtrue" in out

    def test_el_curso_no_queda_clavado(self):
        """Con el id del aula adentro, el paquete solo sirve en esa aula."""
        out = embed_de_studio(ID_INICIO)
        assert "$CANVAS_COURSE_REFERENCE$/external_tools/retrieve" in out
        assert "/courses/" not in out

    def test_la_clase_y_el_tamano_son_los_del_aula(self):
        out = embed_de_studio(ID_INICIO)
        assert 'class="lti-embed"' in out
        assert "width: 700px; height: 441px; display: inline-block;" in out

    def test_sin_id_no_hay_embed(self):
        assert embed_de_studio("") == ""


class TestElBloqueDeVideo:
    def test_sin_id_queda_el_hueco_para_pegarlo(self):
        out = bloque_video_studio(referencia="NAO - V_M1")
        assert "Pegar aquí el embed de Canvas Studio: NAO - V_M1" in out
        assert "lti-embed" not in out

    def test_con_el_embed_ya_no_queda_hueco(self):
        out = bloque_video_studio(referencia="NAO - V_M1",
                                  embed=embed_de_studio(ID_141))
        assert "Pegar aquí" not in out
        assert ID_141 in out


class TestLaClaveDeLaPagina:
    """Los videos se pasan por número de página ("--video 2.3.2=<id>"); el
    de bienvenida, por "inicio"."""

    @pytest.mark.parametrize("titulo,clave", [
        ("1.4.1. La empresa es como un cerebro", "1.4.1"),
        ("2.3.2. Cómo mejorar la toma de decisiones", "2.3.2"),
        ("3.4. Neuroliderazgo estoico en equipos", "3.4"),
        ("Página de inicio", "inicio"),
        ("Introducción", "inicio"),
    ])
    def test_sale_del_titulo_de_la_pagina(self, titulo, clave):
        from maquetador.build.imscc_builder import GeneradorAula
        from maquetador.models import CourseSpec
        gen = GeneradorAula(CourseSpec(nombre="x"), {}, "output")
        assert gen._clave_de_pagina(titulo) == clave


class TestLlenarElBloqueSinPisarloP:
    """El video de bienvenida va DENTRO del bloque del aula base: su <h2>
    con el ícono de casa se conserva, y el aire de cierre queda último."""

    BLOQUE = ('<div class="dp-content-block" data-title="Te damos la '
              'bienvenida">\n<h2 class="dp-has-icon"><i class="fas fa-home">'
              "</i>Te damos la bienvenida</h2>\n<p>&nbsp;</p>\n</div>")

    def _gen(self):
        from maquetador.build.imscc_builder import GeneradorAula
        from maquetador.models import CourseSpec
        return GeneradorAula(CourseSpec(nombre="x"), {}, "output")

    def test_el_encabezado_sobrevive(self):
        html, ok = self._gen()._llenar_bloque(
            self.BLOQUE, "Te damos la bienvenida", "<p>VIDEO</p>")
        assert ok
        assert "fa-home" in html
        assert "<h2" in html
        assert "VIDEO" in html

    def test_el_aire_de_cierre_sigue_siendo_lo_ultimo(self):
        html, _ = self._gen()._llenar_bloque(
            self.BLOQUE, "Te damos la bienvenida", "<p>VIDEO</p>")
        assert html.index("VIDEO") < html.index("&nbsp;")

    def test_si_no_esta_el_bloque_no_inventa_nada(self):
        html, ok = self._gen()._llenar_bloque(
            "<div>otra cosa</div>", "Te damos la bienvenida", "<p>VIDEO</p>")
        assert not ok
        assert "VIDEO" not in html
