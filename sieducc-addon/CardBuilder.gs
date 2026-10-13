/**
 * SiedUCC 2026.2 | VISTA: exclusivamente CardService.
 *
 * Cambios respecto de 2026.1:
 *  · Sección nueva "Componentes interactivos": tabs, expander, acordeón,
 *    flip cards, galería, quick check, tooltip, cita y destacados. Era el
 *    29 % de los pedidos de los asesores y no tenía ningún botón.
 *  · Sección nueva "Revisar documento": corre las validaciones del
 *    maquetador ANTES de entregar.
 *  · Se saca "No pases de largo · Atención" (el catálogo usa Importante).
 *  · El bloque de video pide el id de Canvas Studio.
 */

/* ------------------------------------------------------------------ */
/*  Fábricas de widgets                                                */
/* ------------------------------------------------------------------ */
function _uccAction(name) {
  return CardService.newAction().setFunctionName(name);
}
function _uccButton(label, action) {
  return CardService.newTextButton().setText(label).setOnClickAction(_uccAction(action));
}
function _uccButtonFilled(label, action) {
  return CardService.newTextButton().setText(label)
    .setTextButtonStyle(CardService.TextButtonStyle.FILLED)
    .setOnClickAction(_uccAction(action));
}
function _uccSelect(field, title, options, seleccionado) {
  const w = CardService.newSelectionInput()
    .setFieldName(field).setTitle(title)
    .setType(CardService.SelectionInputType.DROPDOWN);
  options.forEach(function (o, i) {
    const marcado = seleccionado ? (o[1] === seleccionado) : (i === 0);
    w.addItem(o[0], o[1], marcado);
  });
  return w;
}
function _uccText(field, title, hint, multilinea) {
  const w = CardService.newTextInput().setFieldName(field).setTitle(title);
  if (hint) w.setHint(hint);
  if (multilinea) w.setMultiline(true);
  return w;
}
function _uccNota(texto) {
  return CardService.newTextParagraph().setText(texto);
}
function _uccCard(title, subtitle) {
  return CardService.newCardBuilder().setHeader(
    CardService.newCardHeader().setTitle(title).setSubtitle(subtitle || UCC_VERSION)
  );
}

/* ------------------------------------------------------------------ */
/*  Página principal                                                   */
/* ------------------------------------------------------------------ */
function buildHomePage(e) {
  const card = _uccCard('Asistente de Maquetación SiedUCC',
                        'Material académico para Canvas · ' + UCC_VERSION);

  const nav = CardService.newCardSection().setHeader('Herramientas');
  [
    ['1 · Estructura y estilos', 'actionOpenStructure'],
    ['2 · Llamados a la acción', 'actionOpenCTA'],
    ['3 · Resaltados y recuadros', 'actionOpenBoxes'],
    ['4 · Componentes interactivos', 'actionOpenComponents'],
    ['5 · Actividades académicas', 'actionOpenActivities'],
    ['6 · Figuras y tablas', 'actionOpenMetadata'],
    ['7 · Bloques complementarios', 'actionOpenExtras']
  ].forEach(function (it) { nav.addWidget(_uccButton(it[0], it[1])); });
  card.addSection(nav);

  const rev = CardService.newCardSection().setHeader('Antes de entregar');
  rev.addWidget(_uccButtonFilled('Revisar documento', 'actionOpenReview'));
  rev.addWidget(_uccNota(
    'Controla lo que al maquetar suele fallar: figuras sin texto ' +
    'alternativo, numeración de páginas, bibliografía sin separar y ' +
    'marcadores sin completar.'));
  card.addSection(rev);

  card.addSection(CardService.newCardSection().setHeader('Criterio de producción')
    .addWidget(_uccNota(
      'Lo que insertás es editable como cualquier texto. El bloque gris ' +
      '<b>' + UCC_SENTINELA + '</b> es la indicación para quien maqueta: ' +
      'no se publica en Canvas y es lo que le dice al generador qué ' +
      'componente armar. No lo borres ni le cambies la primera línea.')));
  return [card.build()];
}

