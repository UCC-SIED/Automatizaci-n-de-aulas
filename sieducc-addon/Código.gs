/**
 * Asistente de Maquetación SiedUCC 2026.2
 * CONTROLADOR Y SERVICIOS — Google Docs DocumentApp + CardService.
 *
 * IDEA DE FONDO
 * -------------
 * El bloque gris de indicaciones dejó de ser una nota suelta: es el canal
 * por el que el documento le habla al generador del aula.
 *
 *   · Empieza SIEMPRE con la línea centinela UCC_SENTINELA. El generador
 *     descarta ese bloque, así que nunca llega al estudiante. Antes se
 *     publicaba: toda tabla de una columna se convierte en recuadro, y las
 *     indicaciones salían como cajas grises en Canvas.
 *   · Las líneas "Clave: valor" que siguen son legibles por el generador.
 *     Ahí viajan el componente a armar, la modalidad de la actividad, el
 *     texto alternativo, el id de Canvas Studio.
 *   · El contenido del componente va en la TABLA inmediatamente anterior.
 *     La tabla marca dónde empieza y dónde termina: el generador ya no
 *     tiene que adivinar el tramo, que era de donde salía la mayoría de
 *     los errores de maquetado.
 *
 * Lo que el asesor ve en el documento sigue siendo texto editable normal.
 */

/* ================================================================== */
/*  Constantes                                                         */
/* ================================================================== */
const UCC_VERSION = 'SiedUCC 2026.2';
const UCC_SENTINELA = 'SIEDUCC · INDICACIÓN INTERNA (no publicar)';

const UCC26 = Object.freeze({
  azul: '#003087', azulOscuro: '#003366', enlace: '#236FA1',
  texto: '#202124', gris: '#F0F4F8', borde: '#CBD5E0',
  amarillo: '#FFF9DB', amarilloFuerte: '#F4E600',
  naranja: '#FFF0E2', naranjaTexto: '#CC4E00',
  fondoTecnico: '#F1F3F5', grisTecnico: '#52606D', blanco: '#FFFFFF',
  fuente: 'Times New Roman', tamano: 11
});

/**
 * CTA institucionales. `link` es el texto con el que se publica el enlace:
 * el aula usa DOS y nada más —"Ver video" cuando del otro lado hay un
 * video y "Acceso al documento" para todo el resto, incluido un artículo.
 */
const CTA_UCC26 = Object.freeze({
  Video:        { titulo: 'Auriculares on',   link: 'Ver video',           clave: 'cta_video',    descripcion: 'Video' },
  Podcast:      { titulo: 'Auriculares on',   link: 'Acceso al documento', clave: 'cta_podcast',  descripcion: 'Podcast' },
  Lectura:      { titulo: 'Descubrí leyendo', link: 'Acceso al documento', clave: 'cta_lectura',  descripcion: 'Lectura' },
  Imagen:       { titulo: 'Miralo con lupa',  link: 'Acceso al documento', clave: 'cta_imagen',   descripcion: 'Imagen' },
  MultiRecursos:{ titulo: 'Caja de herramientas para usar', link: 'Acceso al documento', clave: 'cta_multiple', descripcion: 'Varios recursos' },
  Actividad:    { titulo: '¿Cómo vengo hasta acá?', link: 'Acceso al documento', clave: 'cta_actividad', descripcion: 'Actividad / autoevaluación' },
  Foro:         { titulo: 'Foro',             link: 'Acceso al documento', clave: 'cta_foro',     descripcion: 'Foro' },
  Mural:        { titulo: 'Voces que construyen', link: 'Acceso al documento', clave: 'cta_mural', descripcion: 'Mural colaborativo' }
});

/**
 * Recuadros. "No pases de largo" va SIEMPRE en la variante Importante
 * (ámbar, con el marcador): la variante Atención (roja, con el triángulo)
 * se sacó del catálogo porque se elegía por error.
 */
const BOX_UCC26 = Object.freeze({
  simple:     { titulo: 'Texto destacado',             clave: 'recuadro_simple',    fondo: UCC26.blanco,  acento: UCC26.azul },
  important:  { titulo: 'No pases de largo',           clave: 'recuadro_importante',fondo: UCC26.naranja, acento: UCC26.naranjaTexto },
  deepening:  { titulo: 'Una pausa para reflexionar',  clave: 'recuadro_pausa',     fondo: UCC26.amarillo,acento: '#757121' },
  examples:   { titulo: 'Ejemplos que iluminan',       clave: 'recuadro_ejemplos',  fondo: UCC26.gris,    acento: UCC26.azul },
  laboratory: { titulo: 'Laboratorio de ideas',        clave: 'recuadro_laboratorio',fondo:'#EDF5FD',     acento: UCC26.azul },
  logbook:    { titulo: 'Bitácora de aprendizaje',     clave: 'recuadro_bitacora',  fondo: '#F8F9FA',     acento: UCC26.azulOscuro },
  sync:       { titulo: 'Clase sincrónica',            clave: 'recuadro_sincronica',fondo: '#EDF3FF',     acento: UCC26.azul }
});

/** Componentes de varios ítems. Todos entran como tabla de una columna. */
const COMP_UCC26 = Object.freeze({
  expander:      { titulo: 'Expander',          clave: 'expander' },
  acordeon:      { titulo: 'Acordeón',          clave: 'acordeon' },
  tabs:          { titulo: 'Tabs horizontales', clave: 'tabs' },
  tabs_vertical: { titulo: 'Tabs verticales',   clave: 'tabs_vertical' },
  flip_card:     { titulo: 'Flip cards',        clave: 'flip_card' }
});

const MARCA_UCC26 = Object.freeze({
  tooltip:            { titulo: 'Tooltip',             clave: 'tooltip' },
  cita:               { titulo: 'Cita destacada',      clave: 'cita' },
  enlazar_actividad:  { titulo: 'Enlazar actividad',   clave: 'enlazar_actividad' },
  genially:           { titulo: 'Genially',            clave: 'genially' },
  no_maquetar:        { titulo: 'No maquetar',         clave: 'no_maquetar' }
});

