# -*- coding: utf-8 -*-
"""Componentes colapsables pedidos por comentario del asesor.

Casos salidos de la auditoría del 2026-09-10: en el curso de prueba la
automatización generó UN solo panel en 13 páginas, aunque la asesora había
pedido tabs, expander y acordeón en varias.

Ver docs/auditoria-fidelidad-gestion-calidad-2026-09-10.md
"""

import re

import pytest

from bs4 import BeautifulSoup

from maquetador.ingest.docx_comments import _clasificar, _VARIANTE_PANEL, \
    aplicar_comentarios
from maquetador.build.componentes_asesor import (construir_panels,
                                                 pares_de_secciones,
                                                 extraer_pares)
from maquetador.build.snippets import maquetar_actividad


class TestVariantesDePanel:
    """Cada tipo de panel tiene SU clase de DesignPLUS."""

    def test_acordeon_y_expander_no_son_la_misma_variante(self):
        assert _VARIANTE_PANEL["acordeon"] == "dp-accordion-default"
        assert _VARIANTE_PANEL["expander"] == "dp-expander-default"

    def test_tabs_usa_la_clase_que_existe(self):
        assert _VARIANTE_PANEL["tabs"] == "dp-tabs-buttons"
        assert _VARIANTE_PANEL["tabs_vertical"] == "dp-tabs-buttons-vertical"

    def test_clasifica_la_orientacion_de_las_tabs(self):
        assert _clasificar("Para maquetación: TABS vertical") == "tabs_vertical"
        assert _clasificar("Para maquetación: tabs") == "tabs"
        assert _clasificar("Maquetación: solapas horizontales") == "tabs"

    def test_colores_de_panel_del_catalogo_ucc(self):
        html = construir_panels([("A", "<p>a</p>"), ("B", "<p>b</p>")],
                                "dp-accordion-default")
        assert "dp-panel-color-dp-primary" in html
        assert "dp-panel-active-color-dp-secondary" in html
        assert "dp-panel-hover-color-dp-secondary" in html


class TestPanelDesdeSubtitulos:
    """'expander (títulos subrayados)': el asesor no arma tabla, subraya los
    subtítulos y escribe el contenido corrido."""

    HTML = ("<div>"
            "<p>Antes de aplicar cualquier herramienta conviene reconocer algo.</p>"
            "<p>Por ejemplo, si un proyecto presenta retrasos en la entrega.</p>"
            "<p><u>El diagrama de Ishikawa: explorar posibles causas</u></p>"
            "<p>Una de las herramientas más utilizadas para analizar problemas.</p>"
            "<p>Su principal objetivo es identificar y organizar las causas.</p>"
            "<p><u>La técnica de los 5 porqués: buscar la causa raíz</u></p>"
            "<p>Mientras que Ishikawa ayuda a explorar diversas posibilidades.</p>"
            "<p><u>El diagrama de Pareto: priorizar esfuerzos</u></p>"
            "<p>Una vez identificados distintos problemas o causas posibles.</p>"
            "</div>")

    def _aplicar(self):
        soup = BeautifulSoup(self.HTML, "html.parser")
        coment = [{"instruccion": "Para maquetación: expander (títulos subrayados)",
                   "anclado": "Antes de aplicar cualquier herramienta conviene",
                   "accion": "expander", "autor": ""}]
        aplicar_comentarios(soup, coment)
        return str(soup), coment[0]

    def test_arma_un_panel_por_subtitulo_subrayado(self):
        out, coment = self._aplicar()
        assert coment.get("_aplicado") is True
        assert out.count('class="dp-panel-group"') == 3

    def test_los_titulos_son_los_subtitulos_completos(self):
        out, _ = self._aplicar()
        titulos = re.findall(r'dp-panel-heading">([^<]+)', out)
        assert titulos == ["El diagrama de Ishikawa: explorar posibles causas",
                           "La técnica de los 5 porqués: buscar la causa raíz",
                           "El diagrama de Pareto: priorizar esfuerzos"]

    def test_cada_panel_se_lleva_sus_parrafos(self):
        out, _ = self._aplicar()
        cuerpos = re.findall(r'dp-panel-content">(.*?)</div>', out, re.S)
        assert cuerpos[0].count("<p>") == 2
        assert cuerpos[1].count("<p>") == 1

    def test_la_introduccion_queda_fuera_del_panel(self):
        """Lo anterior al primer subtítulo no es parte de ningún panel."""
        out, _ = self._aplicar()
        antes = out.split('<div class="dp-panels-wrapper')[0]
        assert "Antes de aplicar cualquier herramienta" in antes
        assert "Por ejemplo, si un proyecto presenta retrasos" in antes

    def test_no_parte_el_subtitulo_por_los_dos_puntos(self):
        """El extractor 'Nombre: contenido' cortaba el título en el ':' y
        perdía los párrafos de la sección — por eso salían paneles basura."""
        out, _ = self._aplicar()
        assert "El diagrama de Ishikawa: explorar posibles causas" in out
        assert 'dp-panel-heading">El diagrama de Ishikawa</h3>' not in out