/* ------------------------------------------------------------------ */
/*  1 · Estructura                                                     */
/* ------------------------------------------------------------------ */
function buildStructureCard() {
  const card = _uccCard('Estructura y estilos');

  const s1 = CardService.newCardSection().setHeader('Plantilla modular 2026');
  s1.addWidget(_uccText('module_carrera', 'Carrera'));
  s1.addWidget(_uccText('module_asignatura', 'Asignatura'));
  s1.addWidget(_uccText('module_docente', 'Docente'));
  s1.addWidget(_uccText('module_numero', 'Número de módulo', 'Ej.: 1'));
  s1.addWidget(_uccText('module_nombre', 'Nombre del módulo'));
  s1.addWidget(_uccButtonFilled('Insertar estructura completa', 'actionInsertModule'));
  card.addSection(s1);

  const s2 = CardService.newCardSection().setHeader('Jerarquía tipográfica');
  s2.addWidget(_uccSelect('estilo_kind', 'Aplicar al párrafo o selección', [
    ['H1 · Módulo', 'H1'], ['H2 · Página', 'H2'], ['H3 · Subtítulo', 'H3'],
    ['H4 · Sub-subtítulo', 'H4'], ['H5', 'H5'], ['H6', 'H6'],
    ['Texto normal', 'NORMAL']
  ]));
  s2.addWidget(_uccButton('Aplicar estilo', 'actionApplyHeading'));
  s2.addWidget(_uccNota(
    'Un subtítulo numerado ("1. El diario estoico") se publica un nivel ' +
    'más abajo que uno sin numerar: no hace falta que lo bajes a mano.'));
  card.addSection(s2);

  const s3 = CardService.newCardSection().setHeader('Página nueva');
  s3.addWidget(_uccText('page_numero', 'Numeración', 'Ej.: 1.3  ·  se publica como "1.3."'));
  s3.addWidget(_uccText('page_title_input', 'Título de página (máximo 110 caracteres)'));
  s3.addWidget(_uccButton('Insertar página', 'actionInsertContentPage'));
  s3.addWidget(_uccNota(
    'La numeración va siempre número punto número punto: <b>1.3.</b> ' +
    'Nunca "1.3 -", "1-3." ni tres niveles.'));
  card.addSection(s3);
  return card.build();
}

/* ------------------------------------------------------------------ */
/*  2 · CTA                                                            */
/* ------------------------------------------------------------------ */
function buildCTACard() {
  const card = _uccCard('Llamados a la acción');
  const s = CardService.newCardSection().setHeader('CTA con introducción y acceso');
  s.addWidget(_uccSelect('cta_tipo', 'Recurso institucional', _uccOpcionesCTA()));
  s.addWidget(_uccText('cta_titulo', 'Bajada del recuadro (opcional)',
                       'Ej.: Un mismo riesgo, tres decisiones'));
  s.addWidget(_uccText('cta_intro', 'Invitación pedagógica',
                       'Anticipar el recurso y la tarea a realizar', true));
  s.addWidget(_uccText('cta_cita', 'Referencia APA (opcional)',
                       'Autor. (Año). Título [Video]. Fuente.'));
  s.addWidget(_uccText('cta_link', 'URL del recurso (opcional)',
                       'https://… ; si falta queda el marcador'));
  s.addWidget(_uccButtonFilled('Insertar CTA', 'actionInsertCTA'));
  s.addWidget(_uccNota(
    'El texto del enlace lo pone el aula: <b>Ver video</b> cuando del otro ' +
    'lado hay un video y <b>Acceso al documento</b> para todo lo demás. ' +
    'No hace falta que lo escribas.'));
  card.addSection(s);
  return card.build();
}

/* ------------------------------------------------------------------ */
/*  3 · Recuadros                                                      */
/* ------------------------------------------------------------------ */
function buildBoxesCard() {
  const card = _uccCard('Resaltados y recuadros');
  const s = CardService.newCardSection().setHeader('Tipos de destacado');
  s.addWidget(_uccSelect('recuadro_tipo', 'Seleccionar', _uccOpcionesRecuadro()));
  s.addWidget(_uccText('recuadro_texto', 'Contenido', '', true));
  s.addWidget(_uccButtonFilled('Insertar resaltado', 'actionInsertBox'));
  s.addWidget(_uccNota(
    'Si el contenido son varios párrafos, pegalos acá separados por un ' +
    'renglón en blanco: cada uno entra como una fila del recuadro y el ' +
    'maquetador sabe dónde termina la caja.'));
  card.addSection(s);
  return card.build();
}

