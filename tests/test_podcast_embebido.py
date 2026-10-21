# -*- coding: utf-8 -*-
"""El audio propio sale con el "Embebido - Podcast" del catálogo.

Hasta ahora todo lo que olía a audio salía como "CTA - Podcast": un
recuadro con un enlace que manda afuera. Pero el catálogo tiene los dos
componentes, y el audio producido por la UCC —los MP3 que el modelo viejo
deja sueltos en la carpeta ("M1 Dispositivos IoT.mp3")— va en el embebido:
el degradé institucional, el nombre del audio en el medio y el reproductor
adentro.

Como con los videos, el id de Canvas Studio no existe cuando se arma el
aula. El recuadro sale igual: con el MP3 del paquete puesto como
reproductor de Canvas —que ya se escucha— y el hueco listo para que
--audio pegue el embed cuando los ids lleguen.
"""

import pytest

from maquetador.build.imscc_builder import GeneradorAula
from maquetador.build.snippets import (bloque_podcast_studio,
                                       componente_de_podcast)
from maquetador.models import CourseSpec


class TestElSnippetDelCatalogo:
    """Markup del "Embebido - Podcast", igual que en `Snipped utilizados`."""

    def test_el_degrade_institucional(self):
        out = bloque_podcast_studio("<p>Escuchalo.</p>")
        assert "linear-gradient(135deg, #003087 0%, #007bff 100%)" in out

    def test_la_superficie_clara_de_adentro(self):
        assert "background-color: #f9f9f9" in bloque_podcast_studio()

    def test_el_titulo_oficial_con_los_auriculares(self):
        out = bloque_podcast_studio()
        assert "fa-headphones" in out
        assert "Auriculares <strong>on</strong>" in out

    def test_el_nombre_del_audio_va_en_el_medio(self):
        out = bloque_podcast_studio("<p>Escuchalo.</p>", "M1 Dispositivos IoT")
        assert "<strong>M1 Dispositivos IoT</strong>" in out

    def test_sin_nombre_no_deja_un_renglon_vacio(self):
        assert "<strong></strong>" not in bloque_podcast_studio()

    def test_el_texto_del_asesor_se_conserva(self):
        out = bloque_podcast_studio("<p>Te invito a escuchar.</p>")
        assert "<p>Te invito a escuchar.</p>" in out

    def test_el_hueco_espera_el_embed_de_studio(self):
        assert "Pegar aquí el audio de Canvas Studio" in bloque_podcast_studio()

    def test_el_hueco_dice_cual_es(self):
        out = bloque_podcast_studio(referencia="M2 Deep Learning")
        assert "Canvas Studio: M2 Deep Learning" in out

    def test_con_el_id_entra_el_reproductor(self):
        out = bloque_podcast_studio(embed="<iframe class='lti-embed'></iframe>")
        assert "lti-embed" in out
        assert "Pegar aquí" not in out

    def test_el_hueco_del_audio_no_lo_agarra_el_de_video(self):
        """Los dos huecos conviven en la misma página: si el patrón de
        video matchara el del audio, --video pegaría un video adentro del
        recuadro de podcast."""
        from maquetador.build.imscc_builder import GeneradorAula as G
        assert not G._PAT_HUECO_VIDEO.search(bloque_podcast_studio())
        assert G._PAT_HUECO_AUDIO.search(bloque_podcast_studio())


class TestCuandoVaElEmbebidoYCuandoElCTA:
    """El catálogo tiene los dos y no son intercambiables."""

    def test_el_audio_propio_va_embebido(self):
        out = componente_de_podcast(
            "<p>Te invito a escuchar el siguiente audio sobre IoT.</p>")
        assert "fa-headphones" in out and "dp-embed-wrapper" in out

    @pytest.mark.parametrize("url", [
        "https://open.spotify.com/episode/x",
        "https://www.ivoox.com/audio_x.html",
        "https://podcasts.apple.com/ar/podcast/x",
    ])
    def test_el_de_una_plataforma_externa_sigue_siendo_un_CTA(self, url):
        """No es nuestro: no se sube a Studio, se abre afuera."""
        out = componente_de_podcast(
            f'<p>Escuchá el podcast en <a href="{url}">este enlace</a>.</p>')
        assert "dp-callout" in out and "dp-embed-wrapper" not in out

    def test_una_caja_que_no_anuncia_ningun_audio_queda_como_estaba(self):
        """El asesor encadena dos recuadros y el segundo hereda la
        etiqueta: armar el embebido dejaría un reproductor vacío."""
        out = componente_de_podcast(
            "<p>Considerando la creciente complejidad de los datos, "
            "¿por qué es necesario el aprendizaje profundo?</p>")
        assert "dp-embed-wrapper" not in out


class TestReconocerElAudioPorSuNombre:
    def _g(self):
        return GeneradorAula.__new__(GeneradorAula)

    def test_separa_el_modulo_de_las_palabras(self):
        assert self._g()._senas_del_audio("M1 Dispositivos IoT") \
            == ("1", ["dispositivos", "iot"])

    def test_las_palabras_vacias_no_cuentan(self):
        modulo, palabras = self._g()._senas_del_audio("M1 Toma de decisiones")
        assert (modulo, palabras) == ("1", ["toma", "decisiones"])

    def test_un_nombre_sin_modulo(self):
        assert self._g()._senas_del_audio("Entrevista Virgolini") \
            == ("", ["entrevista", "virgolini"])