function _uccOpcionesCTA() {
  return [
    ['Video · Auriculares on', 'Video'],
    ['Podcast · Auriculares on', 'Podcast'],
    ['Lectura · Descubrí leyendo', 'Lectura'],
    ['Imagen · Miralo con lupa', 'Imagen'],
    ['Varios · Caja de herramientas', 'MultiRecursos'],
    ['Actividad · ¿Cómo vengo hasta acá?', 'Actividad'],
    ['Foro', 'Foro'],
    ['Mural · Voces que construyen', 'Mural']
  ];
}
function _uccOpcionesRecuadro() {
  return [
    ['Simple', 'simple'],
    ['No pases de largo', 'important'],
    ['Una pausa para reflexionar', 'deepening'],
    ['Ejemplos que iluminan', 'examples'],
    ['Laboratorio de ideas', 'laboratory'],
    ['Bitácora de aprendizaje', 'logbook'],
    ['Clase sincrónica', 'sync']
  ];
}
function _uccOpcionesComponente() {
  return [
    ['Expander (se despliega hacia abajo)', 'expander'],
    ['Acordeón', 'acordeon'],
    ['Tabs horizontales', 'tabs'],
    ['Tabs verticales', 'tabs_vertical'],
    ['Flip cards (se dan vuelta)', 'flip_card']
  ];
}

/* ================================================================== */
/*  Infraestructura CardService                                        */
/* ================================================================== */
function getCardInput(e, campo) {
  const form = e && e.commonEventObject && e.commonEventObject.formInputs;
  const item = form && form[campo];
  const values = item && item.stringInputs && item.stringInputs.value;
  if (values && values.length) return String(values[0]);
  const legacy = e && e.formInput && e.formInput[campo];
  return Array.isArray(legacy) ? String(legacy[0] || '') : String(legacy || '');
}
function _uccNotify(message) {
  return CardService.newActionResponseBuilder()
    .setNotification(CardService.newNotification().setText(String(message))).build();
}
function _uccSafe(fn) {
  try { return _uccNotify(fn()); }
  catch (err) { console.error(err); return _uccNotify('Error: ' + (err.message || err)); }
}
function _uccNavigate(card) {
  return CardService.newActionResponseBuilder()
    .setNavigation(CardService.newNavigation().pushCard(card)).build();
}
function _uccSafeNavigation(builder) {
  try { return _uccNavigate(builder()); }
  catch (err) { console.error(err); return _uccNotify('Error al abrir: ' + err.message); }
}
function actionOpenStructure(e)  { return _uccSafeNavigation(buildStructureCard); }
function actionOpenCTA(e)        { return _uccSafeNavigation(buildCTACard); }
function actionOpenBoxes(e)      { return _uccSafeNavigation(buildBoxesCard); }
function actionOpenComponents(e) { return _uccSafeNavigation(buildComponentsCard); }
function actionOpenActivities(e) { return _uccSafeNavigation(buildActivitiesCard); }
function actionOpenMetadata(e)   { return _uccSafeNavigation(buildMetadataCard); }
function actionOpenExtras(e)     { return _uccSafeNavigation(buildExtrasCard); }
function actionOpenReview(e)     { return _uccSafeNavigation(function () { return buildReviewCard(''); }); }
function actionOpenAssistant(e)  { return actionOpenMetadata(e); }   // compatibilidad
function openFigureTableAssistant() { return buildMetadataCard(); }  // compatibilidad

/* ================================================================== */
/*  Acceso al documento                                                */
/* ================================================================== */
function _uccDocContext() {
  const doc = DocumentApp.getActiveDocument();
  if (!doc) throw new Error('Abrí un documento de Google Docs editable.');
  const tab = typeof doc.getActiveTab === 'function' ? doc.getActiveTab() : null;
  const docTab = tab && typeof tab.asDocumentTab === 'function' ? tab.asDocumentTab() : null;
  return { doc: doc, body: docTab ? docTab.getBody() : doc.getBody() };
}
/** Inserta después del bloque que contiene el cursor; sin cursor, al final. */
function _uccInsertion() {
  const context = _uccDocContext();
  const doc = context.doc, body = context.body;
  const cursor = doc.getCursor();
  if (!cursor) return { body: body, index: body.getNumChildren() };
  let node = cursor.getElement();
  while (node && node.getParent() && node.getParent() !== body) node = node.getParent();
  if (!node || node.getParent() !== body) return { body: body, index: body.getNumChildren() };
  return { body: body, index: body.getChildIndex(node) + 1 };
}

/* ================================================================== */
/*  Escritura con formato                                              */
/* ================================================================== */
function _uccParagraph(body, index, content, heading) {
  const p = body.insertParagraph(index, String(content));
  p.setHeading(heading || DocumentApp.ParagraphHeading.NORMAL)
    .setSpacingBefore(2).setSpacingAfter(5)
    .setAlignment(DocumentApp.HorizontalAlignment.LEFT);
  p.editAsText().setFontFamily(UCC26.fuente).setFontSize(UCC26.tamano)
    .setForegroundColor(UCC26.texto);
  return p;
}
/**
 * Viñeta de verdad, no un párrafo con "• " adelante.
 * Un "\n" dentro de insertParagraph NO abre un párrafo nuevo: queda un
 * salto blando dentro del mismo. Por eso los objetivos y la bibliografía
 * de 2026.1 salían como un bloque único y el generador no los separaba.
 */
function _uccBullet(body, index, texto) {
  const li = body.insertListItem(index, String(texto));
  li.setGlyphType(DocumentApp.GlyphType.BULLET)
    .setSpacingBefore(0).setSpacingAfter(2);
  li.editAsText().setFontFamily(UCC26.fuente).setFontSize(UCC26.tamano)
    .setForegroundColor(UCC26.texto);
  return li;
}
function _uccStyleTable(table, backgrounds) {
  table.setBorderColor(UCC26.borde).setBorderWidth(0.75);
  for (let r = 0; r < table.getNumRows(); r++) {
    const row = table.getRow(r);
    for (let c = 0; c < row.getNumCells(); c++) {
      const cell = row.getCell(c);
      cell.setBackgroundColor((backgrounds && backgrounds[r]) || UCC26.blanco);
      cell.setPaddingTop(8).setPaddingBottom(8).setPaddingLeft(10).setPaddingRight(10);
      cell.setVerticalAlignment(DocumentApp.VerticalAlignment.CENTER);
      for (let p = 0; p < cell.getNumChildren(); p++) {
        const el = cell.getChild(p);
        if (el.getType() === DocumentApp.ElementType.PARAGRAPH) {
          el.asParagraph().setAlignment(DocumentApp.HorizontalAlignment.LEFT)
            .setSpacingBefore(0).setSpacingAfter(0);
        }
      }
      cell.editAsText().setFontFamily(UCC26.fuente).setFontSize(UCC26.tamano)
        .setForegroundColor(UCC26.texto);
    }
  }
  return table;
}
function _uccInsertTable(body, index, rows, backgrounds) {
  return _uccStyleTable(body.insertTable(index, rows), backgrounds);
}
function _uccSetHeader(cell, color, foreground) {
  cell.setBackgroundColor(color);
  cell.editAsText().setBold(true).setForegroundColor(foreground || UCC26.blanco);
}
function _uccSpacer(body, index) {
  const p = _uccParagraph(body, index, '');
  p.setSpacingBefore(2).setSpacingAfter(10);
  return index + 1;
}

