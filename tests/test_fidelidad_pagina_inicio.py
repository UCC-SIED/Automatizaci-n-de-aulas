# -*- coding: utf-8 -*-
"""Página de inicio: la ficha del docente y el video de bienvenida.

Regresión real (Selección y Optimización de Inversiones): la titulación del
docente no venía en un DOCX sino escrita en la columna LINK de la planilla,
renglón por renglón. El generador solo miraba el DOCX, así que el campo salía
vacío con el aviso "completar a mano" aunque el dato estuviera a la vista.
"""

from maquetador.build.imscc_builder import _titulacion_de_planilla


class _Item:
    def __init__(self, referencia):
        self.detalle = {"referencia": referencia}


TITULACION = """Sergio Luis Olivo, Ph.D.
Contador Público. Doctor en Finanzas.
Futures & Options Risk Management Program, Chicago Board of Trade.
Docente en cursos de grado y posgrado en el país y en el exterior."""


class TestTitulacionEscritaEnLaPlanilla:
    def test_un_renglon_por_linea(self):
        assert _titulacion_de_planilla(_Item(TITULACION)) == [
            "Sergio Luis Olivo, Ph.D.",
            "Contador Público. Doctor en Finanzas.",
            "Futures & Options Risk Management Program, Chicago Board of Trade.",
            "Docente en cursos de grado y posgrado en el país y en el exterior."]

    def test_un_enlace_no_es_una_biografia(self):
        # La misma columna trae enlaces (la foto vive en Drive, el video en
        # Studio): publicarlos dejaría una URL suelta en la ficha del docente.
        assert _titulacion_de_planilla(_Item(
            "https://drive.google.com/file/d/1AUg6hNhcnhrjOf5wfw6kIE1/view")) == []
        assert _titulacion_de_planilla(_Item(
            "https://uccor.instructuremedia.com/collections/user/"
            "perspectives/u2Ebsi80p4GHX6Z6RT79pQ/caption/edit/1064")) == []

    def test_una_nota_corta_no_alcanza(self):
        assert _titulacion_de_planilla(_Item("Falta")) == []
        assert _titulacion_de_planilla(_Item("")) == []
