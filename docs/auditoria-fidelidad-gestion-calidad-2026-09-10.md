# Auditoría de fidelidad — "Gestión de la Calidad" (posgrado)

**Fecha:** 2026-09-10
**Material:** `pruebas/gestion-de-la-calidad-2026-export (1).imscc` (automatización, "v1")
vs `(2).imscc` (corrección manual final, "v2") + `pruebas/Errores de integraciones.pdf`.
Curso: MAESTRÍA EN DIRECCIÓN ESTRATÉGICA DE PROYECTOS · 2 módulos · 13 páginas
wiki + 3 actividades + foros + quizzes.

Referencia de marcado: [`docs/referencia-designplus-cidilabs-ucc.md`](referencia-designplus-cidilabs-ucc.md).

---

## Resumen ejecutivo

La automatización **arma bien la estructura del cartucho** (módulos, orden de
ítems, nombres en `module_meta.xml`, foros/actividades/quizzes, bibliografía) y
**el texto llega completo**. Lo que falla es la **maquetación DesignPLUS**:

- **3 defectos sistémicos** que afectan al **100% de las páginas** (tema del
  wrapper desactualizado, banner placeholder, H2 de página vacío).
- **5 defectos de componente** recurrentes: figuras (alt como texto visible +
  borde equivocado + sin centrar), subtítulos que no suben a `H3`, componentes
  colgables (tabs/expander/acordeón) marcados en comentarios que **no se generan**,
  video que queda como placeholder de texto, tokens de color de recuadros.
- **Selección de assets**: foto de docente toma un archivo equivocado
  (miniatura de video), figuras de diseño (esquema, Figura 5) no se incorporan.

Ninguno rompe la importación a Canvas (XML válido), pero el resultado necesita
retoque manual página por página. Abajo, cada punto con evidencia, la corrección
de v2 y **dónde tocar el generador**.

---

## 1. Defectos sistémicos (100% de las páginas)

### 1.1 Wrapper con tema de encabezados viejo — **13/13 páginas**

- **v1** `<div id="dp-wrapper" class="… dp-hdg-txt-h5-dp-white dp-hdg-bg-h6-dp-gray dp-hdg-txt-h6-dp-gray … dp-hdg-b-h6-pill-r dp-hdg-b-h6-bold dp-hdg-b-h5-bold …">` (sin `custom-paragraph-padding`, sin `dp-hdg-txt-h6-dp-primary`, sin `dp-hdg-bg-h5-dp-gray`…).
- **v2 / referencia** `"… dp-hdg-b-h4-bold dp-hdg-b-h3-bold dp-hdg-d-h4-table-l dp-hdg-b-h5-pill-r custom-paragraph-padding dp-hdg-txt-h6-dp-primary dp-hdg-bg-h5-dp-gray dp-hdg-txt-h5-dp-primary dp-hdg-bg-h6-dp-white dp-hdg-b-h6-pill-r&nbsp; custom-paragraph-padding"`.
- **Causa:** el string de clases no está en `maquetador/` — sale **del aula base**
  (`Elementos de las aulas/_extracted_posgrado`), que quedó con un tema anterior.
  Al clonar la página, el generador lo preserva. Un humano que abre la página en
  el editor DesignPLUS obtiene el string nuevo automáticamente al guardar → por
  eso v2 lo tiene y v1 no.
- **PDF:** "El programa no tenía estilo de tema, se actualiza ahora y los encabezados también".
- **Fix generador:** tras clonar, **reescribir la clase del `#dp-wrapper`** al
  string canónico actual (tomarlo de los HTML de referencia). Alternativa más
  cara: re-extraer las aulas base ya actualizadas.

### 1.2 Banner = placeholder — **13/13 páginas**

