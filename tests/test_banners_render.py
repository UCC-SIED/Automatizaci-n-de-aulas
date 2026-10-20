# -*- coding: utf-8 -*-
"""Banners dibujados por el maquetador.

El diseño vive en Figma y hasta ahora los banners se armaban a mano con un
plugin: cargar la planilla, capturar los frames, exportar un ZIP y subirlo
a Canvas página por página. Ahora el paquete los trae dibujados desde la
misma planilla, sobre la plantilla del diseño oficial (el render del
componente sin su capa de texto).

Validado contra el banner que renderiza Figma: el logo y el separador
quedan idénticos y el fondo en 0,76/255 de error.
"""

import pytest

pytest.importorskip("PIL")

from maquetador.build import banners
from maquetador.build.imscc_builder import _banner_de_actividad


HAY_PLANTILLA = (banners.PLANTILLAS / "plantilla-posgrado.png").exists()
sin_plantilla = pytest.mark.skipif(
    not HAY_PLANTILLA, reason="falta la plantilla de posgrado")


class TestLaFuenteEsLaDelDiseno:
    """Montserrat, que es la que declara el archivo de Figma. Se guarda en
    el repo con su licencia (OFL) para no depender de que esté instalada."""

    def test_esta_la_fuente(self):
        assert banners.FUENTE.exists()
        assert (banners.FUENTE.parent / "Montserrat-OFL.txt").exists()

    @pytest.mark.parametrize("variante", ["Bold", "SemiBold"])
    def test_tiene_las_variantes_que_usa_el_diseno(self, variante):
        f = banners._fuente(variante, 33)
        assert f is not None


class TestCorteDeLineas:
    def test_corta_por_palabra_sin_pasarse_del_ancho(self):
        f = banners._fuente("SemiBold", 33)
        texto = ("Modelo Integrado de Neuroliderazgo Estoico aplicado a "
                 "equipos de trabajo")
        lineas = banners._cortar_en_lineas(texto, f, 600)
        assert len(lineas) > 1
        assert all(f.getlength(l) <= 600 for l in lineas)
        assert " ".join(lineas) == texto

    def test_una_palabra_sola_no_se_pierde(self):
        f = banners._fuente("SemiBold", 33)
        assert banners._cortar_en_lineas("Neurociencia", f, 10) == ["Neurociencia"]

    def test_texto_vacio_no_rompe(self):
        f = banners._fuente("SemiBold", 33)
        assert banners._cortar_en_lineas("", f, 600) == []


@sin_plantilla
class TestElBannerQueSale:
    def test_tiene_la_medida_del_diseno(self):
        img = banners.banner_de_pagina("1.3.1. La arquitectura de una neurona")
        assert img.size == (banners.ANCHO * banners.ESCALA,
                            banners.ALTO * banners.ESCALA)

    def test_el_de_modulo_lleva_dos_renglones(self):
        """"Módulo 1" arriba, el nombre abajo: el bloque ocupa más alto que
        el de una página, que lleva un solo renglón."""
        from PIL import ImageChops
        uno = banners.banner_de_pagina("Neurociencia básica")
        dos = banners.banner_de_modulo(1, "Neurociencia básica")
        assert ImageChops.difference(uno.convert("RGB"),
                                     dos.convert("RGB")).getbbox() is not None

    def test_el_texto_solo_toca_su_caja(self):
        from PIL import ImageChops
        vacio = banners.render("", tema="posgrado").convert("RGB")
        con = banners.banner_de_pagina("Una prueba").convert("RGB")
        caja = ImageChops.difference(vacio, con).getbbox()
        x0 = banners.CAJA_X * banners.ESCALA
        x1 = (banners.CAJA_X + banners.CAJA_ANCHO) * banners.ESCALA
        assert caja is not None
        assert caja[0] >= x0 - 2 and caja[2] <= x1 + 2

    @pytest.mark.parametrize("tema", sorted(
        p.stem.replace("plantilla-", "")
        for p in banners.PLANTILLAS.glob("plantilla-*.png")) or ["posgrado"])
    def test_la_plantilla_no_trae_el_texto_viejo_pegado(self, tema):
        """El fantasma del texto que traia el diseño tiene que haberse ido.

        No alcanza con buscar pixeles claros: en el tema de posgrado el
        fantasma es oscuro sobre oscuro y asi pasaba desapercibido —me paso
        con la plantilla de educacion, que di por buena y tenia pegado
        "Modulo 3 / Cultura institucional…". Lo que si lo delata es el
        contorno: un fondo limpio es un degradado liso y casi no cambia al
        desenfocarlo; un fantasma deja bordes que el desenfoque borra."""
        from PIL import ImageChops, ImageFilter, ImageStat
        img = banners.render("", tema=tema).convert("L")
        caja = img.crop((int(banners.CAJA_X * banners.ESCALA),
                         int(banners.CAJA_Y * banners.ESCALA),
                         int((banners.CAJA_X + banners.CAJA_ANCHO) * banners.ESCALA),
                         int((banners.CAJA_Y + banners.CAJA_ALTO) * banners.ESCALA)))
        d = ImageChops.difference(caja, caja.filter(ImageFilter.GaussianBlur(6)))
        assert ImageStat.Stat(d).mean[0] < 1.5, (
            f"la plantilla de {tema} tiene texto pegado")

    def test_un_tema_sin_plantilla_avisa(self):
        with pytest.raises(FileNotFoundError):
            banners.render("Hola", tema="no-existe")


