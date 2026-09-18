# -*- coding: utf-8 -*-
"""Regresión de inyección de actividades en el paquete .imscc."""

import zipfile
from pathlib import Path

import pytest
from bs4 import BeautifulSoup

from maquetador.cli import analizar_curso
from maquetador.extract.extractor import extraer_contenido
from maquetador.build.imscc_builder import generar_imscc, TEMAS

_CASO = (Path(__file__).parent.parent / "Aulas a generar"
         / "Instrumentos del Sistema Financiero"
         / "Instrumentos del Sistema Financiero")

_CASO_LIDERAZGO = (Path(__file__).parent.parent / "Aulas a generar"
                   / "Seminario I - Liderazgo en Accion"
                   / "Seminario I_ Liderazgo en Acción")


def _texto_del_topic(zf, titulo_contiene):
    """Texto plano del mensaje del DiscussionTopic cuyo título contiene el string."""
    import re
    import html as H
    manifest = zf.read("imsmanifest.xml").decode("utf-8", "ignore")
    meta = zf.read("course_settings/module_meta.xml").decode("utf-8", "ignore")
    for m in re.finditer(
            r"<content_type>DiscussionTopic</content_type>\s*"
            r"<workflow_state>[^<]*</workflow_state>\s*<title>([^<]*)</title>\s*"
            r"<identifierref>([^<]+)</identifierref>", meta):
        titulo, rid = m.groups()
        if titulo_contiene.lower() not in titulo.lower():
            continue
        mr = re.search(rf'<resource[^>]*identifier="{rid}"[^>]*>.*?'
                       r'<file href="([^"]+\.xml)"', manifest, re.DOTALL)
        if not mr:
            return None
        raw = zf.read(mr.group(1)).decode("utf-8", "ignore")
        mt = re.search(r"<text[^>]*>(.*?)</text>", raw, re.DOTALL)
        if not mt:
            return ""
        return BeautifulSoup(H.unescape(mt.group(1)), "html.parser").get_text(
            " ", strip=True)
    return None


def _texto_del_assignment(zf, titulo_contiene):
    """Texto plano del HTML del assignment cuyo título contiene el string."""
    import re
    for name in zf.namelist():
        if name.endswith("assignment_settings.xml"):
            xml = zf.read(name).decode("utf-8", "ignore")
            m = re.search(r"<title>([^<]*)</title>", xml)
            if m and titulo_contiene.lower() in m.group(1).lower():
                carpeta = name.rsplit("/", 1)[0]
                for h in zf.namelist():
                    if h.startswith(carpeta + "/") and h.endswith(".html"):
                        return BeautifulSoup(zf.read(h), "html.parser").get_text(
                            " ", strip=True)
    return None


@pytest.mark.skipif(not _CASO.is_dir() or not TEMAS["posgrado"].is_dir(),
                    reason="Requiere el caso 'Instrumentos' extraído y el aula base posgrado.")
def test_docx_dedicado_gana_al_puntero_embebido(tmp_path):
    """La Actividad obligatoria del módulo llega como DOCX dedicado (~4k chars).
    Un puntero embebido en el multimedial ('te invito a realizar la actividad…')
    NO debe reclamar el slot y dejar el assignment en el placeholder del aula
    base: tiene que ganar el contenido del DOCX dedicado."""
    spec = analizar_curso(_CASO, "posgrado")
    media = extraer_contenido(spec)
    salida = generar_imscc(spec, media, tmp_path)

    zf = zipfile.ZipFile(salida)
    texto = _texto_del_assignment(zf, "Actividad obligatoria M1")
    assert texto is not None, "No encontré el assignment 'Actividad obligatoria M1'."
    # El DOCX dedicado trae título, objetivos y consigna: bastante más que el
    # puntero de ~100 chars o el placeholder del aula base.
    assert len(texto) > 1000, (
        f"El assignment M1 quedó casi vacío ({len(texto)} chars): el puntero "
        "embebido pisó al DOCX dedicado.")
    assert "valuación de activos" in texto.lower()


