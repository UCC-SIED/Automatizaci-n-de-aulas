# Traspaso del chat online a local

**Fecha de traspaso:** 2026-09-10
**Motivo:** el chat online (`claude.ai/code/session_018VQwuSe4VxojJHFCTxtpH1`) dejó
de responder. Se recrea el estado de trabajo en local.

**Ubicación del repo:** `C:\SIED` (disco local).
El original quedó en `\\store-ad\$REF4785\jonathan.guillen\Desktop\ProyectoSIED`
(share de red) y **se puede borrar** una vez confirmado que `C:\SIED` anda.

Este archivo es el resumen con las claves para seguir sin perder contexto.

---

## 1. Qué se hizo al traer todo a local (2026-09-10)

1. Se descomprimió `Automatizaci-n-de-aulas-main.zip` (descarga de la rama `main`
   de GitHub) y se aplanó el contenido.
2. Se inicializó `git` y se conectó al repo real:
   `origin = https://github.com/UCC-SIED/Automatizaci-n-de-aulas.git` (repo
   **público**; `g0niii/Automatizaci-n-de-aulas` redirige al mismo).
3. `git reset --hard origin/develop`: **la carpeta quedó parada en `develop`**,
   que es donde vivía el trabajo del chat online (el zip de `main` estaba
   desactualizado, 5 commits atrás).
