/* Cronicas narradas por IA. Nunca se llama a la API sin confirmacion expresa. */
const Cronicas = (() => {
  const el = UI.el;

  async function cargar() {
    const panel = document.getElementById('panel-cronicas');
    UI.poner(panel, el('p', { class: 'vacio', text: 'Cargando...' }));
    let estado = { disponible: false, motivo: '', modelo: '' };
    let guardadas = { cronicas: [] };
    try {
      estado = await API.estadoCronica();
      guardadas = await API.cronicas(App.mundoId());
    } catch (e) { UI.fallo(e); }

    const exp = App.exportActual();
    const desde = el('input', { type: 'number', value: String(exp.anyo_min ?? 0) });
    const hasta = el('input', { type: 'number', value: String(exp.anyo_max ?? 0) });

    UI.poner(panel, el('div', {}, [
      el('div', { class: 'ficha-cabecera' }, [
        el('h3', { text: 'Cronicas narradas' }),
        el('div', { class: 'tipo', text:
          'Se escriben con la API de Anthropic a partir de los hechos del archivo, sin inventar nada. ' +
          'Cada cronica se guarda: pedirla otra vez no cuesta nada.' }),
      ]),

      estado.disponible
        ? el('div', { class: 'alerta buena', text: `Listo. Modelo configurado: ${estado.modelo}.` })
        : el('div', { class: 'alerta', text: estado.motivo }),

      UI.bloque('Cronica de un rango de anyos',
        el('div', { class: 'chips' }, [
          el('label', { class: 'capa' }, [document.createTextNode('desde '), desde]),
          el('label', { class: 'capa' }, [document.createTextNode('hasta '), hasta]),
          el('button', { class: 'boton primario', text: 'Generar',
            onclick: () => pedir({ tipo: 'anyos', desde: Number(desde.value), hasta: Number(hasta.value) },
              `Anyos ${desde.value} a ${hasta.value}`) }),
        ])),

      UI.bloque('Otras cronicas',
        el('p', { class: 'nota', text:
          'La cronica de una figura concreta se pide desde su ficha, en la pestanya de figuras historicas. ' +
          'La de tu fortaleza, desde la pestanya "Mi fortaleza".' })),

      guardadas.cronicas.length ? UI.bloque(`Cronicas ya guardadas (${guardadas.cronicas.length})`,
        UI.tabla(['Ambito', 'Titulo', 'Modelo', 'Generada'], guardadas.cronicas.map((c) => [
          c.scope_key,
          el('span', { class: 'enlace', text: c.title || '(sin titulo)',
            onclick: () => mostrarGuardada(c) }),
          c.model || '—', (c.created_at || '').replace('T', ' ').replace('+00:00', ''),
        ]))) : null,

      el('div', { id: 'salida-cronica' }),
    ]));
  }

  async function mostrarGuardada(c) {
    const ambito = deClave(c.scope_type, c.scope_key);
    if (!ambito) return;
    try {
      const r = await API.generarCron({ export_id: App.exportId(), ambito, regenerar: false });
      volcar(r, ambito);
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
      UI.aviso('No se puede generar la cronica todavia.', previo.motivo);
      return;
    }
    if (previo.ya_generada) {
      const rehacer = await UI.confirmar('Esta cronica ya existe',
        [
          el('p', { text: `Ya se genero el ${(previo.generada_el || '').replace('T', ' ')}. ` +
            'Puedes verla sin gastar nada, o volver a generarla (eso si consume API).' }),
          el('p', { class: 'nota', text: `Ambito: ${previo.titulo || etiqueta}` }),
        ], 'Regenerar (consume API)');
      try {
        const r = await API.generarCron({ export_id: App.exportId(), ambito, regenerar: rehacer });
        volcar(r, ambito);
      } catch (e) { UI.fallo(e); }
      return;
    }

    const ok = await UI.confirmar('Esto va a consumir API', [
      el('p', { text: `Se va a pedir a ${previo.modelo} que redacte: ${previo.titulo || etiqueta}.` }),
      UI.datos([
        ['Hechos que se le envian', previo.hechos],
        ['Tamano del contexto', `${previo.caracteres_contexto} caracteres (~${previo.aproximado_tokens} tokens)`],
        ['Coste', 'Se cobra en tu cuenta de Anthropic. El resultado queda guardado y no se vuelve a pedir.'],
      ]),
    ], 'Generar cronica');
    if (!ok) return;

    const salida = document.getElementById('salida-cronica');
    UI.poner(salida, el('p', { class: 'vacio', text: 'Escribiendo la cronica...' }));
    try {
      const r = await API.generarCron({ export_id: App.exportId(), ambito, regenerar: false });
      volcar(r, ambito);
    } catch (e) { UI.fallo(e); UI.poner(salida, el('p', { class: 'vacio', text: e.mensaje })); }
  }

  function volcar(r, ambito) {
    const salida = document.getElementById('salida-cronica');
    if (!salida) return;
    UI.poner(salida, el('div', { class: 'bloque' }, [
      el('h4', { text: r.titulo || 'Cronica' }),
      el('p', { class: 'nota', text:
        `${r.de_cache ? 'Recuperada de la copia guardada' : 'Generada ahora'} · modelo ${r.modelo}` +
        (r.tokens ? ` · ${r.tokens.entrada} tokens de entrada, ${r.tokens.salida} de salida` : '') }),
      el('div', { class: 'cronica', text: r.texto }),
      el('p', {}, [el('button', { class: 'boton', text: 'Volver a generarla (consume API)',
        onclick: async () => {
          const ok = await UI.confirmar('Regenerar la cronica',
            [el('p', { text: 'Se hara una llamada nueva a la API y se sustituira el texto guardado.' })],
            'Regenerar');
          if (!ok) return;
          try { volcar(await API.generarCron({ export_id: App.exportId(), ambito, regenerar: true }), ambito); }
          catch (e) { UI.fallo(e); }
        } })]),
    ]));
    salida.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }

  return { cargar, pedir };
})();