@pytest.mark.skipif(not _CASO.is_dir() or not TEMAS["posgrado"].is_dir(),
                    reason="Requiere el caso 'Instrumentos' extraído y el aula base posgrado.")
def test_foro_de_apertura_carga_su_docx(tmp_path):
    """El 'Foro de apertura' llega como DOCX dedicado (~1.4k chars). Aunque la
    planilla ponga una URL de Google Docs como referencia (que no sirve para
    matchear por nombre), el foro tiene que cargar la consigna del DOCX, no
    quedar con el placeholder del aula base."""
    spec = analizar_curso(_CASO, "posgrado")
    media = extraer_contenido(spec)
    salida = generar_imscc(spec, media, tmp_path)

    zf = zipfile.ZipFile(salida)
    texto = _texto_del_topic(zf, "Foro de apertura")
    assert texto is not None, "No encontré el DiscussionTopic 'Foro de apertura'."
    assert len(texto) > 500, (
        f"El Foro de apertura quedó con el placeholder ({len(texto)} chars): "
        "no cargó su DOCX dedicado.")
    assert "consigna de participaci" in texto.lower()


@pytest.mark.skipif(not _CASO.is_dir() or not TEMAS["posgrado"].is_dir(),
                    reason="Requiere el caso 'Instrumentos' extraído y el aula base posgrado.")
def test_foro_de_modulo_carga_consigna_de_la_planilla(tmp_path):
    """Cuando el asesor escribe la consigna del foro directamente en la planilla
    de montaje ('Texto del foro: …') en vez de un DOCX, esa consigna tiene que
    volcarse en el foro del módulo, no quedar con el placeholder del aula base."""
    spec = analizar_curso(_CASO, "posgrado")
    media = extraer_contenido(spec)
    salida = generar_imscc(spec, media, tmp_path)

    zf = zipfile.ZipFile(salida)
    texto = _texto_del_topic(zf, "Foro obligatorio M1")
    assert texto is not None, "No encontré el DiscussionTopic 'Foro obligatorio M1'."
    assert len(texto) > 300, (
        f"El foro del módulo 1 quedó con el placeholder ({len(texto)} chars): "
        "no cargó la consigna escrita en la planilla.")
    assert "espacio de debate y tutor" in texto.lower()


@pytest.mark.skipif(not _CASO.is_dir() or not TEMAS["posgrado"].is_dir(),
                    reason="Requiere el caso 'Instrumentos' extraído y el aula base posgrado.")
def test_expander_y_flipcards_desde_comentarios_del_docx(tmp_path):
    """El asesor pide 'expander' y 'flip cards' con un comentario del DOCX sobre
    una tabla de pares título/contenido. Aunque Google Docs ancle el comentario
    a un fragmento invisible ('nte', cola de 'subyacente') dentro de la tabla,
    el componente tiene que armarse a partir de esa tabla."""
    spec = analizar_curso(_CASO, "posgrado")
    media = extraer_contenido(spec)
    salida = generar_imscc(spec, media, tmp_path)

    zf = zipfile.ZipFile(salida)
    todo = "".join(zf.read(n).decode("utf-8", "ignore")
                   for n in zf.namelist() if n.endswith(".html"))
    assert "dp-expander-default" in todo, \
        "No se armó el expander que el asesor pidió sobre la tabla de futuros."
    assert "dp-flip-card" in todo, \
        "No se armaron las flip cards que el asesor pidió sobre la tabla de opciones."


@pytest.mark.skipif(not _CASO.is_dir() or not TEMAS["posgrado"].is_dir(),
                    reason="Requiere el caso 'Instrumentos' extraído y el aula base posgrado.")
