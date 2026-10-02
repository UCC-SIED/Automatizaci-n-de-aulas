# Referencia DesignPLUS / CidiLabs — spec del output UCC

Destilado de los 5 HTML de referencia que están en la raíz del repo (páginas
reales exportadas del curso Canvas 399, "sandbox" de maquetación):

| Archivo | Qué define |
|---|---|
| `Pautas de Estructura y Componentes de Contenido.html` | Jerarquía de títulos + componentes de organización (tabs/expander/acordeón), emergentes (popover/tooltip/modal), tarjetas (flip/flashcards), y **todos los interactivos DesignPLUS** (Quick Check, Fill in Blank, Order, Sort, Match, Select All) |
| `Estilos para Llamados a la Acción y Tipos de Contenido Complementario.html` | Recuadros: **CTAs** (con acción/link) y **RESALTADOS** (sin acción) |
| `Estándares para Recursos Visuales y Datos.html` | Figuras, tablas, videos, presentaciones/Genially, recursos interactivos |
| `Modelo de actividad.html` | Estructura de una actividad (Objetivo/Consigna/Pautas/Criterios/Anexo) + caso Mural |
| `Snipped utilizados.html` | Librería de snippets CidiLabs nombrados (3 tablas: UCC Custom, UCC-Educación, UCC-Posgrado) |

Este documento es la vara contra la que se compara cada `.imscc` generado.

---

## 1. Envoltura de página (obligatoria)

Todo el body de una página va dentro de:

```html
<div id="dp-wrapper" class="dp-wrapper dp-hdg-i-bg-h2-dp-primary dp-hdg-i-align-h2-tc … custom-paragraph-padding"
     data-header-class="dp-header dp-flat-sections"
     data-nav-class="container-fluid dp-link-grid dp-flat-sections dp-fs-1"
     data-img-url="https://designtools.ciditools.com/css/images/banner_desert_sky.png">
  <div class="dp-banner-image"><img src="https://distancia.ucc.edu.ar/courses/<id>/files/<fileid>/preview" alt="<título>" …></div>
  <div class="dp-content-block kl_introduction">
    <p class="lead dp-progress-placeholder dp-module-progress-completion dp-padding-direction-all dp-margin-direction-all" style="display:none; …">Module Item Completion (built in browser, hidden in app)</p>
  </div>
  <div class="dp-content-block kl_readings2" style="background-color:#ffffff; color:#000000;">
    <h2 class="dp-has-icon"><i class="fa-book fas" style="background-color:#003087; color:#ffffff;" aria-hidden="true"><span class="dp-icon-content" style="display:none;">&nbsp;</span></i> … </h2>
    …contenido…
  </div>
</div>
```

- La lista de clases `dp-hdg-*` del wrapper es la config de estilos de encabezado del tema; se copia tal cual.
- Banner: imagen subida a Canvas, se referencia como `/courses/<id>/files/<fileid>/preview` con `data-api-endpoint` y `data-api-returntype="File"`.
- Los `<i>` de FontAwesome siempre llevan `aria-hidden="true"` + `<span class="dp-icon-content" style="display:none;">&nbsp;</span>` dentro.

## 2. Jerarquía de títulos (política)

- `H1` = título del módulo
- `H2` = título de la página (**≤ 110 caracteres**)
- `H3` = subtítulo (sin numeración)
- `H4`/`H5`/`H6` = niveles inferiores (sin numeración)
- `Normal` = cuerpo
- Títulos de **figura y tabla**: **< 110 caracteres**

## 3. Paleta

| Rol | Educación | Posgrado |
|---|---|---|
| Primario | `#003087` / `#003366` / `#004a80` (azul) | `#1b1e31` (azul muy oscuro) |
| Barra de título de callout | fondo claro | `background-color:#1b1e31` |
| Link / acceso | `#236fa1` (a veces `#3598db`) | igual |
| Acento amarillo (reflexión) | `#f4e600` / `#757121` (texto) | igual |

**La diferencia educación vs posgrado es casi solo color.** Misma estructura.

## 4. Componentes de organización

| Componente | Clase raíz |
|---|---|
| Tabs horizontal | `dp-panels-wrapper dp-tabs-buttons dp-panel-color-dp-primary dp-panel-active-color-dp-secondary dp-panel-hover-color-dp-secondary dp-panel-tab-width-fill` |
| Tabs vertical | `dp-panels-wrapper dp-tabs-buttons-vertical …` |
| Tabs pills vertical (figuras) | `dp-panels-wrapper dp-tabs-pills-vertical dp-panel-active-color-dp-primary dp-panel-color-dp-gray` |
| Expander | `dp-panels-wrapper dp-expander-default …` |
| Acordeón | `dp-panels-wrapper dp-accordion-default …` (o `dp-accordion-plus`) |