4. Se armó el entorno: `.venv\` con todas las dependencias de `requirements.txt`.
5. **Se movió todo de la carpeta del Desktop (share de red) a `C:\SIED`** porque
   la ruta del share + los nombres largos del aula base pasaban los 260
   caracteres de Windows y rompían Python y `git` (ver punto 5). En `C:\SIED` la
   suite pasa completa: **211 passed, 9 skipped, 57.11% cobertura**.

### Estado git actual (en `C:\SIED`)

| Cosa | Valor |
|---|---|
| Remoto `origin` | `https://github.com/UCC-SIED/Automatizaci-n-de-aulas.git` |
| Rama local | `develop` → `origin/develop` |
| HEAD | `2eaede3` — "ci: correr los tests en Windows, que es el entorno real del maquetador" |
| `main` (remoto) | `f7bc2b4` — **5 commits atrás de `develop`** (PR #2 sin mergear) |
| Otras ramas remotas | `claude/maquetador-avanzado` |

---

## 2. Trabajo YA CERRADO en el chat online (infraestructura / CI / cobertura)

Vive en `develop` como 5 commits, más el PR #2 abierto hacia `main`.

| Antes | Ahora |
|---|---|
| CI fallaba en 7 s sin correr nada | Verde, corriendo en **Windows** |
| Tests: 169 pasan, 51 salteados | **211 pasan, 9 salteados** |
| Cobertura total: 30,6 % | **57,1 %** |
| `imscc_builder.py`: 8,8 % | **63,9 %** |
| Codecov roto y silencioso | Reemplazado por `scripts/cobertura.py` (script propio) |
| Sin piso de cobertura | **Piso 55 %** (`PISO_POR_DEFECTO` en `scripts/cobertura.py:35`), corta el build si baja |

### Los 5 commits (`git log origin/main..origin/develop`)

1. `5f5d769` fix(ci): destrabar el workflow y sanear los tests que dependían de datos locales
2. `038152b` chore(ci): actualizar actions a versiones con Node 24
3. `239255f` feat(ci): reemplazar Codecov por un informe de cobertura propio
4. `3b40c10` test: curso sintético de prueba — el generador ahora se ejercita en CI
   (`tests/fixtures/curso_sintetico.py`)
5. `2eaede3` ci: correr los tests en Windows, que es el entorno real del maquetador

### Sobre "por qué Windows y no Linux" (venía confundido en el chat)

- El **maquetador** (programa Python) corre siempre en Windows, en las PCs del
  equipo. Nunca en Linux.
- El **`.imscc`** es solo un archivo (ZIP con XML/HTML). No "corre" en ningún
  lado; sale idéntico se genere donde se genere. Que sea portable no dice nada
  del SO donde se fabricó.
- Lo específico de Windows es el manejo de **rutas largas** (`\\?\`) que hizo
  falta por los nombres gigantes del aula base → ver `_copytree_longpath` en
  `maquetador/build/imscc_builder.py`.
- El CI decía `runs-on: ubuntu-latest` por inercia de la plantilla. Ahora
  `runs-on: windows-latest`, que es donde el maquetador realmente vive.

### Lo ÚNICO pendiente de esta parte

**Mergear el PR #2** (`UCC-SIED/Automatizaci-n-de-aulas#2`, `develop` → `main`).
Hasta que eso pase, `main` sigue con el CI en rojo porque el arreglo está en
`develop`. Es una decisión del dueño del repo, no bloquea el trabajo local.

### Oportunidades futuras (no son pendientes)

1. `maquetador/build/snippets.py` — ~29 %, ~354 líneas sin cubrir. Es el módulo
   más riesgoso hoy (recuadros, CTAs, componentes CidiLabs; mucho `if` sobre
   texto).
2. `maquetador/web/app.py` — 20,9 %. La web interna casi no se prueba. Un segundo
   curso sintético con otra forma (un módulo, sin foros, planilla formato viejo)
   cubriría más ramas del parser.
3. Subir el piso (`PISO_POR_DEFECTO`) a medida que 1 y 2 mejoren.

---

## 3. EL NUEVO FOCO: fidelidad del output (cómo sale vs cómo debería salir)

Cambio de plano: de la infraestructura al **producto**. La idea es:

> Agarrar un `.imscc` ya generado, compararlo contra cómo debería quedar
> (aula hecha a mano / criterio del maquetador), anotar diferencias, y pulir el
> generador iterando.

### Material que hay en local para comparar

- `Elementos de las aulas/_extracted_educacion/` y `_extracted_posgrado/` — las
  **dos aulas base** (el molde que el generador clona y modifica). Sirven para
  ver qué reemplazó el generador, qué dejó del molde y qué quedó a medias.

### Material que FALTA (nada de esto se versiona, hay que traerlo)

- El **`.imscc` de ejemplo** que se pidió analizar ("el aula de un archivo que me
  generaste vos"). **Todavía no se subió a la carpeta.**
- Idealmente, el **aula hecha a mano** equivalente (exportada de Canvas) para
  comparar contra un patrón real.
- Para reactivar `scripts/auditar_fidelidad.py` (comparación sistemática):
  - `Elementos de las aulas/Ejemplo de aula ya maquetada/` (carpeta GOLD)
  - 6 `.imscc` de referencia en la raíz del repo (los nombrados en `PARES`
    dentro de `scripts/auditar_fidelidad.py`): Fundamentos de Gestión de
    Proyectos, Atracción/Selección/Retención del Talento, Marketing de la
    Experiencia (CX), Ética y Cumplimiento Corporativo, Problemática del Hábitat,
    Ética y Cooperación Internacional.
  - Los paquetes generados en `output/working_*`.

### Cómo se compara (dos chequeos de `auditar_fidelidad.py`)

1. **Validez XML** de cada paquete (BLOQUEANTE): un `&` sin escapar en un título
   rompe la importación en Canvas.
2. **Fidelidad de páginas** vs el aula a mano: ratio de texto / tablas / links /
   figuras de diseño. Referencia histórica: ~88 % de páginas idénticas; el resto
   son decisiones editoriales que se resuelven en revisión.

---

## 4. Comandos clave

Trabajar siempre desde `C:\SIED`. Entorno: `.venv\` en la raíz.

```powershell
cd C:\SIED

# Tests + cobertura (el checkpoint de "estamos en la misma página")
.\.venv\Scripts\python.exe -m pytest tests\ -q
.\.venv\Scripts\python.exe -m pytest tests\ -q --cov=maquetador --cov-report=xml
.\.venv\Scripts\python.exe scripts\cobertura.py        # aplica el piso 55 %

# Analizar un curso (muestra el plan, sin generar)
.\.venv\Scripts\python.exe -m maquetador.cli "ruta\al\curso" --tema posgrado

# Generar el .imscc  (--tema: educacion | posgrado, siempre elección manual)
.\.venv\Scripts\python.exe -m maquetador.cli "ruta\al\curso" --tema posgrado --generar

# Web interna (subir ZIP del curso, ver plan, generar y descargar)
.\.venv\Scripts\python.exe -m maquetador.web.app       # http://localhost:5000

# Auditoría de fidelidad (necesita el material de referencia del punto 3)
.\.venv\Scripts\python.exe scripts\auditar_fidelidad.py

# Git: traer cambios nuevos del remoto
git pull
```

### Importar en Canvas

Elegir tipo **"Paquete de exportación de asignaturas de Canvas"** (NO "Common
Cartridge", ese modo ignora los módulos). Importar en un **curso nuevo/vacío**.

---

## 5. Notas del entorno local

- **Por qué se movió a `C:\SIED`:** en el share de red
  (`\\store-ad\$REF4785\...\Desktop\ProyectoSIED`, 57 caracteres de base) varios
  archivos del aula base quedaban en rutas de ~276 caracteres. Windows sin "long
  paths" (registro `LongPathsEnabled=0`) corta en 260 → Python no podía abrir
  esos PNG y 8 tests de `test_xml_validation.py` daban `FileNotFoundError`;
  además las escrituras de `git` (config/index/refs) fallaban de forma
  intermitente sobre SMB. En `C:\SIED` (base de 6 caracteres) desaparecen las dos
  cosas: **211 passed, 57.11%**, gate de cobertura en verde.
- **El original en el Desktop** sigue ahí como copia. Se puede borrar cuando
  quieras. Ojo: si tu Desktop está redirigido al servidor por backup, esta copia
  en `C:\` **no** queda respaldada ahí — hacé backup por tu cuenta si importa.
- Config git del repo: `core.longpaths=true`, `core.autocrlf=false`,
  `core.protectNTFS=false` (quedaron seteadas; en `C:\SIED` no molestan).
- **Push:** el remoto es HTTPS. El primer `git push` va a pedir autenticación
  (usuario + **token**, no contraseña). Configurarlo recién cuando haga falta.
- Python: `3.11.9` en
  `C:\Users\jonathan.guillen\AppData\Local\Programs\Python\Python311\`.

---

## 6. Glosario mínimo del proyecto

- **Maquetador** (`maquetador/`): toma los materiales del asesor (Word de
  contenidos, planilla de estructura, imágenes, foros, actividades) y arma un
  `.imscc` listo para Canvas con el diseño institucional **CidiLabs / DesignPLUS**
  de la UCC. Es genérico: no hay scripts por asignatura; la **planilla de montaje
  manda** (define qué páginas van y qué recursos por módulo).
- **Aula base** (`educacion` | `posgrado`): el aula ya maquetada que el generador
  **clona** y a la que le reemplaza el contenido quirúrgicamente, borrando los
  recursos/módulos que la planilla no pide. La elección es **siempre manual**.
- Subcarpetas de `maquetador/`:
  - `ingest/` escaneo de carpeta, parser de planilla (autodetecta formato viejo
    y nuevo), perfilado de DOCX, reconciliación, lectura de comentarios del DOCX
  - `extract/` segmentación del DOCX a HTML por sección
  - `build/` snippets CidiLabs, plantillas de página, generador del `.imscc`,
    bibliografía
  - `web/` app Flask interna
  - `models.py` modelo canónico (`CourseSpec`, `ModuloCurso`, `ItemCurso`, `Issue`)
- `processors/cidilabs_builder.py`: utilidades de diseño CidiLabs (`dp-wrapper`).
- `legacy/`: versión anterior, archivada, el tool no la usa.

---

## 7. Para retomar el trabajo de fidelidad — lo que falta de tu lado

1. Subir a `C:\SIED` (carpeta del proyecto) el **`.imscc` de ejemplo** a analizar.
2. Si se puede, el **aula a mano** equivalente (export de Canvas) o indicaciones
   directas de qué está mal y cómo debería verse.
3. (Opcional, para la auditoría sistemática) el paquete de 6 cursos de referencia
   + la carpeta `Ejemplo de aula ya maquetada`.
