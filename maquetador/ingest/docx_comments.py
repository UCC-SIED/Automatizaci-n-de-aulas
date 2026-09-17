# -*- coding: utf-8 -*-
"""Lectura de los COMENTARIOS de los DOCX (los globos al margen).

Los asesores dejan pedidos de maquetación como comentarios anclados a un texto:
  "Para maquetación, subtítulo."        → ese texto va como <h3>
  "Para maquetación, recuadro simple."  → recuadro
  "Para maquetación, no resaltar/sin recuadro/con sangría" → NO encuadrar
  "Para maquetación: para la lectura"   → CTA Lectura
  "Para maquetación, acordeón / flip card" → componente (se avisa, es manual)
  "Sugiero quitar…"                      → se elimina ese texto

Este módulo extrae cada comentario JUNTO con el texto al que está anclado
(de word/comments.xml + word/document.xml), lo clasifica en una acción y
aplica las acciones simples al HTML ya convertido. Las que no se pueden
automatizar (acordeón, flip card, pedidos sueltos) se devuelven para avisarlas
en el plan.
"""

import re
import zipfile
import xml.etree.ElementTree as ET

from bs4 import BeautifulSoup

from maquetador.ingest.folder_scanner import normalizar
from maquetador.build.snippets import (resaltado_simple, cta_titulo, ICONOS,
                                       bloque_recurso_incrustado,
                                       _PAT_GENIALLY_URL, _PAT_SOLO_ARCHIVO)
from maquetador.build.componentes_asesor import (
    extraer_pares, construir_panels, construir_flipcards,
    construir_tooltip, disparador_tooltip, aplicar_cita,
)

_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
_W14 = "{http://schemas.microsoft.com/office/word/2010/wordml}"
_W15 = "{http://schemas.microsoft.com/office/word/2012/wordml}"

# Acciones que se aplican solas vs. las que solo se avisan.
# "quitar" NO se automatiza: a veces es un micro-pedido ("quitar los dos puntos")
# y borrar el párrafo entero sería un error; se avisa para hacerlo a mano.
_AUTO = {"subtitulo", "subsubtitulo", "recuadro_simple", "lectura", "video",
         "podcast", "sin_recuadro", "otra_pagina", "enlace_descargable",
         "genially_listo", "no_maquetar", "foro_en_lectura",
         "foro_lectura_y_espacio", "figura_expandible", "enlazar_actividad"}

# Nivel de encabezado por acción, según la política de jerarquía de la UCC:
# H2 es el título de la página, H3 el subtítulo y H4 el sub-subtítulo.
_NIVEL_ENCABEZADO = {"subtitulo": "h3", "subsubtitulo": "h4"}

_COMPONENTES = {"acordeon", "tabs", "tabs_vertical", "expander", "flip_card",
                "tooltip", "cita"}
# Clase de variante de DesignPLUS por tipo de panel. Los nombres salen del
# catálogo de snippets UCC: acordeón y expander NO son la misma variante, y
# las tabs son "dp-tabs-buttons" (había quedado "dp-tabs", que no existe y
# dejaba el componente sin estilo).
_VARIANTE_PANEL = {"acordeon": "dp-accordion-default",
                   "expander": "dp-expander-default",
                   "tabs": "dp-tabs-buttons",
                   "tabs_vertical": "dp-tabs-buttons-vertical"}


