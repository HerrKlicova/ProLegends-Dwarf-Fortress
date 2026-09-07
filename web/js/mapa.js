/* Mapa interactivo del mundo con deslizador de anyo.
   Todo el estado historico llega de una vez desde /api/exports/{id}/mapa, asi
   que mover el deslizador no hace ninguna peticion al servidor. */
const Mapa = (() => {

  const CAPAS = [
    { id: 'asentamiento', nombre: 'Asentamientos', color: '#c9b28a' },
    { id: 'ruinas',       nombre: 'Ruinas',        color: '#6b625a' },
    { id: 'guarida',      nombre: 'Guaridas de bestias', color: '#b4573c' },
    { id: 'torre',        nombre: 'Torres y nigromantes', color: '#7d5ba6' },
    { id: 'boveda',       nombre: 'Bovedas y sitios misteriosos', color: '#d9c74a' },
    { id: 'cueva',        nombre: 'Cuevas', color: '#7a6a52' },
    { id: 'tumba',        nombre: 'Tumbas', color: '#8a8f98' },
  ];

  let datos = null;
  let anyo = 0;
  let capas = new Set(CAPAS.map((c) => c.id));
  let faccionesApagadas = new Set();
  let verBestias = true;
  let historia = new Map();     // site_id -> [[anyo, propietario, estado], ...]
  let colorFaccion = new Map(); // entity_id -> color de su civilizacion raiz
  let posiciones = [];          // cache de lo dibujado, para el raton
  let reproduciendo = null;
  let seleccionado = null;

  const lienzo = () => document.getElementById('lienzo');

  async function cargar(exportId) {
    datos = await API.mapa(exportId);
    historia = new Map();
    for (const [sid, y, owner, estado] of datos.propiedad) {
      if (!historia.has(sid)) historia.set(sid, []);
      historia.get(sid).push([y, owner, estado]);
    }
    for (const lista of historia.values()) lista.sort((a, b) => a[0] - b[0]);

    const porId = new Map(datos.facciones.map((f) => [f.id, f]));
    colorFaccion = new Map();
    for (const f of datos.facciones) {
      const raiz = porId.get(f.raiz);
      colorFaccion.set(f.id, (raiz || f).color);
    }

    const min = datos.export.anyo_min ?? 0;
    const max = Math.max(datos.export.anyo_max ?? 0, datos.export.fecha_partida ?? 0, min);
    const rango = document.getElementById('anyo');
    rango.min = min; rango.max = max; rango.value = max;
    anyo = max;
    faccionesApagadas = new Set();
    seleccionado = null;

    pintarCapas();
    pintarLeyenda();
    UI.poner(document.getElementById('panel-sitio'),
      UI.el('p', { class: 'vacio', text: 'Pincha en un sitio del mapa para ver su ficha.' }));
    ajustarLienzo();
    dibujar();
  }

  /* ------------------------------------------------ estado en un anyo dado */
  function estadoEn(sid, y) {
    const lista = historia.get(sid);
    if (!lista || !lista.length) return { existe: true, owner: null, estado: 'desconocido' };
    let encontrado = null;
    for (const fila of lista) {
      if (fila[0] > y) break;
      encontrado = fila;
    }
    if (!encontrado) return { existe: false, owner: null, estado: null };
    return { existe: true, owner: encontrado[1], estado: encontrado[2] };
  }

  function bestiasEn(y) {
    if (!verBestias || !datos) return [];
    const salida = [];
    for (const b of datos.bestias) {
      if (b.nacimiento !== null && b.nacimiento !== undefined && b.nacimiento > y) continue;
      if (b.muerte !== null && b.muerte !== -1 && b.muerte < y) continue;
      let sitio = null;
      for (const [anyoPos, sid] of b.posiciones) {
        if (anyoPos === -1 && sitio === null) sitio = sid;
        else if (anyoPos <= y) sitio = sid;
      }
      if (sitio === null) continue;
      salida.push({ bestia: b, site_id: sitio });
    }
    return salida;
  }

  /* --------------------------------------------------------- panel lateral */
  function pintarCapas() {
    const caja = document.getElementById('capas');
    UI.poner(caja, ...CAPAS.map((c) => UI.el('label', { class: 'capa' }, [
      UI.el('input', {
        type: 'checkbox', checked: capas.has(c.id) ? 'checked' : null,
        onchange: (e) => { e.target.checked ? capas.add(c.id) : capas.delete(c.id); dibujar(); },
      }),
      UI.el('span', { class: 'pastilla', style: `background:${c.color}` }),
      UI.el('span', { text: c.nombre }),
    ])));
  }

  function pintarLeyenda() {
    const caja = document.getElementById('leyenda');
    const civs = datos.facciones.filter((f) => f.raiz === f.id);
    const cuenta = new Map();
    for (const s of datos.sitios) {
      const raiz = s.civ_raiz;
      if (raiz !== null && raiz !== undefined) cuenta.set(raiz, (cuenta.get(raiz) || 0) + 1);
    }
    civs.sort((a, b) => (cuenta.get(b.id) || 0) - (cuenta.get(a.id) || 0));
    UI.poner(caja, ...civs.map((f) => {
      const fila = UI.el('div', {
        class: 'fila' + (faccionesApagadas.has(f.id) ? ' apagada' : ''),
        title: `${f.nombre}${f.raza ? ' · ' + f.raza : ''}`,
        onclick: () => {
          faccionesApagadas.has(f.id) ? faccionesApagadas.delete(f.id) : faccionesApagadas.add(f.id);
          pintarLeyenda(); dibujar();
        },
      }, [
        UI.el('span', { class: 'pastilla', style: `background:${f.color}` }),
        UI.el('span', { text: f.raza || f.nombre }),
        UI.el('span', { class: 'conteo', text: String(cuenta.get(f.id) || 0) }),
      ]);
      return fila;
    }));
    if (!civs.length) UI.poner(caja, UI.el('p', { class: 'nota', text: 'Este export no trae informacion de civilizaciones.' }));
  }

  /* ------------------------------------------------------------- dibujado */
  function ajustarLienzo() {
    const c = lienzo();
    const caja = c.parentElement.getBoundingClientRect();
    const escala = window.devicePixelRatio || 1;
    c.width = Math.max(1, Math.floor(caja.width * escala));
    c.height = Math.max(1, Math.floor(caja.height * escala));
  }

  function dibujar() {
    if (!datos) return;
    const c = lienzo();
    const ctx = c.getContext('2d');
    const ancho = Math.max(1, datos.export.ancho || 1);
    const alto = Math.max(1, datos.export.alto || 1);
    const celda = Math.min(c.width / ancho, c.height / alto);
    const offX = (c.width - celda * ancho) / 2;
    const offY = (c.height - celda * alto) / 2;

    ctx.fillStyle = '#0d0c0a';
    ctx.fillRect(0, 0, c.width, c.height);

    /* rejilla */
    ctx.strokeStyle = 'rgba(255,255,255,.045)';
    ctx.lineWidth = 1;
    const paso = Math.max(1, Math.round(10 / Math.max(celda / 6, .35)));
    for (let x = 0; x <= ancho; x += paso) {
      ctx.beginPath(); ctx.moveTo(offX + x * celda, offY);
      ctx.lineTo(offX + x * celda, offY + alto * celda); ctx.stroke();
    }
    for (let y = 0; y <= alto; y += paso) {
      ctx.beginPath(); ctx.moveTo(offX, offY + y * celda);
      ctx.lineTo(offX + ancho * celda, offY + y * celda); ctx.stroke();
    }
    ctx.strokeStyle = 'rgba(217,164,65,.25)';
    ctx.strokeRect(offX, offY, ancho * celda, alto * celda);

    const tam = Math.max(4, Math.min(celda * 1.6, 13));
    posiciones = [];

    for (const sitio of datos.sitios) {
      if (sitio.x === null || sitio.y === null) continue;
      const est = estadoEn(sitio.id, anyo);
      if (!est.existe) continue;
      const ruina = est.estado === 'ruinas';
      const capa = ruina ? 'ruinas' : sitio.capa;
      if (!capas.has(capa)) continue;

      const raizPropietario = est.owner !== null && est.owner !== undefined
        ? (colorFaccion.get(est.owner) || null) : null;
      const faccionRaiz = faccionRaizDe(est.owner);
      if (faccionRaiz !== null && faccionesApagadas.has(faccionRaiz)) continue;

      const cx = offX + (sitio.x + 0.5) * celda;
      const cy = offY + (sitio.y + 0.5) * celda;
      const color = ruina ? '#5a534b' : (raizPropietario || capaColor(sitio.capa));

      ctx.fillStyle = color;
      ctx.strokeStyle = 'rgba(0,0,0,.55)';
      ctx.lineWidth = 1;
      forma(ctx, sitio.capa, cx, cy, tam, ruina);
      if (seleccionado === sitio.id) {
        ctx.strokeStyle = '#ffffff';
        ctx.lineWidth = 2;
        ctx.beginPath();
        ctx.arc(cx, cy, tam * 0.95, 0, Math.PI * 2);
        ctx.stroke();
      }
      posiciones.push({ tipo: 'sitio', sitio, cx, cy, r: tam, estado: est });
    }

    /* bestias vivas encima */
    const sitiosPorId = new Map(datos.sitios.map((s) => [s.id, s]));
    for (const { bestia, site_id } of bestiasEn(anyo)) {
      const sitio = sitiosPorId.get(site_id);
      if (!sitio || sitio.x === null) continue;
      const cx = offX + (sitio.x + 0.5) * celda;
      const cy = offY + (sitio.y + 0.5) * celda - tam * 0.9;
      ctx.fillStyle = '#e0b055';
      ctx.strokeStyle = '#2b220f';
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(cx, cy - tam * 0.6);
      ctx.lineTo(cx + tam * 0.55, cy + tam * 0.45);
      ctx.lineTo(cx - tam * 0.55, cy + tam * 0.45);
      ctx.closePath(); ctx.fill(); ctx.stroke();
      posiciones.push({ tipo: 'bestia', bestia, cx, cy, r: tam * 0.7 });
    }

    document.getElementById('anyo-txt').textContent = anyo;
    const visibles = posiciones.filter((p) => p.tipo === 'sitio').length;
    document.getElementById('nota-mapa').textContent =
      `Mundo de ${ancho}x${alto} casillas deducido de las coordenadas. ` +
      `${visibles} sitios visibles en el anyo ${anyo} de ${datos.sitios.length} en total.`;
    const nBestias = posiciones.filter((p) => p.tipo === 'bestia').length;
    document.getElementById('nota-bestias').textContent = datos.bestias.length
      ? `${nBestias} con paradero conocido en el anyo ${anyo} (de ${datos.bestias.length} registradas).`
      : 'Este export no registra bestias con paradero conocido.';
  }

  function faccionRaizDe(entityId) {
    if (entityId === null || entityId === undefined || !datos) return null;
    const f = datos.facciones.find((x) => x.id === entityId);
    return f ? f.raiz : null;
  }

  const capaColor = (capa) => (CAPAS.find((c) => c.id === capa) || {}).color || '#8a8f98';

  function forma(ctx, capa, cx, cy, tam, ruina) {
    ctx.beginPath();
    if (ruina) {
      ctx.rect(cx - tam / 2, cy - tam / 2, tam, tam);
      ctx.fill();
      ctx.strokeStyle = 'rgba(255,255,255,.35)';
      ctx.beginPath();
      ctx.moveTo(cx - tam / 2, cy - tam / 2); ctx.lineTo(cx + tam / 2, cy + tam / 2);
      ctx.moveTo(cx + tam / 2, cy - tam / 2); ctx.lineTo(cx - tam / 2, cy + tam / 2);
      ctx.stroke();
      return;
    }
    if (capa === 'torre' || capa === 'boveda') {
      ctx.moveTo(cx, cy - tam * 0.62);
      ctx.lineTo(cx + tam * 0.62, cy);
      ctx.lineTo(cx, cy + tam * 0.62);
      ctx.lineTo(cx - tam * 0.62, cy);
      ctx.closePath();
    } else if (capa === 'guarida' || capa === 'cueva' || capa === 'tumba') {
      ctx.arc(cx, cy, tam * 0.5, 0, Math.PI * 2);
    } else {
      ctx.rect(cx - tam / 2, cy - tam / 2, tam, tam);
    }
    ctx.fill();
    ctx.stroke();
  }

  /* ---------------------------------------------------------------- raton */
  function bajoElRaton(evento) {
    const c = lienzo();
    const caja = c.getBoundingClientRect();
    const escala = (window.devicePixelRatio || 1);
    const x = (evento.clientX - caja.left) * (c.width / caja.width);
    const y = (evento.clientY - caja.top) * (c.height / caja.height);
    let mejor = null, mejorD = Infinity;
    for (const p of posiciones) {
      const d = Math.hypot(p.cx - x, p.cy - y);
      const radio = Math.max(p.r, 7 * escala);
      if (d < radio && d < mejorD) { mejor = p; mejorD = d; }
    }
    return mejor;
  }

  function mover(evento) {
    const objetivo = bajoElRaton(evento);
    const pista = document.getElementById('pista');
    if (!objetivo) { pista.classList.add('oculta'); return; }
    const caja = lienzo().getBoundingClientRect();
    if (objetivo.tipo === 'bestia') {
      const b = objetivo.bestia;
      pista.innerHTML = `<b>${escapar(b.nombre)}</b><br>${escapar(b.tipo || '')}` +
        `${b.raza ? ' · ' + escapar(b.raza) : ''}`;
    } else {
      const s = objetivo.sitio;
      const est = objetivo.estado;
      const f = datos.facciones.find((x) => x.id === est.owner);
      pista.innerHTML = `<b>${escapar(s.nombre || 'sin nombre')}</b><br>` +
        `${escapar(s.tipo || '')} · (${s.x},${s.y})<br>` +
        (est.estado === 'ruinas'
          ? 'En ruinas'
          : (f ? escapar(f.nombre) : 'Propietario desconocido'));
    }
    pista.classList.remove('oculta');
    const px = evento.clientX - caja.left + 14;
    const py = evento.clientY - caja.top + 14;
    pista.style.left = Math.min(px, caja.width - 270) + 'px';
    pista.style.top = Math.min(py, caja.height - 70) + 'px';
  }

  const escapar = (t) => String(t == null ? '' : t)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');

  async function pinchar(evento) {
    const objetivo = bajoElRaton(evento);
    if (!objetivo) return;
    if (objetivo.tipo === 'bestia') {
      App.irAFigura(objetivo.bestia.hf_id);
      return;
    }
    seleccionado = objetivo.sitio.id;
    dibujar();
    await abrirSitio(objetivo.sitio.id);
  }

  async function abrirSitio(siteId) {
    const panel = document.getElementById('panel-sitio');
    UI.poner(panel, UI.el('p', { class: 'vacio', text: 'Cargando ficha...' }));
    try {
      const s = await API.sitio(App.exportId(), siteId);
      seleccionado = siteId;
      UI.poner(panel, ficha(s));
      dibujar();
    } catch (e) { UI.fallo(e); }
  }

  function ficha(s) {
    const el = UI.el;
    const propietarios = s.propietarios.length
      ? UI.tabla(['Anyo', 'Propietario', 'Estado'], s.propietarios.map((p) => [
          String(p.anyo),
          p.entidad
            ? el('span', { class: 'enlace', text: p.entidad, onclick: () => App.verEntidad(p.entidad_id) })
            : (p.estado === 'ruinas' ? 'sin duenyo' : '?'),
          p.estado + (p.origen === 'inicial' ? ' (dato del export, sin evento)' : ''),
        ]))
      : el('p', { class: 'nota', text: 'El archivo no registra ningun cambio de propiedad de este sitio.' });

    return el('div', {}, [
      el('div', { class: 'ficha-cabecera' }, [
        el('h3', { text: s.nombre || 'Sin nombre' }),
        el('div', { class: 'tipo', text: `${s.tipo || 'tipo desconocido'} · (${s.coordenadas.x}, ${s.coordenadas.y})` }),
      ]),
      UI.datos([
        ['Estado', s.estado],
        ['Fundado', s.fundado === null ? null : `anyo ${s.fundado}`],
        ['Propietario', s.propietario.nombre
          ? el('span', { class: 'enlace', text: s.propietario.nombre, onclick: () => App.verEntidad(s.propietario.id) })
          : null],
        ['Civilizacion', s.civilizacion
          ? el('span', { class: 'enlace', text: s.civilizacion.nombre, onclick: () => App.verEntidad(s.civilizacion.id) })
          : null],
      ]),
      UI.bloque('Propietarios a lo largo del tiempo', propietarios),
      s.estructuras.length ? UI.bloque('Estructuras',
        el('div', { class: 'chips' }, s.estructuras.map((e) =>
          el('span', { class: 'chip', text: `${e.name || e.type || '?'}${e.type && e.name ? ' (' + e.type + ')' : ''}` })))) : null,
      s.artefactos.length ? UI.bloque('Artefactos aqui',
        el('div', { class: 'chips' }, s.artefactos.map((a) => el('span', { class: 'chip', text: a.name })))) : null,
      s.habitantes.length ? UI.bloque(`Figuras vinculadas (${s.habitantes.length})`,
        UI.tabla(['Nombre', 'Raza', 'Vinculo'], s.habitantes.slice(0, 80).map((h) => [
          el('span', { class: 'enlace', text: h.name || '?', onclick: () => App.irAFigura(h.hf_id) }),
          h.race || '—', (h.link_type || '') + (h.alive ? '' : ' (fallecida)'),
        ]))) : null,
      s.eventos.length ? UI.bloque(`Eventos ocurridos aqui (${s.eventos.length}${s.eventos_truncados ? '+' : ''})`,
        UI.tabla(['Anyo', 'Suceso', 'Detalles'], s.eventos.map((ev) => [
          String(UI.anyo(ev.anyo)), UI.tipoLegible(ev.tipo),
          el('span', { class: 'nota', text: [ev.hf, ev.asesino ? '→ ' + ev.asesino : '', UI.detallesTexto(ev.detalles)].filter(Boolean).join(' · ') }),
        ]))) : el('p', { class: 'nota', text: 'No hay eventos registrados en este sitio.' }),
    ]);
  }

  /* ------------------------------------------------------------ controles */
  function conectar() {
    const rango = document.getElementById('anyo');
    rango.addEventListener('input', () => { anyo = Number(rango.value); dibujar(); });
    document.getElementById('btn-fin').addEventListener('click', () => {
      rango.value = rango.max; anyo = Number(rango.max); dibujar();
    });
    document.getElementById('btn-play').addEventListener('click', reproducir);
    document.getElementById('capa-bestias').addEventListener('change', (e) => {
      verBestias = e.target.checked; dibujar();
    });
    const c = lienzo();
    c.addEventListener('mousemove', mover);
    c.addEventListener('mouseleave', () => document.getElementById('pista').classList.add('oculta'));
    c.addEventListener('click', pinchar);
    window.addEventListener('resize', () => { ajustarLienzo(); dibujar(); });
  }

  function reproducir() {
    const boton = document.getElementById('btn-play');
    const rango = document.getElementById('anyo');
    if (reproduciendo) {
      clearInterval(reproduciendo); reproduciendo = null; boton.innerHTML = '&#9654;';
      return;
    }
    if (Number(rango.value) >= Number(rango.max)) rango.value = rango.min;
    boton.innerHTML = '&#9632;';
    const total = Number(rango.max) - Number(rango.min);
    const paso = Math.max(1, Math.round(total / 160));
    reproduciendo = setInterval(() => {
      const siguiente = Number(rango.value) + paso;
      if (siguiente >= Number(rango.max)) {
        rango.value = rango.max; anyo = Number(rango.max); dibujar();
        clearInterval(reproduciendo); reproduciendo = null; boton.innerHTML = '&#9654;';
        return;
      }
      rango.value = siguiente; anyo = siguiente; dibujar();
    }, 70);
  }

  function redibujar() { ajustarLienzo(); dibujar(); }

  return { cargar, conectar, redibujar, abrirSitio };
})();