/**
 * Bloque de indicación interna. Primera línea: el centinela. Después, las
 * líneas "Clave: valor" que lee el generador, y al final el texto libre.
 * Como abre con el centinela, el generador lo descarta entero: no se
 * publica en Canvas.
 */
function _uccTechnical(body, index, datos, notas) {
  const tb = _uccInsertTable(body, index, [[UCC_SENTINELA]], [UCC26.fondoTecnico]);
  const cell = tb.getCell(0, 0);
  (datos || []).forEach(function (par) {
    if (par[1] === '' || par[1] === null || par[1] === undefined) return;
    cell.appendParagraph(par[0] + ': ' + par[1]);
  });
  (notas || []).forEach(function (linea) {
    if (linea) cell.appendParagraph('· ' + linea);
  });
  for (let i = 0; i < cell.getNumChildren(); i++) {
    const el = cell.getChild(i);
    if (el.getType() !== DocumentApp.ElementType.PARAGRAPH) continue;
    el.asParagraph().setSpacingBefore(0).setSpacingAfter(0)
      .editAsText().setFontFamily(UCC26.fuente).setFontSize(9)
      .setForegroundColor(UCC26.grisTecnico);
  }
  cell.getChild(0).asParagraph().editAsText().setBold(true);
  return index + 1;
}

/* ================================================================== */
/*  Validación de entradas                                             */
/* ================================================================== */
function _uccRequired(value, label, max) {
  const t = String(value || '').replace(/\s+/g, ' ').trim();
  if (!t) throw new Error('Completá ' + label + '.');
  if (max && t.length > max) throw new Error(label + ' supera los ' + max + ' caracteres.');
  return t;
}
function _uccOptional(value, max, label) {
  const t = String(value || '').trim();
  if (max && t.length > max) throw new Error(label + ' supera los ' + max + ' caracteres.');
  return t;
}
function _uccValidUrl(s) {
  const t = String(s || '').trim();
  if (!t) return '';
  if (!/^https?:\/\/\S+$/i.test(t)) throw new Error('La URL debe empezar con https:// o http://');
  return t;
}
/** Renglones no vacíos de un textarea. */
function _uccLineas(texto) {
  return String(texto || '').split(/\r?\n/)
    .map(function (x) { return x.trim(); })
    .filter(function (x) { return x.length > 0; });
}
/** Párrafos separados por un renglón en blanco. */
function _uccBloques(texto) {
  return String(texto || '').split(/\r?\n\s*\r?\n/)
    .map(function (x) { return x.replace(/\s+/g, ' ').trim(); })
    .filter(function (x) { return x.length > 0; });
}

/**
 * Numeración de página: SIEMPRE número punto número punto ("1.3.").
 * La versión anterior solo arreglaba el caso con espacio después del
 * número: "1.3 - Título", "1-3. Título" o "1.3.Título" pasaban de largo,
 * y aceptaba tres niveles.
 */
function uccNumeracionNormalizada(numero) {
  const crudo = String(numero || '').trim();
  if (!crudo) return '';
  const partes = crudo.match(/\d+/g);
  if (!partes || !partes.length) {
    throw new Error('La numeración debe ser un número, o número.número (ej.: 1.3).');
  }
  if (partes.length > 2) {
    throw new Error('La numeración admite dos niveles como máximo: usá 1.3, no ' +
                    partes.join('.') + '.');
  }
  return partes.join('.') + '.';
}
function uccTituloDePagina(numero, titulo) {
  const t = _uccRequired(titulo, 'el título de página', 110);
  const n = uccNumeracionNormalizada(numero);
  const completo = n ? n + ' ' + t.replace(/^[\s.\-–:,)]+/, '') : t;
  if (completo.length > 110) throw new Error('El título supera los 110 caracteres.');
  return completo;
}

/* ================================================================== */
/*  Estilos                                                            */
/* ================================================================== */
function applyHeading(kind) {
  const map = {
    H1: DocumentApp.ParagraphHeading.HEADING1, H2: DocumentApp.ParagraphHeading.HEADING2,
    H3: DocumentApp.ParagraphHeading.HEADING3, H4: DocumentApp.ParagraphHeading.HEADING4,
    H5: DocumentApp.ParagraphHeading.HEADING5, H6: DocumentApp.ParagraphHeading.HEADING6,
    NORMAL: DocumentApp.ParagraphHeading.NORMAL
  };
  if (!Object.prototype.hasOwnProperty.call(map, kind)) throw new Error('Estilo no válido.');
  const doc = _uccDocContext().doc, selection = doc.getSelection(), elements = [];
  if (selection) selection.getRangeElements().forEach(function (x) { elements.push(x.getElement()); });
  else if (doc.getCursor()) elements.push(doc.getCursor().getElement());
  if (!elements.length) throw new Error('Seleccioná un párrafo o ubicá el cursor.');
  const seen = [];
  elements.forEach(function (el) {
    while (el && el.getType() !== DocumentApp.ElementType.PARAGRAPH && el.getParent()) el = el.getParent();
    if (!el || el.getType() !== DocumentApp.ElementType.PARAGRAPH || seen.indexOf(el) >= 0) return;
    seen.push(el);
    const p = el.asParagraph();
    if (kind === 'H2' && p.getText().trim().length > 110) {
      throw new Error('El título de página supera los 110 caracteres.');
    }
    p.setHeading(map[kind]);
    if (kind === 'NORMAL') p.editAsText().setFontFamily(UCC26.fuente).setFontSize(UCC26.tamano);
  });
  return 'Estilo aplicado a ' + seen.length + ' párrafo(s).';
}
function actionApplyHeading(e) { return _uccSafe(function () { return applyHeading(getCardInput(e, 'estilo_kind')); }); }