def _clasificar(instruccion: str, anclado: str = "") -> str:
    """Mapea el texto del comentario a una acción de maquetación (o None si es
    charla interna del equipo / una confirmación de "dejar como está", no una
    instrucción). `anclado` es el texto del documento al que apunta el globo:
    se usa para desambiguar pedidos genéricos ("CTA", "Recursos") por su
    contenido."""
    n = normalizar(instruccion)
    na = normalizar(anclado)
    if not n:
        return None
    # Charla interna del equipo (menciones @correo de Word/GDocs, asignaciones):
    # no es una instrucción de maquetación. Sin esto, un "podés avanzar en la
    # lectura del módulo…" se clasificaría por error como CTA Lectura.
    if instruccion.strip().startswith("@") or "assigned to" in n:
        return None
    # Confirmación de "queda como está" (no hay nada que maquetar): no se avisa.
    if "queda ok" in n or ("ok" in n and "original" in n) \
            or "queda bien" in n or "sin cambios" in n:
        return None
    # Comentarios que solo repiten algo que ya está escrito en el cuerpo del
    # DOCX: el pie de fuente de una figura ("Nota. Figura elaborada con base
    # en…") y el texto alternativo. El generador los toma del párrafo, no del
    # globo; acá son ruido del proceso editorial que quedó sin limpiar y no
    # tiene que aparecer como un pedido pendiente.
    if re.match(r"^\s*(?:para\s+(?:maquetacion|el\s+maquetado)\s*:\s*)?"
                r"(?:nota\s*[\.:]|texto\s+alt)", n):
        return None
    # El asesor deja el link real de un documento (a veces sin ningún otro
    # texto que "debe ser descargable"): el texto anclado tiene que quedar
    # como link a ese documento, no perderse como charla interna.
    if re.search(r"https?://\S+", instruccion) and "descargable" in n:
        return "enlace_descargable"
    # "Para diseño: …" es un encargo para el diseñador (el Genially, por
    # ejemplo), no una instrucción de maquetación.
    if n.startswith(("para diseno", "para diseño")):
        return None

    # "NO MAQUETAR": el tramo anclado NO va al aula. Es distinto de "quitar"
    # (que no se automatiza porque suele ser un micro-pedido: "quitar los dos
    # puntos"): acá el asesor excluye una sección entera, y dejarla pasar
    # publica material que no es para el estudiante. Caso real: las
    # "Indicaciones para el tutor" al final de una AFI —cómo corregir, qué
    # priorizar— quedaban visibles en el aula.
    if re.match(r"^\s*no\s+(?:se\s+)?maqueta", n):
        return "no_maquetar"

    # Señales negativas primero (NO encuadrar)
    if any(k in n for k in ("sin recuadro", "sin cuadro", "no resaltar",
                            "no encuadrar", "con sangria", "sangria sin")):
        return "sin_recuadro"
    # Marcador de cierre de un componente ("fin del expander"): señala dónde
    # termina, no pide armar otro. Va ANTES de detectar el tipo de componente.
    if re.match(r"^\s*(?:para\s+maquetacion\s*:\s*)?(?:fin|final)\s+(?:de[l ]|"
                r"de la\s)", n):
        return None
    # El asesor deja el texto de un componente (típicamente el foro) en el
    # DOCX de este módulo pero aclara que va en OTRA página ("foro
    # directamente en siguiente pág"): no hay que maquetarlo acá — va antes
    # de "recuadro"/"revisar" para no encuadrarlo como si fuera contenido de
    # esta página.
    if re.search(r"(siguiente|pr[oó]xima)\s*p[aá]g", n):
        return "otra_pagina"
    # Dónde va el recuadro del foro que el docente dejó escrito en la
    # lectura: solo en la página, solo en el espacio del foro (el
    # DiscussionTopic de Canvas), o en los dos. El asesor lo dice de varias
    # formas ("para dejar en la lectura", "esto es para el espacio del
    # foro", "es el mismo contenido para la lectura y para el espacio del
    # foro"). Va ANTES de la rama "lectura", que si no se lleva cualquier
    # mención a la lectura como si fuera un CTA "Descubrí leyendo".
    if "foro" in n or na.startswith("foro"):
        al_espacio = "espacio del foro" in n or "espacio para el foro" in n
        en_lectura = "lectura" in n
        if al_espacio and en_lectura:
            return "foro_lectura_y_espacio"
        if al_espacio:
            return "otra_pagina"
        if en_lectura:
            return "foro_en_lectura"
    # "Maquetación: enlazar actividad" — el asesor deja escrito "Para acceder a
    # la consigna, hacé clic aquí" y marca que ese texto tiene que ser el link
    # al assignment. Va antes que el resto: "enlazar actividad; el buzón debe
    # ser el mismo que se abrió en el módulo 2" también menciona el módulo.
    if re.search(r"\benlaz|\bvincul|\blinke?a", n) \
            and ("actividad" in n or "consigna" in n or "buzon" in n
                 or "entrega" in n):
        return "enlazar_actividad"
    # "sub-subtítulo" contiene "subtítulo": hay que mirarlo primero.
    if re.search(r"sub\s*-?\s*sub\s*-?\s*titulo", n):
        return "subsubtitulo"
    if "subtitulo" in n:
        return "subtitulo"
    if "acordeon" in n:
        return "acordeon"
    # "Tabs"/"solapas"/"pestañas" — componente de DesignPLUS. Palabra completa:
    # no confundir con "tabla" ni con "texto alternativo".
    if re.search(r"\btabs?\b", n) or "solapa" in n or "pestaña" in n \
            or "pestana" in n:
        # El asesor pide la orientación en el mismo comentario
        # ("Para maquetación: TABS vertical").
        return "tabs_vertical" if "vertical" in n else "tabs"
    # "Incluir pop up para ampliar" sobre una figura: no es el componente
    # expander (un panel colapsable) sino la figura con lupa, que se abre
    # en grande al hacer clic. Va ANTES de "expander"/"expandir" para que
    # "ampliar" no se lleve la figura a un panel.
    if re.search(r"(pop\s*-?\s*up|lupa)", n) and "ampli" in n:
        return "figura_expandible"
    if any(k in n for k in ("expander", "expandible", "expandir")):
        return "expander"
    if any(k in n for k in ("flip card", "flipcard", "flip-card", "tarjeta",
                            "se dan vuelta", "se da vuelta")):
        return "flip_card"
    if ("tooltip" in n or "popover" in n or "globo" in n
            or (("clic" in n or "click" in n)
                and ("emerj" in n or "emerge" in n or "aparezca" in n))):
        return "tooltip"
    if any(k in n for k in ("es una cita", "esto es una cita", "es cita", "como cita")):
        return "cita"
    # Quiz / autoevaluación (Quick check, verdadero o falso): se crean a mano en
    # Canvas; nunca se auto-maquetan como recuadro.
    if any(k in n for k in ("quic check", "quick check", "autoevaluacion",
                            "verdadero o falso", "checklist de autoevaluacion")):
        return "quiz"
    if any(k in n for k in ("quitar", "sacar", "eliminar", "borrar")):
        return "quitar"
    # Podcast/audio: el asesor lo dice explícito, o pide un "CTA/Recursos"
    # sobre un texto que habla de un podcast.
    if "podcast" in n or re.search(r"\baudio\b", n):
        return "podcast"
    if ("cta" in n or "recursos" in n) and ("podcast" in na or "audio" in na):
        return "podcast"
    if "recuadro" in n or "resalta" in n:   # resaltar, resaltado, "resaltado simple"
        return "recuadro_simple"
    if "lectura" in n:
        return "lectura"
    if re.search(r"\bvideo\b", n):
        return "video"
    if any(k in n for k in ("falta", "faltante", "pendiente", "hace falta",
                            "no se pudo", "a definir", "queda pendiente",
                            "sin terminar", "incompleto", "no esta disponible",
                            "esperando")):
        return "faltante"
    if n.startswith(("para maquetacion", "para el maquetado", "para diseno",
                     "para diseño", "maquetacion")):
        return "revisar"
    return None