def test_tabs_desde_lista_de_la_planilla(tmp_path):
    """El asesor pide 'tabs' sobre una lista de ítems 'Etiqueta: contenido'
    (Para especular: …, Para cubrirse: …, Para spreading: …). Esa lista tiene
    que convertirse en un componente de tabs, no quedar como aviso manual."""
    spec = analizar_curso(_CASO, "posgrado")
    media = extraer_contenido(spec)
    salida = generar_imscc(spec, media, tmp_path)

    zf = zipfile.ZipFile(salida)
    todo = "".join(zf.read(n).decode("utf-8", "ignore")
                   for n in zf.namelist() if n.endswith(".html"))
    assert "dp-tabs" in todo, \
        "No se armaron los tabs que el asesor pidió sobre la lista de estrategias."


@pytest.mark.skipif(not _CASO_LIDERAZGO.is_dir() or not TEMAS["posgrado"].is_dir(),
                    reason="Requiere el caso 'Liderazgo' extraído y el aula base posgrado.")
def test_foro_participativo_carga_su_docx(tmp_path):
    """El foro participativo llega como DOCX dedicado ('Foro Participativo - Akio
    Toyoda y la crisis Toyota.docx'). El título del foro está contenido en el
    nombre del archivo: aunque el parecido global quede bajo el umbral, el foro
    tiene que cargar su consigna, no quedar con el placeholder."""
    spec = analizar_curso(_CASO_LIDERAZGO, "posgrado")
    media = extraer_contenido(spec)
    salida = generar_imscc(spec, media, tmp_path)

    zf = zipfile.ZipFile(salida)
    texto = _texto_del_topic(zf, "Foro obligatorio M1")
    assert texto is not None, "No encontré el DiscussionTopic 'Foro obligatorio M1'."
    assert len(texto) > 300, (
        f"El foro participativo quedó con el placeholder ({len(texto)} chars): "
        "no cargó su DOCX dedicado por el umbral de confianza.")
    assert "toyoda" in texto.lower()


@pytest.mark.skipif(not _CASO_LIDERAZGO.is_dir() or not TEMAS["posgrado"].is_dir(),
                    reason="Requiere el caso 'Liderazgo' extraído y el aula base posgrado.")
def test_lista_explicativa_no_se_convierte_en_flipcards(tmp_path):
    """Un comentario 'Flip card' anclado a un párrafo no debe arrastrar una lista
    explicativa siguiente (p.ej. 'En lo simple…: …') y partirla en el ':' como si
    fueran tarjetas. Esa lista es contenido, no pares frente/dorso."""
    spec = analizar_curso(_CASO_LIDERAZGO, "posgrado")
    media = extraer_contenido(spec)
    salida = generar_imscc(spec, media, tmp_path)

    zf = zipfile.ZipFile(salida)
    fronts = []
    for n in zf.namelist():
        if n.startswith("wiki_content/") and n.endswith(".html"):
            soup = BeautifulSoup(zf.read(n), "html.parser")
            for fr in soup.find_all("div", class_="dp-front-card"):
                fronts.append(fr.get_text(" ", strip=True).lower())
    malas = [f for f in fronts if "en lo simple" in f or "en lo caótico" in f
             or "en lo complejo" in f]
    assert not malas, f"Lista explicativa convertida en flip cards por error: {malas}"


_CASO_TALLER = (Path(__file__).parent.parent / "Aulas a generar"
                / "Taller de Trabajo Final Integrador"
                / "TALLER DE TRABAJO FINAL INTEGRADOR")


@pytest.mark.skipif(not _CASO_TALLER.is_dir() or not TEMAS["posgrado"].is_dir(),
                    reason="Requiere el caso 'Taller' extraído y el aula base posgrado.")