class TestNoRompeLoQueYaAndaba:
    def test_sigue_armando_desde_nombre_contenido(self):
        soup = BeautifulSoup(
            "<div><p>Autoevaluación: la persona valora su desempeño.</p>"
            "<p>Evaluación por objetivos: mide el cumplimiento.</p></div>",
            "html.parser")
        pares, _ = extraer_pares(soup.find("p"), "Maquetación: acordeón")
        assert len(pares) == 2
        assert pares[0][0] == "Autoevaluación"

    def test_sin_subtitulos_no_inventa_secciones(self):
        soup = BeautifulSoup("<div><p>Un párrafo suelto.</p>"
                             "<p>Otro párrafo suelto.</p></div>", "html.parser")
        pares, _ = pares_de_secciones(soup.find("p"))
        assert pares == []

    def test_un_solo_subtitulo_no_alcanza_para_un_panel(self):
        soup = BeautifulSoup("<div><p><u>Único título</u></p>"
                             "<p>Su contenido.</p></div>", "html.parser")
        pares, _ = pares_de_secciones(soup.find("p"))
        assert pares == []


class TestMaquetadoDeActividad:
    """El "Modelo de actividad": título propio y rótulos de sección.

    En la AFI del curso de prueba el título salía como <h3> arrastrando el
    prefijo "Actividad final integradora: ", que repite el nombre que Canvas
    ya muestra en el módulo, y "Objetivo:" quedaba como párrafo.
    """

    CUERPO = ('<h3>Actividad final integradora: Analizá situaciones reales</h3>'
              '<p>Objetivo: </p>'
              '<p>Interpretar la situación planteada e integrar los conceptos.</p>'
              '<p>Consigna: Elaborá un informe técnico.</p>')

    def test_el_titulo_va_en_el_h2_de_titulo(self):
        out = maquetar_actividad(self.CUERPO)
        assert 'class="dp-ignore-theme"' in out
        assert "text-align: center" in out

    @pytest.mark.parametrize("tema,color", [("educacion", "#003087"),
                                            ("posgrado", "#1b1e31")])
    def test_el_color_del_titulo_sale_del_aula_base(self, tema, color):
        """Estaba fijo en el azul de educación: un curso de posgrado salía con
        el título de la actividad del color equivocado."""
        assert f"color: {color}" in maquetar_actividad(self.CUERPO, tema)

    def test_le_saca_el_prefijo_que_duplica_el_nombre_del_item(self):
        out = maquetar_actividad(self.CUERPO)
        assert "<strong>Analizá situaciones reales</strong>" in out
        assert "Actividad final integradora:" not in out

    def test_los_rotulos_de_seccion_son_encabezados(self):
        out = maquetar_actividad(self.CUERPO)
        assert "<h3>Objetivo</h3>" in out
        assert "<h3>Consigna</h3>" in out
        assert "<p>Objetivo: </p>" not in out

    def test_el_cuerpo_pegado_al_rotulo_queda_debajo(self):
        out = maquetar_actividad(self.CUERPO)
        assert "<h3>Consigna</h3><p>Elaborá un informe técnico.</p>" in out

    def test_no_toca_un_parrafo_que_no_es_rotulo(self):
        out = maquetar_actividad("<p>Nutri Pet S.A.: una empresa del rubro.</p>")
        assert "<h3>" not in out