def _respuestas_por_cid(croot, ext_xml: bytes) -> dict:
    """{cid_padre: [texto_respuesta, ...]} para los comentarios que tienen
    respuestas de otra persona (p.ej. el diseñador responde un "Para diseño:
    Genially…" con el div/iframe ya armado). La liga entre un comentario y
    su respuesta es por w14:paraId (del <w:p> adentro de <w:comment>), no por
    el w:id del comentario — Word guarda esa relación en
    word/commentsExtended.xml (w15:paraIdParent → w15:paraId del padre)."""
    respuestas = {}
    if not ext_xml:
        return respuestas
    paraid_a_cid = {}
    textos_por_cid = {}
    for c in croot.findall(f"{_W}comment"):
        cid = c.get(f"{_W}id")
        textos_por_cid[cid] = " ".join(t.text or "" for t in c.iter(f"{_W}t")).strip()
        for p in c.findall(f"{_W}p"):
            pid = p.get(f"{_W14}paraId")
            if pid:
                paraid_a_cid[pid] = cid
    try:
        eroot = ET.fromstring(ext_xml)
    except ET.ParseError:
        return respuestas
    for ce in eroot:
        pid_hijo = ce.get(f"{_W15}paraId")
        pid_padre = ce.get(f"{_W15}paraIdParent")
        if not pid_hijo or not pid_padre:
            continue
        cid_hijo = paraid_a_cid.get(pid_hijo)
        cid_padre = paraid_a_cid.get(pid_padre)
        if cid_hijo and cid_padre and cid_hijo != cid_padre:
            respuestas.setdefault(cid_padre, []).append(textos_por_cid.get(cid_hijo, ""))
    return respuestas


def extraer_comentarios(docx_path) -> list:
    """[{instruccion, anclado, accion, autor}] de un DOCX. [] si no tiene."""
    try:
        with zipfile.ZipFile(docx_path) as z:
            if "word/comments.xml" not in z.namelist():
                return []
            comments_xml = z.read("word/comments.xml")
            document_xml = z.read("word/document.xml")
            ext_xml = (z.read("word/commentsExtended.xml")
                      if "word/commentsExtended.xml" in z.namelist() else b"")
    except Exception:
        return []

    croot = ET.fromstring(comments_xml)
    textos, autores = {}, {}
    for c in croot.findall(f"{_W}comment"):
        cid = c.get(f"{_W}id")
        textos[cid] = " ".join(t.text or "" for t in c.iter(f"{_W}t")).strip()
        autores[cid] = c.get(f"{_W}author", "")
    respuestas = _respuestas_por_cid(croot, ext_xml)

    # Texto anclado: lo que está entre commentRangeStart/End (en orden de doc).
    droot = ET.fromstring(document_xml)
    padres = {hijo: padre for padre in droot.iter() for hijo in padre}
    activos = set()
    anclado = {cid: [] for cid in textos}
    inicio_el = {}
    for el in droot.iter():
        tag = el.tag
        if tag == f"{_W}commentRangeStart":
            cid = el.get(f"{_W}id")
            activos.add(cid)
            inicio_el.setdefault(cid, el)
        elif tag == f"{_W}commentRangeEnd":
            activos.discard(el.get(f"{_W}id"))
        elif tag == f"{_W}t" and activos:
            for cid in activos:
                if cid in anclado:
                    anclado[cid].append(el.text or "")

    def _bloque_contenedor(el):
        """Párrafo o tabla que contiene el elemento (subiendo por el árbol)."""
        cur = padres.get(el)
        while cur is not None:
            if cur.tag in (f"{_W}p", f"{_W}tbl"):
                return cur
            cur = padres.get(cur)
        return None

    def _ancla(cid):
        """Texto anclado; si es demasiado corto para ubicarlo (p.ej. Google Docs
        ancla el comentario a un fragmento invisible dentro de una tabla), se usa
        el texto del bloque que lo contiene: la celda/párrafo real."""
        crudo = "".join(anclado.get(cid, [])).strip()
        if len(normalizar(crudo)) >= 6 or cid not in inicio_el:
            return crudo
        cont = _bloque_contenedor(inicio_el[cid])
        if cont is None:
            return crudo
        # Los <w:t> de un mismo párrafo/celda se concatenan sin espacio (los
        # espacios ya vienen dentro del texto): unir con "" reconstruye la
        # palabra partida por Google Docs ('subyace' + 'nte' → 'subyacente').
        texto = "".join(t.text or "" for t in cont.iter(f"{_W}t")).strip()
        if texto:
            return texto
        # El globo está clavado SOBRE una imagen (rango vacío, párrafo sin
        # texto): el ancla pasa a ser el primer bloque con texto que sigue
        # —el epígrafe o la nota al pie de la figura—, que es lo que
        # permite ubicarla después en el HTML.
        if cont.find(f".//{_W}drawing") is not None:
            posteriores = [b for b in droot.iter()
                           if b.tag in (f"{_W}p", f"{_W}tbl")]
            vistos, seguir = False, None
            for b in posteriores:
                if b is cont:
                    vistos = True
                    continue
                if vistos:
                    t = "".join(x.text or "" for x in b.iter(f"{_W}t")).strip()
                    if t:
                        seguir = t
                        break
            if seguir:
                return seguir
        return crudo

    out = []
    for cid, instr in textos.items():
        anc = "".join(anclado.get(cid, [])).strip()
        accion = _clasificar(instr, anc)
        if not accion:
            # "Para diseño: … Genially …" no es un pedido de maquetación en
            # sí (se excluye arriba, en _clasificar), pero si el diseñador
            # ya respondió con el div/iframe armado, ESO sí hay que usarlo:
            # el texto anclado (el brief para el diseñador) se reemplaza por
            # el embed real en vez de quedar publicado como si fuera
            # contenido de la página.
            html_listo = next(
                (r for r in respuestas.get(cid, [])
                 if _PAT_GENIALLY_URL.search(r)), None)
            if html_listo:
                out.append({
                    "instruccion": re.sub(r"\s+", " ", instr).strip(),
                    "anclado": _ancla(cid),
                    "accion": "genially_listo",
                    "autor": autores.get(cid, ""),
                    "_html_genially": html_listo,
                })
            continue   # charla interna / confirmación, no es instrucción
        out.append({
            "instruccion": re.sub(r"\s+", " ", instr).strip(),
            "anclado": _ancla(cid),
            "accion": accion,
            "autor": autores.get(cid, ""),
        })
    return out


