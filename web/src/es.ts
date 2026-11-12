/**
 * Spanish interface text, keyed by the English text in the code. Film terms
 * follow Spanish production usage: secuencia, desglose, plan de rodaje,
 * orden de rodaje (call sheet), jornada, citación, figuración, atrezo.
 */
export const ES: Record<string, string> = {
  // Navigation and home
  "Could not reach the Slugline server. Is it running?": "No se puede conectar con Slugline. ¿Está abierto?",
  "Opening the script…": "Abriendo el guion…",
  "Could not open that script.": "No se ha podido abrir ese guion.",
  "Reading {name}…": "Leyendo {name}…",
  "Could not read that file.": "No se ha podido leer ese archivo.",
  "Opening the example…": "Abriendo el ejemplo…",
  "Could not open the example.": "No se ha podido abrir el ejemplo.",
  "The analysis failed.": "El análisis ha fallado.",
  "The element breakdown failed.": "El desglose de elementos ha fallado.",
  "The breakdown could not be cleared.": "No se ha podido vaciar el desglose.",
  "Your scripts": "Tus guiones",
  Scripts: "Guiones",
  "Open script": "Abrir guion",
  Settings: "Ajustes",
  "Change language": "Cambiar idioma",
  "Ask the script": "Pregunta al guion",
  Dismiss: "Cerrar",
  "Remove “{name}” from your scripts? The file on your computer is not touched.":
    "¿Quitar «{name}» de tus guiones? El archivo de tu ordenador no se toca.",
  "Could not remove it.": "No se ha podido quitar.",
  "Drop the script to open it": "Suelta el guion para abrirlo",
  "From screenplay to shooting schedule": "Del guion al plan de rodaje",
  "Open a script and Slugline breaks it down: scenes, cast, locations and every department's elements, a shooting schedule, call sheets and the cast's day out of days. Your scripts stay on this computer.":
    "Abre un guion y Slugline lo desglosa: secuencias, reparto, localizaciones y los elementos de cada departamento, el plan de rodaje, las órdenes de rodaje y los días de cada actor. Tus guiones no salen de este ordenador.",
  "Open a script": "Abrir un guion",
  "Try it with an example script": "Probar con un guion de ejemplo",
  "Fountain, Final Draft (.fdx) and PDF. You can also drop the file anywhere on this page.":
    "Fountain, Final Draft (.fdx) y PDF. También puedes soltar el archivo en cualquier parte de la página.",
  "Everything you did on each one is saved: breakdown, schedule, cast and notes.":
    "Todo lo que hiciste en cada uno está guardado: desglose, plan de rodaje, reparto y notas.",
  "opened {date}": "abierto el {date}",
  "Remove {name}": "Quitar {name}",

  // Export menu
  Export: "Exportar",
  "PDF exports need reportlab: pip install 'slugline[export]'": "Los PDF necesitan reportlab: pip install 'slugline[export]'",
  "Production report (PDF)": "Informe de producción (PDF)",
  "Breakdown sheets, one per scene (PDF)": "Hojas de desglose, una por secuencia (PDF)",
  "Shooting schedule (PDF)": "Plan de rodaje (PDF)",
  "Call sheets, every day (PDF)": "Órdenes de rodaje, todas las jornadas (PDF)",
  "Shooting schedule (CSV)": "Plan de rodaje (CSV)",
  "Day out of days (CSV)": "Días por actor (CSV)",
  "Scenes (CSV)": "Secuencias (CSV)",
  "Elements by scene (CSV)": "Elementos por secuencia (CSV)",
  "Characters (CSV)": "Personajes (CSV)",
  "Locations (CSV)": "Localizaciones (CSV)",
  "Script (Fountain)": "Guion (Fountain)",

  // Dashboard
  "{n} pages": "{n} páginas",
  Scenes: "Secuencias",
  "Pages, estimated": "Páginas, aproximadas",
  "Speaking characters": "Personajes con diálogo",
  Locations: "Localizaciones",
  "Day and night": "Día y noche",
  "Share of the {pages}. Scenes marked LATER or CONTINUOUS count with the scene before.":
    "Reparto de las {pages}. Las secuencias marcadas LATER o CONTINUOUS cuentan con la anterior.",
  "Interior and exterior": "Interior y exterior",
  "Share of the {pages}.": "Reparto de las {pages}.",
  Dawn: "Amanecer",
  Day: "Día",
  Dusk: "Atardecer",
  Night: "Noche",
  Interior: "Interior",
  Exterior: "Exterior",
  "Int./Ext.": "Int./Ext.",
  "Not stated": "Sin indicar",
  "Dialogue share": "Reparto del diálogo",
  "Words spoken by each character, out of {n}.": "Palabras de cada personaje, de un total de {n}.",
  Character: "Personaje",
  Words: "Palabras",
  Share: "Porcentaje",
  Cues: "Intervenciones",
  "words in {cues}, {scenes}": "palabras en {cues}, {scenes}",
  "{n} more in the table view.": "{n} más en la vista de tabla.",
  "Pages to shoot at each one.": "Páginas que hay que rodar en cada una.",
  Location: "Localización",
  "Length (pages)": "Duración (páginas)",
  "Scene numbers": "Números de secuencia",
  "pages, in scenes {list}": "páginas, en las secuencias {list}",
  "The AI features need your Anthropic API key.": "Las funciones de IA necesitan tu clave de API de Anthropic.",
  "Add it in Settings": "Añádela en Ajustes",
  "Story notes": "Notas de la historia",
  "Claude can read the script and add a logline, a synopsis, a summary and emotional tone for every scene, and a proofread of the formatting.":
    "Claude puede leer el guion y añadir una logline, una sinopsis, un resumen y el tono de cada secuencia, y revisar el formato.",
  "Reading the script… about a minute": "Leyendo el guion… cerca de un minuto",
  "Analyze the script": "Analizar el guion",
  "Written by {model}. Check it against the script before it goes on a call sheet.":
    "Escrito por {model}. Compruébalo con el guion antes de llevarlo a una orden de rodaje.",
  "Analyzing again…": "Analizando de nuevo…",
  "Analyze again": "Analizar de nuevo",
  Stripboard: "Stripboard",
  "Every scene in script order, lengths in pages and eighths. Open a scene for its breakdown sheet.":
    "Todas las secuencias en el orden del guion, con su duración en páginas y octavos. Abre una para ver su hoja de desglose.",
  "Int. day": "Int. día",
  "Ext. day": "Ext. día",
  "Int. night": "Int. noche",
  "Ext. night": "Ext. noche",
  Scene: "Secuencia",
  Length: "Duración",
  "Starts p.": "Empieza en p.",
  Cast: "Reparto",
  Elements: "Elementos",
  Tone: "Tono",
  "no lines": "sin diálogo",
  changed: "cambiada",
  new: "nueva",
  Other: "Otros",
  "Who speaks in each scene": "Quién habla en cada secuencia",
  "Words of dialogue per scene, by character.": "Palabras de diálogo por secuencia y personaje.",
  words: "palabras",
  "Character presence": "Presencia de los personajes",
  "Who is in which scene, and how much they say there.": "Quién está en cada secuencia y cuánto habla.",
  "Speaks in scenes": "Habla en las secuencias",
  "Named without lines in": "Aparece sin diálogo en",
  "named in the action, no lines": "aparece en la acción, sin diálogo",
  "Tone across the story": "El tono a lo largo de la historia",
  "Tension and mood, scene by scene. It appears here once the script has been analyzed.":
    "Tensión y ánimo, secuencia a secuencia. Aparece aquí cuando el guion se ha analizado.",
  "Claude's reading of each scene, scored against the rest of this script.":
    "La lectura de Claude de cada secuencia, puntuada en relación con el resto del guion.",
  "Tension (1–5)": "Tensión (1–5)",
  "Mood (−2 to +2)": "Ánimo (−2 a +2)",
  "Formatting notes": "Notas de formato",
  // Folding sections
  "Show this section": "Mostrar esta sección",
  "hidden · click to show": "oculta · pulsa para mostrar",
  "Hide this section": "Ocultar esta sección",
  "Fold all sections": "Plegar todas las secciones",
  "Unfold all sections": "Desplegar todas las secciones",
  // Budget card
  "Country": "País",
  "Sets the social security on wages": "Fija la Seguridad Social sobre los sueldos",
  "Save {amount} by reordering the shooting days.": "Ahorra {amount} reordenando las jornadas de rodaje.",
  "The cast would be on hold {before} days instead of {after}. Each day keeps its scenes and the night block stays together; dates stay on the calendar.": "El reparto pasaría de {before} días de espera pagados a {after}. Cada jornada conserva sus secuencias y el bloque de noches sigue junto; las fechas no se mueven del calendario.",
  "Reordering…": "Reordenando…",
  "Reorder the days": "Reordenar las jornadas",
  "The schedule could not be reordered.": "No se ha podido reordenar el plan.",
  "Production dossier (PDF)": "Dossier de producción (PDF)",
  "Unknown country.": "País desconocido.",
  "Spain": "España",
  "France": "Francia",
  "Italy": "Italia",
  "Germany": "Alemania",
  "Portugal": "Portugal",
  "United Kingdom": "Reino Unido",
  "United States": "Estados Unidos",
  "Mexico": "México",
  "Argentina": "Argentina",
  "Colombia": "Colombia",
  "No social security": "Sin cargas sociales (facturan o va incluida)",
  "{people} more people for {days} shooting days": "{people} personas más durante {days} jornadas de rodaje",
  "shoots on {pct} of the {days} days": "rueda en el {pct} de las {days} jornadas",
  "{pct} of crew wages": "{pct} de los sueldos del equipo técnico",
  "{pct} of cast wages": "{pct} de los sueldos del personal artístico",
  "{pct} of crew wages and overtime": "{pct} de los sueldos y horas extra del equipo técnico",
  "Percentages": "Porcentajes",
  "Social security": "Seguridad Social",
  "Contingency": "Imprevistos",
  "Chapters add up to {subtotal}; with {pct}% for contingency, {total}.": "Los capítulos suman {subtotal}; con un {pct} % de imprevistos, {total}.",
  "Overtime": "Horas extra",
  "Social security for the cast": "Seguridad Social del personal artístico",
  "Social security for the crew": "Seguridad Social del equipo técnico",
  "Budget":
    "Presupuesto",
  "Worked out from the breakdown and the schedule: shooting days, the days each actor works, extras, locations, vehicles. Quantities follow the schedule; the rates are a starting point to replace with your own.":
    "Calculado a partir del desglose y el plan de rodaje: jornadas, días de cada actor, figuración, localizaciones, vehículos. Las cantidades siguen al plan; las tarifas son un punto de partida para cambiar por las tuyas.",
  "Level":
    "Nivel",
  "PDF":
    "PDF",
  "Excel (CSV)":
    "Excel (CSV)",
  "Total":
    "Total",
  "Shooting days":
    "Jornadas de rodaje",
  "Per shooting day":
    "Por jornada",
  "To be quoted":
    "A cotizar",
  "{n} of the days are estimated for scenes not in the schedule yet.":
    "{n} de las jornadas son estimadas, para secuencias que aún no están en el plan.",
  "There is no schedule yet: the days are estimated from a suggested plan. Make the schedule above and the budget follows it.":
    "Aún no hay plan de rodaje: las jornadas se estiman con un plan sugerido. Haz el plan arriba y el presupuesto lo sigue.",
  "{n} lines need a quote (effects that can't be priced from the script). They carry {amount} as a placeholder until you enter the quote.":
    "{n} partidas necesitan presupuesto de proveedor (efectos que no se pueden calcular desde el guion). Llevan {amount} provisionales hasta que pongas la cotización.",
  "The previous draft came to {total} in {days} days. This one: {now} in {now_days} days ({diff}).":
    "La versión anterior del guion salía por {total} en {days} jornadas. Esta: {now} en {now_days} jornadas ({diff}).",
  "By chapter":
    "Por capítulos",
  "What each scene costs to shoot":
    "Lo que cuesta rodar cada secuencia",
  "Its share of the days it is shot on (crew, equipment, location, cast) plus what only it needs. Cutting a scene saves about this much.":
    "Su parte de las jornadas en que se rueda (equipo, material, localización, reparto) más lo que solo necesita ella. Quitar una secuencia ahorra más o menos esto.",
  "Concept":
    "Concepto",
  "Quantity":
    "Cantidad",
  "Unit":
    "Unidad",
  "Rate":
    "Precio",
  "to be quoted":
    "a cotizar",
  "quote":
    "cotización",
  "Quote for {name}":
    "Cotización de {name}",
  "Quantity for {name}":
    "Cantidad de {name}",
  "Rate for {name}":
    "Precio de {name}",
  "Back to the worked-out value":
    "Volver al valor calculado",
  "Reset":
    "Restablecer",
  "Chapters follow the ICAA budget model. This is a first draft from the script: check it with a production manager, and replace the rates with your agreements and quotes before using it for funding.":
    "Los capítulos siguen el modelo de presupuesto del ICAA. Es un primer borrador a partir del guion: revísalo con el jefe de producción y cambia las tarifas por tus acuerdos y cotizaciones antes de usarlo para pedir ayudas.",
  "Add a line: concept":
    "Añadir partida: concepto",
  "lead":
    "protagonista",
  "supporting":
    "secundario",
  "small part":
    "pequeño papel",
  "{role} · works {work} days, {hold} on hold":
    "{role} · trabaja {work} días, {hold} en espera",
  "{role} · works {work} days":
    "{role} · trabaja {work} días",
  "{shooting} shooting days + {prep} preparation":
    "{shooting} jornadas de rodaje + {prep} de preparación",
  "{shooting} shooting days":
    "{shooting} jornadas de rodaje",
  "{people} people on {days} days with extras":
    "{people} personas en {days} jornadas con figuración",
  "{vans} vans for {days} days":
    "{vans} furgonetas durante {days} jornadas",
  "{crew} crew for {days} days, plus {cast} cast days":
    "{crew} personas de equipo durante {days} jornadas, más {cast} días de reparto",
  "{pct} of the rest of the budget":
    "{pct} del resto del presupuesto",
  "scenes {list}":
    "secuencias {list}",
  "The budget could not be worked out.":
    "No se ha podido calcular el presupuesto.",
  "The budget could not be saved.":
    "No se ha podido guardar el presupuesto.",
  "Budget (PDF)":
    "Presupuesto (PDF)",
  "Budget (CSV)":
    "Presupuesto (CSV)",
  "Unknown budget level.":
    "Nivel de presupuesto desconocido.",
  "Too many changes in one budget.":
    "Demasiados cambios en un presupuesto.",
  // Budget (the same text as BUDGET_ES in budget.py)
  "High-budget feature": "Largometraje de alto presupuesto",
  "Second unit: crew and equipment": "Segunda unidad: equipo y material",
  "Visual effects across the film": "Efectos visuales del conjunto de la película",
  "Rest of the crew at studio size": "Resto del equipo a escala de gran producción",
  "Set construction on stage": "Construcción de decorados en plató",
  "Artistic staff": "Personal artístico",
  "Script and music": "Guion y música",
  "Sets and locations": "Escenografía",
  "Studios and sound": "Estudios de rodaje y sonorización",
  "Equipment, shooting and transport": "Maquinaria, rodaje y transportes",
  "Travel, hotels and meals": "Viajes, hoteles y comidas",
  "Digital media": "Soporte digital",
  "Post-production": "Postproducción",
  "Insurance": "Seguros",
  "Overheads": "Gastos generales",
  "Publicity and finance": "Gastos de explotación, comercial y financieros",
  "Script and rights": "Guion y derechos",
  "Original music": "Música original",
  "Stunt team": "Especialistas",
  "Director": "Director/a",
  "First assistant director": "Ayudante de dirección",
  "Script supervisor": "Script",
  "Line producer": "Director/a de producción",
  "Production manager": "Jefe/a de producción",
  "Production assistant": "Auxiliar de producción",
  "Director of photography": "Director/a de fotografía",
  "Focus puller": "Foquista",
  "Camera assistant": "Auxiliar de cámara",
  "Sound mixer": "Jefe/a de sonido",
  "Boom operator": "Microfonista",
  "Production designer": "Director/a de arte",
  "Set dresser": "Ambientador/a",
  "Costume designer": "Figurinista",
  "Makeup artist": "Maquillador/a",
  "Hairdresser": "Peluquero/a",
  "Gaffer": "Jefe/a de eléctricos",
  "Electrician": "Eléctrico/a",
  "Key grip": "Jefe/a de maquinistas",
  "Wardrobe for the main cast": "Vestuario del reparto principal",
  "Makeup and hair materials": "Material de maquillaje y peluquería",
  "Sound studio: dubbing, foley and mix": "Estudio de sonido: doblaje, efectos sala y mezcla",
  "Camera package": "Equipo de cámara",
  "Lighting": "Iluminación",
  "Grip": "Maquinaria",
  "Production vans": "Furgonetas de producción",
  "Fuel and parking": "Combustible y aparcamientos",
  "Catering on set": "Catering en rodaje",
  "Travel, hotels and per diems (shooting away from home)": "Viajes, hoteles y dietas (rodaje fuera)",
  "Drives, backup and data management": "Discos, copias de seguridad y gestión de datos",
  "Editing": "Montaje",
  "Grading and conform": "Etalonaje y conformado",
  "Titles, subtitles and deliveries": "Créditos, subtítulos y entregas",
  "Publicity and festivals": "Publicidad y festivales",
  "Production insurance": "Seguro de producción",
  "Overheads: office, accounting, legal": "Gastos generales: oficina, gestoría, asesoría jurídica",
  "days": "días",
  "people x days": "personas x días",
  "items": "unidades",
  "lump": "global",
  "characters": "personajes",
  "scenes": "secuencias",
  "vans x days": "furgonetas x días",
  "meals": "comidas",
  "units": "unidades",
  "Short film": "Cortometraje",
  "Low-budget feature": "Largometraje de bajo presupuesto",
  "Mid-budget feature": "Largometraje de presupuesto medio",
  // Formatting notes from the checks (the same text as MESSAGES_ES in lint.py)
  "Heading \"{heading}\" has no INT./EXT.":
    "El encabezado \"{heading}\" no dice si es INT. o EXT.",
  "Heading \"{heading}\" has no time of day.":
    "El encabezado \"{heading}\" no dice el momento del día.",
  "Scene \"{heading}\" is empty.":
    "La secuencia \"{heading}\" está vacía.",
  "{character} has a cue with no dialogue.":
    "{character} tiene una intervención sin diálogo.",
  "1 action paragraph longer than {lines} lines; shorter blocks read faster.":
    "1 párrafo de acción de más de {lines} líneas; los bloques cortos se leen mejor.",
  "{n} action paragraphs longer than {lines} lines; shorter blocks read faster.":
    "{n} párrafos de acción de más de {lines} líneas; los bloques cortos se leen mejor.",
  "Characters {a} and {b} differ only in punctuation or spacing ({na} and {nb} cues).":
    "Los personajes {a} y {b} solo se diferencian en la puntuación o los espacios ({na} y {nb} intervenciones).",
  "Characters {a} and {b} look like the same name spelled two ways ({na} and {nb} cues).":
    "Los personajes {a} y {b} parecen el mismo nombre escrito de dos formas ({na} y {nb} intervenciones).",
  "Locations \"{a}\" and \"{b}\" differ only in punctuation or spacing.":
    "Los decorados \"{a}\" y \"{b}\" solo se diferencian en la puntuación o los espacios.",
  "Locations \"{a}\" and \"{b}\" look like the same name spelled two ways.":
    "Los decorados \"{a}\" y \"{b}\" parecen el mismo nombre escrito de dos formas.",
  "Only {n} of {total} scenes have a scene number.":
    "Solo {n} de {total} secuencias tienen número.",
  "Scene number {number} is used {n} times.":
    "El número de secuencia {number} se usa {n} veces.",
  "The script has no title page.":
    "El guion no tiene portada.",
  "Merge as {name}": "Juntar como {name}",
  "Set day or night for scene {n}": "Elegir día o noche para la secuencia {n}",
  "Corrected in Slugline": "Corregido en Slugline",
  "Counted this way in the cast, the locations and the schedule. The script file is not changed.":
    "Así se cuenta en el reparto, los decorados y el plan de rodaje. El archivo del guion no se toca.",
  "{name} counts as {into}": "{name} cuenta como {into}",
  "Undo": "Deshacer",
  "The elements could not be suggested.": "No se han podido sugerir los elementos.",
  "Suggest from words in the script": "Sugerir a partir del guion",
  "Suggest again from words in the script": "Volver a sugerir sin IA",
  "Updates the suggestions made without AI; Claude's and yours stay as they are.":
    "Actualiza las sugerencias hechas sin IA; las de Claude y las tuyas se quedan como están.",
  "From the rule-based checks and Claude's proofread.": "De las comprobaciones automáticas y la revisión de Claude.",
  "From the rule-based checks. Analyzing the script adds a proofread.":
    "De las comprobaciones automáticas. Al analizar el guion se añade una revisión.",
  "Nothing to fix: headings, cues and numbering all look consistent.":
    "Nada que corregir: encabezados, personajes y numeración son coherentes.",
  Fix: "Corregir",
  Note: "Nota",
  "Scene {n}.": "Secuencia {n}.",
  "Found by Claude.": "Lo ha encontrado Claude.",

  // Elements
  "What each department needs, scene by scene: extras, stunts, props, wardrobe, makeup, vehicles, effects and more.":
    "Lo que necesita cada departamento, secuencia a secuencia: figuración, especialistas, atrezo, vestuario, maquillaje, vehículos, efectos y más.",
  "Suggesting again keeps everything you added or edited by hand.": "Al sugerir de nuevo se conserva todo lo que añadiste o editaste a mano.",
  "Breaking down the script… about a minute": "Desglosando el guion… cerca de un minuto",
  "Suggest again with AI": "Sugerir de nuevo con IA",
  "Suggest elements with AI": "Sugerir elementos con IA",
  "No elements yet. Claude can read the script and suggest them for every scene, or you can open a scene and add them by hand.":
    "Aún no hay elementos. Claude puede leer el guion y sugerirlos para cada secuencia, o puedes abrir una secuencia y añadirlos a mano.",
  "Open scene {n}": "Abrir la secuencia {n}",
  "Filter by department": "Filtrar por departamento",
  All: "Todos",
  Element: "Elemento",
  Department: "Departamento",
  Pages: "Páginas",
  "{elements} still as Claude suggested them. Open a scene to check, edit or remove them before you print the breakdown sheets.":
    "{elements} tal como los sugirió Claude. Abre la secuencia para comprobarlos, editarlos o quitarlos antes de imprimir las hojas de desglose.",
  Extras: "Figuración",
  Stunts: "Especialistas",
  Props: "Atrezo",
  Wardrobe: "Vestuario",
  "Makeup & hair": "Maquillaje y peluquería",
  Vehicles: "Vehículos",
  Animals: "Animales",
  "Special effects": "Efectos especiales",
  "Visual effects": "Efectos visuales",
  "Sound & music": "Sonido y música",
  "Set dressing": "Decoración",
  "Special equipment": "Equipo especial",

  "{n} suggested from words in the action, without AI. Check them against the scene: edit or remove what's wrong.":
    "{n} sugeridos a partir de palabras de la acción, sin IA. Compruébalos con la secuencia: edita o quita lo que esté mal.",
  "Suggested from words in the script": "Sugerido a partir de palabras del guion",
  "{elements} suggested from words in the action, without AI: a first pass to check scene by scene. With an API key, Claude reads the whole script and suggests a fuller breakdown.":
    "{elements} sugeridos a partir de palabras de la acción, sin IA: una primera pasada para revisar secuencia a secuencia. Con una clave de API, Claude lee el guion entero y sugiere un desglose más completo.",

  // Revised drafts
  "{scenes} unchanged": "{scenes} sin cambios",
  "{n} reviewed": "{n} revisadas",
  "{scenes} to check": "{scenes} por revisar",
  "{scenes} cut": "{scenes} eliminadas",
  "New draft.": "Nueva versión.",
  "This breakdown was carried over from the previous draft (saved {date}):": "Este desglose viene de la versión anterior (guardada el {date}):",
  "This breakdown was carried over from the previous draft:": "Este desglose viene de la versión anterior:",
  "Check the rewritten scenes:": "Revisa las secuencias reescritas:",
  "Break down the new scenes:": "Desglosa las secuencias nuevas:",
  "Cut from this draft:": "Eliminadas en esta versión:",
  "{elements} dropped": "se pierden {elements}",
  "Start this draft's breakdown empty? The carried-over elements will be removed from this draft.":
    "¿Empezar vacío el desglose de esta versión? Se quitarán de esta versión los elementos que venían de la anterior.",
  "Start this draft empty instead": "Empezar esta versión vacía",

  // Assistant
  "Which scenes could be shot on the same day?": "¿Qué secuencias se podrían rodar el mismo día?",
  "What props do we need for the night scenes?": "¿Qué atrezo necesitamos para las secuencias de noche?",
  "Who has the most dialogue, and in which scenes?": "¿Quién tiene más diálogo, y en qué secuencias?",
  "Looked at the scene list": "Ha mirado la lista de secuencias",
  "Read scenes {list}": "Ha leído las secuencias {list}",
  "Checked the cast": "Ha consultado el reparto",
  "Read {name}'s dialogue": "Ha leído el diálogo de {name}",
  "Checked the locations": "Ha consultado las localizaciones",
  "Searched for “{query}”": "Ha buscado «{query}»",
  "Checked the elements": "Ha consultado los elementos",
  "Checked the shooting schedule": "Ha consultado el plan de rodaje",
  "Checked the formatting": "Ha revisado el formato",
  "The request failed.": "La petición ha fallado.",
  "New chat": "Nueva conversación",
  "Close the assistant": "Cerrar el asistente",
  Close: "Cerrar",
  "The assistant reads the parsed script with tools, so its counts and page lengths are the same ones you see in the breakdown. It also sees the elements and the shooting schedule.":
    "El asistente lee el guion con herramientas, así que sus recuentos y duraciones son los mismos que ves en el desglose. También ve los elementos y el plan de rodaje.",
  "Reading…": "Leyendo…",
  "Thinking…": "Pensando…",
  "Ask about scenes, characters, schedule…": "Pregunta por secuencias, personajes, el plan…",
  "AI features are off": "Las funciones de IA están desactivadas",
  "Answering…": "Respondiendo…",
  Ask: "Preguntar",

  // Breakdown sheet
  "The change could not be saved.": "No se ha podido guardar el cambio.",
  "Breakdown sheet, scene {n}": "Hoja de desglose, secuencia {n}",
  "Scene {n}": "Secuencia {n}",
  "Previous scene": "Secuencia anterior",
  "Next scene": "Secuencia siguiente",
  "Day/Night": "Día/Noche",
  "{n} pp.": "{n} págs.",
  Starts: "Empieza",
  "p. {n}": "p. {n}",
  "Rewritten in this draft": "Reescrita en esta versión",
  "(it was scene {n})": "(era la secuencia {n})",
  "The elements below come from the previous draft: check them against the new text.":
    "Los elementos de abajo vienen de la versión anterior: compruébalos con el texto nuevo.",
  "Mark as reviewed": "Marcar como revisada",
  "New in this draft.": "Nueva en esta versión.",
  "It has no elements from the previous draft.": "No tiene elementos de la versión anterior.",
  "No lines": "Sin diálogo",
  "{n} suggested by Claude. Check them against the scene: edit or remove what's wrong.":
    "{n} sugeridos por Claude. Compruébalos con la secuencia: edita o quita lo que esté mal.",
  Add: "Añadir",
  Edit: "Editar",
  "Suggested by Claude": "Sugerido por Claude",
  suggested: "sugerido",
  "Element, e.g. Revolver": "Elemento, p. ej. Revólver",
  "Notes (optional)": "Notas (opcional)",
  Cancel: "Cancelar",
  "Saving…": "Guardando…",
  Save: "Guardar",

  // Shooting schedule
  "The schedule could not be saved.": "No se ha podido guardar el plan de rodaje.",
  "Shooting schedule": "Plan de rodaje",
  "Put the scenes in shooting order, day by day. Slugline can suggest a first plan: day work first and nights in one block, each location kept together, and each day filled up to the pages you expect to shoot.":
    "Ordena las secuencias por jornadas de rodaje. Slugline puede proponer un primer plan: primero el trabajo de día y las noches en un bloque, cada localización junta, y cada jornada llena hasta las páginas que esperas rodar.",
  "Pages a day": "Páginas por jornada",
  "Planning…": "Planificando…",
  "Suggest a schedule": "Proponer un plan",
  "Start with an empty day": "Empezar con una jornada vacía",
  "Move scene {n}": "Mover la secuencia {n}",
  "Day {n}": "Jornada {n}",
  "Not scheduled": "Sin programar",
  "{days} · {pages} pages · planned at {perDay} pages a day. Drag the strips to reorder them, or use the menu on each strip.":
    "{days} · {pages} páginas · a {perDay} páginas por jornada. Arrastra las tiras para reordenarlas, o usa el menú de cada tira.",
  "Add day": "Añadir jornada",
  "pages a day": "páginas por jornada",
  "Replace this schedule with a new suggestion? Your changes to it will be lost.":
    "¿Sustituir este plan por una nueva propuesta? Se perderán los cambios que le hayas hecho.",
  "Suggest again": "Proponer de nuevo",
  "Delete this shooting schedule?": "¿Borrar este plan de rodaje?",
  Delete: "Borrar",
  "The schedule was carried over from the previous draft. New scenes without a day: {list}.":
    "El plan viene de la versión anterior. Secuencias nuevas sin jornada: {list}.",
  "Date of day {n}": "Fecha de la jornada {n}",
  Call: "Citación",
  "Crew call, day {n}": "Citación general, jornada {n}",
  "{n} of {max} pages": "{n} de {max} páginas",
  "No scenes yet": "Aún sin secuencias",
  "Call sheet": "Orden de rodaje",
  "Its scenes go back to Not scheduled": "Sus secuencias vuelven a Sin programar",
  "Remove day": "Quitar jornada",
  "Drag scenes here.": "Arrastra secuencias aquí.",
  "Meeting point or address": "Punto de encuentro o dirección",
  "Meeting point, day {n}": "Punto de encuentro, jornada {n}",
  "Notes for the call sheet (company move, weather cover…)": "Notas para la orden de rodaje (traslado, alternativa por lluvia…)",
  "Notes, day {n}": "Notas, jornada {n}",
  "Every scene has a day.": "Todas las secuencias tienen jornada.",

  // Call sheet details
  "Nearest hospital": "Hospital más cercano",
  "Nearest hospital, day {n}": "Hospital más cercano, jornada {n}",
  "Cast call times": "Citaciones del reparto",
  "{n} set, the rest at the crew call": "{n} con hora propia, el resto a la citación general",
  "everyone at the crew call": "todos a la citación general",
  "Call time for {name}, day {n}": "Citación de {name}, jornada {n}",
  Crew: "Equipo técnico",
  "Printed on every call sheet, called at the crew call of each day.": "Sale en todas las órdenes de rodaje, citado a la hora general de cada jornada.",
  Role: "Puesto",
  Name: "Nombre",
  Phone: "Teléfono",
  "e.g. First AD": "p. ej. Ayudante de dirección",
  "Add a person": "Añadir persona",
  "The crew list could not be saved.": "No se ha podido guardar el equipo técnico.",

  // Day out of days
  "The cast list could not be saved.": "No se ha podido guardar el reparto.",
  "Cast and day out of days": "Reparto y días por actor",
  "Which shooting days each character works, from the schedule above. Holds are days between work days when the actor is paid but not shooting: moving scenes to cut them saves money. Add the actors' names for the call sheets.":
    "Qué jornadas trabaja cada personaje según el plan de arriba. Las esperas (H) son días entre jornadas de trabajo en los que el actor cobra sin rodar: mover secuencias para quitarlas ahorra dinero. Añade los nombres de los actores para las órdenes de rodaje.",
  "Download CSV": "Descargar CSV",
  Actor: "Actor/actriz",
  Work: "Trabaja",
  Hold: "Espera",
  "Actor's name": "Nombre del actor",
  "Actor playing {name}": "Quién interpreta a {name}",
  "starts work": "empieza a trabajar",
  works: "trabaja",
  finishes: "termina",
  "works this day only": "solo trabaja este día",
  "on hold": "en espera",
  "SW starts work · W works · WF finishes · SWF one day only · H on hold.":
    "SW empieza · W trabaja · WF termina · SWF un solo día · H en espera.",

  // Settings
  "The settings could not be saved.": "No se han podido guardar los ajustes.",
  "AI features": "Funciones de IA",
  "Story notes, element suggestions and the script assistant use Claude through your own Anthropic account. Everything else works without it.":
    "Las notas de la historia, las sugerencias de elementos y el asistente usan Claude con tu propia cuenta de Anthropic. Todo lo demás funciona sin ella.",
  "Using the key in the ANTHROPIC_API_KEY environment variable ({hint}).": "Se usa la clave de la variable de entorno ANTHROPIC_API_KEY ({hint}).",
  "Key saved": "Clave guardada",
  "Key removed.": "Clave eliminada.",
  Remove: "Quitar",
  "Key saved. The AI features are on.": "Clave guardada. Las funciones de IA están activadas.",
  "Replace the key": "Cambiar la clave",
  "Anthropic API key": "Clave de API de Anthropic",
  "Save key": "Guardar clave",
  "Get a key at console.anthropic.com. It is stored only on this computer. Each analysis is billed to your Anthropic account, and using it sends the script to Anthropic.":
    "Consigue una clave en console.anthropic.com. Solo se guarda en este ordenador. Cada análisis se cobra en tu cuenta de Anthropic, y al usarlo el guion se envía a Anthropic.",
  Model: "Modelo",
  "Model changed.": "Modelo cambiado.",
  "Recommended: the best balance of quality and cost.": "Recomendado: el mejor equilibrio entre calidad y coste.",
  "Cheaper and faster, for long scripts or tight budgets.": "Más barato y rápido, para guiones largos o presupuestos ajustados.",
  "The cheapest. Fine for summaries, weaker at breakdowns.": "El más barato. Sirve para resúmenes, flojea en los desgloses.",
  "The most capable and the most expensive.": "El más capaz y el más caro.",
  Language: "Idioma",
  "PDF exports use this language too. AI notes keep the language of the script.":
    "Los PDF también usan este idioma. Las notas de la IA mantienen el idioma del guion.",

  // Licence
  Licence: "Licencia",
  Professional: "Profesional",
  School: "Centro educativo",
  "Production company": "Productora",
  Pilot: "Piloto",
  "{kind} licence for {name}.": "Licencia {kind} a nombre de {name}.",
  "Valid until {date}.": "Válida hasta el {date}.",
  "It does not expire.": "No caduca.",
  "Thank you for supporting Slugline.": "Gracias por apoyar Slugline.",
  "Licence removed from this computer.": "Licencia quitada de este ordenador.",
  "Trial version: everything works, but your library keeps {n} scripts ({used} used) and PDFs are marked as a trial.":
    "Versión de prueba: todo funciona, pero tu biblioteca guarda {n} guiones ({used} usados) y los PDF llevan la marca de prueba.",
  "Licence key": "Clave de licencia",
  "Checking…": "Comprobando…",
  Activate: "Activar",
  "Licence activated. Thank you!": "Licencia activada. ¡Gracias!",
  "The licence could not be activated.": "No se ha podido activar la licencia.",
  "Buy a licence": "Comprar una licencia",
  "Trial version · {used} of {n} scripts.": "Versión de prueba · {used} de {n} guiones.",
  "Activate a licence": "Activar una licencia",

  // Messages from the server
  "The trial keeps 2 scripts. Remove one from your scripts, or activate a licence in Settings.":
    "La versión de prueba guarda 2 guiones. Quita uno de tus guiones o activa una licencia en Ajustes.",
  "That is not a Slugline licence. It should start with SLUG1-.": "Eso no es una licencia de Slugline. Debe empezar por SLUG1-.",
  "That licence is not valid. Check that it was copied whole.": "Esa licencia no es válida. Comprueba que la has copiado entera.",
  "The file is empty.": "El archivo está vacío.",
  "The file is larger than 25 MB.": "El archivo pesa más de 25 MB.",
  "The file is not UTF-8 text. Upload a .fountain, .fdx or .pdf file.": "El archivo no es texto UTF-8. Sube un archivo .fountain, .fdx o .pdf.",
  "No scene headings found. Is this a screenplay in Fountain, Final Draft or PDF format?":
    "No hay encabezados de secuencia. ¿Es un guion en formato Fountain, Final Draft o PDF?",
  "That script is not in your library. Open the file again.": "Ese guion no está en tu biblioteca. Vuelve a abrir el archivo.",
  "That doesn't look like an Anthropic API key. Keys start with sk-ant-.": "Eso no parece una clave de API de Anthropic. Empiezan por sk-ant-.",
  "No Anthropic API key found. Add one in Settings, or set ANTHROPIC_API_KEY.":
    "No hay clave de API de Anthropic. Añade una en Ajustes.",
  "The Anthropic API rejected the API key. Check it in Settings.": "Anthropic ha rechazado la clave de API. Revísala en Ajustes.",
  "The Anthropic API rate limit was hit. Wait a moment and try again.": "Se ha alcanzado el límite de peticiones de Anthropic. Espera un momento y vuelve a intentarlo.",
  "Could not reach the Anthropic API. Check the internet connection.": "No se puede conectar con Anthropic. Revisa la conexión a internet.",
  "The model declined this request.": "El modelo ha rechazado esta petición.",
  "The model's answer was cut off before it finished.": "La respuesta del modelo se cortó antes de terminar.",
  "This script has no shooting schedule yet.": "Este guion aún no tiene plan de rodaje.",
  "This script has no elements yet.": "Este guion aún no tiene elementos.",

  // Charts
  Chart: "Gráfico",
  Table: "Tabla",
  "{unit} in total": "{unit} en total",
  "Fewer {unit}": "Menos {unit}",
  More: "Más",
  "of {total}": "de {total}",
  "Tension and mood in each scene": "Tensión y ánimo en cada secuencia",
  "Tension, 1 to 5": "Tensión, de 1 a 5",
  "Mood, −2 to +2": "Ánimo, de −2 a +2",
  tone: "tono",
  "tension, out of 5": "tensión, sobre 5",
  "mood, from −2 to +2": "ánimo, de −2 a +2",
  "Lighter mood": "Ánimo más luminoso",
  "Darker mood": "Ánimo más oscuro",
};

/** Singular and plural for the words counted with `plural()`. */
export const ES_WORDS: Record<string, [string, string]> = {
  scene: ["secuencia", "secuencias"],
  cue: ["intervención", "intervenciones"],
  element: ["elemento", "elementos"],
  "shooting day": ["jornada de rodaje", "jornadas de rodaje"],
  "rewritten scene": ["secuencia reescrita", "secuencias reescritas"],
  "new scene": ["secuencia nueva", "secuencias nuevas"],
};