class TestTituloGenericoDeActividad:
    """'Actividad obligatoria 1' a secas (sin nada más en el título, solo el
    tipo + número) no aporta nada: Canvas ya muestra ese mismo nombre en el
    banner de la Assignment. Se saca en vez de duplicarlo como H2."""

    @pytest.mark.parametrize("titulo", [
        "Actividad obligatoria 1", "Actividad obligatoria 2",
        "Actividad final integradora", "Actividad M1",
    ])
    def test_titulo_generico_se_saca_sin_dejar_h2(self, titulo):
        out = maquetar_actividad(f"<h3>{titulo}</h3><p>Objetivo: Diagnosticar.</p>")
        assert "dp-ignore-theme" not in out
        assert titulo not in out

    def test_titulo_con_nombre_propio_sigue_yendo_al_h2(self):
        """Diferencia real con el caso de arriba: acá SÍ queda texto propio
        después de sacar el prefijo del tipo de actividad."""
        out = maquetar_actividad(
            "<h3>Actividad obligatoria: Diagnóstico de un caso real</h3>")
        assert 'class="dp-ignore-theme"' in out
        assert "Diagnóstico de un caso real" in out


class TestNivelDeEncabezadosDelCaso:
    """Los "Título N" nativos de Word que trae el caso planteado (más
    profundos que el H2 de la actividad) bajan a <h4>: si quedaran en <h3>
    competirían de igual a igual con los rótulos de sección (Objetivo,
    Consigna…), que sí son <h3>."""

    def test_encabezado_nativo_del_caso_baja_a_h4(self):
        out = maquetar_actividad(
            "<h2>Proyecto: Caso X</h2><h3>Contexto del proyecto:</h3>"
            "<p>Descripción del contexto.</p>")
        assert "<h4>Contexto del proyecto:</h4>" in out
        assert "<h3>Contexto del proyecto:</h3>" not in out

    def test_rotulo_de_seccion_que_llega_como_encabezado_nativo_sigue_en_h3(self):
        """'Pautas de presentación:' puede llegar ya como <h3> (si en el
        DOCX tenía un estilo de título de Word en vez de párrafo normal):
        tiene que terminar en el mismo nivel que sus hermanos armados desde
        <p> (regresión: bajaba a h4 igual que los encabezados del caso)."""
        out = maquetar_actividad(
            "<h2>Actividad obligatoria: Caso X</h2>"
            "<h3>Pautas de presentación:</h3>")
        assert "<h3>Pautas de presentación:</h3>" in out


class TestRotuloEnLineaYDisclaimerDeIA:
    def test_situacion_de_incertidumbre_se_destaca_sin_ser_encabezado(self):
        out = maquetar_actividad(
            "<p>Situación de incertidumbre: el presupuesto se reduce un "
            "10 % durante la ejecución.</p>")
        assert "<h3>" not in out
        assert "<h4>" not in out
        assert "<u><strong>Situación de incertidumbre:</strong></u>" in out
        assert "el presupuesto se reduce" in out

    def test_disclaimer_de_ia_va_en_recuadro_simple(self):
        out = maquetar_actividad(
            "<p>Se recomienda que el aporte de la IA no exceda el 30 % del "
            "trabajo, que su uso esté correctamente citado.</p>")
        assert "dp-callout" in out
        assert "aporte de la IA" in out


