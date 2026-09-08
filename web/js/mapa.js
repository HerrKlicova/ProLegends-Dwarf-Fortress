/* Mapa interactivo del mundo con deslizador de anyo.
   Todo el estado historico llega de una vez desde /api/exports/{id}/mapa, asi
   que mover el deslizador no hace ninguna peticion al servidor. */
const Mapa = (() => {

  const CAPAS = [
    { id: 'asentamiento', nombre: 'Asentamientos', color: '#c9b28a' },
    { id: 'ruinas',       nombre: 'Ruinas',        color: '#6b625a' },
    { id: 'guarida',      nombre: 'Guaridas de bestias', color: '#b4573c' },
    { id: 'torre',        nombre: 'Torres y nigromantes', color: '#7d5ba6' },
    { id: 'boveda',       nombre: 'Bóvedas y sitios misteriosos', color: '#d9c74a' },
    { id: 'cueva',        nombre: 'Cuevas', color: '#7a6a52' },
    { id: 'tumba',        nombre: 'Tumbas', color: '#8a8f98' },
  ];

  let datos = null;
  let anyo = 0;
  let capas = new Set(CAPAS.map((c) => c.id));
  let faccionesApagadas = new Set();
  let verBestias = true;
  let historia = new Map();     // site_id -> [[anyo, propietario, estado], ...]
  let colorFaccion = new Map(); // entity_id -> color de su civilizacion raíz
  let raizDe = new Map();       // entity_id -> id de su civilizacion raíz
  let faccionPorId = new Map(); // entity_id -> faccion
  let posiciones = [];          // cache de lo dibujado, para el raton
  let reproduciendo = null;
  let seleccionado = null;
  // Zoom y desplazamiento. escala 1 = el mundo entero cabe en pantalla.
  let vista = { escala: 1, x: 0, y: 0 };
  let arrastre = null;

  const lienzo = () => document.getElementById('lienzo');

  async function cargar(exportId) {
    datos = await API.mapa(exportId);
    // La geografia va aparte porque no cambia con el anyo: se pide una vez.
    try {
      Atlas.preparar(await API.terreno(exportId));
    } catch (e) {
      Atlas.preparar(null);
      console.warn('No se ha podido cargar el terreno', e);
    }
    historia = new Map();
    for (const [sid, y, owner, estado] of datos.propiedad) {
      if (!historia.has(sid)) historia.set(sid, []);
      historia.get(sid).push([y, owner, estado]);
    }
    for (const lista of historia.values()) lista.sort((a, b) => a[0] - b[0]);

    // Indices previos: dentro del bucle de dibujado no puede haber busquedas
    // lineales, o con un mundo de miles de sitios el deslizador se arrastra.
    faccionPorId = new Map(datos.facciones.map((f) => [f.id, f]));
    colorFaccion = new Map();
    raizDe = new Map();
    for (const f of datos.facciones) {
      const raiz = faccionPorId.get(f.raiz);
      colorFaccion.set(f.id, (raiz || f).color);
      raizDe.set(f.id, f.raiz);
    }

    const min = datos.export.anyo_min ?? 0;
    const max = Math.max(datos.export.anyo_max ?? 0, datos.export.fecha_partida ?? 0, min);
    const rango = document.getElementById('anyo');
    rango.min = min; rango.max = max; rango.value = max;
    anyo = max;
    faccionesApagadas = new Set();
    seleccionado = null;
    vista = { escala: 1, x: 0, y: 0 };

    pintarCapas();
    pintarTerreno();
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

  /* Qué terreno hay en este mundo y con qué color se ha pintado. Los nombres
     son los que trae el export, sin traducir ni maquillar. */
  function pintarTerreno() {
    const caja = document.getElementById('leyenda-terreno');
    if (!caja) return;
    const lista = Atlas.hayMapa() ? Atlas.terrenos() : [];
    if (!lista.length) {
      UI.poner(caja, UI.el('p', { class: 'nota', text: Atlas.hayMapa()
        ? 'Sin terreno reconocible.'
        : 'Este export no trae la geografía del mundo.' }));
      return;
    }
    const total = lista.reduce((n, t) => n + t.casillas, 0) || 1;
    UI.poner(caja, ...lista.map((t) => UI.el('div', { class: 'fila' }, [
      UI.el('span', { class: 'pastilla', style: `background:${t.color}` }),
      UI.el('span', { class: 'nombre-faccion' }, [
        UI.el('span', { class: 'linea1', text: t.nombre }),
        t.conocido ? null : UI.el('span', { class: 'linea2', text: 'sin dibujo propio' }),
      ]),
      UI.el('span', { class: 'conteo', text: `${Math.round(t.casillas * 100 / total)}%` }),
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
    // Puede haber varias civilizaciones de la misma raza, así que cada una se
    // identifica por su nombre propio y la raza queda debajo, más apagada.
    UI.poner(caja, ...civs.map((f) => UI.el('div', {
      class: 'fila' + (faccionesApagadas.has(f.id) ? ' apagada' : ''),
      title: `${f.nombre}${f.raza ? ' · ' + f.raza : ''} — pulsa para ocultarla del mapa`,
      onclick: () => {
        faccionesApagadas.has(f.id) ? faccionesApagadas.delete(f.id) : faccionesApagadas.add(f.id);
        pintarLeyenda(); dibujar();
      },
    }, [
      UI.el('span', { class: 'pastilla', style: `background:${f.color}` }),
      UI.el('span', { class: 'nombre-faccion' }, [
        UI.el('span', { class: 'linea1', text: f.nombre || f.raza || `entidad ${f.id}` }),
        f.raza ? UI.el('span', { class: 'linea2', text: f.raza }) : null,
      ]),
      UI.el('span', { class: 'conteo', text: String(cuenta.get(f.id) || 0) }),
    ])));
    if (!civs.length) UI.poner(caja, UI.el('p', { class: 'nota', text: 'Este export no trae información de civilizaciones.' }));
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
    /* El tamano del mundo sale de los datos. Cuando hay terreno mandan sus
       coordenadas, que cubren el mundo entero; si no, solo se sabe hasta donde
       llegan los sitios. Las dos capas TIENEN que usar la misma rejilla o los
       pueblos aparecerian flotando fuera de su tierra. */
    const geo = Atlas.hayMapa() ? Atlas.info() : null;
    const ancho = Math.max(1, (geo ? geo.ancho : datos.export.ancho) || 1);
    const alto = Math.max(1, (geo ? geo.alto : datos.export.alto) || 1);
    const minX = geo ? geo.min_x : 0;
    const minY = geo ? geo.min_y : 0;
    const base = Math.min(c.width / ancho, c.height / alto);
    const celda = base * vista.escala;
    const offX = (c.width - celda * ancho) / 2 + vista.x;
    const offY = (c.height - celda * alto) / 2 + vista.y;

    /* El terreno se dibuja una vez y se estampa: mover el deslizador no
       vuelve a pintar la geografia, que no cambia de un anyo a otro. */
    if (Atlas.hayMapa()) {
      ctx.drawImage(Atlas.capa(c.width, c.height, { celda, offX, offY }), 0, 0);
    } else {
      ctx.fillStyle = '#0d0c0a';
      ctx.fillRect(0, 0, c.width, c.height);
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
    }

    // Sobre pergamino los sellos van algo mas discretos: manda el mapa.
    // El sello tiene que caber en su casilla: si no, con un mundo poblado se
    // pisan unos a otros y no se ve el mapa que hay debajo.
    const tam = Atlas.hayMapa()
      ? Math.max(4, Math.min(celda * 0.72, 20))
      : Math.max(4, Math.min(celda * 1.6, 13));
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

      const cx = offX + (sitio.x - minX + 0.5) * celda;
      const cy = offY + (sitio.y - minY + 0.5) * celda;
      const color = ruina ? '#5a534b' : (raizPropietario || capaColor(sitio.capa));

      ctx.fillStyle = color;
      ctx.strokeStyle = 'rgba(0,0,0,.55)';
      ctx.lineWidth = 1;
      forma(ctx, sitio.capa, cx, cy, tam, ruina);
      if (seleccionado === sitio.id) {
        ctx.strokeStyle = Atlas.hayMapa() ? '#a8391f' : '#ffffff';
        ctx.lineWidth = 2;
        ctx.beginPath();
        ctx.arc(cx, cy, tam * 1.05, 0, Math.PI * 2);
        ctx.stroke();
      }
      posiciones.push({ tipo: 'sitio', sitio, cx, cy, r: tam, estado: est });
    }

    /* bestias vivas encima */
    const sitiosPorId = new Map(datos.sitios.map((s) => [s.id, s]));
    for (const { bestia, site_id } of bestiasEn(anyo)) {
      const sitio = sitiosPorId.get(site_id);
      if (!sitio || sitio.x === null) continue;
      const cx = offX + (sitio.x - minX + 0.5) * celda;
      const cy = offY + (sitio.y - minY + 0.5) * celda - tam * 0.9;
      const garra = () => {
        ctx.beginPath();
        ctx.moveTo(cx, cy - tam * 0.6);
        ctx.lineTo(cx + tam * 0.55, cy + tam * 0.45);
        ctx.lineTo(cx - tam * 0.55, cy + tam * 0.45);
        ctx.closePath();
      };
      if (Atlas.hayMapa()) {
        ctx.strokeStyle = 'rgba(233,220,190,.9)';
        ctx.lineWidth = Math.max(2.5, tam * 0.45);
        garra(); ctx.stroke();
      }
      ctx.fillStyle = '#c8553d';
      ctx.strokeStyle = '#3f3527';
      ctx.lineWidth = 1;
      garra(); ctx.fill(); ctx.stroke();
      posiciones.push({ tipo: 'bestia', bestia, cx, cy, r: tam * 0.7 });
    }

    if (Atlas.hayMapa()) {
      etiquetas(ctx, celda);
      cartela(ctx, offX, offY);
    }

    document.getElementById('anyo-txt').textContent = anyo;
    const visibles = posiciones.filter((p) => p.tipo === 'sitio').length;
    document.getElementById('nota-mapa').textContent =
      `Mundo de ${ancho}x${alto} casillas deducido de las coordenadas. ` +
      `${visibles} sitios visibles en el año ${anyo} de ${datos.sitios.length} en total.` +
      (vista.escala > 1.01 ? `  ·  ampliado ${vista.escala.toFixed(1)}x` : '') +
      (Atlas.hayMapa()
        ? '  ·  rueda para acercar, arrastra para mover, doble clic para encajarlo.'
          + (Atlas.desconocidos().length
              ? `  ·  sin dibujo propio todavía: ${Atlas.desconocidos().join(', ')}`
              : '')
        : '  ·  ' + (Atlas.motivo() || ''));
    const nBestias = posiciones.filter((p) => p.tipo === 'bestia').length;
    document.getElementById('nota-bestias').textContent = datos.bestias.length
      ? `${nBestias} con paradero conocido en el año ${anyo} (de ${datos.bestias.length} registradas).`
      : 'Este export no registra bestias con paradero conocido.';
  }

  /* La cartela del atlas: como se llama el mundo y en que anyo lo estamos
     mirando. Va fuera del terreno cacheado porque el anyo si cambia. */
  function cartela(ctx, offX, offY) {
    const mundo = App.mundoActual();
    if (!mundo) return;
    const titulo = String(mundo.nombre || '').toUpperCase();
    const sub = mundo.altnombre || '';
    const pie = `Año ${anyo}`;

    ctx.save();
    ctx.textBaseline = 'top';
    ctx.textAlign = 'left';
    ctx.font = '600 15px Georgia, "Times New Roman", serif';
    const anchoTitulo = ctx.measureText(titulo).width;
    ctx.font = 'italic 11px Georgia, "Times New Roman", serif';
    const anchoSub = ctx.measureText(sub).width;
    const w = Math.min(320, Math.max(anchoTitulo, anchoSub, 90) + 26);
    const h = sub ? 62 : 48;
    const x = offX + 14, y = offY + 14;

    ctx.fillStyle = 'rgba(233,220,190,.93)';
    ctx.strokeStyle = '#4a3b28';
    ctx.lineWidth = 1.5;
    ctx.beginPath();
    ctx.rect(x, y, w, h);
    ctx.fill(); ctx.stroke();
    ctx.lineWidth = 0.8;
    ctx.strokeRect(x + 4, y + 4, w - 8, h - 8);

    ctx.fillStyle = '#3f3527';
    ctx.font = '600 15px Georgia, "Times New Roman", serif';
    ctx.fillText(titulo, x + 13, y + 12, w - 26);
    if (sub) {
      ctx.fillStyle = '#6b5c45';
      ctx.font = 'italic 11px Georgia, "Times New Roman", serif';
      ctx.fillText(sub, x + 13, y + 32, w - 26);
    }
    ctx.fillStyle = '#8a5a2b';
    ctx.font = '600 12px Georgia, "Times New Roman", serif';
    ctx.fillText(pie, x + 13, y + h - 20);
    ctx.restore();
  }

  /* Nombres sobre el mapa. Aparecen segun se amplia y se apartan entre ellos:
     mas vale no poner una etiqueta que amontonarlas y no leer ninguna. */
  function etiquetas(ctx, celda) {
    // Hace falta sitio de verdad para que un nombre se lea. Por debajo de esto
    // saldrian amontonados y no se entenderia ninguno: mejor acercarse.
    if (celda < 22) return;
    const cuerpo = Math.max(10, Math.min(celda * 0.34, 15));
    ctx.font = `${cuerpo}px Georgia, "Times New Roman", serif`;
    ctx.textAlign = 'center';
    ctx.textBaseline = 'bottom';
    ctx.lineJoin = 'round';

    // Primero los sitios grandes: si hay que renunciar a alguno, que sea a
    // una cueva perdida y no a una capital.
    const orden = { asentamiento: 0, torre: 1, boveda: 1, tumba: 2, guarida: 3, cueva: 3 };
    const candidatos = posiciones
      .filter((p) => p.tipo === 'sitio' && p.sitio.nombre)
      .sort((a, b) => (orden[a.sitio.capa] ?? 4) - (orden[b.sitio.capa] ?? 4));

    const puestas = [];
    const choca = (c) => puestas.some((o) =>
      c.x1 < o.x2 && c.x2 > o.x1 && c.y1 < o.y2 && c.y2 > o.y1);

    let escritas = 0;
    for (const p of candidatos) {
      if (escritas > 220) break;
      const texto = p.sitio.nombre;
      const w = ctx.measureText(texto).width;
      const cy = p.cy - p.r * 0.8 - 2;
      const caja = { x1: p.cx - w / 2 - 2, x2: p.cx + w / 2 + 2,
                     y1: cy - cuerpo - 1, y2: cy + 2 };
      if (choca(caja)) continue;
      puestas.push(caja);
      escritas++;
      ctx.strokeStyle = 'rgba(233,220,190,.88)';
      ctx.lineWidth = 3;
      ctx.strokeText(texto, p.cx, cy);
      ctx.fillStyle = '#3f3527';
      ctx.fillText(texto, p.cx, cy);
    }
  }

  function faccionRaizDe(entityId) {
    if (entityId === null || entityId === undefined) return null;
    const raiz = raizDe.get(entityId);
    return raiz === undefined ? null : raiz;
  }

  const capaColor = (capa) => (CAPAS.find((c) => c.id === capa) || {}).color || '#8a8f98';

  /* Silueta de cada clase de sitio. Se dibuja como un sello de tinta: primero
     un halo del color del papel, para que se lea sobre cualquier terreno, y
     encima el relleno de su faccion perfilado en tinta. */
  function trazo(ctx, capa, cx, cy, tam) {
    ctx.beginPath();
    if (capa === 'torre' || capa === 'boveda') {
      ctx.moveTo(cx, cy - tam * 0.72);
      ctx.lineTo(cx + tam * 0.44, cy - tam * 0.1);
      ctx.lineTo(cx + tam * 0.44, cy + tam * 0.6);
      ctx.lineTo(cx - tam * 0.44, cy + tam * 0.6);
      ctx.lineTo(cx - tam * 0.44, cy - tam * 0.1);
      ctx.closePath();
    } else if (capa === 'guarida') {
      // Una boca de cueva: medio circulo apoyado en el suelo.
      ctx.moveTo(cx - tam * 0.55, cy + tam * 0.5);
      ctx.arc(cx, cy + tam * 0.5, tam * 0.55, Math.PI, 0);
      ctx.closePath();
    } else if (capa === 'cueva') {
      ctx.arc(cx, cy, tam * 0.48, 0, Math.PI * 2);
    } else if (capa === 'tumba') {
      ctx.moveTo(cx - tam * 0.38, cy + tam * 0.55);
      ctx.lineTo(cx - tam * 0.38, cy - tam * 0.1);
      ctx.arc(cx, cy - tam * 0.1, tam * 0.38, Math.PI, 0);
      ctx.lineTo(cx + tam * 0.38, cy + tam * 0.55);
      ctx.closePath();
    } else {
      // Asentamiento: casita con tejado.
      ctx.moveTo(cx, cy - tam * 0.7);
      ctx.lineTo(cx + tam * 0.6, cy - tam * 0.12);
      ctx.lineTo(cx + tam * 0.44, cy - tam * 0.12);
      ctx.lineTo(cx + tam * 0.44, cy + tam * 0.58);
      ctx.lineTo(cx - tam * 0.44, cy + tam * 0.58);
      ctx.lineTo(cx - tam * 0.44, cy - tam * 0.12);
      ctx.lineTo(cx - tam * 0.6, cy - tam * 0.12);
      ctx.closePath();
    }
  }

  function forma(ctx, capa, cx, cy, tam, ruina) {
    const papel = Atlas.hayMapa();
    const relleno = ctx.fillStyle;

    if (ruina) {
      // Una ruina es una silueta rota: dos muros de pie y nada mas.
      if (papel) {
        ctx.strokeStyle = 'rgba(233,220,190,.9)';
        ctx.lineWidth = Math.max(2, tam * 0.3);
        muro(ctx, cx, cy, tam); ctx.stroke();
      }
      ctx.strokeStyle = papel ? '#5b5048' : 'rgba(255,255,255,.45)';
      ctx.lineWidth = Math.max(1.2, tam * 0.16);
      muro(ctx, cx, cy, tam); ctx.stroke();
      return;
    }

    if (papel) {
      ctx.strokeStyle = 'rgba(233,220,190,.92)';
      ctx.lineWidth = Math.max(2, tam * 0.3);
      ctx.lineJoin = 'round';
      trazo(ctx, capa, cx, cy, tam); ctx.stroke();
    }
    ctx.fillStyle = relleno;
    ctx.strokeStyle = papel ? '#3f3527' : 'rgba(0,0,0,.55)';
    ctx.lineWidth = papel ? Math.max(1, tam * 0.13) : 1;
    trazo(ctx, capa, cx, cy, tam);
    ctx.fill();
    ctx.stroke();
  }

  function muro(ctx, cx, cy, tam) {
    ctx.beginPath();
    ctx.moveTo(cx - tam * 0.45, cy + tam * 0.5);
    ctx.lineTo(cx - tam * 0.45, cy - tam * 0.2);
    ctx.lineTo(cx - tam * 0.1, cy - tam * 0.2);
    ctx.moveTo(cx + tam * 0.15, cy + tam * 0.5);
    ctx.lineTo(cx + tam * 0.45, cy + tam * 0.5);
    ctx.lineTo(cx + tam * 0.45, cy + tam * 0.05);
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
    if (arrastre) {
      if (arrastre.soltado) { arrastre = null; }
      else if (evento.buttons & 1) {
        const [px, py] = enPixeles(evento);
        arrastre.movido = Math.max(arrastre.movido,
                                   Math.abs(px - arrastre.px) + Math.abs(py - arrastre.py));
        vista.x = arrastre.x0 + (px - arrastre.px);
        vista.y = arrastre.y0 + (py - arrastre.py);
        ajustarVista();
        document.getElementById('pista').classList.add('oculta');
        dibujar();
        return;
      } else {
        arrastre = null;
      }
    }
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
      const f = faccionPorId.get(est.owner);
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
    // Soltar tras arrastrar no es pinchar en un sitio.
    if (arrastre && arrastre.movido > 4) { arrastre = null; return; }
    arrastre = null;
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
      ? UI.tabla(['Año', 'Propietario', 'Estado'], s.propietarios.map((p) => [
          String(p.anyo),
          p.entidad
            ? el('span', { class: 'enlace', text: p.entidad, onclick: () => App.verEntidad(p.entidad_id) })
            : (p.estado === 'ruinas' ? 'sin dueño' : '?'),
          p.estado + (p.origen === 'inicial' ? ' (dato del export, sin evento)' : ''),
        ]))
      : el('p', { class: 'nota', text: 'El archivo no registra ningún cambio de propiedad de este sitio.' });

    return el('div', {}, [
      el('div', { class: 'ficha-cabecera' }, [
        el('h3', { text: s.nombre || 'Sin nombre' }),
        el('div', { class: 'tipo', text: `${s.tipo || 'tipo desconocido'} · (${s.coordenadas.x}, ${s.coordenadas.y})` }),
      ]),
      UI.datos([
        ['Estado', s.estado],
        ['Fundado', s.fundado === null ? null : `año ${s.fundado}`],
        ['Propietario', s.propietario.nombre
          ? el('span', { class: 'enlace', text: s.propietario.nombre, onclick: () => App.verEntidad(s.propietario.id) })
          : null],
        ['Civilización', s.civilizacion
          ? el('span', { class: 'enlace', text: s.civilizacion.nombre, onclick: () => App.verEntidad(s.civilizacion.id) })
          : null],
      ]),
      UI.bloque('Propietarios a lo largo del tiempo', propietarios),
      s.estructuras.length ? UI.bloque('Estructuras',
        el('div', { class: 'chips' }, s.estructuras.map((e) =>
          el('span', { class: 'chip', text: `${e.name || e.type || '?'}${e.type && e.name ? ' (' + e.type + ')' : ''}` })))) : null,
      s.artefactos.length ? UI.bloque('Artefactos aquí',
        el('div', { class: 'chips' }, s.artefactos.map((a) => el('span', { class: 'chip', text: a.name })))) : null,
      s.habitantes.length ? UI.bloque(`Figuras vinculadas (${s.habitantes.length})`,
        UI.tabla(['Nombre', 'Raza', 'Vínculo'], s.habitantes.slice(0, 80).map((h) => [
          el('span', { class: 'enlace', text: h.name || '?', onclick: () => App.irAFigura(h.hf_id) }),
          h.race || '—', (h.link_type || '') + (h.alive ? '' : ' (fallecida)'),
        ]))) : null,
      s.eventos.length ? UI.bloque(`Eventos ocurridos aquí (${s.eventos.length}${s.eventos_truncados ? '+' : ''})`,
        UI.tabla(['Año', 'Suceso', 'Detalles'], s.eventos.map((ev) => [
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
    c.addEventListener('mouseleave', () => {
      document.getElementById('pista').classList.add('oculta');
      arrastre = null;
    });
    c.addEventListener('click', pinchar);
    c.addEventListener('wheel', rueda, { passive: false });
    c.addEventListener('mousedown', empezarArrastre);
    window.addEventListener('mouseup', () => { if (arrastre) arrastre.soltado = true; });
    c.addEventListener('dblclick', encajar);
    window.addEventListener('resize', () => { ajustarLienzo(); dibujar(); });
  }

  /* ------------------------------------------------------ zoom y arrastre */
  function enPixeles(evento) {
    const c = lienzo();
    const caja = c.getBoundingClientRect();
    return [(evento.clientX - caja.left) * (c.width / caja.width),
            (evento.clientY - caja.top) * (c.height / caja.height)];
  }

  function rueda(evento) {
    if (!datos) return;
    evento.preventDefault();
    const [px, py] = enPixeles(evento);
    const antes = vista.escala;
    const factor = Math.exp(-evento.deltaY * 0.0016);
    vista.escala = Math.min(9, Math.max(1, antes * factor));
    if (vista.escala === antes) return;
    // El punto que hay bajo el cursor se queda donde está: se amplía hacia
    // donde estás mirando, no hacia el centro.
    const c = lienzo();
    const k = vista.escala / antes;
    vista.x = px - (px - (vista.x + c.width / 2)) * k - c.width / 2;
    vista.y = py - (py - (vista.y + c.height / 2)) * k - c.height / 2;
    ajustarVista();
    dibujar();
  }

  function empezarArrastre(evento) {
    if (!datos || evento.button !== 0) return;
    const [px, py] = enPixeles(evento);
    arrastre = { px, py, x0: vista.x, y0: vista.y, movido: 0, soltado: false };
  }

  /* No dejar que el mundo se escape de la ventana. */
  function ajustarVista() {
    const c = lienzo();
    const margen = Math.min(c.width, c.height) * 0.35;
    const limX = Math.max(0, (c.width * vista.escala - c.width) / 2) + margen;
    const limY = Math.max(0, (c.height * vista.escala - c.height) / 2) + margen;
    vista.x = Math.max(-limX, Math.min(limX, vista.x));
    vista.y = Math.max(-limY, Math.min(limY, vista.y));
    if (vista.escala <= 1.001) { vista.x = 0; vista.y = 0; }
  }

  function encajar() {
    vista = { escala: 1, x: 0, y: 0 };
    dibujar();
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