def _squash(texto: str) -> str:
    """Forma canónica para comparar: solo letras y números. Inmune a los espacios
    que mammoth mete alrededor de la puntuación ('especular :' vs 'especular:')."""
    return re.sub(r"[^a-z0-9]+", "", normalizar(texto))


_TAGS_BUSCABLES = ["p", "li", "h1", "h2", "h3", "h4", "h5", "h6"]


def _buscar_elemento(soup, anclado: str):
    """Encuentra el <p>/<li>/<hN> cuyo texto corresponde al texto anclado.

    Incluye encabezados (<h1>..<h6>) porque un párrafo con estilo Word
    "Subtitle" o "Título N" ya llegó convertido a <hN> (mammoth lo hace en la
    conversión inicial, antes de que este código corra): si solo se buscara
    entre <p>/<li>, un comentario anclado sobre ese texto ("Calidad Total",
    "Costos de la calidad"…) nunca encontraba su elemento y el pedido
    fallaba en silencio — pasaba con un "TABS horizontal" cuyos 3 títulos
    (Calidad Total/Lean/Six Sigma) eran todos estilo "Subtitle".

    Se queda con el candidato MÁS ESPECÍFICO (mayor solapamiento con el
    ancla), no el primero que coincide: un párrafo real puede empezar con la
    misma palabra que una celda de tabla no relacionada más arriba en el
    documento ("Planificación" de un encabezado de tabla vs. "Planificación
    de la calidad", el párrafo real que el comentario señala), y quedarse con
    el primero hacía que el comentario se aplicara sobre el elemento
    equivocado (y fallara en silencio, al no tener con qué seguir armando)."""
    objetivo = _squash(anclado)
    if not objetivo:
        return None
    if len(objetivo) < 6:
        # Ancla muy corta ("Foro"): con tan poco texto, cualquier coincidencia
        # por prefijo/substring es puro azar — solo vale una coincidencia
        # EXACTA (el párrafo entero es, ni más ni menos, ese texto).
        for el in soup.find_all(_TAGS_BUSCABLES):
            if _squash(el.get_text(" ", strip=True)) == objetivo:
                return _lista_de_un_item(el)
        return None
    clave = objetivo[:40]
    mejor, mejor_score = None, 0
    for el in soup.find_all(_TAGS_BUSCABLES):
        t = _squash(el.get_text(" ", strip=True))
        if not t:
            continue
        if t.startswith(clave):
            score = len(clave)
        elif objetivo.startswith(t[:40]):
            score = len(t[:40])
        elif clave in t and len(t) <= len(clave) + 150:
            # El ancla aparece adentro de `t`, pero solo cuenta si `t` no es
            # mucho más largo que el ancla (un párrafo/oración normal, no
            # cualquier párrafo largo de otra parte del documento que solo
            # MENCIONA de paso esa frase: "...junto con las auditorías
            # internas como instrumentos..." en la introducción no debe
            # ganarle al subtítulo real "Auditorías internas" más abajo).
            score = len(clave)
        else:
            continue
        if score > mejor_score:
            mejor, mejor_score = el, score
    return _lista_de_un_item(mejor) if mejor is not None else None