class TestJerarquiaDeSubtitulos:
    """Textos tomados de los comentarios reales del curso de prueba.

    La política de jerarquía de la UCC: H2 título de página, H3 subtítulo,
    H4 sub-subtítulo. "sub-subtítulo" contiene la palabra "subtítulo", así que
    todos caían en H3.
    """

    def test_subtitulo_es_h3(self):
        assert _clasificar("Para maquetación: subtítulo") == "subtitulo"

    @pytest.mark.parametrize("texto", [
        "Para maquetación: sub-subtítulo",
        "Para maquetación: subsubtítulo",
        "Para maquetación: sub subtitulo",
    ])
    def test_sub_subtitulo_es_h4(self, texto):
        assert _clasificar(texto) == "subsubtitulo"

    def test_aplica_el_nivel_correcto(self):
        soup = BeautifulSoup("<div><p>¿Qué es un indicador?</p></div>",
                             "html.parser")
        coment = [{"instruccion": "Para maquetación: sub-subtítulo",
                   "anclado": "¿Qué es un indicador?",
                   "accion": "subsubtitulo", "autor": ""}]
        aplicar_comentarios(soup, coment)
        assert "<h4>¿Qué es un indicador?</h4>" in str(soup)

    def test_el_subtitulo_sigue_siendo_h3(self):
        soup = BeautifulSoup("<div><p>Costos de la calidad</p></div>",
                             "html.parser")
        coment = [{"instruccion": "Para maquetación: subtítulo",
                   "anclado": "Costos de la calidad",
                   "accion": "subtitulo", "autor": ""}]
        aplicar_comentarios(soup, coment)
        assert "<h3>Costos de la calidad</h3>" in str(soup)

    def test_estilo_subtitle_ya_resuelto_no_queda_pendiente_de_revision(self):
        """Un párrafo con estilo Word 'Subtitle' ya llega como <h3> (mammoth,
        vía el style_map de segmenter.py) — _buscar_elemento no lo encuentra
        entre los <p>/<li>. Si el nivel YA es el que pide el comentario, no
        hay nada que hacer: no debe quedar avisado como pendiente."""
        soup = BeautifulSoup(
            "<div><h3>Costos de la calidad</h3></div>", "html.parser")
        coment = [{"instruccion": "Para maquetación: subtítulo",
                   "anclado": "Costos de la calidad",
                   "accion": "subtitulo", "autor": ""}]
        aplicar_comentarios(soup, coment)
        assert coment[0].get("_aplicado") is True
        assert "<h3>Costos de la calidad</h3>" in str(soup)

    def test_estilo_subtitle_en_h3_se_baja_a_h4_si_el_comentario_pide_subsubtitulo(self):
        """El estilo Word 'Subtitle' siempre da <h3>, pero el asesor puede
        pedir sub-subtítulo (h4) para ESE párrafo puntual: hay que corregir
        el nivel, no dejarlo en h3 avisado como 'revisar a mano' sin más
        (regresión real: '¿Qué es un indicador?' y 'Indicadores aplicados a
        proyectos' quedaban en h3 en vez de h4)."""
        soup = BeautifulSoup(
            "<div><h3>¿Qué es un indicador?</h3></div>", "html.parser")
        coment = [{"instruccion": "Para maquetación: sub-subtítulo",
                   "anclado": "¿Qué es un indicador?",
                   "accion": "subsubtitulo", "autor": ""}]
        aplicar_comentarios(soup, coment)
        assert coment[0].get("_aplicado") is True
        assert "<h4>¿Qué es un indicador?</h4>" in str(soup)
        assert "<h3>¿Qué es un indicador?</h3>" not in str(soup)

    def test_una_mencion_de_paso_no_convierte_la_intro_en_titulo(self):
        """Caso real (módulo 2): la introducción del módulo menciona
        'auditorías internas' de pasada; el comentario 'subtítulo' que en
        realidad apunta al subtítulo real (mucho más abajo) no debe resolver
        sobre ese párrafo de introducción y convertirlo entero en <h3>."""
        soup = BeautifulSoup(
            "<div>"
            "<p>Una vez definidos los estándares y mecanismos de calidad, "
            "la gestión del proyecto debe sostenerlos durante toda la "
            "ejecución. Esto implica detectar desvíos, gestionar "
            "evidencias, validar entregables periódicamente e interpretar "
            "la percepción de los interesados a lo largo del tiempo, junto "
            "con las auditorías internas como instrumentos de evaluación "
            "y aprendizaje dentro del proyecto en curso.</p>"
            "<p>Auditorías internas</p>"
            "<p>Permiten evaluar el cumplimiento de los procesos.</p>"
            "</div>", "html.parser")
        coment = [{"instruccion": "Para maquetación: subtítulo",
                   "anclado": "Auditorías internas",
                   "accion": "subtitulo", "autor": ""}]
        aplicar_comentarios(soup, coment)
        out = str(soup)
        assert "<h3>Auditorías internas</h3>" in out
        assert "<h3>La mejora continua" not in out


