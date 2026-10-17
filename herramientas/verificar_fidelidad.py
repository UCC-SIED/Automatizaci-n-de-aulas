# -*- coding: utf-8 -*-
"""Compara lo publicado contra el DOCX del que salió.

Responde dos preguntas que hasta ahora había que mirar a ojo:

  · ¿Se publicó texto que NO está en el material del docente? Es lo que
    disparó esta herramienta: "fijate que hay texto diferente, ¿por qué?,
    he notado eso como que inventaste o tomaste de otro lado". Lo normal
    es que sea texto del aula base que quedó sin reemplazar, o un párrafo
    duplicado por un componente que se armó dos veces.

  · ¿Se perdió texto del DOCX por el camino? ("te faltó todo esto").

No es un test: es una herramienta de revisión. Se corre contra un .imscc
ya generado y la carpeta del curso.

    python herramientas/verificar_fidelidad.py output/Materia.imscc C:\\_src\\curso

Lo que informa son CANDIDATOS. Hay texto publicado que legítimamente no
está en el DOCX (los rótulos del aula base, los títulos de los
componentes) y texto del DOCX que legítimamente no se publica (las
indicaciones para el tutor, los marcadores de video). Por eso lo que se
imprime hay que leerlo, no tomarlo como error.
"""

import re
import sys
import unicodedata
import zipfile
from pathlib import Path

import mammoth
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from maquetador.ingest.folder_scanner import escanear      # noqa: E402
from maquetador.ingest.docx_comments import extraer_comentarios  # noqa: E402
from maquetador.ingest.xlsx_parser import parsear_estructura  # noqa: E402

# Frases que el aula base trae puestas y no vienen del DOCX: no son texto
# inventado, son el molde.
_DEL_AULA_BASE = (
    "module item completion", "te damos la bienvenida", "comenzar",
    "equipo docente", "programa", "módulos", "foro de apertura",
    "actividad obligatoria", "actividad final integradora", "bibliografía",
    "obligatoria", "sugerida y complementaria", "profesor autor", "tutores",
    "sección 1", "acceso al documento", "acceso al artículo", "ver video",
    "descubrí leyendo", "no pases de largo", "auriculares on",
    "rúbrica de evaluación", "visión general", "introducción", "objetivos",
    "conclusión", "referencias", "nota", "figura", "tabla",
)

_MIN_PALABRAS = 8        # menos que esto es un rótulo, no un párrafo

# Páginas que el aula base trae enteras y que ningún curso reemplaza: su
# texto no sale de ningún DOCX y no tiene sentido compararlo.
_PAGINAS_DEL_MOLDE = ("calificacion-de-la-asignatura",)


def _normalizar(texto: str) -> str:
    t = unicodedata.normalize("NFKD", texto or "")
    t = "".join(c for c in t if not unicodedata.combining(c))
    t = t.replace("\u201c", '"').replace("\u201d", '"')
    t = t.replace("\u2018", "'").replace("\u2019", "'")
    t = t.replace("\u2013", "-").replace("\u2014", "-").replace("\u2026", "...")
    t = re.sub(r"[^\w\s]", " ", t.lower())
    return re.sub(r"\s+", " ", t).strip()


def _frases(texto: str) -> list:
    """El texto partido en oraciones comparables."""
    crudas = re.split(r"(?<=[.;:?!])\s+|\n+", texto or "")
    salida = []
    for frase in crudas:
        n = _normalizar(frase)
        if len(n.split()) >= _MIN_PALABRAS:
            salida.append(n)
    return salida


def _texto_del_docx(path: Path) -> str:
    with open(path, "rb") as f:
        html = mammoth.convert_to_html(f).value
    return BeautifulSoup(html, "html.parser").get_text("\n", strip=True)


def _paginas_del_paquete(imscc: Path) -> dict:
    """El texto de cada página, foro y actividad del paquete.

    Los foros no son .html: viven dentro del XML del topic, en un <text>
    escapado. Sin leerlos, la consigna del foro de apertura figuraba como
    "no se publicó" aunque estuviera cargada.
    """
    from html import unescape
    paginas = {}
    with zipfile.ZipFile(imscc) as z:
        for nombre in z.namelist():
            crudo = None
            if nombre.endswith(".html"):
                crudo = z.read(nombre).decode("utf-8", "replace")
            elif nombre.endswith(".xml"):
                xml = z.read(nombre).decode("utf-8", "replace")
                m = re.search(r'<text texttype="text/html">(.*?)</text>',
                              xml, re.DOTALL)
                if m:
                    crudo = unescape(m.group(1))
            if crudo is None:
                continue
            paginas[nombre] = BeautifulSoup(
                crudo, "html.parser").get_text("\n", strip=True)
    return paginas