Estructura interna común: `.dp-panel-group > h3.dp-panel-heading + div.dp-panel-content`.

**Emergentes:**
- Popover: `<a class="dp-popover-trigger" href="#dpPopup0Content">` + `<div id="dpPopup0Content" class="dp-popover-content dp-popup-content">`
- Tooltip: `span.dp-tooltip-container > a.dp-tooltip-trigger.dp-popup-trigger` + `span.dp-tooltip-content.dp-popup-content`
- Modal: `a.dp-modal-trigger` + `div.dp-modal-content.dp-popup-content` con `h4.dp-modal-title`

**Tarjetas:**
- Flip card estándar: `.dp-flip-card > .dp-flip-card-inner > (.dp-front-card | .dp-back-card) > .dp-card.card.h-100.dp-shadow-b3`. Grilla Bootstrap `.container.text-center > .row.justify-content-center > .col-md-4`.
- Flip card "fast" (flex): `.dp-flip-card.dp-flip-card-fast` dentro de wrapper `display:flex; flex-wrap:wrap` con `flex:1 1 31%` (o 45%/48% según cantidad). Snippets: **FlipCards x2 … x6**.
- Flashcards interactivas: `.dp-fcs … data-interactive-type="Flashcards"` con `<dl><dt><div class="dp-fc-front">…<dd><div class="dp-fc-back">`.

## 5. Interactivos DesignPLUS (`data-interactive-type`)

Todos llevan `data-interactive-id` (12 chars), `data-interactive-type`, `data-interactive-title`.

| Nombre | Clase raíz | `data-interactive-type` | Marcado de respuesta |
|---|---|---|---|
| Quick Check | `dp-qc dp-bg dp-shadow-b3` | `Quick Check` | `dl.dp-qc-answers > dt.dp-qc-answer(.dp-qc-correct) + dd.dp-qc-response.d-none(.dp-qc-correct)` |
| Quick Check multi | `dp-qc … dp-qc-ma` | `Quick Check` | varias `dt.dp-qc-answer` sin `dp-qc-correct` |
| Completar | `dp-fill-in-blank dp-fib-horizontal` | `Fill in the Blank` | huecos = `<span class="dp-fib-answer">RESPUESTA </span>`. **Regla: 1 palabra, MAYÚSCULAS, sin acentos** |
| Ordenar | `dp-order-wrapper` | `Order Items` | `ol.dp-order.dp-order-text > li` en orden correcto |
| Clasificación | `dp-si-sort-pool dp-si-sort-type-text` | `Sort Items` | `.dp-si-sort-bucket.dp-si-sort-answer-bank` (distractores) + buckets; items `li.dp-si-item-text` |
| Emparejamiento | `dp-match-items dp-match-pairing` | `Match Items` | `dl.dp-match.dp-match-text > dt/dd[data-pair-id="pair-N"]` |
| Selección | `dp-si-sa` | `Select All` | `ul.dp-sa-list.dp-sa-list-text > li(.dp-sa-correct)` |

- Feedback común: `div.dp-si-feedback.dp-si-correct` / `.dp-si-incorrect` (con `display:none`).
- Botón: `a.dp-qc-submit.btn.btn-dp-primary` con `style="display:none"`.
- **Textos estándar ES**:
  - Correcto: `¡Gran trabajo! ¡Respuesta correcta!`
  - Incorrecto: `¡Revisá el material nuevamente para reforzar tus conocimientos! Mejorarás en el próximo intento.`
- Layouts: Quick Checks se agrupan en `.dp-column-container .row .col-lg-4/.col-lg-6`, o "Question side-by-side" (contenido `col-lg-7` + QC `col-lg-5`).
- **Chequeo de comprensión conceptual = 3 partes obligatorias**: (1) pregunta con una única respuesta correcta, (2) feedback positivo que confirma y **refuerza el concepto**, (3) feedback correctivo que señala el error y **redirige al material**.

## 6. Recuadros — CTAs (Llamados a la Acción)

Base: `div.dp-callout.card.dp-callout-position-default.dp-callout-type-title-bar.dp-callout-color-lg-tip.dp-hover-shadow-b1` > `.card-body` > `p.card-title` (icono FA + nombre) + intro `<p>` + `p.card-text` con link en `#236fa1`.

