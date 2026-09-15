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
from maquetador.build.snippets import resaltado_simple, cta_titulo, ICONOS
from maquetador.build.componentes_asesor import (
    extraer_pares, construir_panels, construir_flipcards,
    construir_tooltip, disparador_tooltip, aplicar_cita,
)

_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"

# Acciones que se aplican solas vs. las que solo se avisan.
# "quitar" NO se automatiza: a veces es un micro-pedido ("quitar los dos puntos")
# y borrar el párrafo entero sería un error; se avisa para hacerlo a mano.
_AUTO = {"subtitulo", "subsubtitulo", "recuadro_simple", "lectura", "video",
         "podcast", "sin_recuadro"}

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
    # "Para diseño: …" es un encargo para el diseñador (el Genially, por
    # ejemplo), no una instrucción de maquetación.
    if n.startswith(("para diseno", "para diseño")):
        return None

    # Señales negativas primero (NO encuadrar)
    if any(k in n for k in ("sin recuadro", "sin cuadro", "no resaltar",
                            "no encuadrar", "con sangria", "sangria sin")):
        return "sin_recuadro"
    # Marcador de cierre de un componente ("fin del expander"): señala dónde
    # termina, no pide armar otro. Va ANTES de detectar el tipo de componente.
    if re.match(r"^\s*(?:para\s+maquetacion\s*:\s*)?(?:fin|final)\s+(?:de[l ]|"
                r"de la\s)", n):
        return None
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


def extraer_comentarios(docx_path) -> list:
    """[{instruccion, anclado, accion, autor}] de un DOCX. [] si no tiene."""
    try:
        with zipfile.ZipFile(docx_path) as z:
            if "word/comments.xml" not in z.namelist():
                return []
            comments_xml = z.read("word/comments.xml")
            document_xml = z.read("word/document.xml")
    except Exception:
        return []

    croot = ET.fromstring(comments_xml)
    textos, autores = {}, {}
    for c in croot.findall(f"{_W}comment"):
        cid = c.get(f"{_W}id")
        textos[cid] = " ".join(t.text or "" for t in c.iter(f"{_W}t")).strip()
        autores[cid] = c.get(f"{_W}author", "")

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
        return texto or crudo

    out = []
    for cid, instr in textos.items():
        anc = "".join(anclado.get(cid, [])).strip()
        accion = _clasificar(instr, anc)
        if not accion:
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


def _buscar_elemento(soup, anclado: str):
    """Encuentra el <p>/<li> cuyo texto corresponde al texto anclado.

    Se queda con el candidato MÁS ESPECÍFICO (mayor solapamiento con el
    ancla), no el primero que coincide: un párrafo real puede empezar con la
    misma palabra que una celda de tabla no relacionada más arriba en el
    documento ("Planificación" de un encabezado de tabla vs. "Planificación
    de la calidad", el párrafo real que el comentario señala), y quedarse con
    el primero hacía que el comentario se aplicara sobre el elemento
    equivocado (y fallara en silencio, al no tener con qué seguir armando)."""
    objetivo = _squash(anclado)
    if len(objetivo) < 6:
        return None
    clave = objetivo[:40]
    mejor, mejor_score = None, 0
    for el in soup.find_all(["p", "li"]):
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
    for el in soup.find_all(["p", "li"]):
        t = _squash(el.get_text(" ", strip=True))
        if t and (t.endswith(clave) or clave.endswith(t)):
            resultado = el
    return resultado


def _texto_tooltip(instruccion: str) -> str:
    """Saca el contenido del popover del comentario: lo que va después de
    'emerja:'/'aparezca:'/'tooltip-->'. Si no hay marcador claro, '' (→ fallback)."""
    for sep in ("emerja lo siguiente:", "emerja:", "aparezca:", "emerge:",
                "tooltip-->", "tooltip -->", "tooltip:", "globo:"):
        if sep in instruccion.lower():
            idx = instruccion.lower().index(sep) + len(sep)
            return instruccion[idx:].strip(" .–-")
    return ""


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
        if c["accion"] in _VARIANTE_PANEL:
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
            pares, consumidos = extraer_pares(el)
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