class TestMarcadorDeCierre:
    """'fin del expander' marca dónde termina, no pide armar otro."""

    @pytest.mark.parametrize("texto", [
        "Para maquetación: fin del expander",
        "Para maquetación: fin de la tabla",
        "fin del acordeón",
    ])
    def test_no_dispara_un_componente(self, texto):
        assert _clasificar(texto) is None

    def test_el_expander_de_verdad_sigue_disparando(self):
        assert _clasificar("Para maquetación: expander") == "expander"


class TestPedidoRepetido:
    """Un mismo pedido anclado en varios lugares es UN componente.

    El asesor marca con el mismo globo cada tramo que va adentro: "TABS
    vertical ISO 14001 ISO 45001" aparece 3 veces en el DOCX del curso de
    prueba y "flipcards" una vez por tarjeta. El generador intentaba armar uno
    por globo.
    """

    HTML = ("<div>"
            "<p><u>ISO 14001</u></p><p>Gestión ambiental de la organización.</p>"
            "<p><u>ISO 45001</u></p><p>Seguridad y salud en el trabajo.</p>"
            "<p><u>ISO 50001</u></p><p>Gestión de la energía.</p>"
            "</div>")
    INSTR = "Para maquetación: TABS vertical ISO 14001 ISO 45001"

    def _aplicar(self):
        soup = BeautifulSoup(self.HTML, "html.parser")
        coments = [{"instruccion": self.INSTR, "anclado": a,
                    "accion": "tabs_vertical", "autor": ""}
                   for a in ("ISO 14001", "Gestión ambiental de la organización.",
                             "Gestión de la energía.")]
        aplicar_comentarios(soup, coments)
        return str(soup), coments

    def test_arma_un_solo_componente(self):
        out, _ = self._aplicar()
        assert out.count("dp-panels-wrapper") == 1

    def test_con_todos_los_paneles(self):
        out, _ = self._aplicar()
        assert out.count('class="dp-panel-group"') == 3

    def test_saldar_todo_el_grupo(self):
        """Los globos repetidos quedan resueltos, no pendientes de aviso."""
        _, coments = self._aplicar()
        assert all(c.get("_aplicado") for c in coments)

    def test_pedidos_distintos_siguen_siendo_componentes_distintos(self):
        """La deduplicación agrupa por pedido: dos pedidos distintos, en dos
        tramos distintos, siguen dando dos componentes."""
        soup = BeautifulSoup(
            "<div>"
            "<p><u>ISO 14001</u></p><p>Gestión ambiental.</p>"
            "<p><u>ISO 45001</u></p><p>Seguridad y salud.</p>"
            "<h2>Otra sección</h2>"
            "<p><u>Planificar</u></p><p>Definir el alcance.</p>"
            "<p><u>Verificar</u></p><p>Medir los resultados.</p>"
            "</div>", "html.parser")
        coments = [
            {"instruccion": "Para maquetación: TABS vertical",
             "anclado": "ISO 14001", "accion": "tabs_vertical", "autor": ""},
            {"instruccion": "Para maquetación: acordeón",
             "anclado": "Planificar", "accion": "acordeon", "autor": ""},
        ]
        aplicar_comentarios(soup, coments)
        out = str(soup)
        assert out.count("dp-panels-wrapper") == 2
        assert "dp-tabs-buttons-vertical" in out
        assert "dp-accordion-default" in out


