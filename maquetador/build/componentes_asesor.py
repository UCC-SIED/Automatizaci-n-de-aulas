# -*- coding: utf-8 -*-
"""Construcción de componentes CidiLabs a partir de los pedidos del asesor.

Un extractor de pares (título, contenido) unificado alimenta a acordeón, tabs,
expander y flip card. Dos fuentes: una tabla de 1 columna con celdas alternadas
(título/contenido/título/contenido…) o párrafos "Nombre: contenido".
"""

import re

from bs4 import BeautifulSoup

_RE_NOMBRE_CONTENIDO = re.compile(r"^(.{2,60}?):\s+(.+)$", re.DOTALL)


def _celda(c) -> tuple:
    return (c.get_text(" ", strip=True), "".join(str(x) for x in c.children).strip())


def _es_titulo_corto(texto: str) -> bool:
    """Heurística de 'celda de título': texto breve (rótulo, no párrafo)."""
    return 0 < len(texto) <= 60


def pares_de_tabla(tabla) -> list:
    """Tabla de pares título/contenido → [(titulo, contenido_html)].

    Dos geometrías:
      · 1 columna con celdas alternadas (título / contenido / título / …).
      · Grilla de N columnas donde las filas alternan una fila de TÍTULOS y una
        fila de DESCRIPCIONES: cada título se empareja con la descripción de su
        misma columna (abajo), no con el título de al lado.
    """
    filas = [[_celda(c) for c in f.find_all(["td", "th"])]
             for f in tabla.find_all("tr")]
    filas = [f for f in filas if any(t for t, _ in f)]   # descartar filas vacías
    if not filas:
        return []
    ncols = max(len(f) for f in filas)

    # Grilla multi-columna con filas alternando títulos / descripciones.
    def _largo_medio(fila):
        return sum(len(t) for t, _ in fila) / max(1, len(fila))
    if ncols >= 2 and len(filas) >= 2 and len(filas) % 2 == 0 \
            and all(len(f) == ncols for f in filas):
        # Fila 0 = rótulos cortos; fila 1 = descripciones, claramente más largas.
        fila_titulos = all(_es_titulo_corto(t) for t, _ in filas[0])
        fila_desc = _largo_medio(filas[1]) > _largo_medio(filas[0]) * 1.5
        if fila_titulos and fila_desc:
            pares = []
            for r in range(0, len(filas), 2):
                for c in range(ncols):
                    pares.append((filas[r][c][0], filas[r + 1][c][1] or "&nbsp;"))
            return pares

    # Caso clásico: celdas en orden, alternando título / contenido.
    plano = [c for f in filas for c in f]
    return [(plano[i][0], plano[i + 1][1] or "&nbsp;")
            for i in range(0, len(plano) - 1, 2)]


def pares_de_texto(parrafos: list) -> list:
    """Párrafos 'Nombre: contenido' → [(nombre, contenido)]."""
    pares = []
    for p in parrafos:
        txt = p.get_text(" ", strip=True)
        if _PAT_EPIGRAFE.match(txt):      # "Tabla 1: …" es epígrafe, no un par
            continue
        m = _RE_NOMBRE_CONTENIDO.match(txt)
        if m:
            pares.append((m.group(1).strip(), m.group(2).strip()))
    return pares


# Etiquetas que forman el flujo de contenido de una sección. Se corta en
# cualquier otra cosa (un <div> ya es un componente armado: recuadro, panel…).
_TAGS_FLUJO = ("p", "ul", "ol", "table", "blockquote", "h3", "h4", "h5", "h6")