**Siempre** llevan una intro que invita al link (anticipa el formato y asigna una tarea).

| Icono FA | Nombre CTA | Uso |
|---|---|---|
| `fab fa-youtube` | **Auriculares on** | video |
| `fas fa-headphones` | **Auriculares on** | podcast |
| `fas fa-book-reader` | **Descubrí leyendo** | lectura |
| `fas fa-image` | **Miralo con lupa** | imagen |
| `fas fa-layer-group` | **Caja de herramientas para usar** | multi-recurso (2+ links) |
| img "Consigna" (file `32108`) | **¿Cómo vengo hasta acá?** | Actividad/Autoevaluación (con espacio de entrega) — la consigna va en el **recurso**, no en la página |
| `far fa-comment-dots` | **Foro: NOMBRE DE ACTIVIDAD** | foro — **MOMENTÁNEAMENTE DESHABILITADOS** |
| `fab fa-buromobelexperte` | **Voces que construyen (Mural colaborativo)** | mural |

**Mural — 2 casos:**
1. Participación directa en Mural, **no calificable** en Canvas (no hay entrega formal).
2. Con **entrega y calificación** en Canvas: primero conssigna/pautas, luego el lienzo, y vuelve a Canvas a adjuntar evidencia.

## 7. Recuadros — RESALTADOS (sin acción)

| Nombre | Clases distintivas | Icono / título |
|---|---|---|
| Simple | `dp-callout-color-lg-tip … dp-callout-type-title-bar` | sin título |
| Título destacado | `dp-callout-type-default dp-callout-color-dp-primary` | `h3.card-title` |
| Profundización (Para pensar / reflexionar) | `dp-callout-type-info dp-callout-color-warning` + `.dp-callout-side-emphasis` amarillo | `fa-lightbulb` — "Una pausa para reflexionar" |
| Atención | `dp-callout-color-danger` | `fa-exclamation-triangle` — "No pases de largo" |
| Importante | `dp-callout-color-success` (edu) / `dp-callout-color-lg-warning` (posg) | `fa-exclamation-circle` — "No pases de largo" |
| Dato curioso | `dp-callout-color-lg-info` | `fa-glasses` — "Dato curioso" |
| Ejemplos | `dp-callout-color-dp-primary dp-callout-type-info` | `fa-copy` — "Ejemplos que iluminan" (link en superposición si es extenso) |
| Clase Sincrónica | `dp-content-block … data-title="Overlap heading"` — h3 con `margin-top:-40px` | "Clase Sincrónica" |
| Laboratorio de ideas | `dp-content-block data-title="Lecture Hook"` + `dp-shape-peak-r` | `fa-flask` — desafío personal sin entrega |
| Bitácora de aprendizaje | div custom, borde izq `#003366` | `fa-diagnoses` — recorrido personal a largo plazo |
| Video / Podcast embebido | wrapper gradiente `linear-gradient(135deg,#003087,#007bff)` | `fa-youtube` / `fa-headphones` — "Auriculares on" |

Variantes de estilo: **Original / Original sin bordes (`border-0`) / Fondo sin borde**.

## 8. Figuras

Campos (sugerencia del sistema — **dónde va cada uno**):
- **N° Figura**: dentro del contenido
- **Título** (<110): dentro del contenido
- **Texto alternativo** (<110): **FUERA del contenido, en un Comentario del DOCX**
- **Nota de pie** (fuente / referencia / link): dentro del contenido

Formato de epígrafe: `FIGURA "N°". Título de la figura` … `FUENTE / LINK`.

| Variante | Clases de `<img>` |
|---|---|
| Figura expandida | `dp-max-width dp-popup-image dp-image-rounded-10 dp-image-padded dp-image-bordered dp-image-shadow` (≈650px) |
| Figura estática | `dp-max-width dp-image-rounded-10 dp-image-bordered` (≈800px) |
| Lado a lado con texto | `dp-content-block dp-popup-gallery` `data-title="Image and Text"` — `figure.dp-image-padded.dp-image-bordered` + `figcaption`, en `.row.align-items-center` col-lg-6 / col-lg-6 |
| Múltiples (grilla) | `dp-popup-gallery` `data-title="Image Grid Gallery 3x3"` — col-lg-4, `img` con `height:200px` |
| En tabs/expander | `dp-panels-wrapper dp-tabs-pills-vertical` |
| Flipcards con figura | front: `img.mx-auto.d-block.object-fit-cover.dp-ratio-3-2` |

## 9. Tablas

Mismos 4 campos que figuras. Epígrafe: `Tabla n° "X". "Título <110"`.