class TestSubtituloEnvueltoEnLista:
    """Mammoth a veces envuelve un subtítulo corto en negrita en una lista de
    un solo ítem ("<ul><li><strong>ISO 14001</strong></li></ul>") en vez de
    dejarlo como <p>. Caso real: "TABS vertical ISO 14001 ISO 45001" — el
    componente no se armaba porque el título vivía en un <li> invisible para
    la detección de encabezados, y el <p> en negrita que sigue (la bajada del
    título, "Gestión ambiental") se tomaba por error como una sección nueva.
    """

    HTML = (
        "<div>"
        "<p>Existen normas relacionadas:</p>"
        "<ul><li><strong>ISO 14001</strong> </li></ul>"
        "<p><strong>Gestión ambiental</strong></p>"
        "<p>Norma de gestión ambiental.</p>"
        "<p>Implica identificar impactos ambientales.</p>"
        "<ul><li><strong>ISO 45001</strong> </li></ul>"
        "<p><strong>Seguridad y salud ocupacional</strong></p>"
        "<p>Norma de seguridad laboral.</p>"
        "<p>Es relevante para reducir accidentes y proteger a las personas "
        "en el trabajo.</p>"
        "<p>Nota: hay más normas de las mencionadas.</p>"
        "</div>")
    INSTR = "Para maquetación: TABS vertical ISO 14001 ISO 45001"

    def _aplicar(self):
        soup = BeautifulSoup(self.HTML, "html.parser")
        coments = [
            {"instruccion": self.INSTR, "anclado": "ISO 14001",
             "accion": "tabs_vertical", "autor": ""},
            {"instruccion": self.INSTR,
             "anclado": "Norma de seguridad laboral.",
             "accion": "tabs_vertical", "autor": ""},
            {"instruccion": self.INSTR,
             "anclado": "Es relevante para reducir accidentes y proteger a "
                        "las personas en el trabajo.",
             "accion": "tabs_vertical", "autor": ""},
        ]
        aplicar_comentarios(soup, coments)
        return BeautifulSoup(str(soup), "html.parser")

    def test_arma_dos_paneles_iso(self):
        soup = self._aplicar()
        titulos = [h.get_text(strip=True)
                   for h in soup.find_all(class_="dp-panel-heading")]
        assert titulos == ["ISO 14001", "ISO 45001"]

    def test_la_bajada_en_negrita_no_abre_seccion_propia(self):
        """'Gestión ambiental' es parte del contenido del panel ISO 14001,
        no un tercer panel."""
        soup = self._aplicar()
        assert len(soup.find_all(class_="dp-panel-group")) == 2

    def test_no_se_come_lo_que_sigue_al_desplegable(self):
        """El párrafo posterior al cierre del tramo anclado queda afuera del
        componente, como contenido normal de la página."""
        soup = self._aplicar()
        wrapper = soup.find(class_="dp-panels-wrapper")
        assert "Nota: hay más normas" not in str(wrapper)
        assert "Nota: hay más normas" in str(soup)


class TestBusquedaDeElementoEsEspecifica:
    """_buscar_elemento se queda con el candidato más específico: una celda
    de tabla corta ('Planificación') que por casualidad es prefijo del texto
    anclado no debe ganarle al párrafo real ('Planificación de la calidad')
    solo por aparecer antes en el documento."""

    def test_prefiere_el_parrafo_largo_al_rotulo_corto_anterior(self):
        from maquetador.ingest.docx_comments import _buscar_elemento
        soup = BeautifulSoup(
            "<div>"
            "<table><tr><th><p><strong>Planificación</strong></p></th></tr></table>"
            "<p><strong>Planificación de la calidad</strong></p>"
            "<p>Define qué significa calidad para el proyecto.</p>"
            "</div>", "html.parser")
        el = _buscar_elemento(soup, "Planificación de la calidad Define qué "
                                     "significa calidad para el proyecto.")
        assert el.name == "p"
        assert el.get_text(strip=True) == "Planificación de la calidad"

    def test_no_confunde_una_mencion_de_paso_con_el_subtitulo_real(self):
        """Caso real (módulo 2): un párrafo largo de introducción MENCIONA
        'auditorías internas' de paso, mucho antes del subtítulo real que el
        comentario 'Para maquetación: subtítulo' señala. La mención de paso
        no debe ganarle al subtítulo real por aparecer antes en el documento
        (regresión: la introducción entera terminaba convertida en <h3>)."""
        from maquetador.ingest.docx_comments import _buscar_elemento
        soup = BeautifulSoup(
            "<div>"
            "<p>Una vez definidos los estándares y mecanismos de calidad, "
            "la gestión del proyecto debe sostenerlos durante toda la "
            "ejecución. Esto implica detectar desvíos, gestionar "
            "evidencias, validar entregables periódicamente e interpretar "
            "la percepción de los interesados a lo largo del tiempo, junto "
            "con las auditorías internas como instrumentos de evaluación "
            "y aprendizaje dentro del proyecto en curso.</p>"
            "<p>Auditorías internas</p>"
            "<p>Permiten evaluar el grado de cumplimiento de los procesos.</p>"
            "</div>", "html.parser")
        el = _buscar_elemento(soup, "Auditorías internas")
        assert el.get_text(strip=True) == "Auditorías internas"

    def test_ancla_muy_corta_solo_matchea_por_igualdad_exacta(self):
        """Un ancla de menos de 6 caracteres squasheados ('Foro') es
        demasiado corta para prefijo/substring: solo vale si el párrafo
        candidato es, entero, ese mismo texto — así 'Foro' no matchea por
        casualidad contra 'Foro de discusión' u otro párrafo no relacionado."""
        from maquetador.ingest.docx_comments import _buscar_elemento
        soup = BeautifulSoup(
            "<div>"
            "<p>Foro de discusión general del curso.</p>"
            "<p><strong>Foro</strong></p>"
            "<p>Reflexioná sobre el rol de la calidad.</p>"
            "</div>", "html.parser")
        el = _buscar_elemento(soup, "Foro")
        assert el is not None
        assert el.get_text(strip=True) == "Foro"


