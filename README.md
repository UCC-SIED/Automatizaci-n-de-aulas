# Automatización de Maquetación de Aulas (UCC)

Convierte los materiales que envían los asesores (Word de contenidos, planilla de
estructura, imágenes, foros, actividades) en un paquete **`.imscc`** listo para
importar en **Canvas LMS**, replicando el diseño institucional **CidiLabs /
DesignPLUS** de la Universidad Católica de Córdoba.

El sistema es **genérico**: no tiene scripts por asignatura. Se adapta a los
distintos formatos de entrega de cada asesor y usa la **planilla de montaje como
fuente de verdad** (qué páginas van y qué recursos dejar en cada módulo).

> 📖 Documentación detallada en la [**Wiki**](../../wiki).

---

## Qué hace

A partir de una carpeta de curso:

1. **Escanea** la carpeta (tolerante a distintas convenciones) y clasifica cada
   archivo por rol (planilla, Word modulares, foros, actividades, fotos, figuras
   de diseño, programa…).
2. **Lee la planilla** de estructura (autodetecta formato viejo y nuevo): código,
   docentes, módulos, páginas y qué recursos pide cada módulo.
3. **Corta los Word** por sección (intro, objetivos, páginas, conclusión,
   bibliografía) y aplica el diseño UCC.
4. **Genera el `.imscc`**: clona el aula base elegida (educación o posgrado) y
   reemplaza quirúrgicamente el contenido, dejando solo los recursos que la
   planilla pide.

## Requisitos

- Python 3.11+
- `pip install -r requirements.txt`
  (mammoth, beautifulsoup4, openpyxl, python-docx, lxml, Flask)

## Uso

### Línea de comandos

```bash
# Analizar (muestra el plan, sin generar)
python -m maquetador.cli "ruta/al/curso" --tema posgrado

# Generar el .imscc (educacion | posgrado)
python -m maquetador.cli "ruta/al/curso" --tema posgrado --generar
```

El `--tema` (aula base) **siempre lo elige la persona**: `educacion` (Educación a
Distancia) o `posgrado`.

### Web interna

```bash
python -m maquetador.web.app    # http://localhost:5000
```

Subir un ZIP del curso → ver el plan (módulos, páginas, recursos, avisos) →
elegir aula base → generar y descargar el `.imscc`.

## Importar en Canvas

> **Importante:** elegí el tipo **"Paquete de exportación de asignaturas de
> Canvas"** (NO "Common Cartridge"; ese modo ignora los módulos).
> Importá en un **curso nuevo/vacío** (reimportar sobre un curso con contenido
> no pisa la página de inicio).

## Estructura del proyecto

```
maquetador/
  ingest/       escaneo de carpetas, parser de planilla, perfilado de DOCX,
                reconciliación, lectura de comentarios del DOCX
  extract/      segmentación del DOCX a HTML por sección
  build/        snippets CidiLabs, plantillas de página, generador del .imscc,
                bibliografía
  web/          app Flask interna
  models.py     modelo canónico (CourseSpec, ModuloCurso, ItemCurso, Issue)
  cli.py        entrada por consola
processors/     cidilabs_builder.py: utilidades de diseño CidiLabs (dp-wrapper)
scripts/        auditar_fidelidad.py: valida XML + compara fidelidad vs aulas a mano
tests/          suite pytest
legacy/         código de la versión anterior (no lo usa el tool; archivado)
Elementos de las aulas/_extracted_educacion , _extracted_posgrado   aulas base
```

## Qué identifica y maqueta

- **Recuadros / CTAs** según el texto o el comentario del asesor: Lectura, Video,
  Imagen, Atención, Para reflexionar, Ejemplo…
- **Foros y actividades**: la consigna va en el **recurso** (no en la página),
  conservando el diseño base (banner + navegación + h2 + contenido).
- **Bibliografía** con la estructura oficial (columnas con icono); clasifica
  Obligatoria / Sugerida solo si el DOCX lo trae.
- **Programa (Syllabus)**: enlaza el PDF + índice de módulos/páginas +
  bibliografía consolidada.
- **Página de inicio**: equipo docente (foto, nombre, bio, género) y tutor.
- **Comentarios del DOCX** (los del margen): aplica los pedidos de maquetación
  (subtítulo, recuadro, sin recuadro) y avisa los manuales (acordeón, flip card,
  faltantes).
- **Acordeones** ("Expander") y **flip cards** desde el contenido.
- **Genially**: incrusta si hay URL; si es una descripción, marca dónde va.
- **Figuras de DISEÑO**: reemplazan a las imágenes del docente (sin duplicar).
- **Intro + objetivos** del módulo → página "Introducción MX".
- **Limpieza**: borra del aula base los recursos/módulos que la planilla no pide;
  **clona** un módulo si el curso tiene más módulos que la base.

## Calidad

`python scripts/auditar_fidelidad.py` valida el XML de cada paquete (un `&` sin escapar
rompe la importación en Canvas) y compara la fidelidad de las páginas contra las
aulas hechas a mano. Suite de 6 cursos de referencia (~88% de páginas idénticas;
el resto son decisiones editoriales que se resuelven en revisión).

### Tests y cobertura

```bash
pytest tests/ --cov=maquetador --cov-report=xml   # correr la suite
python scripts/cobertura.py                        # informe de cobertura
```

`scripts/cobertura.py` rankea los módulos por **líneas sin cubrir** (dónde está
el riesgo real, no el porcentaje plano) y corta si la cobertura total baja del
piso definido en el script. Corre igual en local y en CI, sin depender de
ningún servicio externo. El piso es un trinquete: se sube a medida que la
cobertura mejora, nunca se baja.

### Curso sintético de prueba

El material real de asesoría (`Aulas a generar/`) y los paquetes generados
(`output/`) no se versionan. Para que la suite no dependa de tenerlos,
`tests/fixtures/curso_sintetico.py` **construye por código** una entrega
mínima pero completa —planilla, DOCX de dos módulos, foro, actividad, guion,
figuras, foto del docente y material descartable— y de ahí se genera un
`.imscc` real en cada corrida.

Se genera en vez de commitearse porque un `.docx` es un ZIP: como binario
sería un blob imposible de revisar en un diff o de ajustar sin abrir Word.

Los tests usan el material real cuando está y el sintético cuando no, así que
el flujo local no cambia. Quedan salteados solo los tests atados a cursos
reales concretos, que no tiene sentido sintetizar.

## Notas

- La elección del aula base es **siempre manual** (decisión del maquetador).
- La **planilla de montaje manda**: define páginas y qué recursos van/no van.
- Los componentes que requieren el editor de DesignPLUS (algunos Genially, flip
  cards) se marcan/avisan para revisión.

🤖 Documentado con ayuda de [Claude Code](https://claude.com/claude-code)