def test_modulo_clonado_renumera_assignment_y_posicion(tmp_path):
    """El aula base posgrado trae 3 módulos; este curso tiene 4, así que se clona
    un módulo. El módulo clonado debe quedar como 'M4' (no duplicar 'M3') tanto en
    el título del assignment como en la posición del módulo."""
    import re
    spec = analizar_curso(_CASO_TALLER, "posgrado")
    media = extraer_contenido(spec)
    salida = generar_imscc(spec, media, tmp_path)

    zf = zipfile.ZipFile(salida)
    # Título real de los assignments (lo que ve Canvas)
    titulos = []
    for n in zf.namelist():
        if n.endswith("assignment_settings.xml"):
            m = re.search(r"<title>([^<]*)</title>", zf.read(n).decode("utf-8", "ignore"))
            if m:
                titulos.append(m.group(1))
    obligatorias = sorted(t for t in titulos if "obligatoria" in t.lower())
    assert "Actividad obligatoria M4" in obligatorias, \
        f"El assignment del módulo clonado no quedó como M4: {obligatorias}"
    assert len([t for t in obligatorias if t == "Actividad obligatoria M3"]) == 1, \
        f"Hay 'Actividad obligatoria M3' duplicada: {obligatorias}"

    # Posiciones de los módulos únicas (M4 no debe compartir posición con M3)
    meta = zf.read("course_settings/module_meta.xml").decode("utf-8", "ignore")
    posiciones = re.findall(
        r"<title>\s*M[óo]dulo\s*(\d+)\s*:[^<]*</title>\s*"
        r"<workflow_state>[^<]*</workflow_state>\s*<position>(\d+)</position>", meta)
    posn = [p for _num, p in posiciones]
    assert len(posn) == len(set(posn)), \
        f"Módulos con posición duplicada: {posiciones}"


_CASO_DISCAP = (Path(__file__).parent.parent / "Aulas a generar"
                / "Problematica Social de la Discapacidad"
                / "Problemática Social de la Discapacidad")


@pytest.mark.skipif(not _CASO_DISCAP.is_dir() or not TEMAS["educacion"].is_dir(),
                    reason="Requiere el caso 'Discapacidad' extraído y el aula base educación.")
def test_foro_introductorio_carga_como_apertura(tmp_path):
    """El foro de apertura llega como 'Foro Introductorio.docx'. 'Introductorio'
    es sinónimo de apertura: debe cargarse en el Foro de apertura, no quedar con
    el placeholder ni tomar por error otro foro del módulo."""
    spec = analizar_curso(_CASO_DISCAP, "educacion")
    media = extraer_contenido(spec)
    salida = generar_imscc(spec, media, tmp_path)

    zf = zipfile.ZipFile(salida)
    texto = _texto_del_topic(zf, "Foro de apertura")
    assert texto is not None, "No encontré el DiscussionTopic 'Foro de apertura'."
    assert len(texto) > 300, (
        f"El Foro de apertura quedó con el placeholder ({len(texto)} chars): "
        "no cargó el 'Foro Introductorio.docx'.")


def test_cuerpo_topic_con_diseno_deja_aire_al_final():
    """El aula base cierra cada topic con un <p>&nbsp;</p> de aire debajo del
    contenido; _cuerpo_topic_con_diseno lo quita (junto al resto de los
    placeholders) para insertar el contenido real, pero tiene que devolverlo:
    si no, el foro queda con el último párrafo pegado al borde del bloque."""
    from maquetador.build.imscc_builder import GeneradorAula

    base_body = (
        '<div id="dp-wrapper"><div class="dp-content-block content-block">'
        '<h2>Título</h2>'
        '<p>&nbsp;</p><p>&nbsp;</p>'
        '</div></div>')
    resultado = GeneradorAula._cuerpo_topic_con_diseno(
        None, base_body, "<p>¡Bienvenidos!</p>")
    assert resultado.rstrip().endswith("<p>\xa0</p></div></div>")
    assert "¡Bienvenidos!" in resultado