class TestHastaAdentroDeUnaLista:
    """El límite `hasta` de pares_de_secciones() puede caer en un <li>
    adentro de un <ul>/<ol> (el ancla final del comentario terminó en un
    ítem de lista, no en un párrafo suelto): ese <li> nunca es un hermano de
    nivel superior que el recorrido visite directo, así que el corte tiene
    que reconocer cuándo `hasta` es DESCENDIENTE del elemento que sí se
    visita (regresión real: un expander de módulo 2 se comía toda una
    sección extra — "No conformidades y acciones de mejora" — porque el
    límite real terminaba en un <li> de una lista de viñetas)."""

    def test_se_detiene_en_el_li_final_sin_comerse_lo_que_sigue(self):
        from maquetador.build.componentes_asesor import pares_de_secciones
        soup = BeautifulSoup(
            "<div>"
            "<p><u>Título uno</u></p><p>Cuerpo uno.</p>"
            "<p><u>Título dos</u></p>"
            "<p>Antes de la lista.</p>"
            "<ul><li>Primer punto</li><li>Último punto</li></ul>"
            "<p>Esto no debería entrar al componente.</p>"
            "</div>", "html.parser")
        el = soup.find("p")
        hasta = soup.find_all("li")[-1]
        pares, consumidos = pares_de_secciones(el, modo="subrayado", hasta=hasta)
        assert len(pares) == 2
        cuerpo_total = "".join(c for _, c in pares)
        assert "Último punto" in cuerpo_total
        assert "Esto no debería entrar" not in cuerpo_total
        assert all("Esto no debería entrar" not in str(c) for c in consumidos)


class TestAcordeonSeDetieneEnSuAncla:
    """Un acordeón de un solo globo también tiene un final: el texto anclado
    completo (no solo el arranque) marca hasta dónde llega el componente."""

    def test_no_sigue_de_largo_mas_alla_del_texto_anclado(self):
        soup = BeautifulSoup(
            "<div>"
            "<p><strong>Planificación</strong></p>"
            "<p>Define qué se va a medir.</p>"
            "<p><strong>Control</strong></p>"
            "<p>Verifica que se cumplan los criterios.</p>"
            "<h3>Video módulo 1</h3>"
            "<p>Contenido que no debería entrar al acordeón.</p>"
            "</div>", "html.parser")
        coment = [{
            "instruccion": "Para maquetación: acordeón",
            "anclado": "Planificación Define qué se va a medir. Control "
                       "Verifica que se cumplan los criterios.",
            "accion": "acordeon", "autor": "",
        }]
        aplicar_comentarios(soup, coment)
        out = str(soup)
        assert "Contenido que no debería entrar al acordeón" not in \
            soup.find(class_="dp-panels-wrapper").decode_contents()
        assert "Video módulo 1" in out