def _lista_de_un_item(el):
    """Si `el` es el único <li> de su <ul>/<ol>, devuelve esa lista: mammoth
    envuelve así algunos párrafos cortos en negrita, y la lista (no el <li>
    suelto) es el nodo del flujo que hay que anclar/recorrer."""
    padre = getattr(el, "parent", None)
    if el.name == "li" and getattr(padre, "name", None) in ("ul", "ol") \
            and len(padre.find_all("li", recursive=False)) == 1:
        return padre
    return el


def _buscar_elemento_final(soup, anclado: str):
    """Como _buscar_elemento, pero ubica el elemento donde TERMINA un tramo
    por el SUFIJO del texto anclado: el asesor a veces marca con el mismo
    comentario el principio y el final de un desplegable largo, resaltando
    tramos discontinuos del documento que comparten el mismo texto de
    comentario (ver aplicar_comentarios)."""
    objetivo = _squash(anclado)
    if len(objetivo) < 6:
        return None
    clave = objetivo[-40:]
    resultado = None
    for el in soup.find_all(_TAGS_BUSCABLES):
        t = _squash(el.get_text(" ", strip=True))
        if t and (t.endswith(clave) or clave.endswith(t)):
            resultado = el
    return resultado


def _imagen_cercana(el):
    """La <img> que acompaña al elemento anclado. El globo de "ampliar" se
    clava sobre la imagen, y el ancla termina siendo el texto más cercano
    (el epígrafe o la nota al pie). Según cómo armó el docente la figura,
    ese texto puede ser un hermano de la imagen o una celda distinta de la
    MISMA tabla sin bordes que envuelve figura + epígrafe + nota."""
    dentro = el if getattr(el, "name", None) == "img" else el.find("img")
    if dentro is not None:
        return dentro
    for cand in list(el.find_previous_siblings())[:3] \
            + list(el.find_next_siblings())[:3]:
        img = cand if getattr(cand, "name", None) == "img" else cand.find("img")
        if img is not None:
            return img
    contenedor = el.find_parent("table") or el.parent
    return contenedor.find("img") if contenedor is not None else None


def _cuerpo_de_recuadro(tabla) -> str:
    """El contenido de un recuadro-tabla, sin su rótulo. Hay dos geometrías
    según cómo lo armó el docente: el rótulo en su propia fila (2 filas × 1
    columna) o el rótulo y el cuerpo como párrafos de la MISMA celda (1×1).
    Con la segunda, mirar solo `tr[1:]` devolvía vacío y el foro quedaba sin
    consigna."""
    filas = tabla.find_all("tr")
    piezas = []
    for fila in filas[1:]:
        celda = fila.find(["td", "th"])
        if celda is not None:
            piezas.append("".join(str(x) for x in celda.children))
    if piezas:
        return "".join(piezas)
    celda = tabla.find(["td", "th"])
    if celda is None:
        return ""
    hijos = [h for h in celda.children
             if getattr(h, "name", None) or str(h).strip()]
    return "".join(str(h) for h in hijos[1:])   # sin el párrafo del rótulo


def _tramo_hasta(el, hasta) -> list:
    """[el, …, hasta] recorriendo hermanos de flujo desde `el`. `hasta`
    puede ser el propio hermano o un descendiente suyo (p.ej. el último
    <li> de una lista, ver pares_de_secciones). Si no se llega a `hasta`
    (o es None), devuelve solo [el] — más vale no tocar de más."""
    if hasta is None:
        return [el]
    tramo, actual = [el], el
    while actual is not None:
        if actual is hasta or any(a is actual for a in hasta.parents):
            return tramo
        actual = actual.find_next_sibling()
        if actual is not None:
            tramo.append(actual)
    return [el]


def _texto_tooltip(instruccion: str) -> str:
    """Saca el contenido del popover del comentario: lo que va después de
    'emerja:'/'aparezca:'/'tooltip-->'. Si no hay marcador claro, '' (→ fallback)."""
    for sep in ("emerja lo siguiente:", "emerja:", "aparezca:", "emerge:",
                "tooltip-->", "tooltip -->", "tooltip:", "globo:"):
        if sep in instruccion.lower():
            idx = instruccion.lower().index(sep) + len(sep)
            return instruccion[idx:].strip(" .–-")
    return ""


def _archivo_referenciado(el) -> str:
    """Nombre del DOCX que el asesor anotó al pie del recuadro para decir a qué
    actividad apunta el enlace ("EP - AFI.docx", "AEO 1 - GRyI.docx").

    Es el dato exacto —mejor que adivinar por la prosa, que menciona tanto la
    entrega preparatoria como la obligatoria en el mismo párrafo—. El párrafo
    en sí es una nota para maquetación y no se publica (lo saca
    procesar_contenido, ver _PAT_SOLO_ARCHIVO)."""
    caja = el.find_parent("table") or el.parent
    if caja is None:
        return ""
    for p in caja.find_all(["p", "li"]):
        m = _PAT_SOLO_ARCHIVO.match(p.get_text(" ", strip=True))
        if m:
            return m.group(0).strip()
    return ""


