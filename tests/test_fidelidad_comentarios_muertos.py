# -*- coding: utf-8 -*-
"""Comentarios que no son pedidos de maquetación.

Los DOCX llegan con globos del proceso editorial que ya no corresponden al
pasar a maquetación. Dos grupos grandes repiten algo que YA está escrito en el
cuerpo —el pie de fuente de la figura y el texto alternativo—, que el
generador toma del párrafo, no del globo. Y "Para diseño: …" es un encargo
para el diseñador.

Sobre el curso de prueba esto baja el cajón de "revisar" de 12 a 1.

Ver docs/auditoria-fidelidad-gestion-calidad-2026-09-10.md
"""

import pytest

from maquetador.ingest.docx_comments import _clasificar


class TestComentariosMuertos:
    @pytest.mark.parametrize("texto", [
        "Para maquetación: Nota. Figura elaborada con base en Out of the crisis, "
        "por W. E. Deming, 2000, Penguin.",
        "Nota. Figura elaborada con base en Sistemas de gestión de la calidad.",
        "Para maquetación: Texto alternativo: Diagrama de Ishikawa.",
        "Texto alternativo: Gráfico de barras sobre la frecuencia de reclamos.",
    ])
    def test_los_que_duplican_el_cuerpo_no_son_pedidos(self, texto):
        assert _clasificar(texto) is None

    def test_el_encargo_de_diseno_no_es_de_maquetacion(self):
        assert _clasificar(
            "Para diseño: M1 RI1 --> Genially Pantalla principal con 7 botones") is None


class TestNoSeLlevaPuestoLoQueSiImporta:
    def test_una_instruccion_real_sigue_avisandose(self):
        assert _clasificar("Para maquetación: foro directamente en siguiente pág") \
            == "revisar"

    @pytest.mark.parametrize("texto,esperado", [
        ("Para maquetación: subtítulo", "subtitulo"),
        ("Para maquetación: sub-subtítulo", "subsubtitulo"),
        ("Para maquetación: acordeón", "acordeon"),
        ("Para maquetación: TABS vertical", "tabs_vertical"),
        ("Para maquetación: flipcards", "flip_card"),
        ("Para maquetación: tooltip --> Sistema de Gestión", "tooltip"),
    ])
    def test_los_pedidos_de_verdad_no_se_filtran(self, texto, esperado):
        assert _clasificar(texto) == esperado

    def test_no_confunde_una_nota_al_pie_con_notar_algo(self):
        """'notar' no es 'Nota.' — el filtro pide el punto o los dos puntos."""
        assert _clasificar("Para maquetación: notar que va en recuadro") \
            == "recuadro_simple"