function insertContentPage(numero, titulo) {
  const completo = uccTituloDePagina(numero, titulo);
  const pos = _uccInsertion();
  _uccParagraph(pos.body, pos.index, completo, DocumentApp.ParagraphHeading.HEADING2)
    .setSpacingAfter(8);
  return 'Página insertada: ' + completo;
}
function actionInsertContentPage(e) {
  return _uccSafe(function () {
    return insertContentPage(getCardInput(e, 'page_numero'), getCardInput(e, 'page_title_input'));
  });
}

/* ================================================================== */
/*  Estructura de módulo                                               */
/* ================================================================== */
function insertModule2026(data) {
  const carrera = _uccRequired(data.carrera, 'la carrera');
  const asignatura = _uccRequired(data.asignatura, 'la asignatura');
  const docente = _uccRequired(data.docente, 'el docente');
  const nombre = _uccRequired(data.nombre, 'el nombre del módulo', 110);
  const numero = String(data.numero || '').replace(/\D/g, '') || '1';

  const pos = _uccInsertion(), body = pos.body;
  let i = pos.index;
  i = _uccMeta(body, i, 'Carrera', carrera);
  i = _uccMeta(body, i, 'Asignatura', asignatura);
  i = _uccMeta(body, i, 'Docente', docente);
  _uccParagraph(body, i++, 'Módulo ' + numero + ': ' + nombre, DocumentApp.ParagraphHeading.HEADING1);

  _uccParagraph(body, i++, 'Introducción', DocumentApp.ParagraphHeading.HEADING2);
  _uccParagraph(body, i++, '[Desarrollar la introducción del módulo.]');

  _uccParagraph(body, i++, 'Objetivos del módulo', DocumentApp.ParagraphHeading.HEADING2);
  _uccParagraph(body, i++, 'Al finalizar este módulo lograrás:');
  _uccBullet(body, i++, '[Objetivo 1]');
  _uccBullet(body, i++, '[Objetivo 2]');

  _uccParagraph(body, i++, numero + '.1. [Título de la primera página]',
                DocumentApp.ParagraphHeading.HEADING2);
  _uccParagraph(body, i++, '[Desarrollo del contenido.]');

  _uccParagraph(body, i++, 'Conclusión', DocumentApp.ParagraphHeading.HEADING2);
  _uccParagraph(body, i++, '[Redactar la conclusión.]');

  i = _uccBibliografia(body, i);

  i = _uccTechnical(body, i,
    [['Componente', 'modulo'], ['Modulo', numero]],
    ['Cada página del módulo es un H2 con numeración ' + numero + '.N. (máximo 110 caracteres).',
     'Completar todos los marcadores entre corchetes antes de entregar.']);
  _uccSpacer(body, i);
  return 'Estructura del módulo ' + numero + ' insertada.';
}
function _uccMeta(body, i, label, value) {
  const p = _uccParagraph(body, i, label + ': ' + value);
  p.editAsText().setBold(0, label.length, true);
  return i + 1;
}
function actionInsertModule(e) {
  return _uccSafe(function () {
    return insertModule2026({
      carrera: getCardInput(e, 'module_carrera'),
      asignatura: getCardInput(e, 'module_asignatura'),
      docente: getCardInput(e, 'module_docente'),
      numero: getCardInput(e, 'module_numero'),
      nombre: getCardInput(e, 'module_nombre')
    });
  });
}

/* ================================================================== */
/*  CTA                                                                */
/* ================================================================== */
function insertCTAUCC(tipo, opts) {
  if (!Object.prototype.hasOwnProperty.call(CTA_UCC26, tipo)) throw new Error('CTA no válido.');
  const cta = CTA_UCC26[tipo], data = opts || {};
  const bajada = _uccOptional(data.titulo, 110, 'La bajada');
  const intro = _uccOptional(data.intro, 0, 'La invitación') ||
                '[Escribir la invitación y la tarea para el estudiante.]';
  const cita = _uccOptional(data.cita, 0, 'La referencia');
  const url = _uccValidUrl(data.url);

  // El rótulo va SOLO en la primera fila: es el nombre institucional del
  // recuadro y el generador lo usa para reconocerlo. En 2026.1 se le
  // pegaba " · <título>" y ese agregado se perdía al publicar.
  const rows = [[cta.titulo]];
  if (bajada) rows.push([bajada]);
  rows.push([intro]);
  if (cita) rows.push([cita]);
  rows.push([url ? cta.link : cta.link + ' (PEGAR LINK)']);

  const fondos = [UCC26.azul];
  while (fondos.length < rows.length) fondos.push(UCC26.blanco);

  const pos = _uccInsertion(), body = pos.body;
  let i = pos.index;
  const table = _uccInsertTable(body, i++, rows, fondos);
  _uccSetHeader(table.getCell(0, 0), UCC26.azul, UCC26.blanco);
  if (bajada) table.getCell(1, 0).editAsText().setBold(true);
  _uccLink(table.getCell(rows.length - 1, 0), url);

  i = _uccTechnical(body, i,
    [['Componente', cta.clave], ['URL', url]],
    ['Recuadro ' + cta.descripcion + ' · ' + cta.titulo + '.',
     url ? '' : 'PENDIENTE: falta la URL definitiva.',
     tipo === 'Foro' ? 'Confirmar que el foro esté habilitado antes de publicar.' : '',
     tipo === 'Mural' ? 'Definir si se participa en el mural o hay entrega evaluable en Canvas.' : '']);
  _uccSpacer(body, i);
  return 'CTA ' + cta.descripcion + ' insertado.';
}
function _uccLink(cell, url) {
  const text = cell.editAsText();
  text.setBold(true);
  if (url) {
    text.setForegroundColor(UCC26.enlace).setLinkUrl(url);
  } else {
    text.setForegroundColor(UCC26.naranjaTexto);   // pendiente, no es un link
  }
}
function actionInsertCTA(e) {
  return _uccSafe(function () {
    return insertCTAUCC(getCardInput(e, 'cta_tipo'), {
      titulo: getCardInput(e, 'cta_titulo'),
      intro: getCardInput(e, 'cta_intro'),
      cita: getCardInput(e, 'cta_cita'),
      url: getCardInput(e, 'cta_link')
    });
  });
}

