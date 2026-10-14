# -*- coding: utf-8 -*-
"""La ficha "Equipo docente" de la página de inicio.

Los dos temas traen la MISMA ficha pero rellenada distinto: el aula base de
posgrado deja escrito qué va en cada renglón ("Nombre y Apellido del docente
contenidista") y la de educación los vació dejando un punto. El maquetador
buscaba por ese texto, así que en educación la ficha salía con la foto
genérica, sin nombre y sin biografía —y el bloque de tutores con el monigote
gris y unos puntos suspensivos—. Ahora se completa por la estructura, que
las dos comparten.
"""

import pytest
from bs4 import BeautifulSoup

from maquetador.build.imscc_builder import (_es_hueco_de_ficha,
                                            _seccion_de_ficha,
                                            _escribir_en_hueco,
                                            nombre_de_asignatura)


# Marcado real de los dos archivos Aula base-*.imscc, recortado.
FICHA_EDUCACION = """
<h3 class=""><span>Profesor autor</span></h3>
<div class="" style="display: flex; align-items: center; min-height: 100%;">
  <div style="width: 150px; flex-shrink: 0;">
    <p><img id="28409" role="presentation" src="base.png" alt="" width="150" height="150" /></p>
  </div>
  <div style="padding-left: 8px;">
    <div style="display: flex;">
      <p style="flex-shrink: 0;"><strong><img role="presentation" src="i.png" alt="" width="26" height="26" /></strong></p>
      <p class="text-break" style="padding-left: 8px;"><strong>.</strong></p>
    </div>
    <div style="display: flex;">
      <p style="flex-shrink: 0;"><img role="presentation" src="i.png" alt="" width="26" height="26" /></p>
      <p>&nbsp; .</p>
    </div>
  </div>
</div>
<h3>Tutores</h3>
<div style="padding-top: 4px;">
  <p style="background-color: #d3d3d3;"><strong>Secci&oacute;n 1</strong></p>
  <div style="display: flex; align-items: flex-start; gap: 12px; padding: 8px;">
    <div style="flex-shrink: 0;">
      <img id="28412" style="width: 100px; height: auto;" role="presentation" src="base.png" alt="" width="100" height="96" />
    </div>
    <div>
      <p style="margin: 0;"><img role="presentation" src="i.png" alt="" width="26" height="26" /><strong> ...</strong></p>
      <p style="flex-shrink: 0;"><img role="presentation" src="i.png" alt="" width="26" height="26" />...</p>
    </div>
  </div>
</div>
"""

FICHA_POSGRADO = """
<h3 class=""><span>Profesor autor</span></h3>
<div class="" style="display: flex; align-items: center; min-height: 100%;">
  <div style="width: 150px; flex-shrink: 0;">
    <p><img class="" src="base.png" alt="Avatar docente" /></p>
  </div>
  <div style="padding-left: 8px;">
    <div style="display: flex;">
      <p style="flex-shrink: 0;"><img role="presentation" src="i.png" alt="" width="26" height="26" /></p>
      <p class="text-break" style="padding-left: 8px;"><strong>Nombre y Apellido del docente contenidista</strong></p>
    </div>
    <div style="display: flex;">
      <p style="flex-shrink: 0;"><img role="presentation" src="i.png" alt="" width="26" height="26" /></p>
      <p class="text-break" style="padding-left: 8px;"><strong>Titulaci&oacute;n relevante.</strong></p>
    </div>
  </div>
</div>
<p>&nbsp;</p>
<h3 class="">Tutores</h3>
<div class="" style="padding-top: 4px;">
  <p style="background-color: #d3d3d3;"><strong>Secci&oacute;n 1</strong></p>
  <div style="display: flex; align-items: flex-start; gap: 12px; padding: 8px;">
    <div style="flex-shrink: 0;">
      <img src="base.png" alt="Avatar tutor" width="100" height="97" />
    </div>
    <div>
      <p style="margin: 0;">&nbsp;</p>
      <p class="dp-heading-ignore" style="margin: 0;"><strong><span style="font-size: 12pt;"><img role="presentation" src="i.png" alt="" width="26" height="26" /> Nombre y Apellido del docente tutor</span></strong></p>
    </div>
  </div>
</div>
"""


class TestQueRenglonEsUnHueco:
    """El punto delicado: distinguir el renglón que hay que completar del
    <p> que solo sostiene el iconito de 26px, y del <p> espaciador."""

    @pytest.mark.parametrize("html", [
        '<p class="text-break"><strong>.</strong></p>',            # educación
        '<p>&nbsp; .</p>',                                          # educación
        '<p><img width="26" /><strong> ...</strong></p>',           # educación tutor
        '<p><img width="26" />...</p>',                             # educación tutor
        '<p><strong>Nombre y Apellido del docente contenidista</strong></p>',
        '<p><strong>Titulaci&oacute;n relevante.</strong></p>',
        '<p><strong><span><img width="26" /> Nombre y Apellido del docente tutor</span></strong></p>',
    ])
    def test_los_renglones_a_completar(self, html):
        assert _es_hueco_de_ficha(BeautifulSoup(html, "html.parser").p) is True

    @pytest.mark.parametrize("html", [
        '<p style="flex-shrink: 0;"><img width="26" /></p>',   # solo el icono
        '<p><strong><img width="26" /></strong></p>',          # idem, en negrita
        '<p style="margin: 0;">&nbsp;</p>',                    # espaciador
        '<p><strong>Secci&oacute;n 1</strong></p>',            # rótulo real
        '<p><strong>Adriana Di Francesco</strong></p>',        # ya completado
    ])
    def test_lo_que_no_hay_que_tocar(self, html):
        assert _es_hueco_de_ficha(BeautifulSoup(html, "html.parser").p) is False