def _destino_de_actividad(el, instruccion: str) -> str:
    """Qué actividad hay que enlazar, leída del pedido y de su contexto.

    Devuelve "obligatoria" o "sugerida", con el módulo pegado cuando el asesor
    lo aclara ("el buzón debe ser el mismo que se abrió en el módulo 2" →
    "sugerida:2"): el buzón de la entrega preparatoria es uno solo para los
    módulos 2 y 3, y sin esa aclaración se abriría uno por módulo.
    """
    n = normalizar(instruccion)
    contexto = normalizar(
        (el.find_parent("table") or el).get_text(" ", strip=True))
    # "preparatoria" primero: el párrafo que invita a la entrega preparatoria
    # también nombra la obligatoria que vendrá después.
    if any(k in contexto for k in ("preparatoria", "preparatorio")):
        clase = "sugerida"
    elif "obligatoria" in contexto or "obligatoria" in n:
        clase = "obligatoria"
    elif "sugerida" in contexto or "opcional" in contexto:
        clase = "sugerida"
    else:
        clase = "obligatoria"
    m = re.search(r"m[oó]dulo\s*(\d+)", n)
    return f"{clase}:{m.group(1)}" if m else clase


def _marcar_enlace_de_actividad(soup, el, instruccion: str) -> bool:
    """Convierte el texto anclado en un <a> marcado con la actividad a la que
    tiene que apuntar. El href lo completa el generador, que es quien conoce
    los ids de los recursos de Canvas."""
    if el.find("a") is not None:
        return False
    contenido = "".join(str(x) for x in el.children).strip()
    if not contenido:
        return False
    atributos = {"class": "dp-course-link",
                 "data-actividad": _destino_de_actividad(el, instruccion)}
    archivo = _archivo_referenciado(el)
    if archivo:
        atributos["data-actividad-archivo"] = archivo
    enlace = soup.new_tag("a", **atributos)
    enlace.append(BeautifulSoup(contenido, "html.parser"))
    el.clear()
    el.append(enlace)
    return True