/* ================================================================== */
/*  Recuadros                                                          */
/* ================================================================== */
function insertBoxUCC(tipo, text) {
  if (!Object.prototype.hasOwnProperty.call(BOX_UCC26, tipo)) throw new Error('Recuadro no válido.');
  const model = BOX_UCC26[tipo];
  const bloques = _uccBloques(text);
  const rows = [[model.titulo]];
  if (bloques.length) bloques.forEach(function (b) { rows.push([b]); });
  else rows.push(['[Escribir el contenido del recuadro.]']);

  const fondos = [model.fondo];
  while (fondos.length < rows.length) fondos.push(UCC26.blanco);

  const pos = _uccInsertion(), body = pos.body;
  let i = pos.index;
  const table = _uccInsertTable(body, i++, rows, fondos);
  _uccSetHeader(table.getCell(0, 0), model.fondo, model.acento);
  i = _uccTechnical(body, i,
    [['Componente', model.clave]],
    ['Recuadro ' + model.titulo + '. Es una caja informativa, no un llamado a la acción.']);
  _uccSpacer(body, i);
  return 'Resaltado insertado: ' + model.titulo + '.';
}
function actionInsertBox(e) {
  return _uccSafe(function () {
    return insertBoxUCC(getCardInput(e, 'recuadro_tipo'), getCardInput(e, 'recuadro_texto'));
  });
}
function insertSimpleBoxUCC()    { return insertBoxUCC('simple'); }
function insertDeepeningBoxUCC() { return insertBoxUCC('deepening'); }
function insertSyncClassBoxUCC() { return insertBoxUCC('sync'); }

/* ================================================================== */
/*  Componentes interactivos                                           */
/* ================================================================== */
/**
 * Cada ítem entra como DOS filas de una tabla de una columna: título y
 * contenido. Es la geometría que el generador lee sin ambigüedad, y la
 * tabla marca dónde termina el componente.
 */
function insertComponentUCC(tipo, items) {
  if (!Object.prototype.hasOwnProperty.call(COMP_UCC26, tipo)) throw new Error('Componente no válido.');
  const model = COMP_UCC26[tipo];
  const pares = [];
  _uccLineas(items).forEach(function (linea) {
    const m = linea.match(/^(.{1,60}?)\s*[=:]\s*(.+)$/);
    if (m) pares.push([m[1].trim(), m[2].trim()]);
  });
  if (pares.length < 2) {
    throw new Error('Cargá al menos dos ítems con el formato  Título = Contenido.');
  }
  const rows = [];
  pares.forEach(function (p) { rows.push([p[0]]); rows.push([p[1]]); });
  const fondos = [];
  for (let r = 0; r < rows.length; r++) fondos.push(r % 2 === 0 ? UCC26.gris : UCC26.blanco);

  const pos = _uccInsertion(), body = pos.body;
  let i = pos.index;
  const table = _uccInsertTable(body, i++, rows, fondos);
  for (let r = 0; r < rows.length; r += 2) {
    table.getCell(r, 0).editAsText().setBold(true).setForegroundColor(UCC26.azul);
  }
  i = _uccTechnical(body, i,
    [['Componente', model.clave], ['Items', String(pares.length)]],
    [model.titulo + ' con ' + pares.length + ' ítems.',
     'Las filas van de a pares: título y contenido.']);
  _uccSpacer(body, i);
  return model.titulo + ' insertado (' + pares.length + ' ítems).';
}
function actionInsertComponent(e) {
  return _uccSafe(function () {
    return insertComponentUCC(getCardInput(e, 'comp_tipo'), getCardInput(e, 'comp_items'));
  });
}

/** Quick check: una fila por pregunta, terminando en Verdadero o Falso. */
function insertQuickCheckUCC(texto) {
  const preguntas = [];
  _uccLineas(texto).forEach(function (linea) {
    const m = linea.match(/^(.*?)[\s(]*\b(verdadero|falso)\b[\s).]*$/i);
    if (m && m[1].trim()) {
      preguntas.push([m[1].replace(/^\s*\d+\s*[.)\-]?\s*/, '').trim(),
                      m[2].charAt(0).toUpperCase() + m[2].slice(1).toLowerCase()]);
    }
  });
  if (preguntas.length < 2) {
    throw new Error('Cargá al menos dos preguntas que terminen en Verdadero o Falso.');
  }
  const rows = [['Quick check']];
  preguntas.forEach(function (p, n) { rows.push([(n + 1) + '. ' + p[0] + ' ' + p[1]]); });
  const fondos = [UCC26.azulOscuro];
  while (fondos.length < rows.length) fondos.push(UCC26.blanco);

  const pos = _uccInsertion(), body = pos.body;
  let i = pos.index;
  const table = _uccInsertTable(body, i++, rows, fondos);
  _uccSetHeader(table.getCell(0, 0), UCC26.azulOscuro, UCC26.blanco);
  i = _uccTechnical(body, i,
    [['Componente', 'quick_check'], ['Preguntas', String(preguntas.length)]],
    ['Se publica como "¿Cómo vengo hasta acá?", de a dos tarjetas por fila.']);
  _uccSpacer(body, i);
  return 'Quick check insertado (' + preguntas.length + ' preguntas).';
}
function actionInsertQuickCheck(e) {
  return _uccSafe(function () { return insertQuickCheckUCC(getCardInput(e, 'qc_preguntas')); });
}

/** Serie de figuras: se publican en solapas, una por figura. */
function insertSerieFigurasUCC(desde, hasta) {
  const a = parseInt(String(desde).replace(/\D/g, ''), 10);
  const b = parseInt(String(hasta).replace(/\D/g, ''), 10);
  if (!a || !b || b <= a) throw new Error('Indicá un rango válido, por ejemplo de 3 a 7.');
  const pos = _uccInsertion(), body = pos.body;
  let i = pos.index;
  i = _uccTechnical(body, i,
    [['Componente', 'galeria'], ['Figuras', a + '-' + b]],
    ['Las figuras ' + a + ' a ' + b + ' se publican en solapas verticales.',
     'Cada figura conserva su epígrafe, su nota y su texto alternativo.']);
  _uccSpacer(body, i);
  return 'Serie de figuras ' + a + ' a ' + b + ' marcada.';
}
function actionInsertSerie(e) {
  return _uccSafe(function () {
    return insertSerieFigurasUCC(getCardInput(e, 'serie_desde'), getCardInput(e, 'serie_hasta'));
  });
}