def _plano(texto: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", texto.lower())


# Epígrafe de figura/tabla/esquema. Va en negrita como un subtítulo, pero NO es
# un título de sección: si se lo toma como tal, el componente se traga la
# figura (pasó con "Figura 5. Síntesis de enfoques", que terminó de título de
# una solapa con la tabla adentro, y encima dejó sin ubicar la figura de
# diseño que tenía que reemplazarla).
_PAT_EPIGRAFE = re.compile(r"^(figura|tabla|esquema|nota)\s*\d*\s*[\.:]", re.I)


def _titulo_en_negrita_al_inicio(el):
    """Título que el asesor marcó poniendo en negrita SOLO las primeras
    palabras del párrafo, no todo.

    Caso real: "<strong>Principio N.° 1</strong>: Enfoque al cliente" — el
    comentario pedía "TABS horizontal (palabras en negrita)". Devuelve
    (titulo, resto_html) o (None, None).
    """
    if getattr(el, "name", None) != "p":
        return None, None
    hijos = [h for h in el.children
             if getattr(h, "name", None) or str(h).strip()]
    if not hijos or getattr(hijos[0], "name", None) not in ("strong", "b"):
        return None, None
    titulo = hijos[0].get_text(" ", strip=True)
    if not (2 <= len(titulo) <= 60):
        return None, None
    resto = "".join(str(h) for h in hijos[1:]).lstrip(" :–—-")
    if not BeautifulSoup(resto, "html.parser").get_text(strip=True):
        return None, None       # todo el párrafo era el título: no es prefijo
    return titulo, f"<p>{resto}</p>"


def _es_encabezado_de_seccion(el, modo: str = "auto") -> bool:
    """¿El elemento abre una sección?

    Tres formas de marcarlo, según lo que diga el comentario del asesor:
      · "subrayado": todo el párrafo subrayado.
      · "negrita":   el párrafo ARRANCA con las palabras en negrita y sigue
                     con el contenido ("Principio N.° 1: Enfoque al cliente").
      · "auto":      todo el párrafo subrayado o todo en negrita.
    """
    nombre = getattr(el, "name", None)
    if nombre in ("h1", "h2", "h3", "h4", "h5", "h6"):
        return modo != "subrayado"
    if nombre in ("ul", "ol"):
        # Mammoth a veces envuelve un subtítulo corto en negrita en una lista
        # de un solo ítem ("<ul><li><strong>ISO 14001</strong></li></ul>") en
        # vez de dejarlo como <p>, según la numeración interna de Word. Un
        # ítem así, solo en su lista, es en los hechos el mismo párrafo suelto.
        items = el.find_all("li", recursive=False)
        if len(items) != 1:
            return False
        el = items[0]
        nombre = "li"
    if nombre not in ("p", "li"):
        return False
    texto = el.get_text(" ", strip=True)
    if not texto or el.find("img") or _PAT_EPIGRAFE.match(texto):
        return False

    def _cubre(tags):
        if not tags:
            return False
        return _plano(" ".join(t.get_text(" ", strip=True) for t in tags)) == _plano(texto)

    if modo == "negrita" and _titulo_en_negrita_al_inicio(el)[0]:
        return True
    if len(texto) > 90:
        return False
    if _cubre(el.find_all("u")):
        return True
    if modo == "subrayado":
        return False
    return _cubre(el.find_all(["strong", "b"]))


def pares_de_secciones(el, modo: str = "auto", hasta=None) -> tuple:
    """Tramo de párrafos con subtítulos intercalados → (pares, consumidos).

    El asesor no arma una tabla: escribe el contenido corrido y marca los
    cortes. Cada subtítulo abre un panel y se lleva los párrafos que lo siguen.
    `modo` dice cómo están marcados (ver _es_encabezado_de_seccion).
    `hasta`, si se pasa, es el último elemento que debe entrar al componente
    (inclusive): el asesor a veces marca con el mismo comentario el principio
    Y el final del tramo, y sin este límite el armado sigue de largo por el
    resto de la página.
    """
    elementos, actual = [], el
    while actual is not None and getattr(actual, "name", None) in _TAGS_FLUJO:
        elementos.append(actual)
        if hasta is not None and actual is hasta:
            break
        actual = actual.find_next_sibling()

    # Lo anterior al primer subtítulo es introducción: queda fuera del panel.
    idx = next((i for i, e in enumerate(elementos)
                if _es_encabezado_de_seccion(e, modo)), None)
    if idx is None:
        return [], []

    pares, consumidos, titulo, cuerpo = [], [], None, []
    titulo_es_marcador_lista = False
    for e in elementos[idx:]:
        abre = _es_encabezado_de_seccion(e, modo)
        # Un "<ul><li><strong>…</strong></li></ul>" (ver _es_encabezado_de_
        # seccion) suele venir seguido, en el propio DOCX, de un <p> también
        # todo en negrita que es su bajada ("ISO 14001" → "Gestión
        # ambiental"): esa bajada es parte del MISMO título, no abre una
        # sección nueva.
        if abre and titulo_es_marcador_lista and not cuerpo:
            abre = False
        if abre:
            if titulo is not None:
                pares.append((titulo, "".join(cuerpo) or "&nbsp;"))
            # Con el título en negrita al inicio, lo que sigue en ESE mismo
            # párrafo ya es contenido del panel.
            prefijo, resto = ((None, None) if modo != "negrita"
                              else _titulo_en_negrita_al_inicio(e))
            if prefijo:
                titulo, cuerpo = prefijo, [resto]
            else:
                titulo, cuerpo = e.get_text(" ", strip=True), []
            titulo_es_marcador_lista = getattr(e, "name", None) in ("ul", "ol")
        else:
            cuerpo.append(str(e))
        consumidos.append(e)
    if titulo is not None:
        pares.append((titulo, "".join(cuerpo) or "&nbsp;"))
    return (pares, consumidos) if len(pares) >= 2 else ([], [])


def extraer_pares(el, instruccion: str = "", hasta=None):
    """Desde el elemento anclado → (pares, consumidos). ([], []) si <2 pares.

    `hasta`: último elemento que debe entrar al componente (inclusive), si el
    comentario del asesor marca también el final del tramo (ver
    pares_de_secciones).

    `consumidos` son los elementos del soup que el componente reemplaza: el
    primero se sustituye por el componente y el resto se elimina (así no quedan
    párrafos duplicados cuando el componente se arma desde varios párrafos).

    1) Tabla asociada (el mismo, o su hermano <table> siguiente).
    2) Lista <ul>/<ol> cuyos <li> son 'Nombre: contenido'.
    3) Si no, el elemento + hermanos <p>/<li> consecutivos con 'Nombre: contenido'.
    """
    # 1) Tabla
    if el.name == "table":
        tabla, consumidos_tabla = el, [el]
    else:
        t = el.find_next_sibling("table")
        tabla, consumidos_tabla = (t, [el, t]) if t is not None else (None, None)
    if tabla is not None:
        pares = pares_de_tabla(tabla)
        if len(pares) >= 2:
            return pares, consumidos_tabla

    # 2) Lista <ul>/<ol> con ítems 'Nombre: contenido' cuando el asesor ancla el
    #    comentario SOBRE la lista misma o sobre uno de sus <li>. No se salta a
    #    una lista siguiente no relacionada (sería contenido explicativo, no
    #    pares frente/dorso).
    lista = None
    if el.name in ("ul", "ol"):
        lista = el
    elif el.name == "li" and getattr(el.parent, "name", None) in ("ul", "ol"):
        lista = el.parent
    if lista is not None:
        items = lista.find_all("li", recursive=False)
        pares = pares_de_texto(items)
        if len(pares) >= 2:
            consumidos = [lista] if el in (lista, *lista.contents) else [el, lista]
            return pares, consumidos

    # 2.5) Tramo de párrafos con subtítulos intercalados. Va ANTES del extractor
    #      "Nombre: contenido" a propósito: un subtítulo como "El diagrama de
    #      Ishikawa: explorar posibles causas" también encaja en ese patrón, y
    #      salía un panel con el título cortado a la mitad y sin los párrafos
    #      que le seguían.
    # Cada asesor escribe el pedido distinto ("títulos subrayados", "palabras
    # en negrita", "poner Principio 1 / Principio 2 y el título dentro del
    # TAB"…). En vez de atarse a la redacción: si el comentario nombra una
    # forma, se respeta; si no, se prueban todas y gana la que dé secciones.
    plano = _plano(instruccion)
    if "subrayad" in plano:
        modos = ("subrayado",)
    elif "negrita" in plano:
        modos = ("negrita",)
    else:
        modos = ("auto", "negrita")
    for modo in modos:
        pares, consumidos = pares_de_secciones(el, modo=modo, hasta=hasta)
        if len(pares) >= 2:
            return pares, consumidos

    # 3) Texto
    parrafos, actual = [], el
    while actual is not None and getattr(actual, "name", None) in ("p", "li"):
        parrafos.append(actual)
        actual = actual.find_next_sibling()
    pares = pares_de_texto(parrafos)
    if len(pares) >= 2:
        consumidos = [p for p in parrafos
                      if _RE_NOMBRE_CONTENIDO.match(p.get_text(" ", strip=True))]
        return pares, consumidos
    return [], []


def construir_panels(pares: list, variante: str = "dp-expander-default") -> str:
    """Panel colapsable CidiLabs. Misma estructura para acordeón
    (dp-accordion-default), expander (dp-expander-default) y tabs
    (dp-tabs-buttons / dp-tabs-buttons-vertical); cambia la variante.

    Los colores son los del catálogo de snippets UCC y los de las aulas
    maquetadas a mano: base primary, activo y hover secondary.
    """
    grupos = "\n".join(
        '<div class="dp-panel-group">\n'
        f'<h3 class="dp-panel-heading">{t}</h3>\n'
        f'<div class="dp-panel-content">{c}</div>\n</div>'
        for t, c in pares)
    return (f'<div class="dp-panels-wrapper {variante} '
            'dp-panel-color-dp-primary dp-panel-active-color-dp-secondary '
            'dp-panel-hover-color-dp-secondary">\n'
            f'{grupos}\n</div>')


def construir_flipcards(pares: list) -> str:
    """Flip cards CidiLabs: frente = título (negrita), dorso = contenido."""
    cards = "\n".join(
        '<div class="dp-flip-card">\n<div class="dp-flip-card-inner">\n'
        '<div class="dp-front-card">'
        '<div class="dp-card card h-100 dp-shadow-b3 text-center">'
        f'<p><strong>{t}</strong></p></div></div>\n'
        '<div class="dp-back-card">'
        '<div class="dp-card card h-100 text-center dp-shadow-b3" style="padding: 16px;">'
        f'<p style="text-align: left;">{c}</p></div></div>\n'
        '</div>\n</div>'
        for t, c in pares)
    return f'<div class="row justify-content-center">\n{cards}\n</div>'


# Palabras que no aportan inicial a una sigla ("Sistema de Gestión de la
# Calidad" → SGC).
_VACIAS_SIGLA = {"de", "del", "la", "las", "el", "los", "y", "e", "en", "a",
                 "para", "por", "con", "al"}


def sigla_de(contenido: str) -> str:
    """Sigla que forman las iniciales de un término ('SGC')."""
    palabras = [w for w in re.findall(r"[^\W\d_]+", contenido, re.UNICODE)
                if w.lower() not in _VACIAS_SIGLA]
    return "".join(w[0].upper() for w in palabras)


def disparador_tooltip(texto: str, contenido: str) -> str:
    """Qué palabra del texto debe abrir el tooltip.

    El asesor ancla el comentario sobre TODO el párrafo y escribe aparte qué
    tiene que emerger. Lo que hay que marcar es el término que ese contenido
    explica: primero la sigla que forman sus iniciales (SGC ← Sistema de
    Gestión de la Calidad), y si no, el término escrito completo. Devuelve ""
    si no aparece ninguno: marcar el párrafo entero como disparador —que es lo
    que pasaba— deja la página con un párrafo convertido en link.
    """
    sigla = sigla_de(contenido)
    if len(sigla) >= 2 and re.search(rf"\b{re.escape(sigla)}\b", texto):
        return sigla
    if contenido and contenido.lower() in texto.lower():
        i = texto.lower().index(contenido.lower())
        return texto[i:i + len(contenido)]
    return ""


def construir_tooltip(palabra: str, contenido: str, n: int) -> str:
    """Tooltip CidiLabs: el globo gris chico que aparece sobre un término.

    Distinto del popover (que es una ficha grande y se dispara con clic): el
    disparador y el contenido van juntos dentro del mismo contenedor.
    """
    return (f'<span class="dp-tooltip-container">'
            f'<a id="dpPopup{n}" class="dp-tooltip-trigger dp-popup-trigger" '
            f'role="button" href="#dpPopup{n}tooltip" aria-describedby="" '
            f'data-bs-toggle="tooltip">{palabra}</a> '
            f'<span id="dpPopup{n}tooltip" '
            'class="dp-tooltip-content dp-popup-content" '
            'style="background-color: #545454; color: #ffffff; '
            'padding: 2px 5px; border-radius: 3px;" role="tooltip">'
            f'{contenido}</span></span>')


def construir_popover(palabra: str, contenido: str, n: int) -> tuple:
    """Popover CidiLabs: trigger (la palabra) + content (lo que emerge)."""
    trigger = (f'<a class="dp-popover-trigger" href="#dpPopup{n}Content" '
               f'id="dpPopup{n}" aria-describedby="dpPopup{n}Content">{palabra}</a>')
    content = (f'<div class="dp-popover-content dp-popup-content" id="dpPopup{n}Content" '
               'style="border: 1px solid #A9A9A9; background: #f7f7f7; padding: 10px; '
               'width: 600px; max-width: 100%; margin: auto; border-radius: 3px;">'
               f'<p>{contenido}</p></div>')
    return trigger, content


def aplicar_cita(el) -> None:
    """Sangra el párrafo anclado (sin caja, pedido del usuario)."""
    estilo = el.get("style", "").rstrip("; ")
    el["style"] = (estilo + "; " if estilo else "") + "margin-left: 40px;"
