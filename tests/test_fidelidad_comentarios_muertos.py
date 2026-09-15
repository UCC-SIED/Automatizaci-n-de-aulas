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
        """El foro 'directamente en siguiente pág' ya no cae en el cajón
        genérico de revisar a mano: se reconoce como su propio pedido
        (sacar el contenido de esta página, ver TestOtraPagina) y de
        cualquier forma sigue sin perderse como si fuera ruido editorial."""
        assert _clasificar("Para maquetación: foro directamente en siguiente pág") \
            == "otra_pagina"
        assert _clasificar("Para maquetación: revisar este párrafo") == "revisar"

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


class TestOtraPagina:
    """El asesor deja el texto de un componente (el foro) en el DOCX de este
    módulo pero aclara que va en OTRA página: no hay que maquetarlo acá.
    Caso real: 'foro directamente en siguiente pág', anclado sobre una tabla
    de 1 columna cuya primera celda dice apenas 'Foro' — el resto de la
    tabla es la consigna completa del foro."""

    def test_se_reconoce_la_instruccion(self):
        from maquetador.ingest.docx_comments import _clasificar
        assert _clasificar("Para maquetación: foro directamente en "
                            "siguiente pág") == "otra_pagina"
        assert _clasificar("Para maquetación: va en la próxima página") \
            == "otra_pagina"

    def test_se_saca_la_tabla_entera_no_solo_la_celda_del_titulo(self):
        from bs4 import BeautifulSoup
        from maquetador.ingest.docx_comments import aplicar_comentarios
        soup = BeautifulSoup(
            "<div><p>Texto de la página.</p>"
            "<table><tr><th><p><strong>Foro</strong></p></th></tr>"
            "<tr><th><p>Reflexioná sobre el rol de la calidad en tu "
            "ámbito.</p></th></tr></table>"
            "<p>Sigue el resto de la página.</p></div>", "html.parser")
        coment = [{"instruccion": "Para maquetación: foro directamente en "
                                  "siguiente pág",
                   "anclado": "Foro", "accion": "otra_pagina", "autor": ""}]
        aplicar_comentarios(soup, coment)
        out = str(soup)
        assert "<table>" not in out
        assert "Reflexioná sobre el rol" not in out
        assert "Sigue el resto de la página" in out
        assert coment[0].get("_aplicado") is True