/** Marcas sobre el texto que ya está escrito. */
function insertMarcaUCC(tipo, detalle) {
  if (!Object.prototype.hasOwnProperty.call(MARCA_UCC26, tipo)) throw new Error('Marca no válida.');
  const model = MARCA_UCC26[tipo];
  const texto = _uccOptional(detalle, 0, 'El detalle');
  if (tipo === 'genially' && !texto) throw new Error('Pegá la URL del Genially.');
  if (tipo === 'tooltip' && texto.indexOf('=') < 0) {
    throw new Error('Para el tooltip escribí  Término = Definición.');
  }
  const pos = _uccInsertion(), body = pos.body;
  let i = pos.index;
  i = _uccTechnical(body, i,
    [['Componente', model.clave], ['Detalle', texto]],
    [model.titulo + '.',
     tipo === 'no_maquetar' ? 'Este tramo NO se publica en Canvas.' : '',
     tipo === 'enlazar_actividad' ? 'El enlace apunta a la actividad del mismo módulo.' : '']);
  _uccSpacer(body, i);
  return model.titulo + ' marcado.';
}
function actionInsertMarca(e) {
  return _uccSafe(function () {
    return insertMarcaUCC(getCardInput(e, 'marca_tipo'), getCardInput(e, 'marca_detalle'));
  });
}

/* ================================================================== */
/*  Actividades                                                        */
/* ================================================================== */
function insertActivityUCC(data) {
  const title = _uccRequired(data.titulo, 'el título de la actividad', 110);
  const modalidad = data.modalidad, caracter = data.tipo, entrega = data.entrega;
  if (['Individual', 'Grupal'].indexOf(modalidad) < 0) throw new Error('Modalidad incorrecta.');
  if (['Obligatoria', 'No obligatoria', 'Final integradora'].indexOf(caracter) < 0) {
    throw new Error('Carácter de actividad incorrecto.');
  }
  if (['Archivo', 'Texto', 'URL', 'Multimedia', 'Comentario'].indexOf(entrega) < 0) {
    throw new Error('Formato de entrega incorrecto.');
  }
  const grupo = _uccOptional(data.grupo, 0, 'Integrantes');
  if (modalidad === 'Grupal' && (!/^[1-9]\d*$/.test(grupo) || Number(grupo) < 2)) {
    throw new Error('Para una actividad grupal indicá al menos 2 integrantes.');
  }
  const nota = String(data.nota || '').replace(/\D/g, '');

  const pos = _uccInsertion(), body = pos.body;
  let i = pos.index;
  // El título va sin el prefijo "Actividad obligatoria N:": Canvas ya
  // muestra ese nombre en el banner de la entrega.
  _uccParagraph(body, i++, title, DocumentApp.ParagraphHeading.HEADING2);
  ['Contextualización', 'Consigna', 'Pautas de presentación',
   'Criterios de evaluación', 'Anexo'].forEach(function (name) {
    _uccParagraph(body, i++, name, DocumentApp.ParagraphHeading.HEADING3);
    _uccParagraph(body, i++, '[Completar ' + name.toLowerCase() + '.]');
  });
  if (nota) {
    const p = _uccParagraph(body, i++,
      'Calificación mínima para aprobar la actividad: ' + nota + '/100.');
    p.editAsText().setBold(true);
  }
  i = _uccTechnical(body, i,
    [['Componente', 'actividad'], ['Modalidad', modalidad.toLowerCase()],
     ['Caracter', caracter.toLowerCase()], ['Entrega', entrega.toLowerCase()],
     ['Integrantes', modalidad === 'Grupal' ? grupo : ''],
     ['Nota minima', nota]],
    [modalidad === 'Grupal'
      ? 'Grupal: el aula agrega sola el instructivo "Actividad Grupal".'
      : 'Individual: no lleva instructivo de grupos.',
     'Verificar la configuración de entrega y evaluación en Canvas.']);
  _uccSpacer(body, i);
  return 'Actividad insertada (' + modalidad.toLowerCase() + ', ' +
         caracter.toLowerCase() + ').';
}
function actionInsertActivity(e) {
  return _uccSafe(function () {
    return insertActivityUCC({
      titulo: getCardInput(e, 'actividad_titulo'),
      modalidad: getCardInput(e, 'actividad_modalidad'),
      tipo: getCardInput(e, 'actividad_tipo'),
      entrega: getCardInput(e, 'actividad_entrega'),
      grupo: getCardInput(e, 'actividad_grupo'),
      nota: getCardInput(e, 'actividad_nota')
    });
  });
}

/* ================================================================== */
/*  Figuras y tablas                                                   */
/* ================================================================== */
function _uccCounter(kind) {
  const props = PropertiesService.getDocumentProperties();
  if (!props) throw new Error('No están disponibles las propiedades de este documento.');
  const key = kind === 'tabla' ? 'TAB_COUNTER' : 'FIG_COUNTER';
  const lock = LockService.getDocumentLock();
  if (lock) lock.waitLock(10000);
  try {
    const n = Number(props.getProperty(key) || '0') + 1;
    props.setProperty(key, String(n));
    return n;
  } finally { if (lock) lock.releaseLock(); }
}
function peekNextNumber(kind) {
  const props = PropertiesService.getDocumentProperties();
  if (!props) return 1;
  return Number(props.getProperty(kind === 'tabla' ? 'TAB_COUNTER' : 'FIG_COUNTER') || '0') + 1;
}
function uccEstadoContadores() {
  try {
    return 'La próxima será <b>Figura ' + peekNextNumber('figura') +
           '</b> y <b>Tabla ' + peekNextNumber('tabla') + '</b>. ' +
           'Los contadores son de este documento: si el módulo va en un ' +
           'archivo propio, la numeración arranca en 1 como corresponde.';
  } catch (err) { return 'Contadores no disponibles.'; }
}
function resetCounters() {
  const props = PropertiesService.getDocumentProperties();
  if (!props) throw new Error('No hay propiedades del documento.');
  props.deleteProperty('TAB_COUNTER'); props.deleteProperty('FIG_COUNTER');
  return 'Contadores reiniciados.';
}
function actionResetCounters(e) { return _uccSafe(resetCounters); }