class TestBannerDeCadaActividad:
    """El nombre del archivo del aula base dice qué actividad es.

    El texto del banner es el NOMBRE con que la actividad queda en Canvas,
    no una descripción: "Actividad obligatoria M1", no "…del módulo 1". El
    banner y el ítem tienen que decir lo mismo."""

    @pytest.mark.parametrize("archivo,clave,texto", [
        ("actividad-obligatoria-m2", "actividad-obligatoria-m2",
         "Actividad obligatoria M2"),
        ("actividad-final-integradora", "actividad-final-integradora",
         "Actividad final integradora"),
    ])
    def test_cada_una_con_su_texto(self, archivo, clave, texto):
        assert _banner_de_actividad(archivo, "educacion") == (clave, texto)

    @pytest.mark.parametrize("tema,texto", [
        ("educacion", "Actividad sugerida M3"),
        ("posgrado", "Actividad M3"),
    ])
    def test_la_no_obligatoria_se_llama_distinto_en_cada_aula(self, tema, texto):
        """Igual que los foros: en educación es "sugerida" y en posgrado va
        a secas."""
        assert _banner_de_actividad("actividad-sugerida-m3", tema) == (
            "actividad-sugerida-m3", texto)

    def test_la_obligatoria_se_llama_igual_en_los_dos(self):
        for tema in ("educacion", "posgrado"):
            assert _banner_de_actividad("actividad-obligatoria-m1", tema)[1] \
                == "Actividad obligatoria M1"

    def test_otro_archivo_no_lleva_banner_propio(self):
        assert _banner_de_actividad("pagina-de-inicio", "educacion") == ("", "")


# Esqueleto de un assignment del aula base: el bloque "Actividad" tiene que
# cerrar contra </body>, que es lo que busca _escribir_assignment.
_PLANTILLA_ASSIGNMENT = (
    "<html><body>"
    '<div class="dp-banner-image"><img src="x.png" alt="viejo"/></div>'
    '<div class="dp-content-block" data-title="Actividad">'
    "<p>&nbsp;</p>"
    "</div></div></body></html>")


class TestElBannerDelClonSugerido:
    """El clon de la actividad sugerida conserva el nombre de archivo de la
    obligatoria, así que por el archivo le tocaba el banner de ella: los dos
    salían cruzados ("el banner que pusiste es Actividad Sugerida M1",
    revisión de Metodología II)."""

    def _generador(self, tmp_path, tema="educacion"):
        from maquetador.build.imscc_builder import GeneradorAula
        from maquetador.models import CourseSpec
        spec = CourseSpec(nombre="Materia")
        spec.tema = tema
        g = GeneradorAula(spec, {}, tmp_path)
        g.working = tmp_path
        return g

    def test_manda_la_ranura_y_no_el_nombre_del_archivo(self, tmp_path):
        g = self._generador(tmp_path)
        g.rid_sugerida[1] = "ridClon"
        # El clon guarda su HTML con el nombre de la obligatoria.
        carpeta = tmp_path / "ridClon"
        carpeta.mkdir()
        (carpeta / "actividad-obligatoria-m1.html").write_text(
            _PLANTILLA_ASSIGNMENT, encoding="utf-8")
        g._escribir_assignment("ridClon", "<p>La consigna.</p>", "ctx")
        salida = (carpeta / "actividad-obligatoria-m1.html").read_text(
            encoding="utf-8")
        assert 'alt="Actividad sugerida M1"' in salida

    def test_en_posgrado_el_clon_va_sin_la_palabra_sugerida(self, tmp_path):
        g = self._generador(tmp_path, tema="posgrado")
        g.rid_sugerida[2] = "ridClon"
        carpeta = tmp_path / "ridClon"
        carpeta.mkdir()
        (carpeta / "actividad-obligatoria-m2.html").write_text(
            _PLANTILLA_ASSIGNMENT, encoding="utf-8")
        g._escribir_assignment("ridClon", "<p>La consigna.</p>", "ctx")
        salida = (carpeta / "actividad-obligatoria-m2.html").read_text(
            encoding="utf-8")
        assert 'alt="Actividad M2"' in salida

    def test_la_obligatoria_de_verdad_no_se_confunde(self, tmp_path):
        g = self._generador(tmp_path)
        carpeta = tmp_path / "ridObl"
        carpeta.mkdir()
        (carpeta / "actividad-obligatoria-m1.html").write_text(
            _PLANTILLA_ASSIGNMENT, encoding="utf-8")
        g._escribir_assignment("ridObl", "<p>La consigna.</p>", "ctx")
        salida = (carpeta / "actividad-obligatoria-m1.html").read_text(
            encoding="utf-8")
        assert 'alt="Actividad obligatoria M1"' in salida