def _es_del_molde(frase: str) -> bool:
    return any(k in frase for k in (_normalizar(x) for x in _DEL_AULA_BASE))


def revisar(imscc: Path, carpeta: Path) -> int:
    inv = escanear(carpeta)
    fuentes = list(inv.docx_modulos.values()) + [
        p for _n, p in inv.actividades] + [p for _n, p in inv.foros]
    fuentes += inv.programa + inv.biografia
    # El programa cuenta como material (nada de lo suyo es "inventado")
    # pero NO se espera publicado: va adjunto como PDF. Sin separarlo, sus
    # objetivos y competencias llenaban la lista de "texto perdido".
    programas = {p for p in inv.programa}
    texto_fuente, corrido, solo_de_referencia = set(), [], set()
    for p in fuentes:
        if p.suffix.lower() != ".docx":
            continue
        try:
            crudo = _texto_del_docx(p)
        except Exception as e:                              # pragma: no cover
            print(f"  (no pude leer {p.name}: {e})")
            continue
        frases = _frases(crudo)
        texto_fuente.update(frases)
        # "Texto alternativo: …" describe una figura y va al atributo alt,
        # no al cuerpo: no es texto perdido.
        solo_de_referencia.update(
            f for f in frases if f.startswith(("texto alternativo", "nota ")))
        if p in programas:
            solo_de_referencia.update(frases)
        corrido.append(_normalizar(crudo))
        # Lo que el asesor escribe en un globo tambien es material suyo: el
        # llamado a la acción de una actividad sugerida sale del comentario
        # y no del cuerpo del DOCX. Sin esto figuraba como inventado.
        # Las indicaciones del asesor son material suyo, pero son para
        # maquetar: nunca se publican. Cuentan para no denunciar como
        # inventado lo que sale de ellas, y no cuentan como texto perdido.
        try:
            for c in extraer_comentarios(p):
                instruccion = str(c.get("instruccion") or "")
                frases_c = _frases(instruccion)
                texto_fuente.update(frases_c)
                solo_de_referencia.update(frases_c)
                corrido.append(_normalizar(instruccion))
        except Exception:                                   # pragma: no cover
            pass
    # El material entero como un solo texto normalizado. Comparar frase
    # contra frase da falsos positivos cuando el corte de oraciones no
    # coincide —una comilla o un ":" de más y la misma frase queda partida
    # distinto—, y entonces texto que SÍ está en el DOCX se denuncia como
    # inventado. Buscarla acá adentro no depende del corte.
    # La planilla también es material del asesor: de ahí salen los títulos
    # de módulo que el syllabus publica, y sin ella figuraban como texto
    # aparecido de la nada.
    if inv.estructura_xlsx:
        try:
            spec = parsear_estructura(inv.estructura_xlsx)
            rotulos = [spec.nombre or ""]
            for mod in spec.modulos:
                rotulos.append(mod.titulo or "")
                rotulos += [i.titulo or "" for i in mod.items]
            corrido.append(_normalizar(" \n ".join(rotulos)))
        except Exception as e:                              # pragma: no cover
            print(f"  (no pude leer la planilla: {e})")

    fuente_corrida = " \n ".join(corrido)
    if not texto_fuente:
        print("No encontré material de origen que comparar.")
        return 1

    paginas = _paginas_del_paquete(imscc)
    publicado = set()
    sospechosas = []
    for nombre, texto in sorted(paginas.items()):
        del_molde = any(k in nombre for k in _PAGINAS_DEL_MOLDE)
        for frase in _frases(texto):
            if del_molde:
                publicado.add(frase)
                continue
            publicado.add(frase)
            if frase in texto_fuente or _es_del_molde(frase):
                continue
            if frase in fuente_corrida:
                continue
            sospechosas.append((nombre, frase))

    publicado_corrido = " \n ".join(
        _normalizar(t) for t in paginas.values())
    perdidas = [f for f in texto_fuente
                if f not in publicado and f not in publicado_corrido
                and f not in solo_de_referencia]

    print(f"\nFrases comparadas: {len(texto_fuente)} del material, "
          f"{len(publicado)} publicadas.")
    print(f"\n— PUBLICADO QUE NO ESTÁ EN EL MATERIAL ({len(sospechosas)}) —")
    for nombre, frase in sospechosas[:40]:
        print(f"  [{Path(nombre).name[:40]}] {frase[:110]}")
    if len(sospechosas) > 40:
        print(f"  … y {len(sospechosas) - 40} más")

    print(f"\n— DEL MATERIAL QUE NO SE PUBLICÓ ({len(perdidas)}) —")
    for frase in perdidas[:40]:
        print(f"  {frase[:110]}")
    if len(perdidas) > 40:
        print(f"  … y {len(perdidas) - 40} más")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    sys.exit(revisar(Path(sys.argv[1]), Path(sys.argv[2])))
