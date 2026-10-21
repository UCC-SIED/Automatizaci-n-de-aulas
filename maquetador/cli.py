# -*- coding: utf-8 -*-
"""CLI del maquetador.

    python -m maquetador.cli "ruta/a/carpeta del curso" [--tema educacion|posgrado]

Analiza la carpeta tal como la envía asesoría y produce el plan de
maquetación (texto en consola + JSON en output/planes/). La generación del
.imscc a partir del plan llega en la fase siguiente.
"""

import argparse
import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from maquetador.ingest.folder_scanner import escanear
from maquetador.ingest.xlsx_parser import parsear_estructura
from maquetador.ingest.reconciler import reconciliar
from maquetador.models import CourseSpec, Issue, Severidad
from maquetador.plan import generar_reporte_texto, guardar_plan, TEMAS_DISPONIBLES


def analizar_curso(carpeta: Path, tema: str = "") -> CourseSpec:
    inv = escanear(carpeta)
    if inv.estructura_xlsx:
        spec = parsear_estructura(inv.estructura_xlsx)
    else:
        spec = CourseSpec(nombre=inv.nombre_curso)
    spec.tema = tema
    if not tema:
        spec.issues.append(Issue(Severidad.BLOQUEANTE,
            "Falta elegir el aula base: --tema educacion (Educación a Distancia) "
            "o --tema posgrado."))
    return reconciliar(spec, inv)


def main():
    # UTF-8 en consola Windows (solo cuando corre como CLI, no al importar)
    if hasattr(sys.stdout, "buffer"):
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                                      errors="replace")
    parser = argparse.ArgumentParser(
        description="Analiza una carpeta de curso y genera el plan de maquetación.")
    parser.add_argument("carpeta", help="Carpeta del curso (como llega de asesoría)")
    parser.add_argument("--tema", choices=TEMAS_DISPONIBLES, default="",
                        help="Aula base a usar: educacion | posgrado")
    parser.add_argument("--salida", default="output/planes",
                        help="Carpeta donde guardar el plan JSON")
    parser.add_argument("--extraer", action="store_true",
                        help="Además del plan, extraer el HTML de cada sección "
                             "y mostrar el resumen de extracción")
    parser.add_argument("--video", action="append", default=[],
                        metavar="PAGINA=MEDIA_ID",
                        help="Video de Canvas Studio que llego despues "
                             "de armar el aula: --video 1.4.1=<id> o "
                             "--video inicio=<id>. Acepta el id pelado "
                             "(<uuid>-<numero>) o el iframe entero.")
    parser.add_argument("--audio", action="append", default=[],
                        metavar="AUDIO=MEDIA_ID",
                        help="Audio de Canvas Studio para el recuadro "
                             "\"Embebido - Podcast\": --audio \"M1 "
                             "Dispositivos IoT=<id>\" (tambien vale el "
                             "numero de la pagina). Sin esto el recuadro "
                             "sale con el MP3 del paquete.")
    parser.add_argument("--afi-url", default="", metavar="URL",
                        help="Link del archivo de la herramienta de la "
                             "AFI ya subido al aula, para el iframe. Solo "
                             "hace falta si $IMS-CC-FILEBASE$ no resuelve.")
    parser.add_argument("--banners", default="", metavar="ZIP",
                        help="ZIP (o carpeta) con los banners del plugin "
                             "de Figma. Los archivos van nombrados por la "
                             "numeracion de la pagina: 1.3.1.png, M2.png.")
    parser.add_argument("--inferir-componentes", action="store_true",
                        help="Deducir componentes del texto (un parrafo que "
                             "arranca con \"es importante señalar\" sale como "
                             "recuadro de atencion, uno con \"te invito a "
                             "leer\" como CTA de lectura). Apagado por "
                             "defecto: los componentes salen solo cuando el "
                             "asesor los pide. Se usa con el material viejo, "
                             "que no trae esas marcas.")
    parser.add_argument("--generar", action="store_true",
                        help="Generar el paquete .imscc (implica --extraer). "
                             "Requiere --tema y que no haya issues bloqueantes.")
    args = parser.parse_args()
    if args.generar:
        args.extraer = True

    carpeta = Path(args.carpeta)
    if not carpeta.is_dir():
        print(f"⛔ No existe la carpeta: {carpeta}")
        sys.exit(1)

    spec = analizar_curso(carpeta, args.tema)
    for par in args.video:
        from maquetador.build.snippets import media_id_de_studio
        clave, _, valor = par.partition("=")
        media_id = media_id_de_studio(valor)
        if not media_id:
            print(f"⛔ --video {par}: no reconozco un id de Canvas Studio "
                  "ahi. Va el id del medio (<uuid>-<numero>) o el iframe que "
                  "copias desde Canvas.")
            sys.exit(1)
        spec.videos_studio[clave.strip().strip(".")] = media_id
    for par in args.audio:
        from maquetador.build.snippets import media_id_de_studio
        clave, _, valor = par.partition("=")
        media_id = media_id_de_studio(valor)
        if not media_id:
            print(f"⛔ --audio {par}: no reconozco un id de Canvas Studio "
                  "ahi. Va el id del medio (<uuid>-<numero>) o el iframe que "
                  "copias desde Canvas.")
            sys.exit(1)
        spec.audios_studio[clave.strip().strip(".")] = media_id
    spec.afi_url = args.afi_url.strip()
    spec.banners = args.banners.strip()
    if args.inferir_componentes:
        # Interruptor global del modulo: vale para toda esta corrida.
        from maquetador.build import snippets
        snippets.INFERIR_COMPONENTES_POR_TEXTO = True
    print(generar_reporte_texto(spec))

    media = {}
    if args.extraer:
        from maquetador.extract.extractor import extraer_contenido, resumen_extraccion
        media = extraer_contenido(spec)
        print("\n— EXTRACCIÓN DE CONTENIDO —")
        print(resumen_extraccion(spec))
        print(f"\nImágenes embebidas extraídas: {len(media)}")

    path = guardar_plan(spec, Path(args.salida))
    print(f"\nPlan guardado en: {path}")

    if args.generar:
        from maquetador.models import Severidad
        bloqueantes = [s for i in spec.todos_los_items() for s in i.issues
                       if s.severidad == Severidad.BLOQUEANTE]
        bloqueantes += [s for s in spec.issues if s.severidad == Severidad.BLOQUEANTE]
        if bloqueantes:
            print(f"\n⛔ No genero el paquete: hay {len(bloqueantes)} issues "
                  "bloqueantes (ver arriba). Resolvelos o ajustá el plan.")
            sys.exit(2)
        from maquetador.build.imscc_builder import generar_imscc
        salida = generar_imscc(spec, media, Path("output"))
        print(f"\n📦 Paquete .imscc generado: {salida}")
        if spec.issues:
            print("Avisos de generación:")
            for s in spec.issues:
                print(f"  - [{s.severidad.value}] {s.mensaje}")


if __name__ == "__main__":
    main()