class TestLaFichaSeUbicaEnLosDosTemas:
    @pytest.mark.parametrize("ficha,huecos_autor,huecos_tutor",
                             [(FICHA_EDUCACION, 2, 2), (FICHA_POSGRADO, 2, 1)])
    def test_encuentra_foto_y_renglones(self, ficha, huecos_autor, huecos_tutor):
        soup = BeautifulSoup(ficha, "html.parser")
        _s, foto, huecos = _seccion_de_ficha(soup, "Profesor autor")
        assert foto is not None and foto.get("width") != "26"
        assert len(huecos) == huecos_autor
        _s, foto_t, huecos_t = _seccion_de_ficha(soup, "Tutores")
        assert foto_t is not None and foto_t.get("width") != "26"
        assert len(huecos_t) == huecos_tutor

    def test_una_seccion_que_no_existe_no_rompe(self):
        soup = BeautifulSoup("<p>nada</p>", "html.parser")
        assert _seccion_de_ficha(soup, "Profesor autor") == (None, None, [])


class TestEscribirEnElRenglon:
    def test_conserva_el_iconito(self):
        """En educación el icono vive dentro del MISMO <p> que el texto:
        reemplazar el párrafo entero lo habría borrado."""
        p = BeautifulSoup(
            '<p><img width="26" src="i.png" /><strong> ...</strong></p>',
            "html.parser").p
        _escribir_en_hueco(p, "Adriana Di Francesco")
        assert p.find("img") is not None
        assert p.get_text(strip=True) == "Adriana Di Francesco"

    def test_no_duplica_la_negrita(self):
        p = BeautifulSoup("<p><strong>.</strong></p>", "html.parser").p
        _escribir_en_hueco(p, "Adriana Di Francesco")
        assert len(p.find_all("strong")) == 1

    def test_escapa_lo_que_escribe(self):
        p = BeautifulSoup("<p>.</p>", "html.parser").p
        _escribir_en_hueco(p, "Gestión & Educación")
        assert "&amp;" in str(p)
        assert p.get_text(strip=True) == "Gestión & Educación"


class TestElNombreDeLaAsignatura:
    """La planilla de esta materia nombra la asignatura con la carrera
    pegada, y el banner de portada salía con todo eso adentro."""

    def test_saca_la_carrera_entre_parentesis(self):
        assert nombre_de_asignatura(
            "Metodología de la investigación II "
            "(Lic. en Gestión de la Educación Especial)"
        ) == "Metodología de la investigación II"

    @pytest.mark.parametrize("sufijo", [
        "(Licenciatura en Gestión Educativa)",
        "(Mgter. en Dirección de Empresas)",
        "(Especialización en Docencia Universitaria)",
        "(Doctorado en Ciencias de la Educación)",
    ])
    def test_las_otras_formas_de_nombrar_la_carrera(self, sufijo):
        assert nombre_de_asignatura("Materia X " + sufijo) == "Materia X"

    @pytest.mark.parametrize("nombre", [
        "Neurociencia aplicada a las organizaciones I",
        "Gestión de la Calidad",
        "Economía de la Energía (II)",          # el paréntesis es del nombre
        "Taller (avanzado)",
    ])
    def test_no_toca_lo_que_no_es_una_carrera(self, nombre):
        assert nombre_de_asignatura(nombre) == nombre

    def test_vacio_no_rompe(self):
        assert nombre_de_asignatura("") == ""
        assert nombre_de_asignatura(None) == ""


class TestElGeneroDelRotulo:
    """Los DOS temas traen "Profesor autor" en el aula base. El ajuste
    existente solo sabía pasar de femenino a masculino, así que nunca
    corría: Adriana Di Francesco salía como "Profesor autor"."""

    def test_la_ficha_se_encuentra_igual_en_femenino(self):
        """El género se ajusta ANTES de completar la ficha, así que para
        entonces el rótulo puede decir "Profesora autora"."""
        soup = BeautifulSoup(
            FICHA_EDUCACION.replace("Profesor autor", "Profesora autora"),
            "html.parser")
        _s, foto, huecos = _seccion_de_ficha(soup, "Profesor autor")
        assert foto is not None
        assert len(huecos) == 2

    def test_una_biografia_femenina_se_detecta(self):
        from maquetador.build.imscc_builder import _genero_texto
        assert _genero_texto(
            "Dra. en Educación; Licenciada en Ciencias de la Educación. "
            "Profesora de Historia. Directora de Equipo de investigación."
        ) == "f"

    def test_una_masculina_tambien(self):
        from maquetador.build.imscc_builder import _genero_texto
        assert _genero_texto(
            "Doctor en Economía; Licenciado en Administración. "
            "Profesor titular e investigador.") == "m"