def test_cuerpo_topic_con_diseno_encuentra_el_bloque_sin_la_clase_bare():
    """El aula base NO siempre marca el bloque de contenido real con la
    clase bare "content-block" (la variante que trae 'Foro de apertura'):
    los foros obligatorios de módulo, por ejemplo, solo traen "kl_lectures2"
    junto a "dp-content-block" (la única clase universal). Buscar solo por
    "content-block" nunca encontraba ese bloque — el foro se armaba con el
    wrapper mínimo, sin banner ni navegación del aula base, como si el
    diseño no tuviera la estructura esperada."""
    from maquetador.build.imscc_builder import GeneradorAula

    base_body = (
        '<div id="dp-wrapper">'
        '<div class="dp-banner-image"><img src="banner.png"></div>'
        '<div class="dp-content-block kl_introduction">'
        '<p class="lead dp-progress-placeholder">placeholder oculto</p>'
        '</div>'
        '<div class="dp-content-block kl_lectures2">'
        '<h2 class="dp-has-icon"></h2>'
        '<p>&nbsp;</p><p>&nbsp;</p>'
        '</div></div>')
    resultado = GeneradorAula._cuerpo_topic_con_diseno(
        None, base_body, "<p>Consigna del foro.</p>")
    assert resultado is not None
    assert "dp-banner-image" in resultado
    assert "Consigna del foro." in resultado


# --------------------------------------------------------------------------
#  Actividad que se resuelve en una herramienta externa (Padlet, Mural, Miro)
# --------------------------------------------------------------------------

class TestHerramientaExterna:
    """La planilla nombra la herramienta en la columna de referencia en vez de
    un DOCX ("Actividad sugerida | Padlet"). No hay archivo que volcar, pero la
    actividad existe. Regresión real: Gestión del Riesgo, módulo 1."""

    def _item(self, referencia):
        from maquetador.models import ItemCurso, TipoItem
        return ItemCurso(titulo="Actividad sugerida", tipo=TipoItem.TAREA,
                         detalle={"referencia": referencia})

    def test_reconoce_las_herramientas_del_catalogo(self):
        from maquetador.build.imscc_builder import _herramienta_externa
        assert _herramienta_externa(self._item("Padlet")) == "Padlet"
        assert _herramienta_externa(self._item("Mural colaborativo")) == "Mural"
        assert _herramienta_externa(self._item("Miro")) == "Miro"

    def test_un_docx_no_es_una_herramienta(self):
        from maquetador.build.imscc_builder import _herramienta_externa
        assert _herramienta_externa(self._item("AEO 1 - GRyI.docx")) == ""
        assert _herramienta_externa(self._item("")) == ""

    def test_no_confunde_una_consigna_larga_con_una_referencia(self):
        """La referencia es el nombre de un archivo o de una herramienta, no un
        párrafo: un texto largo que MENCIONE la herramienta no cuenta."""
        from maquetador.build.imscc_builder import _herramienta_externa
        largo = ("Participar del mural colaborativo que se abre al final del "
                 "módulo, con la consigna que figura en el multimedial.")
        assert _herramienta_externa(self._item(largo)) == ""