/* ------------------------------------------------------------------ */
/*  4 · Componentes interactivos                                       */
/* ------------------------------------------------------------------ */
function buildComponentsCard() {
  const card = _uccCard('Componentes interactivos');

  const s = CardService.newCardSection().setHeader('Componente de varios ítems');
  s.addWidget(_uccSelect('comp_tipo', 'Tipo', _uccOpcionesComponente()));
  s.addWidget(_uccText('comp_items', 'Ítems',
                       'Un ítem por renglón, con el formato  Título = Contenido',
                       true));
  s.addWidget(_uccButtonFilled('Insertar componente', 'actionInsertComponent'));
  s.addWidget(_uccNota(
    'Entra como una tabla: cada fila es un ítem y el límite del componente ' +
    'queda marcado. Así el maquetador no tiene que adivinar dónde termina, ' +
    'que es de donde salían la mayoría de los errores.'));
  card.addSection(s);

  const q = CardService.newCardSection().setHeader('Quick check (verdadero / falso)');
  q.addWidget(_uccText('qc_preguntas', 'Preguntas',
                       'Una por renglón, terminando en Verdadero o Falso', true));
  q.addWidget(_uccButton('Insertar quick check', 'actionInsertQuickCheck'));
  card.addSection(q);

  const g = CardService.newCardSection().setHeader('Serie de figuras');
  g.addWidget(_uccText('serie_desde', 'Desde la figura N°', 'Ej.: 3'));
  g.addWidget(_uccText('serie_hasta', 'Hasta la figura N°', 'Ej.: 7'));
  g.addWidget(_uccButton('Marcar serie de figuras', 'actionInsertSerie'));
  g.addWidget(_uccNota('Las figuras se publican en solapas, una por figura.'));
  card.addSection(g);

  const o = CardService.newCardSection().setHeader('Marcas sobre el texto');
  o.addWidget(_uccSelect('marca_tipo', 'Marca', [
    ['Tooltip sobre un término', 'tooltip'],
    ['Cita destacada', 'cita'],
    ['Enlazar con una actividad', 'enlazar_actividad'],
    ['Recurso Genially ya armado', 'genially'],
    ['Esto NO se maqueta', 'no_maquetar']
  ]));
  o.addWidget(_uccText('marca_detalle', 'Detalle',
                       'Término y definición, URL del Genially, etc.', true));
  o.addWidget(_uccButton('Insertar marca', 'actionInsertMarca'));
  card.addSection(o);
  return card.build();
}

/* ------------------------------------------------------------------ */
/*  5 · Actividades                                                    */
/* ------------------------------------------------------------------ */
function buildActivitiesCard() {
  const card = _uccCard('Actividades académicas');
  const s = CardService.newCardSection().setHeader('Actividad completa');
  s.addWidget(_uccText('actividad_titulo', 'Título de la actividad (máximo 110 caracteres)',
                       'Sin el prefijo "Actividad obligatoria N:"'));
  s.addWidget(_uccSelect('actividad_modalidad', 'Modalidad', [
    ['Individual', 'Individual'], ['Grupal', 'Grupal']
  ]));
  s.addWidget(_uccSelect('actividad_tipo', 'Carácter', [
    ['Obligatoria', 'Obligatoria'], ['No obligatoria', 'No obligatoria'],
    ['Final integradora', 'Final integradora']
  ]));
  s.addWidget(_uccSelect('actividad_entrega', 'Formato de entrega', [
    ['Archivo', 'Archivo'], ['Texto en Canvas', 'Texto'], ['URL', 'URL'],
    ['Multimedia', 'Multimedia'], ['Comentario', 'Comentario']
  ]));
  s.addWidget(_uccText('actividad_grupo', 'Integrantes por grupo (si es grupal)'));
  s.addWidget(_uccText('actividad_nota', 'Calificación mínima para aprobar', 'Ej.: 70'));
  s.addWidget(_uccButtonFilled('Insertar actividad', 'actionInsertActivity'));
  s.addWidget(_uccNota(
    'La modalidad y el carácter quedan declarados para el maquetador: con ' +
    '"Grupal" el aula agrega sola el instructivo de grupos.'));
  card.addSection(s);
  return card.build();
}