def aplicar_comentarios(soup, comentarios: list) -> None:
    """Aplica al soup las acciones automáticas cuyo texto anclado aparezca en
    él, y arma los componentes de pedido del asesor (acordeon/tabs/expander/
    flip_card/tooltip/cita) cuando hay estructura suficiente. Marca
    c['_aplicado']=True solo en los que efectivamente se aplican. Se llama una
    vez por cada sección ya cortada (así un comentario se aplica en la sección
    que lo contiene y nunca rompe los límites de sección)."""
    contador_popover = 0
    # Un mismo pedido de componente suele venir anclado en varios lugares: el
    # asesor marca con el mismo globo cada tramo que va adentro ("TABS vertical
    # ISO 14001 ISO 45001" aparece 3 veces, "flipcards" una por tarjeta). Es UN
    # componente, no uno por globo: en cuanto se arma, el resto del grupo queda
    # saldado para no apilar componentes repetidos.
    grupos_armados = set()

    # El texto anclado del ÚLTIMO globo del grupo (en orden del documento; el
    # propio globo si el pedido no se repite) marca dónde termina el tramo:
    # sin este límite, el armado sigue consumiendo párrafos hasta quedarse
    # sin _TAGS_FLUJO, mucho más allá de lo que el asesor pidió (pasó con
    # "TABS vertical ISO 14001 ISO 45001", cuyo comentario se repite 3 veces,
    # y con un "acordeón" de un solo globo cuyo texto anclado también tiene
    # un final preciso: sin usarlo, el armado seguía de largo hasta la
    # bibliografía).
    grupos_textos = {}
    for c in comentarios:
        if c["accion"] in _VARIANTE_PANEL or c["accion"] == "genially_listo" \
                or c["accion"] == "flip_card":
            grupos_textos.setdefault(
                (c["accion"], normalizar(c["instruccion"])), []).append(c)
    # Un ancla corta ("ISO 14001") es una simple etiqueta de arranque, no una
    # marca de final: solo un ancla larga (un tramo real de contenido) sirve
    # como límite de cierre. Sin este piso, un ancla corta usada como "fin"
    # coincide con el propio elemento de arranque y trunca el componente a
    # un solo elemento.
    grupos_fin = {}
    for grupo, cs in grupos_textos.items():
        if len(_squash(cs[-1]["anclado"])) < 40:
            continue
        el_fin = _buscar_elemento_final(soup, cs[-1]["anclado"])
        if el_fin is not None:
            grupos_fin[grupo] = el_fin

    for c in comentarios:
        accion = c["accion"]
        if c.get("_aplicado"):
            continue
        if accion not in _AUTO and accion not in _COMPONENTES:
            continue
        grupo = (accion, normalizar(c["instruccion"]))
        es_componente = accion in _VARIANTE_PANEL or accion == "flip_card"
        if es_componente and grupo in grupos_armados:
            c["_aplicado"] = True
            continue
        el = _buscar_elemento(soup, c["anclado"])
        if el is None:
            # "Para maquetación: subtítulo"/"sub-subtítulo" sobre un párrafo
            # con estilo Word "Subtitle": mammoth ya lo convirtió en <h3> (ver
            # _MAMMOTH_STYLE_MAP en segmenter.py), así que _buscar_elemento no
            # lo encuentra entre los <p>/<li>. Si ya quedó en el nivel que
            # pide el comentario no hay nada que hacer (avisar "revisar a
            # mano" ahí sería ruido); si quedó en OTRO nivel —el estilo
            # "Subtitle" siempre da h3, pero el asesor pidió sub-subtítulo
            # (h4)— se corrige el nivel en vez de dejarlo mal y sin avisar.
            if accion in _NIVEL_ENCABEZADO:
                objetivo = _squash(c["anclado"])
                nivel = _NIVEL_ENCABEZADO[accion]
                encabezado = next(
                    (h for h in soup.find_all(
                        ["h1", "h2", "h3", "h4", "h5", "h6"])
                     if objetivo and _squash(h.get_text(" ", strip=True)) == objetivo),
                    None)
                if encabezado is not None:
                    if encabezado.name != nivel:
                        encabezado.name = nivel
                    c["_aplicado"] = True
            continue
        # "NO MAQUETAR": se borra TODO el tramo anclado, no solo el elemento
        # donde arranca. El asesor marca de una una sección entera (p.ej. las
        # "Indicaciones para el tutor" al cierre de una AFI), así que borrar
        # solo el primer párrafo dejaría publicado el resto.
        if accion == "no_maquetar":
            fin = _buscar_elemento_final(soup, c["anclado"])
            for elemento in _tramo_hasta(el, fin):
                elemento.decompose()
            c["_aplicado"] = True
            continue

        # "Enlazar actividad": el asesor escribió "Para acceder a la consigna,
        # hacé clic aquí" y pide que ESE texto sea el link al assignment. Acá
        # todavía no existen los recursos de Canvas (ni sus ids), así que queda
        # marcado con qué actividad hay que enlazarlo y el generador resuelve
        # el href cuando el aula ya está armada.
        if accion == "enlazar_actividad":
            if _marcar_enlace_de_actividad(soup, el, c["instruccion"]):
                c["_aplicado"] = True
            continue

        # Ya está dentro de un recuadro/componente armado: encuadrarlo otra vez
        # deja una caja dentro de otra.
        if accion == "recuadro_simple" and el.find_parent(class_="dp-callout"):
            c["_aplicado"] = True
            continue

        # El comentario del asesor suele anclar sobre una tabla de pares
        # título/contenido (o un fragmento dentro de ella): el componente se
        # arma desde esa tabla, así que se sube al <table> contenedor.
        if accion in _VARIANTE_PANEL or accion == "flip_card":
            if el.name != "table":
                tabla_cont = el.find_parent("table")
                if tabla_cont is not None:
                    el = tabla_cont

        # --- Componentes de pedido del asesor ---
        if accion in _VARIANTE_PANEL:                 # acordeon / tabs / expander
            pares, consumidos = extraer_pares(
                el, c["instruccion"], hasta=grupos_fin.get(grupo))
            if len(pares) >= 2:
                html = construir_panels(pares, _VARIANTE_PANEL[accion])
                consumidos[0].replace_with(BeautifulSoup(html, "html.parser"))
                for extra in consumidos[1:]:
                    extra.decompose()
                c["_aplicado"] = True
                grupos_armados.add(grupo)
            continue
        if accion == "flip_card":
            pares, consumidos = extraer_pares(el, hasta=grupos_fin.get(grupo))
            if len(pares) >= 2:
                html = construir_flipcards(pares)
                consumidos[0].replace_with(BeautifulSoup(html, "html.parser"))
                for extra in consumidos[1:]:
                    extra.decompose()
                c["_aplicado"] = True
                grupos_armados.add(grupo)
            continue
        if accion == "tooltip":
            # El asesor ancla el comentario sobre TODO el párrafo y escribe
            # aparte qué debe emerger. Lo que se marca es el término que ese
            # contenido explica (la sigla, o el término completo), no el
            # párrafo entero: eso dejaba la página con un párrafo hecho link.
            contenido = _texto_tooltip(c["instruccion"])
            anclado = (c["anclado"] or "").strip()
            texto_el = el.get_text(" ", strip=True)
            if anclado and len(anclado) <= 40 and anclado in texto_el:
                # El asesor señaló la palabra exacta: esa es.
                palabra = anclado
            elif contenido:
                palabra = disparador_tooltip(texto_el, contenido)
            else:
                palabra = ""
            nodo = (el.find(string=lambda s: bool(s) and palabra in s)
                    if palabra else None)
            if nodo is not None:
                html = construir_tooltip(palabra, contenido, contador_popover)
                contador_popover += 1
                antes, _, despues = nodo.partition(palabra)
                cont = BeautifulSoup(html, "html.parser").find("span")
                nodo.replace_with(cont)
                if antes:
                    cont.insert_before(antes)
                if despues:
                    cont.insert_after(despues)
                c["_aplicado"] = True
            continue
        if accion == "cita":
            aplicar_cita(el)
            c["_aplicado"] = True
            continue

        # --- Acciones simples existentes ---
        c["_aplicado"] = True
        inner = "".join(str(x) for x in el.children).strip()
        if accion in _NIVEL_ENCABEZADO:
            if el.find_parent("table") is not None:
                # Adentro de un recuadro (la tabla que después se convierte
                # en la caja): un <hN> ahí compite con el propio título del
                # recuadro. Queda como línea destacada —letra más grande y
                # en negrita— sin asumir la categoría de encabezado, igual
                # que las bajadas de panel.
                el.name = "p"
                el["class"] = (el.get("class") or []) + ["lead", "dp-text-bold"]
            else:
                enc = soup.new_tag(_NIVEL_ENCABEZADO[accion])
                enc.string = el.get_text(" ", strip=True)
                el.replace_with(enc)
        elif accion == "quitar":
            el.decompose()
        elif accion == "recuadro_simple":
            el.replace_with(BeautifulSoup(resaltado_simple(inner), "html.parser"))
        elif accion == "lectura":
            el.replace_with(BeautifulSoup(
                cta_titulo("Lectura", f"<p>{inner}</p>", ICONOS["lectura"]),
                "html.parser"))
        elif accion == "video":
            el.replace_with(BeautifulSoup(
                cta_titulo("Video", f"<p>{inner}</p>", ICONOS["video"]),
                "html.parser"))
        elif accion == "podcast":
            el.replace_with(BeautifulSoup(
                cta_titulo("Podcast", f"<p>{inner}</p>", ICONOS["podcast"]),
                "html.parser"))
        elif accion == "sin_recuadro":
            # El asesor pide NO encuadrar: se marca para que procesar_contenido
            # no lo convierta en recuadro por sus heurísticas.
            el["data-keep-plain"] = "1"
        elif accion == "otra_pagina":
            # El contenido (típicamente el foro) vive en el DOCX de este
            # módulo pero el asesor aclaró que va en OTRA página: se saca
            # entero de acá, tabla incluida si el ancla cayó en una celda,
            # para que no quede maquetado como si fuera de esta página. Antes
            # de sacarlo, se guarda el cuerpo (todo menos la fila/celda del
            # rótulo) para que ese contenido pueda ir a parar a donde
            # corresponde de verdad (ver aplicar_comentarios/segmentar_docx).
            tabla = el if el.name == "table" else el.find_parent("table")
            if tabla is not None:
                c["_contenido_extraido"] = _cuerpo_de_recuadro(tabla)
                tabla.decompose()
            else:
                c["_contenido_extraido"] = inner
                el.decompose()
        elif accion == "figura_expandible":
            # El globo está sobre la imagen (o sobre su epígrafe/nota): se
            # marca la figura vecina para que procesar_contenido le ponga
            # el estilo con lupa en vez del estático.
            img = _imagen_cercana(el)
            if img is not None:
                img["data-ampliable"] = "1"
            else:
                c["_aplicado"] = False
                continue
        elif accion == "foro_en_lectura":
            # El asesor confirma que ESTE recuadro se queda donde está: no
            # hay nada que hacer, pero se marca aplicado para que no salga
            # como pedido pendiente.
            pass
        elif accion == "foro_lectura_y_espacio":
            # El mismo contenido va en los dos lados: se copia para el
            # espacio del foro y se deja igual en la lectura (a diferencia
            # de "otra_pagina", que lo saca de la página).
            tabla = el if el.name == "table" else el.find_parent("table")
            c["_contenido_extraido"] = (_cuerpo_de_recuadro(tabla)
                                        if tabla is not None else inner)
        elif accion == "enlace_descargable":
            # El asesor deja el link real en el comentario (a veces sin más
            # texto que "debe ser descargable"): el texto anclado pasa a ser
            # el link a ese documento.
            url_m = re.search(r"https?://\S+", c["instruccion"])
            texto_link = (c["anclado"] or "").strip()
            nodo = (el.find(string=lambda s: bool(s) and texto_link in s)
                    if url_m and texto_link else None)
            if nodo is not None:
                url = url_m.group(0).rstrip(".,;)")
                a = soup.new_tag("a", href=url)
                a["class"] = "inline_disabled dp-ext-ignore"
                a["target"] = "_blank"
                a.string = texto_link
                antes, _, despues = nodo.partition(texto_link)
                nodo.replace_with(a)
                if antes:
                    a.insert_before(antes)
                if despues:
                    a.insert_after(despues)
        elif accion == "genially_listo":
            # El brief para el diseñador ("Para diseño: … Genially …") no va
            # como contenido de la página: se reemplaza entero —desde el
            # ancla hasta donde termina el tramo marcado por el comentario—
            # por el embed real que el diseñador ya dejó armado en su
            # respuesta.
            iframe = BeautifulSoup(
                c.get("_html_genially", ""), "html.parser").find("iframe")
            tramo = _tramo_hasta(el, grupos_fin.get(grupo))
            nuevo = bloque_recurso_incrustado(str(iframe) if iframe else "")
            tramo[0].replace_with(BeautifulSoup(nuevo, "html.parser"))
            for extra in tramo[1:]:
                extra.decompose()