function insertMetadataUCC(data) {
  const kind = String(data.tipo || '').toLowerCase();
  if (['figura', 'tabla'].indexOf(kind) < 0) throw new Error('Elegí Figura o Tabla.');
  const title = _uccRequired(data.titulo, 'el título', 110);
  const alt = _uccRequired(data.alt, 'el texto alternativo', 110);
  const note = _uccOptional(data.nota, 0, 'La nota');
  const url = _uccValidUrl(data.url);
  const origen = data.origen === 'propia' ? 'propia' : 'diseno';

  const pos = _uccInsertion(), body = pos.body;
  let i = pos.index;
  const num = _uccCounter(kind);

  // Epígrafe en un solo renglón: "Figura 3. Título".
  const label = (kind === 'tabla' ? 'Tabla ' : 'Figura ') + num + '. ' + title;
  const p = _uccParagraph(body, i++, label);
  p.setAlignment(DocumentApp.HorizontalAlignment.CENTER);
  p.editAsText().setBold(true).setFontSize(10);

  // El texto alternativo va como párrafo propio con el rótulo exacto que
  // el generador reconoce: lo pasa al atributo alt de la imagen y lo saca
  // de la página. En 2026.1 vivía solo en la ficha y se perdía.
  _uccParagraph(body, i++, 'texto alternativo: ' + alt);

  if (origen === 'diseno') {
    const ph = _uccInsertTable(body, i++,
      [['[La figura la provee diseño: ' + (kind === 'tabla' ? 'Tabla ' : 'Figura ') + num + ']']],
      [UCC26.gris]);
    ph.getCell(0, 0).getChild(0).asParagraph()
      .setAlignment(DocumentApp.HorizontalAlignment.CENTER);
  }
  if (note) {
    const n = _uccParagraph(body, i++, 'Nota. ' + note);
    n.editAsText().setFontSize(10).setItalic(true);
  }
  if (url) _uccParagraph(body, i++, 'Fuente: ' + url).editAsText().setLinkUrl(8, 7 + url.length, url);

  i = _uccTechnical(body, i,
    [['Componente', kind], ['Numero', String(num)], ['Origen', origen], ['Alt', alt]],
    [origen === 'diseno'
      ? 'Reemplazar el marcador por el archivo de la carpeta de diseño.'
      : 'Se publica la imagen que está en el documento.',
     'Si la imagen tiene mucho texto se publica ampliable.']);
  _uccSpacer(body, i);
  return (kind === 'tabla' ? 'Tabla ' : 'Figura ') + num + ' insertada.';
}
function insertFromAssistant(data) { return insertMetadataUCC(data); }
function actionInsertMetadata(e) {
  return _uccSafe(function () {
    return insertMetadataUCC({
      tipo: getCardInput(e, 'meta_tipo'), titulo: getCardInput(e, 'meta_titulo'),
      alt: getCardInput(e, 'meta_alt'), nota: getCardInput(e, 'meta_nota'),
      url: getCardInput(e, 'meta_url'), origen: getCardInput(e, 'meta_origen')
    });
  });
}

/* ================================================================== */
/*  Video de Canvas Studio y bibliografía                              */
/* ================================================================== */
/** El id del medio: "<uuid>-<número>", pelado o dentro del iframe. */
function uccMediaId(texto) {
  const t = String(texto || '');
  let m = t.match(/custom_arc_media_id(?:%3D|=)([0-9a-f-]{36}-\d+)/i);
  if (m) return m[1];
  m = t.match(/\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}-\d+\b/i);
  return m ? m[0] : '';
}
function insertVideoBlockUCC(tipo, nombre, mediaRaw) {
  const esIntro = tipo === 'introVideo';
  const rotulo = esIntro ? 'Video introductorio' : 'Video de desarrollo';
  const ref = _uccOptional(nombre, 80, 'El nombre del video');
  const media = uccMediaId(mediaRaw);
  if (String(mediaRaw || '').trim() && !media) {
    throw new Error('No reconozco el id de Studio. Va "uuid-número", o pegá el iframe entero.');
  }
  const pos = _uccInsertion(), body = pos.body;
  let i = pos.index;
  // Marcador que el generador entiende como "acá va el video".
  const marca = '(AQUÍ VA VIDEO' + (ref ? ' ' + ref : '') + ')';
  const table = _uccInsertTable(body, i++, [[rotulo], [marca]], [UCC26.azul, UCC26.blanco]);
  _uccSetHeader(table.getCell(0, 0), UCC26.azul);
  table.getCell(1, 0).editAsText().setForegroundColor(UCC26.grisTecnico).setItalic(true);

  i = _uccTechnical(body, i,
    [['Componente', 'video_studio'], ['Ubicacion', esIntro ? 'introduccion' : 'pagina'],
     ['Nombre', ref], ['Media id', media]],
    [rotulo + ' de Canvas Studio.',
     media ? 'El video se incrusta solo con este id.'
           : 'PENDIENTE: pegar el id de Studio cuando compartan la colección.']);
  _uccSpacer(body, i);
  return rotulo + (media ? ' con id cargado.' : ' insertado (falta el id).');
}
function insertDevVideoBlock()   { return insertVideoBlockUCC('devVideo', '', ''); }
function insertIntroVideoBlock() { return insertVideoBlockUCC('introVideo', '', ''); }
function actionInsertVideo(e) {
  return _uccSafe(function () {
    return insertVideoBlockUCC(getCardInput(e, 'video_tipo'),
                               getCardInput(e, 'video_nombre'),
                               getCardInput(e, 'video_media_id'));
  });
}

function _uccBibliografia(body, i) {
  _uccParagraph(body, i++, 'Bibliografía', DocumentApp.ParagraphHeading.HEADING2);
  _uccParagraph(body, i++, 'Obligatoria', DocumentApp.ParagraphHeading.HEADING3);
  _uccParagraph(body, i++, '[Referencias según APA 7.]');
  _uccParagraph(body, i++, 'Sugerida y complementaria', DocumentApp.ParagraphHeading.HEADING3);
  _uccParagraph(body, i++, '[Referencias según APA 7.]');
  return i;
}
function insertBibliographyBlock() {
  const pos = _uccInsertion(), body = pos.body;
  let i = _uccBibliografia(pos.body, pos.index);
  i = _uccTechnical(body, i,
    [['Componente', 'bibliografia']],
    ['Los dos apartados van siempre, aunque uno quede vacío.',
     'Citar textos, videos, podcasts y sitios en APA 7, con el enlace.']);
  _uccSpacer(body, i);
  return 'Bibliografía insertada.';
}
function actionInsertBiblio(e) { return _uccSafe(insertBibliographyBlock); }
function actionInsertExtraBlock(e) {   // compatibilidad con 2026.1
  return _uccSafe(function () {
    const tipo = getCardInput(e, 'extra_tipo');
    if (tipo === 'biblio') return insertBibliographyBlock();
    return insertVideoBlockUCC(tipo, '', '');
  });
}

