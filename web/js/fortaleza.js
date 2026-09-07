/* Panel de MI fortaleza: detección, resumen, novedades entre exports y avisos. */
const Fortaleza = (() => {
  const el = UI.el;

  async function cargar() {
    const panel = document.getElementById('panel-fortaleza');
    UI.poner(panel, el('p', { class: 'vacio', text: 'Buscando tu fortaleza...' }));
    try {
      const d = await API.fortaleza(App.mundoId());
      UI.poner(panel, pintar(d));
      panel.scrollTop = 0;
    } catch (e) { UI.fallo(e); UI.poner(panel, el('p', { class: 'vacio', text: e.mensaje })); }
  }

  function pintar(d) {
    if (!d.seleccion.site_id) return sinFortaleza(d);
    const r = d.resumen || {};
    const a = d.avisos || {};
    const n = d.novedades;

    return el('div', {}, [
      el('div', { class: 'ficha-cabecera' }, [
        el('h3', {}, [
          document.createTextNode(r.sitio ? (r.sitio.nombre || 'Sin nombre') : 'Fortaleza'),
          el('span', { class: 'tipo', text: r.sitio ? `  ${r.sitio.tipo || ''} · (${r.sitio.x}, ${r.sitio.y})` : '' }),
        ]),
        el('div', { class: 'tipo' }, [
          document.createTextNode(
            d.seleccion.origen === 'manual'
              ? 'Elegida a mano por ti. '
              : 'Detectada automáticamente. '),
          el('span', { class: 'enlace', text: 'cambiar', onclick: () => elegir(d) }),
        ]),
      ]),

      el('div', { class: 'tarjetas' }, [
        tarjeta(r.fundacion === null || r.fundacion === undefined ? '?' : r.fundacion, 'Año de fundación'),
        tarjeta((r.habitantes || {}).vivos ?? 0, 'Figuras vivas vinculadas'),
        tarjeta((r.habitantes || {}).muertos ?? 0, 'Figuras fallecidas'),
        tarjeta(((r.artefactos || {}).creados_aqui || []).length, 'Artefactos creados aquí'),
        tarjeta((r.caravanas || []).length, 'Caravanas registradas'),
        tarjeta((r.ataques || []).length, 'Ataques registrados'),
      ]),

      n ? novedades(n, d) : el('p', { class: 'nota', text:
        'Solo hay un export de este mundo. Cuando importes otro más reciente aparecera aquí que ha cambiado.' }),

      avisos(a),

      UI.bloque('Ficha', UI.datos([
        ['Estado', r.sitio ? r.sitio.estado : null],
        ['Gobierno', r.propietario ? el('span', { class: 'enlace', text: r.propietario.name,
          onclick: () => Figuras.verEntidad(r.propietario.entity_id) }) : null],
        ['Civilización', r.civilizacion ? el('span', { class: 'enlace', text: r.civilizacion.name,
          onclick: () => Figuras.verEntidad(r.civilizacion.entity_id) }) : null],
        ['Censo de la civilización', (r.censo_civilizacion || []).length
          ? r.censo_civilizacion.map((c) => `${c.race}: ${c.count}`).join(', ') : null],
      ])),

      (r.artefactos && r.artefactos.creados_aqui.length) ? UI.bloque('Artefactos creados aquí',
        UI.tabla(['Año', 'Artefacto', 'Autor'], r.artefactos.creados_aqui.map((x) => [
          String(UI.anyo(x.year)), x.name || `artefacto ${x.artifact_id}`,
          x.autor ? el('span', { class: 'enlace', text: x.autor, onclick: () => App.irAFigura(x.hfid) }) : '—',
        ]))) : null,

      (r.caravanas || []).length ? UI.bloque('Caravanas recibidas',
        UI.tabla(['Año', 'Suceso', 'Datos del archivo'], r.caravanas.map((c) => [
          String(UI.anyo(c.anyo)), UI.tipoLegible(c.tipo),
          el('span', { class: 'nota', text: UI.detallesTexto(c.detalles) }),
        ]))) : null,

      (r.ataques || []).length ? UI.bloque('Ataques registrados',
        UI.tabla(['Año', 'Suceso', 'Datos del archivo'], r.ataques.map((c) => [
          String(UI.anyo(c.anyo)), UI.tipoLegible(c.tipo),
          el('span', { class: 'nota', text: UI.detallesTexto(c.detalles) }),
        ]))) : null,

      (r.habitantes && r.habitantes.lista_vivos.length) ? UI.bloque(
        `Habitantes vivos (${r.habitantes.vivos})`,
        UI.tabla(['Nombre', 'Raza', 'Vínculo'], r.habitantes.lista_vivos.map((h) => [
          el('span', { class: 'enlace', text: h.name || '?', onclick: () => App.irAFigura(h.hf_id) }),
          h.race || '—', h.link_type || '—',
        ]))) : null,

      (r.habitantes && r.habitantes.lista_muertos.length) ? UI.bloque(
        `Fallecidos (${r.habitantes.muertos})`,
        UI.tabla(['Nombre', 'Raza', 'Año'], r.habitantes.lista_muertos.map((h) => [
          el('span', { class: 'enlace', text: h.name || '?', onclick: () => App.irAFigura(h.hf_id) }),
          h.race || '—', String(UI.anyo(h.death_year)),
        ]))) : null,

      el('div', { class: 'bloque' }, [
        el('button', { class: 'boton', text: 'Generar crónica de mi fortaleza',
          onclick: () => Cronicas.pedir({ tipo: 'fortaleza', site_id: d.seleccion.site_id },
            `Crónica de ${r.sitio ? r.sitio.nombre : 'mi fortaleza'}`) }),
        el('button', { class: 'boton', text: 'Ver en el mapa',
          onclick: () => App.verSitio(d.seleccion.site_id) }),
      ]),
    ]);
  }

  const tarjeta = (cifra, etiqueta) => el('div', { class: 'tarjeta' }, [
    el('div', { class: 'cifra', text: String(cifra) }),
    el('div', { class: 'etiqueta', text: etiqueta }),
  ]);

  function novedades(n, d) {
    const secciones = [
      ['Sucesos en mi fortaleza', n.en_mi_fortaleza, 'novedad'],
      ['Ataques en mi fortaleza o cerca', n.ataques_cerca, 'alerta'],
      ['Reclamaciones sobre mis artefactos', n.reclamaciones, 'alerta'],
      ['Llegadas', n.llegadas, 'novedad'],
      ['Caravanas', n.caravanas, 'novedad'],
    ];
    const bloques = secciones.filter(([, lista]) => lista && lista.length).map(([titulo, lista, clase]) =>
      UI.bloque(`${titulo} (${lista.length})`, ...lista.slice(0, 60).map((ev) =>
        el('div', { class: clase }, [
          el('strong', { text: `Año ${UI.anyo(ev.anyo)} · ${UI.tipoLegible(ev.tipo)}` }),
          ev.sitio ? el('span', { text: ` en ${ev.sitio}` }) : null,
          ev.distancia !== null && ev.distancia !== undefined && ev.distancia > 0
            ? el('span', { class: 'nota', text: ` (a ${ev.distancia} casillas)` }) : null,
          Object.keys(ev.detalles || {}).length
            ? el('div', { class: 'nota', text: UI.detallesTexto(ev.detalles) }) : null,
        ]))));

    if (n.artefactos_nuevos.length) {
      bloques.push(UI.bloque(`Artefactos nuevos (${n.artefactos_nuevos.length})`,
        UI.tabla(['Artefacto', 'Objeto', 'Dónde'], n.artefactos_nuevos.slice(0, 80).map((a) => [
          a.name || '?', a.item || '—',
          (a.sitio || '—') + (a.mio ? '  ← en mi fortaleza' : ''),
        ]))));
    }
    if (n.muertes_nuevas.length) {
      bloques.push(UI.bloque(`Han muerto desde el export anterior (${n.muertes_nuevas.length})`,
        UI.tabla(['Nombre', 'Raza', 'Año'], n.muertes_nuevas.slice(0, 100).map((m) => [
          el('span', { class: 'enlace', text: m.name || '?', onclick: () => App.irAFigura(m.hf_id) }),
          [m.race, m.associated_type !== 'standard' ? m.associated_type : null].filter(Boolean).join(' · ') || '—',
          String(UI.anyo(m.death_year)),
        ]))));
    }
    if (n.sitios_nuevos.length) {
      bloques.push(UI.bloque(`Asentamientos nuevos (${n.sitios_nuevos.length})`,
        UI.tabla(['Sitio', 'Tipo', 'Distancia'], n.sitios_nuevos.slice(0, 80).map((s) => [
          el('span', { class: 'enlace', text: s.name || '?', onclick: () => App.verSitio(s.site_id) }),
          s.type || '—',
          s.distancia === null || s.distancia === undefined ? '—' : `${s.distancia} casillas`,
        ]))));
    }

    return el('div', { class: 'bloque' }, [
      el('h4', { text: `Novedades desde el export anterior (${n.eventos_nuevos} sucesos nuevos)` }),
      bloques.length ? el('div', {}, bloques)
        : el('p', { class: 'nota', text: 'No hay novedades relevantes entre los dos exports.' }),
    ]);
  }

  function avisos(a) {
    if (!a) return null;
    const filas = [];
    for (const g of (a.guerras || [])) {
      filas.push(el('div', { class: 'alerta' }, [
        el('strong', { text: 'Guerra activa: ' }),
        document.createTextNode(`${g.name || 'sin nombre'} — ${g.atacante || '?'} contra ${g.defensor || '?'} (desde el año ${UI.anyo(g.start_year)})`),
      ]));
    }
    for (const s of (a.sitios_hostiles || [])) {
      filas.push(el('div', { class: 'alerta' + (s.en_guerra ? '' : ' suave') }, [
        el('span', { class: 'enlace', text: s.nombre || `sitio ${s.site_id}`, onclick: () => App.verSitio(s.site_id) }),
        document.createTextNode(` — ${s.tipo || ''}, a ${s.distancia} casillas. ${s.motivo}.`),
      ]));
    }
    for (const b of (a.bestias || [])) {
      filas.push(el('div', { class: 'alerta suave' }, [
        el('span', { class: 'enlace', text: b.nombre || `figura ${b.hf_id}`, onclick: () => App.irAFigura(b.hf_id) }),
        document.createTextNode(` — ${b.tipo || 'bestia'} viva${b.raza ? ' (' + b.raza + ')' : ''}, a ${b.distancia} casillas, en ${b.sitio}.`),
      ]));
    }
    return UI.bloque(`Avisos en ${a.radio} casillas a la redonda`,
      filas.length ? el('div', {}, filas)
        : el('div', { class: 'alerta buena', text: 'Ni sitios hostiles, ni bestias vivas cerca, ni guerras activas.' }));
  }

  function sinFortaleza(d) {
    const candidatos = d.seleccion.candidatos || [];
    return el('div', {}, [
      el('div', { class: 'ficha-cabecera' }, [el('h3', { text: 'Mi fortaleza' })]),
      el('p', { class: 'nota', text: d.seleccion.ambiguo
        ? 'Hay varios sitios que podrian ser tu fortaleza. Elige uno; se recordara para este mundo.'
        : 'No se ha podido deducir cual es tu fortaleza. Importa un export más reciente del mismo mundo, o elige el sitio a mano.' }),
      candidatos.length ? UI.tabla(['Sitio', 'Tipo', 'Fundado', 'Por qué', ''],
        candidatos.map((c) => [
          c.nombre || `sitio ${c.site_id}`, c.tipo || '—', String(UI.anyo(c.fundado)),
          el('span', { class: 'nota', text: c.razones.join('; ') }),
          el('button', { class: 'boton pequeño', text: 'Es esta',
            onclick: () => guardar(c.site_id) }),
        ])) : null,
      el('div', { class: 'bloque' }, [
        el('button', { class: 'boton', text: 'Elegir cualquier sitio del mapa a mano',
          onclick: () => elegir(d) }),
      ]),
    ]);
  }

  async function guardar(siteId) {
    try {
      await API.elegirFort(App.mundoId(), siteId);
      await cargar();
    } catch (e) { UI.fallo(e); }
  }

  async function elegir(d) {
    let sitios = [];
    try {
      const mapa = await API.mapa(d.export_id);
      sitios = mapa.sitios;
    } catch (e) { UI.fallo(e); return; }
    const buscador = el('input', { type: 'search', placeholder: 'Escribe el nombre del sitio...' });
    const lista = el('div', { class: 'lista', style: 'max-height:320px;overflow:auto' });
    let elegido = null;
    const refrescar = () => {
      const q = buscador.value.trim().toLowerCase();
      const filtrados = sitios
        .filter((s) => !q || (s.nombre || '').toLowerCase().includes(q))
        .slice(0, 200);
      UI.poner(lista, ...filtrados.map((s) => el('div', {
        class: 'item', onclick: (ev) => {
          elegido = s.id;
          lista.querySelectorAll('.item').forEach((n) => n.classList.remove('activo'));
          ev.currentTarget.classList.add('activo');
        },
      }, [
        el('span', { text: s.nombre || `sitio ${s.id}` }),
        el('span', { class: 'sub', text: `${s.tipo || ''} (${s.x},${s.y})` }),
      ])));
    };
    buscador.addEventListener('input', refrescar);
    refrescar();
    const ok = await UI.confirmar('Elegir mi fortaleza', [
      el('p', { class: 'nota', text: 'La elección se guarda para este mundo y manda sobre la detección automática.' }),
      buscador, lista,
      el('p', {}, [el('button', { class: 'boton pequeño', text: 'Olvidar la elección guardada',
        onclick: async () => { await API.elegirFort(App.mundoId(), null); document.getElementById('modal').classList.add('oculto'); cargar(); } })]),
    ], 'Guardar');
    if (ok && elegido !== null) await guardar(elegido);
  }

  return { cargar };
})();