/* ------------------------------------------------------------------ */
/*  6 · Figuras y tablas                                               */
/* ------------------------------------------------------------------ */
function buildMetadataCard() {
  const card = _uccCard('Figuras y tablas');
  const s = CardService.newCardSection().setHeader('Ficha de recurso visual');
  s.addWidget(_uccSelect('meta_tipo', 'Tipo', [['Figura', 'figura'], ['Tabla', 'tabla']]));
  s.addWidget(_uccText('meta_titulo', 'Título (máximo 110 caracteres)'));
  s.addWidget(_uccText('meta_alt', 'Texto alternativo (máximo 110 caracteres)',
                       'Qué muestra la imagen, para quien no puede verla'));
  s.addWidget(_uccText('meta_nota', 'Fuente / nota al pie'));
  s.addWidget(_uccText('meta_url', 'URL de la fuente (opcional)'));
  s.addWidget(_uccSelect('meta_origen', 'Origen de la imagen', [
    ['La provee diseño', 'diseno'],
    ['Va la que está en el documento', 'propia']
  ]));
  s.addWidget(_uccButtonFilled('Insertar recurso', 'actionInsertMetadata'));
  card.addSection(s);

  const c = CardService.newCardSection().setHeader('Numeración');
  c.addWidget(_uccNota(uccEstadoContadores()));
  c.addWidget(_uccButton('Reiniciar contadores', 'actionResetCounters'));
  card.addSection(c);
  return card.build();
}

/* ------------------------------------------------------------------ */
/*  7 · Bloques complementarios                                        */
/* ------------------------------------------------------------------ */
function buildExtrasCard() {
  const card = _uccCard('Bloques complementarios');

  const v = CardService.newCardSection().setHeader('Video de Canvas Studio');
  v.addWidget(_uccSelect('video_tipo', 'Ubicación', [
    ['Video de desarrollo (en esta página)', 'devVideo'],
    ['Video introductorio (apertura del módulo)', 'introVideo']
  ]));
  v.addWidget(_uccText('video_nombre', 'Nombre del archivo del video',
                       'Ej.: NAO - V_M1'));
  v.addWidget(_uccText('video_media_id', 'ID de Canvas Studio (pegar al cerrar)',
                       'uuid-número, o el iframe entero copiado de Canvas'));
  v.addWidget(_uccButton('Insertar bloque de video', 'actionInsertVideo'));
  v.addWidget(_uccNota(
    'El id recién existe cuando se comparte la colección. Dejá el bloque ' +
    'ahora y volvé a pegar el id acá cuando te lo pasen: el aula sale con ' +
    'el video puesto, sin tener que incrustarlo a mano.'));
  card.addSection(v);

  const b = CardService.newCardSection().setHeader('Bibliografía');
  b.addWidget(_uccButton('Insertar bibliografía', 'actionInsertBiblio'));
  b.addWidget(_uccNota(
    'Siempre con los dos apartados: <b>Obligatoria</b> y <b>Sugerida y ' +
    'complementaria</b>.'));
  card.addSection(b);
  return card.build();
}

/* ------------------------------------------------------------------ */
/*  Revisión previa a la entrega                                       */
/* ------------------------------------------------------------------ */
function buildReviewCard(resultado) {
  const card = _uccCard('Revisar documento', 'Antes de entregar a maquetación');
  const s = CardService.newCardSection();
  if (!resultado) {
    s.addWidget(_uccNota(
      'Corre los mismos controles que hace el generador del aula. No ' +
      'modifica el documento.'));
    s.addWidget(_uccButtonFilled('Revisar ahora', 'actionRunReview'));
  } else {
    s.addWidget(_uccNota(resultado));
    s.addWidget(_uccButton('Revisar de nuevo', 'actionRunReview'));
  }
  card.addSection(s);
  return card.build();
}
