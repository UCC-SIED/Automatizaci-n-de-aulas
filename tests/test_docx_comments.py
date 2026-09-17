# -*- coding: utf-8 -*-
from maquetador.ingest.docx_comments import _clasificar


class TestClasificarComponentes:
    def test_tabs(self):
        assert _clasificar("Maquetación: tabs al costado") == "tabs"
        assert _clasificar("hacer pestañas con esto") == "tabs"

    def test_expander(self):
        assert _clasificar("Maquetación: expander") == "expander"
        assert _clasificar("esto es un expandible") == "expander"

    def test_tooltip(self):
        assert _clasificar("que al hacer clic aparezca: Gestión por objetivos") == "tooltip"
        assert _clasificar("Maquetación: tooltip --> User Stories") == "tooltip"

    def test_cita(self):
        assert _clasificar("Maquetación: esto es una cita") == "cita"
        assert _clasificar("es una cita") == "cita"

    def test_acordeon_flip_siguen(self):
        assert _clasificar("Maquetación: acordeón") == "acordeon"
        assert _clasificar("tarjetas que se dan vuelta") == "flip_card"

    def test_regresion_tooltip_aparezca_clic(self):
        """Regresión: 'aparezca' sin clic debe auto-aplicar (no ser tooltip)."""
        # "que aparezca como recuadro" → recuadro_simple (no tooltip)
        assert _clasificar("que aparezca como recuadro") == "recuadro_simple"
        # "que aparezca el video de la clase" → video (no tooltip)
        assert _clasificar("que aparezca el video de la clase") == "video"
        # "al hacer clic que aparezca la definicion" → tooltip (CON clic)
        assert _clasificar("al hacer clic que aparezca la definicion") == "tooltip"

class TestNoMaquetar:
    """"NO MAQUETAR" excluye el tramo anclado. Es distinto de "quitar" (que
    no se automatiza porque suele ser un micro-pedido): acá el asesor saca
    una sección entera. Antes devolvía None y el comentario se descartaba en
    silencio — en un caso real, las "Indicaciones para el tutor" de una AFI
    (cómo corregir, qué priorizar) quedaban publicadas en el aula."""

    def test_se_reconoce(self):
        assert _clasificar("NO MAQUETAR") == "no_maquetar"
        assert _clasificar("no maquetar esta sección") == "no_maquetar"
        assert _clasificar("Esto no se maqueta") is None   # no arranca con "no maquetar"

    def test_no_se_confunde_con_un_pedido_comun(self):
        assert _clasificar("Para maquetación, subtítulo.") == "subtitulo"


class TestUbicacionDelForo:
    """El recuadro del foro que el docente escribió dentro de la lectura
    puede quedar en la página, irse al espacio del foro (el DiscussionTopic)
    o ir a los dos lados. El asesor lo dice en prosa y el ancla es el rótulo
    del recuadro ("Foro del módulo 1")."""

    def test_solo_en_la_lectura(self):
        assert _clasificar("Para maquetación, para dejar en la lectura.",
                           "Foro del módulo 1") == "foro_en_lectura"

    def test_solo_en_el_espacio_del_foro(self):
        assert _clasificar("Para maquetación, para el espacio del foro.",
                           "Foro del módulo 1") == "otra_pagina"
        assert _clasificar("Para maquetación, esto es para el espacio del foro.",
                           "Foro del módulo 2") == "otra_pagina"

    def test_en_los_dos_lados(self):
        assert _clasificar("Para maquetación, es el mismo contenido para la "
                           "lectura y para el espacio del foro.",
                           "Foro del módulo 3") == "foro_lectura_y_espacio"

    def test_una_lectura_sin_foro_sigue_siendo_cta(self):
        """Sin foro de por medio, "lectura" sigue armando el CTA de siempre."""
        assert _clasificar("Para maquetación: recuadro de lectura",
                           "Te invito a leer el capítulo 3.") == "recuadro_simple"
        assert _clasificar("Maquetación: lectura sugerida",
                           "Te invito a leer el capítulo 3.") == "lectura"


class TestFiguraAmpliable:
    """"Incluir pop up para ampliar" sobre una figura pide la imagen con
    lupa (dp-popup-image), no el componente expander."""

    def test_pop_up_para_ampliar(self):
        assert _clasificar("Para maquetación, incluir pop up para ampliar.") \
            == "figura_expandible"

    def test_no_se_lleva_el_expander(self):
        assert _clasificar("Para maquetación: expander") == "expander"


class TestClasificarComponentesExtra:
    def test_dead_code_acordeon_simple_eliminado(self):
        """Dead code: 'acordeon-simple' era inalcanzable (acordeon lo captura)."""
        # 'acordeon-simple' debe ser capturado por la rama 'acordeon', no 'expander'
        assert _clasificar("acordeon-simple") == "acordeon"
        assert _clasificar("expander") == "expander"