- Páginas de contenido: `src="$IMS-CC-FILEBASE$/Multimedia%20cargada/1.1.%20(El%20primer%20uno%20hace%20referencia%20al%20modulo%20y%20el%20segundo%20uno%20corresponde%20al%20subm%C3%B3dulo).png"` — el **nombre del archivo es la instrucción de nomenclatura**, no un banner real. Y **todas las páginas de un módulo comparten el mismo** (`1.1.…png` para 1.1–1.4, `2.1.…png` para 2.1–2.4).
- Intro/biblio: `… - EP.png` (`Introducción M1 - EP.png`, `Bibliografía M1 - EP.png`).
- Portada: `src="…/Nombre de la asignatura - EP.png"` con **`alt="Nombre de la asignatura - EP.png"`** (el alt es el nombre del archivo).
- **v2:** banners reales por página en `Uploaded Media/` (`2.2 (4).png`, `M1 (8).png`, `Gestión de la Calidad.png`…) con `alt` descriptivo (p. ej. `alt="Módulo 1: Fundamentos de la gestión de la calidad en proyectos"`) y `width`/`height`.
- **PDF:** "Falta el banner correcto con el texto alternativo correcto en todas las páginas".
- **Fix generador:** el banner branded es un asset manual (no lo puede fabricar el
  tool), pero el generador **debe**: (a) poner `alt` = título de la página/módulo,
  nunca el nombre de archivo; (b) emitir un **Issue por página** "banner
  placeholder — reemplazar"; (c) `_extraer_banner()` en
  [maquetador/build/imscc_builder.py:97](../maquetador/build/imscc_builder.py#L97) hoy solo
  copia el `src` del base — que sepa distinguir "placeholder" de "real".

### 1.3 ~~H2 de página vacío~~ — **FALSO POSITIVO** (revisado 2026-09-10)

El `<h2 class="dp-has-icon">` con solo el icono y sin texto **es correcto**: es
el **divisor de sección**, y las clases `dp-hdg-i-*` del wrapper son las que lo
estilan (píldora, borde, fondo primary). v1 y v2 lo emiten idéntico.

En el sistema hay tres usos distintos y no hay que confundirlos:

| Rol | Markup | Dónde |
|---|---|---|
| Divisor de sección | `<h2 class="dp-has-icon"><i …></i></h2>` sin texto | páginas de contenido, arranque de actividad |
| Divisor con rótulo | el mismo, con texto después del `</i>` | secciones tipo "Videos conceptuales", "Presentación" |
| **Título** | `<h2 class="dp-ignore-theme" style="color: #003087;">` **separado** | título de la actividad |

En las páginas de contenido el título lo lleva el banner, por eso el divisor va
sin texto. **No hay nada que arreglar ahí.** El hueco real está en las
actividades → ver §4.bis.

---

## 2. Defectos de componente

### 2.1 Figuras — alt como párrafo visible, borde equivocado, sin centrar — **7/7 páginas con figura**

- **v1 (Figura 2, pág. 2.2):**
  ```html
  <p class="dp-heading-ignore" style="text-align: center;"><span style="font-size:10pt;"><strong>Figura 2. Ejemplo simplificado de diagrama de Ishikawa</strong></span></p>
  <p><strong><img class="dp-popup-image dp-image-rounded-10 dp-image-padded dp-image-bordered dp-image-shadow" src="…/M_2 fig 2.jpg" style="width:700px; height:auto;" loading="lazy"></strong></p>
  <p>Texto alternativo: Diagrama de Ishikawa para identificar las posibles causas de un problema.</p>
  ```
  → el `<img>` **no tiene `alt`**; el texto alternativo quedó como **párrafo
  visible** en la página; la imagen está **envuelta en `<strong>`**; el `<p>` de
  la imagen **no está centrado**; usa el estilo **expandido** (`dp-popup-image …
  dp-image-shadow`) siempre.
- **v2:**
  ```html
  <p style="text-align: center;"><span style="font-size:10pt;"><strong>Figura 2. …</strong></span></p>
  <p style="text-align: center;"><span style="font-size:10pt;"><strong><img class="dp-image-rounded-10 dp-image-bordered" style="height:auto; width:700px;" src="…/M_2 fig 2.jpg" alt="Diagrama de Ishikawa para identificar las posibles causas de un problema" width="700" height="335.708" …></strong></span></p>
  ```
  → `alt` **en el atributo**, sin párrafo "Texto alternativo:", **centrada**,
  borde **estático** (`dp-image-rounded-10 dp-image-bordered`, sin `popup` ni `shadow`).
- **PDF:** "figura 2 no está centrada, falta el caption metido y el texto
  alternativo… el texto alternativo es para que esté dentro de la figura/tabla
  no en la página" · "si no se expande la imagen se le pone otro borde".
- **Causa:** estas figuras vienen **embebidas en el DOCX** (el asesor pega imagen
  + escribe "Figura N." arriba y "Texto alternativo: …" debajo). El pipeline
  (mammoth → segmenter) las pasa **tal cual**. El normalizador de
  [maquetador/build/snippets.py:865](../maquetador/build/snippets.py#L865) solo agrega la clase
  `dp-popup-image dp-image-rounded-10 dp-image-padded dp-image-bordered dp-image-shadow`
  a cualquier `<img>` sin `dp-popup-image` — por eso **todas** quedan con estilo
  expandido. El builder "propio" de figuras
  ([snippets.py:366](../maquetador/build/snippets.py#L366)) sí pone `alt`, pero **no se
  aplica** a las imágenes que ya venían en el HTML del DOCX.
- **Fix generador:** detector de "figura embebida en DOCX" = patrón
  `<p>…Figura N. …</p>` + `<img>` + `<p>Texto alternativo: …</p>`. Al detectarlo:
  mover el texto tras "Texto alternativo:" al `alt=` del `<img>` y **borrar ese
  párrafo**; envolver imagen y caption en `<p style="text-align:center;">`;
  quitar `<strong>` envolvente; elegir borde **estático** por defecto
  (`dp-image-rounded-10 dp-image-bordered`) y solo usar `dp-popup-image … dp-image-shadow`
  si la figura está marcada como expandible.

### 2.2 Subtítulos que no suben a `H3` — **5 páginas** (intro-M1, 1.3, 2.2, 2.3, 2.4)

- **v1 (2.2):** `<p>El diagrama de Ishikawa: explorar posibles causas</p>`,
  `<p>La técnica de los 5 porqués: buscar la causa raíz</p>`,
  `<p>El diagrama de Pareto: priorizar esfuerzos</p>`,
  `<p>¿Cuándo conviene utilizar Ishikawa?</p>` … → **todos como párrafo plano**.
  Solo "Comprender los problemas antes de actuar" y "No conformidades y acciones
  de mejora" quedaron en `<h3>`.
- **v2:** los tres primeros pasan a `<h3 class="dp-panel-heading">` (dentro del
  acordeón, ver 2.3); los "¿Cuándo conviene…?" a `<p><strong>…</strong></p>`.
- **PDF:** "cuando el comentario marca subtítulo, debe ponerse en h3" ·
  "expander (títulos subrayados): no se tomaron en cuenta 'El diagrama de
  Ishikawa: explorar posibles causas'".
- **Causa:** el segmentador solo respeta el estilo de párrafo del DOCX; no aplica
  los comentarios de la asesora que marcan "subtítulo". Ver
  [maquetador/ingest/docx_comments.py](../maquetador/ingest/docx_comments.py) +
  cómo se consume en `extract/segmenter.py`.
- **Fix generador:** cuando un comentario del DOCX sobre un párrafo dice
  "subtítulo" (o el párrafo está subrayado y corto), promover ese `<p>` a `<h3>`.

### 2.3 Componentes colgables (tabs / expander / acordeón) — casi ninguno

- **v1:** en las 13 páginas hay **1 solo** `dp-panels-wrapper` (en 1.3). El resto
  de comentarios de la asesora pidiendo tabs/expander/acordeón **no generaron nada**.
- **v2 (2.2):** Ishikawa/5 porqués/Pareto envueltos en
  ```html
  <div class="dp-panels-wrapper dp-accordion-default dp-panel-color-dp-primary dp-panel-active-color-dp-secondary dp-panel-hover-color-dp-secondary">
    <div class="dp-panel-group"><h3 class="dp-panel-heading">El diagrama de Ishikawa: …</h3><div class="dp-panel-content">…</div></div>
    …
  </div>
  ```
- **PDF:** "comentario de expander sin aplicar" · "tabs horizontales, en
  comentarios pero no se hizo" · "no se ejecutó correctamente: Para maquetación:
  TABS vertical / ISO 14001 / ISO 45001" · "no se hizo bien el desplegable
  acordeón que dejó como comentario la asesora" · "pusiste un expander donde no
  iba, ¿por qué lo hiciste?" (→ el único que hizo, lo puso mal).
- **Causa:** el mapeo comentario→componente en el pipeline está mayormente
  inactivo o no matchea los textos reales ("Para maquetación: TABS vertical",
  "expander (títulos subrayados)", "acordeón"). Cuando sí dispara (1.3), agrupa mal.
- **Fix generador:** reforzar el parser de comentarios de maquetación:
  reconocer `TABS (horizontal|vertical)`, `expander`, `acordeón`, tomar el **rango
  de párrafos** que abarca el comentario y las **líneas subrayadas** como títulos
  de panel; construir `dp-panels-wrapper` con la variante correcta
  (`dp-tabs-buttons` / `dp-tabs-buttons-vertical` / `dp-expander-default` /
  `dp-accordion-default`).

### 2.4 Video — placeholder de texto en lugar de embed

- **v1 (2.2):** recuadro CTA `dp-callout … dp-callout-type-title-bar` "Auriculares
  on" con texto que termina en "**VIDEO M2.**", y al final de la página el texto
  "**VIDEO 2**". El video no está.
- **v2 (2.2):** bloque propio
  ```html
  <div class="dp-content-block" data-title="Video" data-category="+UCC">
    <h2 class="dp-has-icon"><i class="dp-icon fab fa-youtube" …></i></h2>
    <p>…intro…</p>
    <div class="dp-embed-wrapper mx-auto d-block" style="text-align:center;">
      <iframe class="lti-embed" … src="$CANVAS_COURSE_REFERENCE$/external_tools/retrieve?display=borderless&url=https%3A%2F%2Fuccor.instructuremedia.com%2Flti%2Flaunch%3Fcustom_arc_launch_type%3Dlearn_embed%26custom_arc_media_id%3D…"></iframe>
    </div>
  </div>
  ```
  (mismo patrón en portada para "Video de desarrollo de la asignatura").
- **PDF:** "Video de desarrollo de la asignatura, que va directamente desde
  canvasStudio, no es un snippet de video común".
- **Fix generador:** cuando el contenido referencia "VIDEO Mx" / "video de
  desarrollo" y hay un ID de Canvas Studio (o se declara), emitir el bloque
  `dp-content-block data-title="Video"` + `iframe.lti-embed` a
  `instructuremedia.com/lti/launch?...custom_arc_launch_type=learn_embed...`.
  Si no hay ID, dejar Issue "falta media_id de Canvas Studio" — **no** dejar
  "VIDEO M2." en el cuerpo.

### 2.5 Recuadros — tokens de color y espaciado

- **"Una pausa para reflexionar" (Profundización):**
  - v1: `dp-callout-type-info dp-callout-color-lg-warning`, side-emphasis **sin**
    `background-color`.
  - v2 / referencia: `dp-callout-type-info dp-callout-color-warning` +
    `<div class="dp-callout-side-emphasis" style="background-color:#f4e600; color:#000000;">`.
- **PDF:** "Espaciado de recuadro de profundización, actualizar el color
  correspondiente, antes de una titulación".
- **Recuadros simples:** PDF marca varios casos —
  - "¿Estamos creando las condiciones…?" → recuadro simple **duplicado** (se puso
    doble) y, si la frase es corta, **centrar**.
  - "La participación temprana de stakeholders…" → debe ir en **simple + centrado**,
    con **espaciado menor** (soft-return `shift+enter` dentro del párrafo, no
    párrafos separados).
  - "detectar defectos → controlar procesos → asegurar consistencia → generar
    valor" → **apply lead font style pero seguir siendo `<p>`, en negrita**
    (no convertir en lista ni en heading).
- **Fix generador:** (a) usar `dp-callout-color-warning` para Profundización;
  (b) no emitir dos `dp-callout` simples consecutivos idénticos; (c) para frases
  cortas en recuadro simple, `text-align:center`; (d) respetar soft-returns del
  DOCX como `<br>` dentro del mismo `<p>` en lugar de partir en varios `<p>`.

---

## 3. Selección de assets

| Qué | v1 (automatización) | v2 (correcto) | PDF |
|---|---|---|---|
| Foto profesora autora | `Multimedia cargada/video-01.jpg` (**miniatura de video**), `alt="Fotografía del docente Emiliano Marino"` | `Uploaded Media/Fotografía de EMILIANO MARINO.png`, `alt="Fotografía de docente"` | "imagen de docente, puso otra nada que ver… crop circular en fotor.com estilo Circle. Renombrar archivo y ponerle texto alternativo" |
| Foto tutor | mismo `video-01.jpg`, sin clase | `Uploaded Media/EMILIANO MARINO 2.jpg`, `class="dp-image-rounded-10 dp-image-bordered"` | idem |
| Bio profesora | `<strong>Titulación relevante.</strong>` (**placeholder literal**) | bio real ("Ingeniero Químico. Magíster en Tecnología de Alimentos. Más de 13 años…") | — |
| Esquema (figura de diseño) | ausente | `Uploaded Media/M_Esquema.jpg` | "El esquema no se sumó desde la carpeta de diseño" |
| Figura 5 (cláusulas ISO) | ausente | presente | "Figura 5. Cláusulas del sistema de gestión de la calidad (no lo pusiste)" |
| Video de bienvenida (portada) | bloque vacío | `iframe.lti-embed` Canvas Studio | "Video de desarrollo… desde canvasStudio" |

- **Foto de docente:** [maquetador/build/imscc_builder.py:501-524](../maquetador/build/imscc_builder.py#L501)
  hace el swap de `src` sobre `<img alt="Avatar docente">`. El archivo elegido
  (`video-01.jpg`) sale mal clasificado en `ingest/folder_scanner.py` /
  `reconciler.py` — una miniatura de video se tomó como retrato. **Fix:** excluir
  nombres tipo `video-*`, priorizar archivos cuyo nombre contenga el apellido del
  docente; `alt` = `"Fotografía de docente"`.
- **Bio "Titulación relevante.":** el generador deja el texto placeholder del
  aula base cuando no encuentra la bio en la fuente. **Fix:** si no hay bio,
  Issue "falta bio del docente" y dejar el campo vacío, no el placeholder.
- **Esquema / Figura 5:** figuras de diseño no incorporadas. Revisar
  [maquetador/build/imscc_builder.py:1599-1618](../maquetador/build/imscc_builder.py#L1599)
  (figuras de DISEÑO → `Multimedia cargada/`): el match entre "Figura N" del
  contenido y el archivo de la carpeta de diseño no está cubriendo todos los casos.

---

## 4. Objetivos — `<h3>` dentro de `<ul>` — **intro-M1 (y 4 páginas más con el mismo patrón)**

- **v1:**
  ```html
  <ul>
    <li>Comprender la evolución…</li>
    <li>Analizar los principios…</li>
    <li>Reconocer el aporte…</li>
    <h3>Distinguir los procesos de planificación, aseguramiento y control…</h3>   <!-- BUG -->
    <li>Interpretar el rol de stakeholders…</li>
  </ul>
  ```
- **v2:** los 5 como `<li>`.
- **PDF:** "items de objetivos con titulación adicional".
- **Causa:** `objetivos_html` llega ya construido desde la segmentación del DOCX
  (`intro_item.detalle["objetivos_html"]` / `extras_mod["objetivos"]`, ver
  [maquetador/build/imscc_builder.py:281](../maquetador/build/imscc_builder.py#L281)); un
  bullet del DOCX tenía estilo Heading y mammoth lo convirtió en `<h3>`.
  `pages.py:pagina_intro()` lo inserta sin sanear.
- **Fix generador:** sanear la lista de objetivos — **forzar todos los hijos
  directos a `<li>`**; si hay `<h3>/<h4>` sueltos entre `<li>`, degradarlos a `<li>`.

---

## 4.bis Actividades: título y subtítulos de sección

Comparando `actividad-final-integradora.html`:

```html
<!-- v1 (automatización) -->
<h2 class="dp-has-icon" style="text-align: center;"><i class="dp-icon fas fa-tasks" …></i></h2>
<h3>Actividad final integradora: Analizá situaciones reales</h3>
<p>Objetivo: </p>
<p>Interpretar la situación planteada; integrar y aplicar los conceptos…</p>

<!-- v2 (corregido a mano) -->
<h2 class="dp-has-icon" style="text-align: center;"><i class="dp-icon fas fa-tasks" …></i></h2>
<h2 class="dp-ignore-theme" style="color: #003087; text-align: center;"><strong>Analizá situaciones reales</strong></h2>
<h3>Objetivo</h3>
<p>Interpretar la situación planteada; integrar y aplicar los conceptos…</p>
```

Tres diferencias:

1. **El título va como `<h2 class="dp-ignore-theme">` centrado**, no como `<h3>`.
2. **Se le saca el prefijo** "Actividad final integradora: " — repite el nombre
   que Canvas ya muestra en el ítem del módulo.
3. **Los rótulos de sección del "Modelo de actividad"** (Objetivo, Consigna,
   Pautas de presentación, Criterios de evaluación, Anexo) van como encabezado,
   no como `<p>Objetivo: </p>` con dos puntos y el cuerpo en el párrafo
   siguiente.

---

## 5. Otros hallazgos del PDF (a confirmar en páginas no diffeadas a fondo)

- **Tooltip mal puesto** (`dp-tooltip-*`) — revisar 1.x.
- **Genially:** si el comentario dice "insertar lo seleccionado" → **no maquetar**,
  incrustar el `iframe` de `view.genially.com` tal cual. v1 parece haber intentado
  maquetarlo.
- **"recorda que no debes modificar contenido":** v1 aplana runs `<span>/<i>` del
  DOCX y reescribe frases; el pipeline no debe tocar el texto, solo envolverlo.
- **Comentarios sin resolver:** el comentario de "Dirección de Carrera a Distancia"
  sobre Ishikawa/5 Porqués/Pareto quedó **sin marcar como pendiente** en la salida.
  El generador debería listar en Issues todo comentario del DOCX que no pudo
  aplicar automáticamente (acordeón, flip card, faltantes…), como dice el README.
- **Programa (Syllabus):** "no tenía estilo de tema, se actualiza ahora y los
  encabezados" — mismo problema 1.1 aplicado a la página de Programa.
- **Foro de apertura:** "información sumada de más" junto a la tabla Unidad
  académica / Carrera / Asignatura — revisar el builder del foro de apertura.
- **Espaciados entre jerarquías:** v2 agrega `<p>&nbsp;</p>` / `<br><br>`
  deliberados entre niveles y antes de cada heading; v1 casi no.

---

## 6. Backlog para el generador (prioridad)

1. **Reescribir la clase de `#dp-wrapper`** al string canónico actual tras clonar. *(sistémico, 13/13)*
2. **Figuras embebidas en DOCX**: alt al atributo + borrar "Texto alternativo:" + centrar + quitar `<strong>` + borde estático por defecto. *(7/7 páginas)*
3. **Sanear lista de objetivos**: todos los hijos a `<li>`. *(5 páginas)*
4. **Comentarios de maquetación → componentes**: TABS h/v, expander, acordeón; líneas subrayadas = títulos de panel; promover subtítulos marcados a `<h3>`. *(≥5 páginas)*
5. **Banner**: `alt` = título (nunca nombre de archivo) + Issue "placeholder" por página.
6. **Video Canvas Studio**: bloque `data-title="Video"` + `iframe.lti-embed`; nunca dejar "VIDEO Mx" en el cuerpo.
7. **Foto de docente**: excluir `video-*`, matchear por apellido, `alt="Fotografía de docente"`; bio vacía + Issue si no hay bio (no "Titulación relevante.").
8. **Figuras de diseño** (esquema, Figura 5): mejorar el match "Figura N" ↔ archivo de carpeta de diseño.
9. **Recuadros**: `dp-callout-color-warning` para Profundización; no duplicar callouts simples; centrar frases cortas; soft-return como `<br>` intra-`<p>`.
10. **H2 de página**: confirmar criterio (vacío vs título) y aplicarlo.
11. **Issues**: listar todo comentario del DOCX no aplicado.
12. **Espaciado** entre jerarquías/recursos.

---

## 7. Re-auditoría — estado de `scripts/auditar_fidelidad.py`

Sigue sin poder correr: espera `Elementos de las aulas/Ejemplo de aula ya maquetada/`
+ 6 `.imscc` de referencia + `output/working_*` que no están. **Pero ahora
tenemos un par real** (`pruebas/(1)` vs `(2)`), así que se puede:

1. Adaptar `PARES` para incluir
   `('gestion-de-la-calidad-2026-export (2).imscc', '<extracción de (1)>', 'GestiónCalidad')`
   usando el **(2) como "gold"** y el **(1) como "generado"**.
2. El chequeo de **validez XML** ya se puede correr sobre ambos `.imscc` (ninguno
   debería tener `&` sin escapar — verificar).
3. Sumar a la comparación de fidelidad los **checks nuevos** que salieron de esta
   auditoría (los 7 puntos del `docs/referencia-designplus-cidilabs-ucc.md` +):
   - wrapper class == string canónico
   - ningún `<p>` que empiece con "Texto alternativo:"
   - ningún `<img>` de figura sin `alt`
   - ningún `<h3>`/`<h4>` como hijo directo de `<ul>`/`<ol>`
   - sin texto "VIDEO M" / "VIDEO N" suelto en el cuerpo
   - banner `alt` != nombre de archivo
   - conteo de `dp-panels-wrapper` esperado vs generado (según comentarios)

Estos son asserts baratos que el generador debería pasar antes de dar por bueno
un paquete.