class TestSlotDeActividadDelAulaBase:
    """El aula base trae una sola Assignment por módulo, la obligatoria. Si la
    planilla no pide obligatoria (Gestión del Riesgo pide solo una sugerida en
    Padlet en el módulo 1), ese slot tiene que borrarse: dejarlo publica un
    assignment vacío con el placeholder del aula base."""

    def _generador(self):
        from maquetador.build.imscc_builder import GeneradorAula
        from maquetador.models import CourseSpec
        gen = GeneradorAula.__new__(GeneradorAula)
        gen.spec = CourseSpec(nombre="X")
        return gen

    def _modulo(self, *titulos):
        from maquetador.models import ModuloCurso, ItemCurso, TipoItem
        mod = ModuloCurso(numero=1, titulo="M1")
        mod.items = [ItemCurso(titulo=t, tipo=TipoItem.TAREA) for t in titulos]
        return mod

    def test_solo_sugerida_no_reserva_el_slot_de_la_obligatoria(self):
        quedan = self._generador()._recursos_que_pide_modulo(
            self._modulo("Actividad sugerida"))
        assert "Actividad obligatoria M1" not in quedan
        assert "Actividad sugerida M1" in quedan

    def test_con_obligatoria_el_slot_se_conserva(self):
        quedan = self._generador()._recursos_que_pide_modulo(
            self._modulo("Actividad sugerida (individual)",
                         "Actividad obligatoria (individual)"))
        assert "Actividad obligatoria M1" in quedan
        assert "Actividad sugerida M1" in quedan

    def test_una_actividad_sin_adjetivo_sigue_siendo_la_obligatoria(self):
        quedan = self._generador()._recursos_que_pide_modulo(
            self._modulo("Actividad"))
        assert "Actividad obligatoria M1" in quedan


class TestColorYAireDelPlaceholderDeActividad:
    """El aula base de la AFI trae un banner fijo "¡Llegaste al final!" en
    azul (#003087), siempre, sin importar el tema del curso, seguido de dos
    párrafos vacíos antes de donde se inserta el título del caso. El título
    que genera maquetar_actividad debía usar el mismo azul (no el del tema)
    y el doble espacio debía reducirse a uno. Regresión real: AFI de "Gestión
    de la Calidad" (tema posgrado, que por defecto usa #1b1e31)."""

    from maquetador.build.imscc_builder import GeneradorAula as _GA

    PLACEHOLDER_AFI = (
        '<p class="" style="color: #003087;"><span style="font-size: 24pt;">'
        '<strong>¡Llegaste al final!</strong></span></p>'
        '<p><span style="font-size: 18pt;"><strong>Es tu momento de '
        'demostrar lo aprendido.</strong></span></p>'
        '<hr><p>&nbsp;</p><p>&nbsp;</p>')

    def test_extrae_el_color_del_banner_fijo(self):
        assert self._GA._color_del_placeholder(self.PLACEHOLDER_AFI) == "#003087"

    def test_sin_banner_fijo_no_hay_color_que_extraer(self):
        assert self._GA._color_del_placeholder(
            '<h2 class="dp-has-icon"></h2><p>&nbsp;</p>') == ""

    def test_el_doble_espacio_final_queda_en_uno_solo(self):
        out = self._GA._sacar_un_espacio_final(self.PLACEHOLDER_AFI)
        assert out.count("<p>&nbsp;</p>") == 1
        assert "¡Llegaste al final!" in out    # el resto no se toca

    def test_un_solo_espacio_final_no_se_toca(self):
        """El resto de los assignments (Actividad obligatoria M1/M2, sin este
        banner) solo traen un párrafo vacío: no hay nada que recortar."""
        placeholder = '<h2 class="dp-has-icon"></h2><p>&nbsp;</p>'
        assert self._GA._sacar_un_espacio_final(placeholder) == placeholder

    def test_el_titulo_del_caso_usa_el_color_del_banner_no_el_del_tema(self):
        from maquetador.build.snippets import maquetar_actividad
        color = self._GA._color_del_placeholder(self.PLACEHOLDER_AFI)
        out = maquetar_actividad(
            "<h2>Analizá situaciones reales</h2><p>Cuerpo.</p>",
            tema="posgrado", color_titulo=color)
        assert 'style="color: #003087; text-align: center;"' in out
        assert "#1b1e31" not in out   # el accent de posgrado no debe colarse

    def test_sin_color_de_banner_sigue_usando_el_del_tema(self):
        from maquetador.build.snippets import maquetar_actividad
        out = maquetar_actividad(
            "<h2>Proyecto de ampliación de una planta</h2><p>Cuerpo.</p>",
            tema="posgrado")
        assert "#1b1e31" in out
