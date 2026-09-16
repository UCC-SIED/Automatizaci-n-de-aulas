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
