# -*- coding: utf-8 -*-
"""Informe de cobertura propio, sin depender de ningún servicio externo.

Lee el coverage.xml que ya genera pytest-cov y hace tres cosas:

  1) Rankea los módulos por **líneas sin cubrir**, no por porcentaje. Un
     archivo de 20 líneas al 50% deja 10 líneas sueltas; imscc_builder.py al
     8% deja 861. El porcentaje solo esconde dónde está el riesgo real.
  2) Corta el build si la cobertura total baja del piso (--piso). Esto es lo
     que Codecov nunca hizo acá: avisaba, pero no frenaba nada.
  3) Si corre dentro de GitHub Actions, escribe el informe en el resumen del
     job ($GITHUB_STEP_SUMMARY), que queda visible en la página de la corrida
     sin tener que abrir logs ni descargar artifacts.

Uso:
    python scripts/cobertura.py                  # piso por defecto
    python scripts/cobertura.py --piso 35        # exigir más
    python scripts/cobertura.py --top 5          # ver solo los 5 peores
"""
import argparse
import io
import os
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                                  errors="replace")

# Piso actual. Subirlo a medida que la cobertura mejore: es un trinquete, no
# una meta — solo debería moverse hacia arriba.
#   30% → 55%  al incorporar el curso sintético, que hizo que el generador
#              (imscc_builder) pasara de 8,8% a ~64%.
PISO_POR_DEFECTO = 55.0


def leer_cobertura(path: Path) -> list:
    """[(archivo, sentencias, cubiertas)] a partir del XML de coverage.py."""
    raiz = ET.parse(path).getroot()
    modulos = []
    for clase in raiz.iter("class"):
        lineas = clase.findall("./lines/line")
        if not lineas:
            continue
        total = len(lineas)
        cubiertas = sum(1 for ln in lineas if int(ln.get("hits", 0)) > 0)
        modulos.append((clase.get("filename", "?"), total, cubiertas))
    return modulos


def _pct(cubiertas: int, total: int) -> float:
    return 100.0 * cubiertas / total if total else 100.0


def construir_informe(modulos: list, top: int) -> tuple:
    """Devuelve (porcentaje_total, líneas_informe, filas_tabla_markdown)."""
    total = sum(m[1] for m in modulos)
    cubiertas = sum(m[2] for m in modulos)
    pct_total = _pct(cubiertas, total)

    # Orden por riesgo: primero el que más líneas sin probar acumula.
    peores = sorted(modulos, key=lambda m: m[1] - m[2], reverse=True)
    peores = [m for m in peores if m[1] - m[2] > 0][:top]

    L = [f"Cobertura total: {pct_total:.2f}%  "
         f"({cubiertas} de {total} líneas ejecutadas por los tests)", ""]
    filas = []
    if peores:
        L.append(f"Módulos con más líneas sin cubrir (top {len(peores)}):")
        L.append(f"  {'módulo':<48} {'sin cubrir':>10} {'cobertura':>10}")
        for archivo, tot, cub in peores:
            L.append(f"  {archivo:<48} {tot - cub:>10} {_pct(cub, tot):>9.1f}%")
            filas.append((archivo, tot - cub, _pct(cub, tot)))
    return pct_total, L, filas


def escribir_resumen_github(pct: float, piso: float, filas: list) -> None:
    """Publica el informe en el resumen del job (solo dentro de Actions)."""
    destino = os.environ.get("GITHUB_STEP_SUMMARY")
    if not destino:
        return
    estado = "✅" if pct >= piso else "❌"
    md = [f"## {estado} Cobertura: {pct:.2f}%",
          "", f"Piso exigido: **{piso:.2f}%**", ""]
    if filas:
        md += ["### Dónde está el riesgo", "",
               "Ordenado por líneas sin probar, no por porcentaje.", "",
               "| Módulo | Líneas sin cubrir | Cobertura |",
               "|---|---:|---:|"]
        md += [f"| `{a}` | {n} | {p:.1f}% |" for a, n, p in filas]
    with open(destino, "a", encoding="utf-8") as fh:
        fh.write("\n".join(md) + "\n")


def main() -> int:
    ap = argparse.ArgumentParser(description="Informe de cobertura del proyecto.")
    ap.add_argument("--xml", default="coverage.xml",
                    help="Ruta del coverage.xml (lo genera pytest --cov-report=xml)")
    ap.add_argument("--piso", type=float, default=PISO_POR_DEFECTO,
                    help=f"Cobertura mínima aceptable (default: {PISO_POR_DEFECTO})")
    ap.add_argument("--top", type=int, default=10,
                    help="Cuántos módulos riesgosos listar (default: 10)")
    args = ap.parse_args()

    xml = Path(args.xml)
    if not xml.is_file():
        print(f"⛔ No encuentro {xml}. Corré primero:")
        print("   pytest tests/ --cov=maquetador --cov-report=xml")
        return 1

    pct, lineas, filas = construir_informe(leer_cobertura(xml), args.top)
    print("\n".join(lineas))
    escribir_resumen_github(pct, args.piso, filas)

    print()
    if pct < args.piso:
        print(f"⛔ La cobertura ({pct:.2f}%) bajó del piso exigido "
              f"({args.piso:.2f}%). Agregá tests o justificá el cambio.")
        return 1
    print(f"✅ Cobertura {pct:.2f}% — por encima del piso ({args.piso:.2f}%).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
