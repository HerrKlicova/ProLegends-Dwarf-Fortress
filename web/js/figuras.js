/* Explorador de figuras históricas y de entidades. Todo enlazado entre si. */
const Figuras = (() => {
  const el = UI.el;
  let ultimaBusqueda = '';
  let temporizador = null;

  function conectar() {
    const buscar = document.getElementById('buscar-figura');
    buscar.addEventListener('input', () => {
      clearTimeout(temporizador);
      temporizador = setTimeout(listar, 220);
    });
    ['filtro-raza', 'filtro-vivas', 'filtro-orden'].forEach((id) =>
      document.getElementById(id).addEventListener('change', listar));
    document.getElementById('btn-matadores').addEventListener('click', verMatadores);
  }

  async function inicializar() {
    const datos = await API.figuras(App.exportId(), 'limite=1');
    const sel = document.getElementById('filtro-raza');
    UI.poner(sel, el('option', { value: '', text: `todas (${datos.total} figuras)` }),
      ...datos.razas.map((r) => el('option', { value: r.race, text: `${r.raza || r.race} (${r.n})` })));
    UI.poner(document.getElementById('panel-figura'),
      el('p', { class: 'vacio', text: 'Busca una figura histórica y pincha en ella.' }));
    await listar();
  }

  async function listar() {
    const q = document.getElementById('buscar-figura').value.trim();
    const raza = document.getElementById('filtro-raza').value;
    const vivas = document.getElementById('filtro-vivas').value;
    const orden = document.getElementById('filtro-orden').value;
    const parametros = new URLSearchParams({ limite: '250', orden });
    if (q) parametros.set('q', q);
    if (raza) parametros.set('raza', raza);
    if (vivas) parametros.set('vivas', vivas);
    ultimaBusqueda = parametros.toString();
    try {
      const datos = await API.figuras(App.exportId(), ultimaBusqueda);
      const caja = document.getElementById('lista-figuras');
      if (!datos.figuras.length) {
        UI.poner(caja, el('p', { class: 'nota', text: 'Ninguna figura coincide con la busqueda.' }));
        return;
      }
      UI.poner(caja, ...datos.figuras.map((f) => el('div', {
        class: 'item', dataset: { hf: String(f.hf_id) },
        onclick: () => abrir(f.hf_id),
      }, [
        el('span', { class: 'pastilla', style: `background:${f.color}` }),
        el('span', { text: f.name || `figura ${f.hf_id}` }),
        el('span', { class: 'sub', text: f.alive ? 'viva' : `† ${UI.anyo(f.death_year)}` }),
      ])));
    } catch (e) { UI.fallo(e); }
  }

  async function abrir(hfId) {
    const panel = document.getElementById('panel-figura');
    UI.poner(panel, el('p', { class: 'vacio', text: 'Cargando ficha...' }));
    document.querySelectorAll('#lista-figuras .item').forEach((n) =>
      n.classList.toggle('activo', n.dataset.hf === String(hfId)));
    try {
      UI.poner(panel, ficha(await API.figura(App.exportId(), hfId)));
      panel.scrollTop = 0;
    } catch (e) { UI.fallo(e); }
  }

  function listaChips(titulo, valores) {
    if (!valores || !valores.length) return null;
    return UI.bloque(titulo, el('div', { class: 'chips' },
      valores.map((v) => el('span', { class: 'chip', text: String(v) }))));
  }

  function ficha(f) {
    const banderas = Object.entries(f.banderas).filter(([, v]) => v).map(([k]) => k);
    return el('div', {}, [
      el('div', { class: 'ficha-cabecera' }, [
        el('h3', { text: f.nombre || `Figura ${f.id}` }),
        el('div', { class: 'tipo', text: [f.raza, f.casta, f.tipo_legible || f.tipo].filter(Boolean).join(' · ') }),
      ]),
      UI.datos([
        ['Nacimiento', f.nacimiento === null || f.nacimiento === -1 ? null : `año ${f.nacimiento}`],
        ['Muerte', f.vive ? 'sigue viva' : (f.muerte === -1 ? 'desconocida' : `año ${f.muerte}`)],
        ['Apareció', f.aparecio === null || f.aparecio === -1 ? null : `año ${f.aparecio}`],
        ['Muertes causadas', f.muertes_causadas || null],
        ['Rasgos', banderas.length ? banderas.join(', ') : null],
      ]),

      f.ficha_muerte ? UI.bloque('Cómo murió', el('p', {}, [
        document.createTextNode(`Año ${f.ficha_muerte.year}. `),
        el('span', { text: f.ficha_muerte.frase || '' }),
        f.ficha_muerte.asesino
          ? el('div', { class: 'nota' }, ['Ver a ', el('span', {
              class: 'enlace', text: f.ficha_muerte.asesino,
              onclick: () => abrir(f.ficha_muerte.slayer_hfid) })])
          : null,
      ])) : null,

      f.pertenencias.length ? UI.bloque('Entidades a las que pertenece o perteneció',
        UI.tabla(['Entidad', 'Tipo', 'Vínculo'], f.pertenencias.map((p) => [
          p.entidad
            ? el('span', { class: 'enlace', text: p.entidad, onclick: () => verEntidad(p.entidad_id) })
            : `entidad ${p.entidad_id}`,
          [p.tipo_entidad_legible || p.tipo_entidad, p.raza].filter(Boolean).join(' · ') || '—',
          (p.vinculo_legible || p.vinculo || '') + (p.antiguo ? ' (antiguo)' : ''),
        ]))) : null,

      f.cargos.length ? UI.bloque('Cargos',
        UI.tabla(['Cargo', 'En'], f.cargos.map((c) => [
          c.cargo || '—',
          c.entidad ? el('span', { class: 'enlace', text: c.entidad, onclick: () => verEntidad(c.entity_id) }) : '—',
        ]))) : null,

      f.sitios.length ? UI.bloque('Sitios vinculados',
        el('div', { class: 'chips' }, f.sitios.map((s) => el('span', {
          class: 'chip enlace', text: `${s.nombre || 'sitio ' + s.site_id} · ${s.legible || s.link_type || ''}`,
          onclick: () => App.verSitio(s.site_id),
        })))) : null,

      f.deidades && f.deidades.length ? UI.bloque('Deidades',
        el('div', { class: 'chips' }, f.deidades.map((d) => el('span', {
          class: 'chip enlace',
          text: `${d.nombre || 'sin nombre'}${d.vinculo ? ' · ' + (d.vinculo_legible || d.vinculo) : ''}`,
          onclick: () => (d.hf_id !== null && d.hf_id !== undefined)
            ? abrir(d.hf_id) : verEntidad(d.entidad_id),
        })))) : null,

      listaChips('Esferas', f.esferas_legibles && f.esferas_legibles.length ? f.esferas_legibles : f.esferas),
      listaChips('Objetivos vitales', f.objetivos_legibles && f.objetivos_legibles.length ? f.objetivos_legibles : f.objetivos),
      listaChips('Secretos conocidos', f.secretos),
      listaChips('Interacciones', f.interacciones),
      listaChips('Profesiones', f.profesiones),

      f.habilidades.length ? UI.bloque('Habilidades',
        el('div', { class: 'chips' }, f.habilidades.slice(0, 40).map((h) =>
          el('span', { class: 'chip', text: `${h.legible || h.skill} (${h.total_ip})` })))) : null,

      f.artefactos.length ? UI.bloque('Artefactos que posee',
        el('div', { class: 'chips' }, f.artefactos.map((a) =>
          el('span', { class: 'chip', text: a.name || a.item || `artefacto ${a.artifact_id}` })))) : null,

      f.tramas.length ? UI.bloque('Tramas de intriga',
        UI.tabla(['Tipo', 'Detalles'], f.tramas.map((t) => [
          t.type ? UI.tipoLegible(t.type) : '—',
          el('span', { class: 'nota', text: UI.detallesTexto(t.detalles) }),
        ]))) : null,

      f.relaciones.length ? UI.bloque('Relaciones',
        UI.tabla(['Figura', 'Vínculo'], f.relaciones.slice(0, 120).map((r) => [
          r.nombre
            ? el('span', { class: 'enlace', text: r.nombre, onclick: () => abrir(r.hf_id) })
            : `figura ${r.hf_id}`,
          r.vinculo_legible || r.vinculo || '—',
        ]))) : null,

      f.victimas.length ? UI.bloque(`A quién mató (${f.victimas.length})`,
        UI.tabla(['Año', 'Víctima', 'Raza'], f.victimas.map((v) => [
          String(UI.anyo(v.year)),
          v.name ? el('span', { class: 'enlace', text: v.name, onclick: () => abrir(v.hfid) }) : `figura ${v.hfid}`,
          v.raza || v.race || '—',
        ]))) : null,

      f.eventos.length ? UI.bloque(`Sucesos de su vida (${f.eventos.length}${f.eventos_truncados ? '+' : ''})`,
        UI.tabla(['Año', 'Qué pasó', 'Lugar'], f.eventos.map((ev) => [
          String(UI.anyo(ev.anyo)), UI.suceso(ev),
          ev.sitio ? el('span', { class: 'enlace', text: ev.sitio, onclick: () => App.verSitio(ev.site_id) }) : '—',
        ]))) : null,

      el('div', { class: 'bloque' }, [
        el('button', { class: 'boton', text: 'Generar crónica de esta figura',
          onclick: () => Cronicas.pedir({ tipo: 'figura', hf_id: f.id }, `Vida de ${f.nombre}`) }),
      ]),
    ]);
  }

  async function verEntidad(entityId) {
    App.pestanya('figuras');
    const panel = document.getElementById('panel-figura');
    UI.poner(panel, el('p', { class: 'vacio', text: 'Cargando entidad...' }));
    try {
      const e = await API.entidad(App.exportId(), entityId);
      UI.poner(panel, fichaEntidad(e));
      panel.scrollTop = 0;
    } catch (err) { UI.fallo(err); }
  }

  function fichaEntidad(e) {
    return el('div', {}, [
      el('div', { class: 'ficha-cabecera' }, [
        el('h3', {}, [
          el('span', { class: 'pastilla', style: `background:${e.color};margin-right:.4rem` }),
          document.createTextNode(e.nombre || `Entidad ${e.id}`),
        ]),
        el('div', { class: 'tipo', text: [e.tipo, e.raza].filter(Boolean).join(' · ') }),
      ]),
      UI.datos([
        ['Pertenece a', e.padre ? el('span', { class: 'enlace', text: e.padre.nombre, onclick: () => verEntidad(e.padre.id) }) : null],
        ['Civilización raíz', e.raiz && e.raiz.id !== e.id
          ? el('span', { class: 'enlace', text: e.raiz.nombre, onclick: () => verEntidad(e.raiz.id) }) : null],
      ]),
      e.hijos.length ? UI.bloque(`Entidades hijas (${e.hijos.length})`,
        el('div', { class: 'chips' }, e.hijos.map((h) => el('span', {
          class: 'chip enlace', text: h.name || `entidad ${h.entity_id}`,
          onclick: () => verEntidad(h.entity_id) })))) : null,
      e.sitios.length ? UI.bloque(`Sitios (${e.sitios.length})`,
        UI.tabla(['Sitio', 'Tipo', 'Estado'], e.sitios.map((s) => [
          el('span', { class: 'enlace', text: s.name || `sitio ${s.site_id}`, onclick: () => App.verSitio(s.site_id) }),
          s.type || '—', s.state || '—',
        ]))) : null,
      e.guerras.length ? UI.bloque('Guerras y conflictos',
        UI.tabla(['Años', 'Nombre', 'Atacante', 'Defensor'], e.guerras.map((g) => [
          `${UI.anyo(g.start_year)} – ${g.end_year === -1 || g.end_year === null ? 'en curso' : g.end_year}`,
          g.name || g.type || '—', g.attacking_nombre || '—', g.defending_nombre || '—',
        ]))) : null,
      e.cargos.length ? UI.bloque('Cargos',
        UI.tabla(['Cargo', 'Titular'], e.cargos.map((c) => [
          c.name || '—',
          c.titular ? el('span', { class: 'enlace', text: c.titular, onclick: () => abrir(c.hfid) }) : '—',
        ]))) : null,
      e.miembros.length ? UI.bloque(`Miembros registrados (${e.miembros.length})`,
        UI.tabla(['Nombre', 'Raza', 'Vínculo'], e.miembros.slice(0, 150).map((m) => [
          el('span', { class: 'enlace', text: m.name || '?', onclick: () => abrir(m.hf_id) }),
          m.raza || m.race || '—', (m.vinculo_legible || m.link_type || '') + (m.alive ? '' : ' (fallecido)'),
        ]))) : null,
    ]);
  }

  async function verMatadores() {
    App.pestanya('figuras');
    const panel = document.getElementById('panel-figura');
    UI.poner(panel, el('p', { class: 'vacio', text: 'Calculando...' }));
    try {
      const datos = await API.matadores(App.exportId());
      if (!datos.matadores.length) {
        UI.poner(panel, el('p', { class: 'vacio', text: 'Este export no registra ninguna muerte con causante conocido.' }));
        return;
      }
      UI.poner(panel, el('div', {}, [
        el('div', { class: 'ficha-cabecera' }, [
          el('h3', { text: 'Quién mató a quién' }),
          el('div', { class: 'tipo', text: 'Ranking por muertes registradas en el archivo de leyendas.' }),
        ]),
        UI.tabla(['#', 'Figura', 'Raza', 'Muertes', 'Algunas víctimas'],
          datos.matadores.map((m, i) => [
            String(i + 1),
            el('span', { class: 'enlace', text: m.name || `figura ${m.hf_id}`, onclick: () => abrir(m.hf_id) }),
            [m.raza || m.race, m.associated_type !== 'standard' ? (m.tipo_legible || m.associated_type) : null].filter(Boolean).join(' · ') || '—',
            String(m.kills),
            el('span', { class: 'nota', text: m.victimas.map((v) => `${v.name || '?'} (${v.year})`).join(', ') }),
          ])),
      ]));
    } catch (e) { UI.fallo(e); }
  }

  return { conectar, inicializar, abrir, verEntidad, verMatadores };
})();
