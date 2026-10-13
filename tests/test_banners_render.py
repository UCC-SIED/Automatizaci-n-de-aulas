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

    def test_la_plantilla_no_trae_texto_pegado(self):
        """El fantasma del texto original del diseño tiene que haberse ido:
        la plantilla sola y el banner con texto solo pueden diferir dentro
        de la caja de texto."""
        from PIL import ImageChops
        vacio = banners.render("", tema="posgrado").convert("RGB")
        con = banners.banner_de_pagina("Una prueba").convert("RGB")
        caja = ImageChops.difference(vacio, con).getbbox()
        x0 = banners.CAJA_X * banners.ESCALA
        x1 = (banners.CAJA_X + banners.CAJA_ANCHO) * banners.ESCALA
        assert caja is not None
        assert caja[0] >= x0 - 2 and caja[2] <= x1 + 2

    def test_un_tema_sin_plantilla_avisa(self):
        with pytest.raises(FileNotFoundError):
            banners.render("Hola", tema="no-existe")


class TestBannerDeCadaActividad:
    """El nombre del archivo del aula base dice qué actividad es."""

    @pytest.mark.parametrize("archivo,clave,texto", [
        ("actividad-obligatoria-m2", "actividad-obligatoria-m2",
         "Actividad obligatoria del módulo 2"),
        ("actividad-sugerida-m3", "actividad-sugerida-m3",
         "Actividad sugerida del módulo 3"),
        ("actividad-final-integradora", "actividad-final-integradora",
         "Actividad final integradora"),
    ])
    def test_cada_una_con_su_texto(self, archivo, clave, texto):
        assert _banner_de_actividad(archivo) == (clave, texto)

    def test_otro_archivo_no_lleva_banner_propio(self):
        assert _banner_de_actividad("pagina-de-inicio") == ("", "")