/* ================================================================== */
/*  Revisión previa a la entrega                                       */
/* ================================================================== */
/**
 * Corre los controles que, cuando fallan, obligan a rehacer el aula a
 * mano. No modifica el documento.
 */
function uccRevisarDocumento() {
  const body = _uccDocContext().body;
  const problemas = [], avisos = [];
  let figuras = 0, conAlt = 0, marcadores = 0;
  let hayBiblio = false, hayObligatoria = false, haySugerida = false;
  const titulos = [];

  for (let i = 0; i < body.getNumChildren(); i++) {
    const child = body.getChild(i);
    const tipo = child.getType();

    if (tipo === DocumentApp.ElementType.TABLE) {
      const t = child.asTable().getText();
      if (t.indexOf(UCC_SENTINELA) === 0) continue;       // bloque interno
      if (/\[[^\]]{3,}\]/.test(t)) marcadores++;
      if (/\(PEGAR LINK\)/.test(t)) avisos.push('Hay un enlace sin completar.');
      continue;
    }
    if (tipo !== DocumentApp.ElementType.PARAGRAPH &&
        tipo !== DocumentApp.ElementType.LIST_ITEM) continue;

    const texto = child.asText ? child.getText() : '';
    if (/\[[^\]]{3,}\]/.test(texto)) marcadores++;
    if (/^\s*(figura|tabla)\s+\d+\s*\./i.test(texto)) figuras++;
    if (/^\s*texto alternativo\s*:/i.test(texto)) conAlt++;

    if (tipo !== DocumentApp.ElementType.PARAGRAPH) continue;
    const p = child.asParagraph(), h = p.getHeading(), txt = p.getText().trim();
    if (h === DocumentApp.ParagraphHeading.HEADING2) {
      if (/^\d/.test(txt)) titulos.push(txt);
      if (txt.length > 110) problemas.push('Título de más de 110 caracteres: "' + txt.slice(0, 40) + '…"');
      if (/^bibliograf/i.test(txt)) hayBiblio = true;
    }
    if (h === DocumentApp.ParagraphHeading.HEADING3) {
      if (/^obligatoria$/i.test(txt)) hayObligatoria = true;
      if (/^sugerida/i.test(txt)) haySugerida = true;
    }
  }

  titulos.forEach(function (t) {
    if (!/^\d+(?:\.\d+)?\.\s\S/.test(t)) {
      problemas.push('Numeración fuera de norma: "' + t.slice(0, 40) + '" (va 1.3.)');
    } else if (/^\d+\.\d+\.\d/.test(t)) {
      problemas.push('Numeración de tres niveles: "' + t.slice(0, 40) + '"');
    }
  });
  if (figuras > conAlt) {
    problemas.push((figuras - conAlt) + ' figura(s) sin texto alternativo.');
  }
  if (hayBiblio && !(hayObligatoria && haySugerida)) {
    problemas.push('La bibliografía no tiene los dos apartados (Obligatoria y Sugerida y complementaria).');
  }
  if (marcadores) avisos.push(marcadores + ' marcador(es) [entre corchetes] sin completar.');
  if (!titulos.length) avisos.push('No encontré páginas numeradas (H2 con 1.1., 1.2., …).');

  let salida = '<b>Revisión · ' + UCC_VERSION + '</b><br><br>';
  if (!problemas.length && !avisos.length) {
    return salida + 'Sin observaciones: el documento está listo para maquetar.';
  }
  if (problemas.length) {
    salida += '<b>Hay que corregir</b><br>';
    problemas.forEach(function (x) { salida += '• ' + x + '<br>'; });
    salida += '<br>';
  }
  if (avisos.length) {
    salida += '<b>Para revisar</b><br>';
    _uccUnicos(avisos).forEach(function (x) { salida += '• ' + x + '<br>'; });
  }
  return salida;
}
function _uccUnicos(lista) {
  const vistos = {}, salida = [];
  lista.forEach(function (x) { if (!vistos[x]) { vistos[x] = true; salida.push(x); } });
  return salida;
}
function actionRunReview(e) {
  try {
    return _uccNavigate(buildReviewCard(uccRevisarDocumento()));
  } catch (err) {
    console.error(err);
    return _uccNotify('Error al revisar: ' + err.message);
  }
}

/* ================================================================== */
/*  Utilidad heredada                                                  */
/* ================================================================== */
/**
 * Quita la numeración manual de los subtítulos.
 * CUIDADO: el generador usa la numeración de un subtítulo ("1. El diario
 * estoico") para publicarlo un nivel más abajo. Si la borrás, todos los
 * subtítulos quedan al mismo nivel. Usala solo para limpiar numeración
 * heredada de otro documento.
 */
function stripNumbersFromSubheads() {
  const body = _uccDocContext().body;
  let cleaned = 0;
  const rex = /^\s*(?:Página\s+)?\d+(?:\.\d+)*[.)]?\s*[-–:]?\s+/i;
  const niveles = [DocumentApp.ParagraphHeading.HEADING3, DocumentApp.ParagraphHeading.HEADING4,
                   DocumentApp.ParagraphHeading.HEADING5, DocumentApp.ParagraphHeading.HEADING6];
  for (let i = 0; i < body.getNumChildren(); i++) {
    const child = body.getChild(i);
    if (child.getType() !== DocumentApp.ElementType.PARAGRAPH) continue;
    const p = child.asParagraph();
    if (niveles.indexOf(p.getHeading()) < 0) continue;
    const match = p.getText().match(rex);
    if (match) { p.editAsText().deleteText(0, match[0].length - 1); cleaned++; }
  }
  return 'Subtítulos limpiados: ' + cleaned + '. Revisá que no hayas perdido jerarquía.';
}
