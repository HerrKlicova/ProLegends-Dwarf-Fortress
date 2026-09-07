/* Crónicas narradas por IA.

   Dos reglas que no se rompen:
   - Nunca se llama a la API sin que el usuario lo confirme expresamente.
   - Lo ya generado se lee del disco y no cuesta nada volver a verlo. */
const Cronicas = (() => {
  const el = UI.el;
  let estado = { disponible: false, motivo: '', modelo: '' };
  let guardadas = { grupos: [], total: 0, carpeta: '' };
  let seleccionada = null;

  async function cargar() {
    try { estado = await API.estadoCronica(); } catch (e) { UI.fallo(e); }
    await refrescarArbol();
    pintarGenerador();
    if (!seleccionada) pintarPortada();
  }

  /* ---------------------------------------------- panel izquierdo: generar */
  function pintarGenerador() {
    const exp = App.exportActual();
    const desde = el('input', { type: 'number', value: String(exp.anyo_min ?? 0) });
    const hasta = el('input', { type: 'number', value: String(exp.anyo_max ?? 0) });

    UI.poner(document.getElementById('cronica-generar'), el('div', {}, [
      estado.disponible
        ? el('div', { class: 'alerta buena', text: `Listo. Modelo: ${estado.modelo}.` })
        : el('div', { class: 'alerta', text: estado.motivo }),
      el('label', { text: 'Rango de años' }),
      el('div', { class: 'rango' }, [
        desde, el('span', { class: 'nota', text: 'a' }), hasta,
      ]),
      el('button', {
        class: 'boton primario ancho', text: 'Generar crónica del rango',
        onclick: () => pedir(
          { tipo: 'anyos', desde: Number(desde.value), hasta: Number(hasta.value) },
          `Años ${desde.value} a ${hasta.value}`),
      }),
      el('p', { class: 'nota', text:
        'La crónica de una figura se pide desde su ficha, en "Figuras históricas". ' +
        'La de tu fortaleza, desde "Mi fortaleza".' }),
    ]));
  }

  /* ------------------------------------------------ panel izquierdo: árbol */
  async function refrescarArbol() {
    try { guardadas = await API.cronicas(App.mundoId()); }
    catch (e) { guardadas = { grupos: [], total: 0, carpeta: '' }; }

    const caja = document.getElementById('cronica-arbol');
    caja.className = 'arbol';
    if (!guardadas.total) {
      UI.poner(caja, el('p', { class: 'nota', text: 'Todavía no has generado ninguna.' }));
      document.getElementById('cronica-carpeta').textContent = '';
      return;
    }

    UI.poner(caja, ...guardadas.grupos.map((g) => el('details', { open: 'open' }, [
      el('summary', {}, [
        document.createTextNode(g.nombre + ' '),
        el('span', { class: 'cuenta', text: `(${g.cronicas.length})` }),
      ]),
      ...g.cronicas.map((c) => el('div', {
        class: 'item' + (seleccionada === c.clave ? ' activo' : ''),
        dataset: { clave: c.clave },
        title: c.fichero || '',
        onclick: () => abrir(c),
      }, [
        el('span', { text: c.titulo || c.clave }),
        el('span', { class: 'sub', text: [
          c.generada ? c.generada.slice(0, 10) : null,
          c.palabras ? `${c.palabras} palabras` : null,
        ].filter(Boolean).join(' · ') }),
      ])),
    ])));

    document.getElementById('cronica-carpeta').textContent =
      `Guardadas como ficheros de texto en ${guardadas.carpeta}`;
  }

  /* ------------------------------------------------------ panel principal */
  function pintarPortada() {
    UI.poner(document.getElementById('panel-cronicas'), el('div', {}, [
      el('div', { class: 'ficha-cabecera' }, [
        el('h3', { text: 'Crónicas narradas' }),
        el('div', { class: 'tipo', text:
          'Se escriben con la API de Anthropic a partir de los hechos del archivo, ' +
          'sin inventar nada.' }),
      ]),
      guardadas.total
        ? el('p', { class: 'vacio', text: 'Elige una crónica de la lista de la izquierda.' })
        : el('p', { class: 'vacio', text:
            'Todavía no hay ninguna. Genera la primera desde la izquierda, desde la ' +
            'ficha de una figura, o desde el panel de tu fortaleza.' }),
      el('div', { class: 'bloque' }, [
        el('h4', { text: 'Dónde se guardan' }),
        el('p', { class: 'nota', text:
          'Cada crónica es un fichero de texto dentro de data/cronicas/. Puedes leerlas ' +
          'con el Bloc de notas sin abrir el programa, y no se pierden al borrar la base ' +
          'de datos. Si te bajas una versión nueva, copia esa carpeta y las conservas.' }),
      ]),
    ]));
  }

  async function abrir(resumen) {
    seleccionada = resumen.clave;
    const panel = document.getElementById('panel-cronicas');
    UI.poner(panel, el('p', { class: 'vacio', text: 'Abriendo...' }));
    try {
      const c = await API.cronica(App.mundoId(), resumen.ambito, resumen.clave);
      volcar({
        texto: c.texto, titulo: c.titulo, modelo: c.modelo,
        creada: c.generada, fichero: c.fichero, de_cache: true,
      }, deClave(c.ambito, c.clave));
      await refrescarArbol();
    } catch (e) { UI.fallo(e); }
  }

  function deClave(tipo, clave) {
    const valor = String(clave).split(':')[1] || '';
    if (tipo === 'anyos') {
      const [d, h] = valor.split('-');
      return { tipo: 'anyos', desde: Number(d), hasta: Number(h) };
    }
    if (tipo === 'figura') return { tipo: 'figura', hf_id: Number(valor) };
    if (tipo === 'fortaleza') return { tipo: 'fortaleza', site_id: Number(valor) };
    return null;
  }

  /* Punto de entrada desde cualquier vista. Siempre avisa antes de gastar. */
  async function pedir(ambito, etiqueta) {
    App.pestanya('cronicas');
    let previo;
    try {
      previo = await API.prepararCron({ export_id: App.exportId(), ambito });
    } catch (e) { UI.fallo(e); return; }

    if (!previo.disponible && !previo.ya_generada) {
      UI.aviso('No se puede generar la crónica todavía.', previo.motivo);
      return;
    }
    if (previo.ya_generada) {
      const rehacer = await UI.confirmar('Esta crónica ya existe', [
        el('p', { text: `Ya se generó el ${(previo.generada_el || '').replace('T', ' ')}. ` +
          'Puedes verla sin gastar nada, o volver a generarla (eso sí consume API).' }),
        el('p', { class: 'nota', text: `Ámbito: ${previo.titulo || etiqueta}` }),
      ], 'Regenerar (consume API)');
      try {
        volcar(await API.generarCron({ export_id: App.exportId(), ambito, regenerar: rehacer }), ambito);
        await refrescarArbol();
      } catch (e) { UI.fallo(e); }
      return;
    }

    const ok = await UI.confirmar('Esto va a consumir API', [
      el('p', { text: `Se va a pedir a ${previo.modelo} que redacte: ${previo.titulo || etiqueta}.` }),
      UI.datos([
        ['Hechos que se le envían', previo.hechos],
        ['Tamaño del contexto', `${previo.caracteres_contexto} caracteres (~${previo.aproximado_tokens} tokens)`],
        ['Coste', 'Se cobra en tu cuenta de Anthropic. El resultado queda guardado como ' +
                  'fichero y no se vuelve a pedir.'],
      ]),
    ], 'Generar crónica');
    if (!ok) return;

    const panel = document.getElementById('panel-cronicas');
    UI.poner(panel, el('p', { class: 'vacio', text: 'Escribiendo la crónica...' }));
    try {
      volcar(await API.generarCron({ export_id: App.exportId(), ambito, regenerar: false }), ambito);
      await refrescarArbol();
    } catch (e) { UI.fallo(e); UI.poner(panel, el('p', { class: 'vacio', text: e.mensaje })); }
  }

  function volcar(r, ambito) {
    const panel = document.getElementById('panel-cronicas');
    if (!panel) return;
    UI.poner(panel, el('div', {}, [
      el('div', { class: 'ficha-cabecera' }, [
        el('h3', { text: r.titulo || 'Crónica' }),
        el('div', { class: 'tipo', text:
          `${r.de_cache ? 'Guardada' : 'Generada ahora'}` +
          (r.modelo ? ` · modelo ${r.modelo}` : '') +
          (r.creada ? ` · ${String(r.creada).replace('T', ' ').replace('+00:00', '')}` : '') +
          (r.tokens ? ` · ${r.tokens.entrada} tokens de entrada, ${r.tokens.salida} de salida` : '') }),
      ]),
      el('div', { class: 'cronica', text: r.texto }),
      r.fichero ? el('p', { class: 'nota', text: `Fichero: ${r.fichero}` }) : null,
      ambito ? el('p', {}, [el('button', {
        class: 'boton', text: 'Volver a generarla (consume API)',
        onclick: async () => {
          const ok = await UI.confirmar('Regenerar la crónica',
            [el('p', { text: 'Se hará una llamada nueva a la API y se sustituirá el texto guardado.' })],
            'Regenerar');
          if (!ok) return;
          try {
            volcar(await API.generarCron({ export_id: App.exportId(), ambito, regenerar: true }), ambito);
            await refrescarArbol();
          } catch (e) { UI.fallo(e); }
        },
      })]) : null,
    ]));
    panel.scrollTop = 0;
  }

  return { cargar, pedir };
})();