- Estilo Canvas principal: `table.ic-Table.dp-shadow-b3.ic-Table--striped.dp-border-dir-all.cp-bg-dp-white` (border-radius 10, `table-layout:fixed`), `thead` oscuro (`#1b1e31` o `#004a80`).
- Variante simple: `table.ic-Table.table-bordered` con `thead.cp-bg-dp-primary`.
- Todas envueltas en `div.dp-table-scroll`.
- Una tabla también puede insertarse **como imagen** (mismo formato de epígrafe).

## 10. Videos / Multimedia — POLÍTICA

**No se incrustan videos externos (YouTube) directamente en Canvas.** Motivo: los
enlaces externos caducan / se eliminan / cambian. Se usan:
- **enlaces directos**, o
- **servicios de video institucionales** (Instructure Media / Canvas Studio):
  `iframe.lti-embed` con `src=".../external_tools/retrieve?display=borderless&url=…instructuremedia.com/lti/launch…"`.

(En los HTML de referencia aparecen algunos `youtube.com/embed` — son ejemplos del
componente, no el patrón final aprobado.)

- **Genially / presentación**: `iframe src="https://view.genially.com/<id>"` dentro de un wrapper `padding-bottom:56.25%`.
- **Recurso interactivo** (HTML propio): `iframe src=".../files/<id>/download"`. El texto alternativo tiene que venir embebido desde diseño (no hay forma de ponerlo en el iframe).

## 11. Modelo de actividad

**Contenido que ve el estudiante** (subtítulos H4): **Objetivo, Consigna, Pautas
de presentación, Criterios de evaluación, Anexo (opcional)**.

**Datos para el maquetador** (van en la **planilla de estructura**, no en la página):
Modalidad (individual/grupal), Tipo (obligatoria / no obligatoria), personas por
grupo, formato de entrega (archivos / cuadro de texto / URL / multimedia /
comentario).

Dos maquetas:
- **Simple**: H2 + secciones como H4.
- **"Content plus"**: `col-lg-8` (Título + Consigna) + `col-lg-4` (`dp-accordion-plus` con Objetivo / Pautas / Criterios / Anexo).

**Caso Mural**: doble info (consigna + título) **no duplicada**. Dentro del recurso
mural: tabla "INDICACIONES DENTRO DEL RECURSO MURAL" (Título <110 / Propósito /
Indicaciones) + "TABLA DE AYUDA TÉCNICA" (Crear Post / Escribir / Adjuntar / Finalizar).

## 12. Librería de snippets (`Snipped utilizados.html`)

3 tablas `Name | Snippet HTML to Add`:

1. **UCC Custom**: Actividades en grupo General · Actividad en grupo que mantiene grupos · Grupos de Auto-registro · Portafolio · FlipCards x2–x6 · Tabla EDUCACIÓN · Tabla POSGRADO · Check x1 / Multiple / x3 / x4 / Check-Lectura e Interacción · Completar · Ordenar elementos · Clasificación · Emparejamiento · Selección
2. **UCC - Educación**: CTA - Video / Lectura / Imagen / Podcast / Multi-Recursos / Actividad-Autoevaluación / Foro / Mural · Resaltado - Simple / Título destacado / Profundización / Atención / Dato curioso / Importante / Por ejemplo / Clase Sincrónica / Laboratorio de ideas / Bitácora de aprendizaje · Embebido - Video / Podcast
3. **UCC - Posgrado**: misma lista, tematizada oscura (`#1b1e31`), + "¿Qué vemos en el módulo?"

---

### Cómo se usa esto en la auditoría de fidelidad

Al comparar un `.imscc` generado contra este spec, revisar en cada página:
1. ¿Está la envoltura `dp-wrapper` completa (banner, `kl_introduction` con placeholder, `kl_readings2`)?
2. ¿La jerarquía de títulos respeta H1→H6 sin numeración y con los límites de caracteres?
3. Cada recuadro: ¿es el CTA/RESALTADO correcto según el icono y el nombre canónico? ¿Tiene intro que invita al link?
4. Interactivos: ¿clases `dp-*` correctas, `data-interactive-*` presentes, respuesta correcta marcada, feedback en los dos idiomas de estado con los textos estándar?
5. Figuras/tablas: ¿4 campos en su lugar (alt en comentario, resto dentro), epígrafe con el formato `FIGURA "N°"` / `Tabla n° "X"`?
6. Videos: ¿sin YouTube embebido directo? ¿link directo o LTI institucional?
7. Tema (educación/posgrado) aplicado de forma consistente en colores.
