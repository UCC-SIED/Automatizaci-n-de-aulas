# -*- coding: utf-8 -*-
"""Los foros duplicados que las aulas base traen sueltos.

Las dos aulas base traen los foros DUPLICADOS: "Foro sugerido M1" aparece
dos veces, "Foro obligatorio M2" otras dos, y solo una copia de cada uno
está puesta en un módulo. Las demás viajan igual en el manifiesto, así que
Canvas las importa y quedan sueltas en "Foros de discusión" — quince por
curso, que después alguien borra a mano. Es lo que anotó la revisión de
Metodología II como "actualizar aula base, con respecto a los foros que
traen".
"""

from pathlib import Path

import pytest

from maquetador.build.imscc_builder import GeneradorAula
from maquetador.models import CourseSpec


def _generador(tmp_path):
    spec = CourseSpec(nombre="Materia")
    spec.tema = "educacion"
    g = GeneradorAula(spec, {}, tmp_path)
    g.working = tmp_path
    return g


MANIFEST = """<manifest>
  <resources>
    <resource identifier="topicA" type="imsdt_xmlv1p1">
      <file href="topicA.xml"/>
      <dependency identifierref="metaA"/>
    </resource>
    <resource identifier="metaA" type="associatedcontent/imscc_xmlv1p1/learning-application-resource" href="metaA.xml">
      <file href="metaA.xml"/>
    </resource>
    <resource identifier="topicB" type="imsdt_xmlv1p1">
      <file href="topicB.xml"/>
      <dependency identifierref="metaB"/>
    </resource>
    <resource identifier="metaB" type="associatedcontent/imscc_xmlv1p1/learning-application-resource" href="metaB.xml">
      <file href="metaB.xml"/>
    </resource>
  </resources>
</manifest>"""

# topicA está puesto en un módulo; topicB no.
META = """<modules>
  <module>
    <items>
      <item identifier="i1">
        <content_type>DiscussionTopic</content_type>
        <workflow_state>active</workflow_state>
        <title>Foro de apertura</title>
        <identifierref>topicA</identifierref>
      </item>
    </items>
  </module>
</modules>"""


@pytest.fixture
def generador(tmp_path):
    g = _generador(tmp_path)
    g.manifest = MANIFEST
    g.meta = META
    for nombre in ("topicA.xml", "metaA.xml", "topicB.xml", "metaB.xml"):
        (tmp_path / nombre).write_text("<x/>", encoding="utf-8")
    return g


class TestSeVanLosQueNoEstanEnNingunModulo:
    def test_el_foro_suelto_se_elimina(self, generador):
        generador._eliminar_foros_sueltos()
        assert 'identifier="topicB"' not in generador.manifest

    def test_el_foro_puesto_en_un_modulo_se_queda(self, generador):
        generador._eliminar_foros_sueltos()
        assert 'identifier="topicA"' in generador.manifest

    def test_se_borra_tambien_su_archivo(self, generador, tmp_path):
        generador._eliminar_foros_sueltos()
        assert not (tmp_path / "topicB.xml").exists()
        assert (tmp_path / "topicA.xml").exists()

    def test_se_va_con_su_topicmeta(self, generador, tmp_path):
        """La dependencia quedaba en el manifiesto apuntando a un recurso
        que ya no existía: cinco por curso."""
        generador._eliminar_foros_sueltos()
        assert 'identifier="metaB"' not in generador.manifest
        assert not (tmp_path / "metaB.xml").exists()
        # La del foro que se queda, intacta.
        assert 'identifier="metaA"' in generador.manifest

    def test_no_toca_un_foro_que_acabamos_de_escribir(self, generador):
        """Un foro cargado por nosotros puede todavía no estar en el meta
        (el de consultas de la AFI se engancha al final): no se borra."""
        generador.topics_escritos.add("topicB")
        generador._eliminar_foros_sueltos()
        assert 'identifier="topicB"' in generador.manifest


class TestLaDependenciaCompartidaNoSeBorra:
    def test_si_otro_recurso_la_usa_se_queda(self, tmp_path):
        g = _generador(tmp_path)
        g.meta = ""
        g.manifest = (
            '<manifest><resources>'
            '<resource identifier="t1" type="imsdt_xmlv1p1">'
            '<file href="t1.xml"/><dependency identifierref="comun"/></resource>'
            '<resource identifier="t2" type="imsdt_xmlv1p1">'
            '<file href="t2.xml"/><dependency identifierref="comun"/></resource>'
            '<resource identifier="comun" href="comun.xml">'
            '<file href="comun.xml"/></resource>'
            '</resources></manifest>')
        for nombre in ("t1.xml", "t2.xml", "comun.xml"):
            (tmp_path / nombre).write_text("<x/>", encoding="utf-8")
        g._eliminar_recurso("t1")
        assert 'identifier="comun"' in g.manifest
        assert (tmp_path / "comun.xml").exists()


class TestTambienLosCuestionariosSueltos:
    """El aula base arrastra un "Test - Canva - Encuesta" que quedó del
    armado y viaja en cada curso. La encuesta de valoración final, que sí
    está puesta en un módulo, no se toca."""

    MANIFEST = (
        '<manifest><resources>'
        '<resource identifier="quizOk" '
        'type="imsqti_xmlv1p2/imscc_xmlv1p1/assessment">'
        '<file href="quizOk/assessment_qti.xml"/></resource>'
        '<resource identifier="quizTest" '
        'type="imsqti_xmlv1p2/imscc_xmlv1p1/assessment">'
        '<file href="quizTest/assessment_qti.xml"/></resource>'
        '</resources></manifest>')

    META = ('<modules><module><items><item identifier="i1">'
            '<content_type>Quizzes::Quiz</content_type>'
            '<workflow_state>active</workflow_state>'
            '<title>Encuesta de valoración final</title>'
            '<identifierref>quizOk</identifierref>'
            '</item></items></module></modules>')

    @pytest.fixture
    def generador(self, tmp_path):
        g = _generador(tmp_path)
        g.manifest = self.MANIFEST
        g.meta = self.META
        for rid in ("quizOk", "quizTest"):
            (tmp_path / rid).mkdir()
            (tmp_path / rid / "assessment_qti.xml").write_text("<x/>",
                                                               encoding="utf-8")
        return g

    def test_el_test_que_nadie_puso_se_va(self, generador, tmp_path):
        generador._eliminar_foros_sueltos()
        assert 'identifier="quizTest"' not in generador.manifest
        assert not (tmp_path / "quizTest").exists()

    def test_la_encuesta_real_se_queda(self, generador, tmp_path):
        generador._eliminar_foros_sueltos()
        assert 'identifier="quizOk"' in generador.manifest
        assert (tmp_path / "quizOk" / "assessment_qti.xml").exists()


class TestLoQueNoHayQueTocar:
    """Las herramientas externas y los archivos viven fuera de los módulos
    a propósito: borrarlos rompería el aula."""

    @pytest.mark.parametrize("tipo", [
        "imsbasiclti_xmlv1p3",                 # herramientas LTI
        "webcontent",                          # imágenes, banners, páginas
    ])
    def test_no_se_borran_aunque_esten_sueltos(self, tmp_path, tipo):
        g = _generador(tmp_path)
        g.meta = ""
        g.manifest = (f'<manifest><resources><resource identifier="r1" '
                      f'type="{tipo}"><file href="r1.xml"/>'
                      f'</resource></resources></manifest>')
        (tmp_path / "r1.xml").write_text("<x/>", encoding="utf-8")
        g._eliminar_foros_sueltos()
        assert 'identifier="r1"' in g.manifest