def _generador(tmp_path, paginas, audios=("M1 Dispositivos IoT.mp3",)):
    g = GeneradorAula.__new__(GeneradorAula)
    g.spec = CourseSpec(nombre="Inteligencia Artificial Aplicada I")
    g.working = tmp_path / "working"
    (g.working / "wiki_content").mkdir(parents=True)
    recursos = g.working / "web_resources" / "Recursos"
    recursos.mkdir(parents=True)
    for nombre in audios:
        (recursos / nombre).write_bytes(b"ID3")
    for archivo, html in paginas.items():
        (g.working / "wiki_content" / archivo).write_text(
            html, encoding="utf-8")
    return g


def _pagina(titulo, cuerpo):
    return (f"<html><head><title>{titulo}</title></head>"
            f"<body>{cuerpo}</body></html>")


class TestElAudioDelPaqueteEntraEnElRecuadro:
    """Sin el id de Studio el recuadro no queda vacío: el MP3 ya viaja."""

    CUERPO = _pagina(
        "1.2. Conceptos de Big Data",
        bloque_podcast_studio(
            "<p>Te invito a escuchar el siguiente audio sobre "
            "Dispositivos IoT.</p>"))

    def _correr(self, tmp_path, **kw):
        g = _generador(tmp_path, {"1-2.html": self.CUERPO}, **kw)
        g._completar_podcasts()
        return (g.working / "wiki_content" / "1-2.html").read_text(
            encoding="utf-8"), g

    def test_pone_el_nombre_del_audio_en_el_renglon_del_medio(self, tmp_path):
        html, _ = self._correr(tmp_path)
        assert "<strong>M1 Dispositivos IoT</strong>" in html

    def test_publica_el_mp3_como_reproductor_de_canvas(self, tmp_path):
        html, _ = self._correr(tmp_path)
        assert "instructure_audio_link" in html
        assert "$IMS-CC-FILEBASE$/Recursos/M1%20Dispositivos%20IoT.mp3" in html

    def test_deja_el_hueco_para_cuando_llegue_el_id(self, tmp_path):
        html, _ = self._correr(tmp_path)
        assert "Pegar aquí el audio de Canvas Studio" in html

    def test_no_cruza_el_audio_de_otro_modulo(self, tmp_path):
        """"M2 Deep Learning" no puede caer en una página del módulo 1."""
        html, g = self._correr(tmp_path, audios=("M2 Deep Learning.mp3",))
        assert "instructure_audio_link" not in html
        assert any("M2 Deep Learning" in i.mensaje for i in g.spec.issues)

    def test_el_enlace_al_drive_del_asesor_se_cae(self, tmp_path):
        """Con el audio ya en la página, mandar al Drive donde se grabó es
        mandar al estudiante a una carpeta que no tiene por qué abrir."""
        g = _generador(tmp_path, {"1-2.html": _pagina(
            "1.2. Conceptos de Big Data", bloque_podcast_studio(
                '<p>Te invito a escuchar el siguiente <a class="inline_disabled"'
                ' href="https://drive.google.com/file/d/1PB/view">audio</a>'
                " sobre Dispositivos IoT.</p>"))})
        g._completar_podcasts()
        html = (g.working / "wiki_content" / "1-2.html").read_text(
            encoding="utf-8")
        assert "drive.google.com" not in html
        assert "el siguiente audio sobre Dispositivos IoT" in html

    def test_un_audio_no_se_repite_en_dos_recuadros(self, tmp_path):
        g = _generador(tmp_path, {
            "1-2.html": self.CUERPO,
            "1-4.html": _pagina("1.4. Oportunidades", bloque_podcast_studio(
                "<p>Te invito a escuchar el siguiente audio sobre "
                "Dispositivos IoT otra vez.</p>"))})
        g._completar_podcasts()
        leer = lambda n: (g.working / "wiki_content" / n).read_text(
            encoding="utf-8")
        assert leer("1-2.html").count("instructure_audio_link") == 1
        assert "instructure_audio_link" not in leer("1-4.html")


class TestCuandoLleganLosIds:
    CUERPO = _pagina(
        "1.2. Conceptos de Big Data",
        bloque_podcast_studio(
            "<p>Te invito a escuchar el siguiente audio sobre "
            "Dispositivos IoT.</p>"))
    ID = "7a0bdca8-7eae-4cc7-a80e-799772975463-1113"

    def _correr(self, tmp_path, clave):
        g = _generador(tmp_path, {"1-2.html": self.CUERPO})
        g.spec.audios_studio = {clave: self.ID}
        g._completar_podcasts()
        return (g.working / "wiki_content" / "1-2.html").read_text(
            encoding="utf-8"), g

    @pytest.mark.parametrize("clave", ["M1 Dispositivos IoT", "1.2"])
    def test_incrusta_el_embed_de_studio(self, tmp_path, clave):
        html, _ = self._correr(tmp_path, clave)
        assert f"custom_arc_media_id%3D{self.ID}" in html
        assert "lti-embed" in html

    def test_el_hueco_y_el_mp3_dejan_lugar_al_embed(self, tmp_path):
        html, _ = self._correr(tmp_path, "M1 Dispositivos IoT")
        assert "Pegar aquí el audio" not in html
        assert "instructure_audio_link" not in html

    def test_avisa_si_el_id_no_encuentra_su_recuadro(self, tmp_path):
        _, g = self._correr(tmp_path, "M3 Un audio que no existe")
        assert any("no encontré el recuadro" in i.mensaje
                   for i in g.spec.issues)
