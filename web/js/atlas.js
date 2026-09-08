/* El mapa dibujado: pergamino, costas, biomas, ríos y calzadas.

   Todo esto sale de los datos del export (las regiones traen la lista de
   casillas que ocupan), así que no hace falta ninguna imagen del juego.

   Se dibuja UNA vez en un lienzo aparte y luego se estampa en cada fotograma:
   mover el deslizador de año no vuelve a pintar la geografía, que no cambia,
   solo los sitios y sus dueños. */
const Atlas = (() => {

  /* Paleta de atlas: tintas y tierras sobre papel, no colores de pantalla. */
  const ALFABETO = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/';

  const PAPEL       = '#e9dcbe';
  const PAPEL_OSCURO= '#dccca6';
  const TINTA       = '#4a3b28';
  const TINTA_SUAVE = 'rgba(74,59,40,.45)';
  const MAR         = '#b9cdd8';
  const MAR_TINTA   = '#7d9db0';
  const RIO         = '#6d93ab';

  /* Cada bioma, su color de papel y su motivo. Los nombres son los que usa
     Dwarf Fortress; se comparan en minúsculas y por si acaso por trozos, que
     hay versiones que escriben "Temperate Forest" o "Tropical Grassland". */
  const BIOMAS = [
    { clave: 'glacier',   color: '#eef2f4', motivo: 'hielo'    },
    { clave: 'tundra',    color: '#d5dbcd', motivo: 'puntitos' },
    { clave: 'mountain',  color: '#bdb09a', motivo: 'montanya' },
    { clave: 'hill',      color: '#c9bd8f', motivo: 'loma'     },
    { clave: 'jungle',    color: '#83a259', motivo: 'selva'    },
    { clave: 'forest',    color: '#9cb26e', motivo: 'bosque'   },
    { clave: 'wetland',   color: '#adbd8a', motivo: 'junco'    },
    { clave: 'marsh',     color: '#adbd8a', motivo: 'junco'    },
    { clave: 'swamp',     color: '#a3b47e', motivo: 'junco'    },
    { clave: 'grassland', color: '#c8ce8c', motivo: 'hierba'   },
    { clave: 'savanna',   color: '#dbcf8d', motivo: 'hierba'   },
    { clave: 'steppe',    color: '#d8cd93', motivo: 'mata'     },
    { clave: 'shrubland', color: '#cfc890', motivo: 'mata'     },
    { clave: 'desert',    color: '#eddc96', motivo: 'duna'     },
    { clave: 'badland',   color: '#dcc79a', motivo: 'duna'     },
    { clave: 'lake',      color: '#c2d4dd', motivo: 'agua'     },
    { clave: 'ocean',     color: '#b9cdd8', motivo: 'agua'     },
    { clave: 'sea',       color: '#b9cdd8', motivo: 'agua'     },
  ];
  const TIERRA_DESCONOCIDA = { color: '#d9cca8', motivo: null };

  let datos = null;         // lo que devuelve /terreno
  let clasificado = null;   // por índice de bioma: {agua, color, motivo}
  let cache = null;         // { clave, lienzo }
  let porQueNo = '';        // por qué este export no se puede dibujar
  // Qué capas del terreno se dibujan. Cambiarlas obliga a repintar el mapa.
  const opciones = { rios: true, arroyos: false, construcciones: true, motivos: true };

  function opcion(nombre, valor) {
    if (opciones[nombre] === valor) return;
    opciones[nombre] = valor;
    cache = null;
  }

  function preparar(terreno) {
    datos = terreno && terreno.hay_mapa ? terreno : null;
    porQueNo = (terreno && terreno.motivo) || '';
    cache = null;
    if (!datos) return;
    clasificado = datos.biomas.map(clasificar);
  }

  function clasificar(nombre) {
    const n = String(nombre || '').toLowerCase();
    for (const b of BIOMAS) {
      if (n.includes(b.clave)) {
        return { agua: b.motivo === 'agua', color: b.color, motivo: b.motivo,
                 nombre, conocido: true };
      }
    }
    // No se inventa un dibujo para un terreno que no se sabe qué es: se pinta
    // liso y se dice, que es mejor que fingir que es un bosque.
    return { agua: false, color: TIERRA_DESCONOCIDA.color, motivo: null,
             nombre, conocido: false };
  }

  /* Qué terrenos hay en este mundo y con qué color se han pintado, para poder
     poner una leyenda de verdad al lado del mapa. */
  function terrenos() {
    if (!datos) return [];
    const cuenta = new Map();
    for (const c of datos.rejilla) {
      if (c === '.') continue;
      const i = ALFABETO.indexOf(c);
      if (i >= 0) cuenta.set(i, (cuenta.get(i) || 0) + 1);
    }
    return [...cuenta.entries()]
      .map(([i, n]) => ({ ...clasificado[i], casillas: n }))
      .sort((a, b) => b.casillas - a.casillas);
  }

  const desconocidos = () => terrenos().filter((t) => !t.conocido).map((t) => t.nombre);

  const hayMapa = () => !!datos;
  const info = () => datos;

  /* Ruido estable: la misma casilla sale siempre igual, así el mapa no
     "tiembla" al redibujar. */
  function azar(x, y, sal) {
    let h = (x * 374761393 + y * 668265263 + sal * 1442695040) | 0;
    h = (h ^ (h >>> 13)) * 1274126177;
    return ((h ^ (h >>> 16)) >>> 0) / 4294967296;
  }

  /* --------------------------------------------------- lienzo del terreno */
  function capa(anchoPx, altoPx, geom) {
    const clave = `${anchoPx}x${altoPx}|${geom.celda.toFixed(3)}|${geom.offX.toFixed(1)}`
      + `|${opciones.rios}${opciones.arroyos}${opciones.construcciones}${opciones.motivos}`;
    if (cache && cache.clave === clave) return cache.lienzo;
    const lienzo = document.createElement('canvas');
    lienzo.width = anchoPx;
    lienzo.height = altoPx;
    dibujarTerreno(lienzo.getContext('2d'), anchoPx, altoPx, geom);
    cache = { clave, lienzo };
    return lienzo;
  }

  function indice(x, y) {
    const i = y * datos.ancho + x;
    if (datos.rejilla[i] === '.' || datos.rejilla[i] === undefined) return -1;
    return ALFABETO.indexOf(datos.rejilla[i]);
  }

  function dibujarTerreno(ctx, anchoPx, altoPx, geom) {
    const { celda, offX, offY } = geom;
    const ancho = datos.ancho, alto = datos.alto;

    /* Solo se dibuja lo que se ve. Sin esto, ampliar un mundo de 257x257
       obligaria a pintar 66.000 casillas de las que apenas se ven unas pocas. */
    const desde = {
      x: Math.max(0, Math.floor(-offX / celda) - 1),
      y: Math.max(0, Math.floor(-offY / celda) - 1),
      hx: Math.min(ancho, Math.ceil((anchoPx - offX) / celda) + 1),
      hy: Math.min(alto, Math.ceil((altoPx - offY) / celda) + 1),
    };

    papel(ctx, anchoPx, altoPx);

    // Clasificación de cada casilla, una sola vez.
    const tipo = new Int8Array(ancho * alto);      // índice de bioma, -1 si no hay
    const esAgua = new Uint8Array(ancho * alto);
    for (let y = 0; y < alto; y++) {
      for (let x = 0; x < ancho; x++) {
        const i = indice(x, y);
        tipo[y * ancho + x] = i;
        esAgua[y * ancho + x] = (i < 0 || (clasificado[i] && clasificado[i].agua)) ? 1 : 0;
      }
    }

    const px = (x) => offX + x * celda;
    const py = (y) => offY + y * celda;
    /* En un atlas de verdad el grosor de la pluma y el tamano de los simbolos
       no cambian al mirar mas de cerca: lo que cambia es cuanto terreno cabe.
       Por eso el dibujo se acota, aunque la casilla se haga enorme. */
    const pluma = Math.min(celda, 16);

    // 1. El mar, de fondo, en todo el rectángulo del mundo, con las líneas
    //    horizontales de las cartas antiguas.
    ctx.fillStyle = MAR;
    ctx.fillRect(offX, offY, ancho * celda, alto * celda);
    ctx.save();
    ctx.beginPath();
    ctx.rect(offX, offY, ancho * celda, alto * celda);
    ctx.clip();
    ctx.strokeStyle = 'rgba(125,157,176,.22)';
    ctx.lineWidth = 1;
    for (let y = offY; y < offY + alto * celda; y += Math.max(4, celda * 0.62)) {
      ctx.beginPath();
      ctx.moveTo(offX, Math.round(y) + 0.5);
      ctx.lineTo(offX + ancho * celda, Math.round(y) + 0.5);
      ctx.stroke();
    }
    ctx.restore();

    // 2. La orilla: líneas paralelas a la costa, como en las cartas antiguas.
    const orilla = bordes(esAgua, ancho, alto, desde);
    for (let k = 4; k >= 1; k--) {
      ctx.strokeStyle = `rgba(125,157,176,${0.13 + 0.03 * (4 - k)})`;
      ctx.lineWidth = pluma * 0.5 * k;
      ctx.lineJoin = 'round';
      ctx.lineCap = 'round';
      trazar(ctx, orilla, px, py);
    }

    // 3. La tierra, un color por bioma.
    const porTipo = new Map();
    for (let y = desde.y; y < desde.hy; y++) {
      for (let x = desde.x; x < desde.hx; x++) {
        const i = tipo[y * ancho + x];
        if (i < 0 || esAgua[y * ancho + x]) continue;
        if (!porTipo.has(i)) porTipo.set(i, []);
        porTipo.get(i).push([x, y]);
      }
    }
    for (const [i, casillas] of porTipo) {
      ctx.fillStyle = (clasificado[i] || TIERRA_DESCONOCIDA).color;
      ctx.beginPath();
      for (const [x, y] of casillas) {
        // Un pelín más grandes para que no se vean juntas de las casillas.
        ctx.rect(px(x) - 0.4, py(y) - 0.4, celda + 0.8, celda + 0.8);
      }
      ctx.fill();
      // Y una sombra distinta en cada casilla: un terreno pintado a mano no es
      // una plancha de color uniforme.
      for (const [x, y] of casillas) {
        const v = azar(x, y, 21);
        if (v < 0.62) continue;
        ctx.fillStyle = v > 0.84 ? 'rgba(90,75,45,.055)' : 'rgba(255,250,225,.06)';
        ctx.fillRect(px(x) - 0.4, py(y) - 0.4, celda + 0.8, celda + 0.8);
      }
    }

    // 4. Lagos: agua interior, con su propio tono y su borde.
    const lagos = [];
    for (let y = desde.y; y < desde.hy; y++) {
      for (let x = desde.x; x < desde.hx; x++) {
        const i = tipo[y * ancho + x];
        if (i >= 0 && clasificado[i] && clasificado[i].agua
            && String(clasificado[i].nombre).toLowerCase().includes('lake')) {
          lagos.push([x, y]);
        }
      }
    }
    if (lagos.length) {
      ctx.fillStyle = '#bcd2de';
      ctx.beginPath();
      for (const [x, y] of lagos) ctx.rect(px(x) - 0.4, py(y) - 0.4, celda + 0.8, celda + 0.8);
      ctx.fill();
    }

    // 5. Los motivos: montañas dibujadas como montañas, bosques como árboles.
    if (celda >= 5 && opciones.motivos) {
      motivos(ctx, tipo, esAgua, ancho, celda, pluma, px, py, desde);
    }

    // 6. Ríos y calzadas.
    if (opciones.rios) rios(ctx, geom, pluma);
    if (opciones.construcciones) construcciones(ctx, geom, pluma);

    // 7. La línea de costa, en tinta, por encima de todo lo del terreno.
    ctx.strokeStyle = TINTA;
    ctx.lineWidth = Math.max(0.8, pluma * 0.11);
    ctx.lineJoin = 'round';
    ctx.lineCap = 'round';
    trazar(ctx, orilla, px, py);

    // 8. Picos con nombre.
    picos(ctx, geom, pluma);

    // 9. Marco, rosa de los vientos y escala.
    marco(ctx, offX, offY, ancho * celda, alto * celda);
    rosa(ctx, offX + ancho * celda - celda * 3.4, offY + celda * 3.4, celda * 2.3);
    escala(ctx, offX + 16, offY + alto * celda - 34, celda, ancho);
  }

  /* ------------------------------------------------------------- pergamino */
  function papel(ctx, anchoPx, altoPx) {
    ctx.fillStyle = PAPEL;
    ctx.fillRect(0, 0, anchoPx, altoPx);
    // Grano: manchitas sueltas, más densas hacia los bordes.
    for (let i = 0; i < (anchoPx * altoPx) / 900; i++) {
      const x = azar(i, 7, 1) * anchoPx;
      const y = azar(i, 13, 2) * altoPx;
      const a = azar(i, 3, 5);
      ctx.fillStyle = a > 0.5 ? 'rgba(150,125,85,.055)' : 'rgba(255,250,235,.07)';
      ctx.fillRect(x, y, 1 + a * 2.2, 1 + a * 2.2);
    }
    // Sombra de los bordes, como papel viejo.
    const g = ctx.createRadialGradient(
      anchoPx / 2, altoPx / 2, Math.min(anchoPx, altoPx) * 0.32,
      anchoPx / 2, altoPx / 2, Math.max(anchoPx, altoPx) * 0.75);
    g.addColorStop(0, 'rgba(120,95,60,0)');
    g.addColorStop(1, 'rgba(120,95,60,.20)');
    ctx.fillStyle = g;
    ctx.fillRect(0, 0, anchoPx, altoPx);
  }

  /* Los tramos de borde entre agua y tierra: la costa exacta, sin las juntas
     interiores que saldrían al contornear casilla a casilla. */
  function bordes(esAgua, ancho, alto, desde) {
    const tramos = [];
    const agua = (x, y) => (x < 0 || y < 0 || x >= ancho || y >= alto)
      ? 1 : esAgua[y * ancho + x];
    for (let y = desde.y; y < desde.hy; y++) {
      for (let x = desde.x; x < desde.hx; x++) {
        if (esAgua[y * ancho + x]) continue;
        if (agua(x, y - 1)) tramos.push([x, y, x + 1, y]);
        if (agua(x, y + 1)) tramos.push([x, y + 1, x + 1, y + 1]);
        if (agua(x - 1, y)) tramos.push([x, y, x, y + 1]);
        if (agua(x + 1, y)) tramos.push([x + 1, y, x + 1, y + 1]);
      }
    }
    return tramos;
  }

  function trazar(ctx, tramos, px, py) {
    ctx.beginPath();
    for (const [x1, y1, x2, y2] of tramos) {
      ctx.moveTo(px(x1), py(y1));
      ctx.lineTo(px(x2), py(y2));
    }
    ctx.stroke();
  }

  /* ---------------------------------------------------------- los motivos */
  function motivos(ctx, tipo, esAgua, ancho, celda, pluma, px, py, desde) {
    ctx.lineWidth = Math.max(0.6, pluma * 0.07);
    ctx.lineCap = 'round';
    for (let y = desde.y; y < desde.hy; y++) {
      for (let x = desde.x; x < desde.hx; x++) {
        const i = tipo[y * ancho + x];
        if (i < 0 || esAgua[y * ancho + x]) continue;
        const clase = clasificado[i];
        if (!clase || !clase.motivo || clase.motivo === 'agua') continue;
        const cx = px(x) + celda / 2 + (azar(x, y, 1) - 0.5) * pluma * 0.3;
        const cy = py(y) + celda / 2 + (azar(x, y, 2) - 0.5) * pluma * 0.3;
        motivo(ctx, clase.motivo, cx, cy, pluma, x, y);
      }
    }
  }

  function motivo(ctx, cual, cx, cy, pluma, x, y) {
    const r = pluma * 0.34;
    const salta = azar(x, y, 3);
    switch (cual) {
      case 'montanya': {
        // Dos cumbres por casilla, una detrás de otra: se leen como una
        // cordillera en vez de como triángulos sueltos.
        const cumbres = salta > 0.45
          ? [[-r * 0.5, r * 0.16, 0.82], [r * 0.42, 0, 1.0]]
          : [[r * 0.45, r * 0.2, 0.78], [-r * 0.35, 0, 1.0]];
        ctx.strokeStyle = TINTA;
        for (const [dx, dy, escala] of cumbres) {
          const bx = cx + dx, by = cy + dy, br = r * escala;
          ctx.fillStyle = escala < 1 ? '#a2947a' : '#b6a78a';
          ctx.beginPath();
          ctx.moveTo(bx - br * 1.05, by + r * 0.72);
          ctx.lineTo(bx, by - br * 1.0);
          ctx.lineTo(bx + br * 1.05, by + r * 0.72);
          ctx.closePath();
          ctx.fill(); ctx.stroke();
          ctx.fillStyle = 'rgba(74,59,40,.2)';
          ctx.beginPath();
          ctx.moveTo(bx, by - br * 1.0);
          ctx.lineTo(bx + br * 1.05, by + r * 0.72);
          ctx.lineTo(bx + br * 0.12, by + r * 0.72);
          ctx.closePath();
          ctx.fill();
        }
        break;
      }
      case 'loma':
        ctx.strokeStyle = TINTA_SUAVE;
        ctx.beginPath();
        ctx.arc(cx - r * 0.42, cy + r * 0.25, r * 0.52, Math.PI, 0);
        ctx.moveTo(cx + r * 0.1, cy + r * 0.25);
        ctx.arc(cx + r * 0.55, cy + r * 0.25, r * 0.45, Math.PI, 0);
        ctx.stroke();
        break;
      case 'bosque':
      case 'selva': {
        // Un bosque es espeso: tres arbolitos por casilla, de tamaños algo
        // distintos, para que la mancha se vea frondosa y no un sello repetido.
        const cuantos = cual === 'selva' ? 3 : (salta > 0.35 ? 3 : 2);
        ctx.strokeStyle = cual === 'selva' ? '#3f5029' : '#4d5f31';
        for (let k = 0; k < cuantos; k++) {
          const ax = cx + (k - (cuantos - 1) / 2) * r * 0.78
                     + (azar(x, y, 30 + k) - 0.5) * r * 0.25;
          const ay = cy + (azar(x, y, 4 + k) - 0.5) * r * 0.55;
          const rr = r * (0.38 + azar(x, y, 40 + k) * 0.22);
          ctx.fillStyle = cual === 'selva'
            ? (k % 2 ? '#6c8548' : '#7b9553')
            : (k % 2 ? '#7d9055' : '#8b9d61');
          ctx.beginPath();
          ctx.moveTo(ax, ay + rr * 1.5);
          ctx.lineTo(ax, ay + rr * 0.5);
          ctx.stroke();
          ctx.beginPath();
          ctx.arc(ax, ay - rr * 0.15, rr, 0, Math.PI * 2);
          ctx.fill(); ctx.stroke();
        }
        break;
      }
      case 'hierba':
        if (salta > 0.82) break;
        ctx.strokeStyle = 'rgba(108,110,60,.55)';
        ctx.beginPath();
        ctx.moveTo(cx - r * 0.35, cy + r * 0.3); ctx.lineTo(cx - r * 0.1, cy - r * 0.35);
        ctx.moveTo(cx + r * 0.35, cy + r * 0.3); ctx.lineTo(cx + r * 0.1, cy - r * 0.3);
        ctx.stroke();
        break;
      case 'mata':
        if (salta > 0.8) break;
        ctx.strokeStyle = 'rgba(122,110,66,.5)';
        ctx.beginPath();
        ctx.moveTo(cx - r * 0.5, cy); ctx.lineTo(cx + r * 0.5, cy);
        ctx.stroke();
        break;
      case 'duna':
        ctx.strokeStyle = 'rgba(150,122,70,.5)';
        if (salta > 0.6) {
          ctx.beginPath();
          ctx.arc(cx, cy + r * 0.45, r * 0.62, Math.PI * 1.15, Math.PI * 1.85);
          ctx.stroke();
        } else {
          ctx.fillStyle = 'rgba(150,122,70,.45)';
          for (let k = 0; k < 3; k++) {
            ctx.beginPath();
            ctx.arc(cx + (k - 1) * r * 0.5, cy + (azar(x, y, 9 + k) - 0.5) * r * 0.7,
                    Math.max(0.6, r * 0.1), 0, Math.PI * 2);
            ctx.fill();
          }
        }
        break;
      case 'junco':
        ctx.strokeStyle = 'rgba(90,110,90,.6)';
        ctx.beginPath();
        for (let k = 0; k < 2; k++) {
          const ay = cy + (k - 0.5) * r * 0.7;
          ctx.moveTo(cx - r * 0.55, ay);
          ctx.lineTo(cx + r * 0.55, ay);
        }
        ctx.stroke();
        break;
      case 'puntitos':
        if (salta > 0.5) break;
        ctx.fillStyle = 'rgba(90,95,85,.4)';
        ctx.beginPath();
        ctx.arc(cx, cy, Math.max(0.6, r * 0.13), 0, Math.PI * 2);
        ctx.fill();
        break;
      case 'hielo':
        ctx.strokeStyle = 'rgba(120,150,170,.55)';
        ctx.beginPath();
        ctx.moveTo(cx - r * 0.5, cy + r * 0.2);
        ctx.lineTo(cx, cy - r * 0.3);
        ctx.lineTo(cx + r * 0.5, cy + r * 0.2);
        ctx.stroke();
        break;
      default:
        break;
    }
  }

  /* ------------------------------------------------------ agua que corre */
  /* Los caminos vienen casilla a casilla, así que en crudo son escaleras de
     ángulos rectos. Se quitan los puntos que no aportan nada y se redondean
     las esquinas: un río de verdad no gira noventa grados cada paso. */
  function limpiar(camino) {
    const salida = [];
    for (const punto of camino) {
      const ultimo = salida[salida.length - 1];
      if (ultimo && ultimo[0] === punto[0] && ultimo[1] === punto[1]) continue;
      salida.push(punto);
    }
    // Fuera los puntos alineados con sus dos vecinos.
    const recto = [salida[0]];
    for (let i = 1; i < salida.length - 1; i++) {
      const [ax, ay] = salida[i - 1], [bx, by] = salida[i], [cx, cy] = salida[i + 1];
      if ((bx - ax) * (cy - by) !== (by - ay) * (cx - bx)) recto.push(salida[i]);
    }
    if (salida.length > 1) recto.push(salida[salida.length - 1]);
    return recto;
  }

  /* Corte de esquinas de Chaikin: cada vuelta redondea un poco más. */
  function chaikin(puntos, vueltas) {
    let p = puntos;
    for (let v = 0; v < vueltas && p.length > 2; v++) {
      const nueva = [p[0]];
      for (let i = 0; i < p.length - 1; i++) {
        const [ax, ay] = p[i], [bx, by] = p[i + 1];
        nueva.push([ax * 0.75 + bx * 0.25, ay * 0.75 + by * 0.25]);
        nueva.push([ax * 0.25 + bx * 0.75, ay * 0.25 + by * 0.75]);
      }
      nueva.push(p[p.length - 1]);
      p = nueva;
    }
    return p;
  }

  /* Las casillas de un río o de una calzada NO vienen necesariamente en el
     orden en que se recorren: en los exports reales son "las casillas que
     ocupa esto", y punto. Unirlas por orden de lista traza rayas de un extremo
     al otro del mundo. Así que se reconstruye la red: se mira qué casillas se
     tocan y se siguen las cadenas. Lo que no se toca, no se une. */
  function cadenas(puntos, ancho, alto) {
    const dentro = puntos.filter(([x, y]) =>
      x >= 0 && y >= 0 && x < ancho && y < alto);
    if (dentro.length < 2) return [];

    const clave = (x, y) => y * ancho + x;
    const casillas = new Map();
    for (const [x, y] of dentro) casillas.set(clave(x, y), [x, y]);

    const vecinas = (x, y) => {
      const salida = [];
      for (const [dx, dy] of [[1, 0], [-1, 0], [0, 1], [0, -1],
                              [1, 1], [1, -1], [-1, 1], [-1, -1]]) {
        const k = clave(x + dx, y + dy);
        if (casillas.has(k)) salida.push(k);
      }
      return salida;
    };

    // Se empieza por los extremos (una sola vecina) para que las cadenas
    // salgan enteras; lo que quede en medio, después.
    const grado = new Map();
    for (const [k, [x, y]] of casillas) grado.set(k, vecinas(x, y).length);
    const pendientes = [...casillas.keys()].sort(
      (a, b) => (grado.get(a) || 0) - (grado.get(b) || 0));

    const usadas = new Set();
    const salida = [];
    for (const inicio of pendientes) {
      if (usadas.has(inicio)) continue;
      let actual = inicio;
      const cadena = [];
      while (actual !== undefined && !usadas.has(actual)) {
        usadas.add(actual);
        cadena.push(casillas.get(actual));
        const [x, y] = casillas.get(actual);
        // Se sigue por la vecina menos conectada que quede libre: así se
        // recorren primero los brazos y no se dan saltos raros.
        let siguiente, mejor = Infinity;
        for (const k of vecinas(x, y)) {
          if (usadas.has(k)) continue;
          const g = grado.get(k) || 0;
          if (g < mejor) { mejor = g; siguiente = k; }
        }
        actual = siguiente;
      }
      if (cadena.length >= 2) salida.push(cadena);
    }
    return salida;
  }

  function suave(ctx, camino, px, py, vueltas = 2) {
    if (camino.length < 2) return;
    const recto = limpiar(camino);
    if (recto.length < 2) return;
    const p = chaikin(recto.map(([x, y]) => [px(x + 0.5), py(y + 0.5)]), vueltas);
    ctx.beginPath();
    ctx.moveTo(p[0][0], p[0][1]);
    for (let i = 1; i < p.length; i++) ctx.lineTo(p[i][0], p[i][1]);
    ctx.stroke();
  }

  /* Un río es "principal" si su caudal llega a la quinta parte del mayor del
     mundo. No es una cifra inventada: el caudal viene en el propio export, y
     el juego tampoco pinta los arroyos en el mapa del mundo. */
  const UMBRAL = 0.2;

  function esPrincipal(rio) {
    const tope = datos.caudal_maximo || 0;
    if (!tope || rio.caudal === null || rio.caudal === undefined) return true;
    return rio.caudal >= tope * UMBRAL;
  }

  function rios(ctx, geom, pluma) {
    const { celda, offX, offY } = geom;
    const px = (x) => offX + x * celda, py = (y) => offY + y * celda;
    const tope = datos.caudal_maximo || 0;
    ctx.strokeStyle = RIO;
    ctx.lineCap = 'round';
    ctx.lineJoin = 'round';
    for (const rio of datos.rios) {
      const principal = esPrincipal(rio);
      if (!principal && !opciones.arroyos) continue;
      // El grosor sale del caudal, que es un dato del export: un arroyo es un
      // hilo y un río caudaloso una línea gruesa.
      const parte = tope && rio.caudal ? Math.sqrt(rio.caudal / tope) : 0.45;
      ctx.lineWidth = Math.max(0.7, pluma * (0.07 + 0.19 * parte));
      ctx.globalAlpha = principal ? 1 : 0.55;
      for (const tramo of cadenas(rio.camino, datos.ancho, datos.alto)) {
        suave(ctx, tramo, px, py);
      }
    }
    ctx.globalAlpha = 1;
  }

  /* Cuántos ríos hay y cuántos se están dibujando, para poder decirlo. */
  function cuentaRios() {
    if (!datos) return { total: 0, principales: 0 };
    const principales = datos.rios.filter(esPrincipal).length;
    return { total: datos.rios.length, principales };
  }

  function construcciones(ctx, geom, pluma) {
    const { celda, offX, offY } = geom;
    const px = (x) => offX + x * celda, py = (y) => offY + y * celda;
    ctx.lineCap = 'butt';
    for (const c of datos.construcciones) {
      const tipo = c.tipo || 'road';
      ctx.strokeStyle = tipo === 'tunnel' ? 'rgba(74,59,40,.55)' : '#8a6a41';
      ctx.lineWidth = Math.max(0.9, pluma * 0.14);
      ctx.setLineDash(tipo === 'tunnel' ? [pluma * 0.25, pluma * 0.35]
                    : tipo === 'bridge' ? [pluma * 0.7, pluma * 0.25]
                    : [pluma * 0.55, pluma * 0.4]);
      const tramos = cadenas(c.camino, datos.ancho, datos.alto);
      if (!tramos.length && c.camino.length === 1) {
        // Un puente puede ocupar una sola casilla: se marca con un trazo corto.
        const [x, y] = c.camino[0];
        if (x >= 0 && y >= 0 && x < datos.ancho && y < datos.alto) {
          ctx.setLineDash([]);
          ctx.beginPath();
          ctx.moveTo(px(x) + celda * 0.2, py(y) + celda * 0.5);
          ctx.lineTo(px(x) + celda * 0.8, py(y) + celda * 0.5);
          ctx.stroke();
        }
        continue;
      }
      for (const tramo of tramos) {
        suave(ctx, tramo, px, py);
      }
    }
    ctx.setLineDash([]);
  }

  function picos(ctx, geom, pluma) {
    const { celda, offX, offY } = geom;
    if (celda < 4) return;
    for (const p of datos.picos) {
      const cx = offX + (p.x + 0.5) * celda;
      const cy = offY + (p.y + 0.5) * celda;
      const r = Math.max(4, pluma * 0.8);
      ctx.fillStyle = p.volcan ? '#9a6a55' : '#a2916f';
      ctx.strokeStyle = TINTA;
      ctx.lineWidth = Math.max(0.7, pluma * 0.08);
      ctx.beginPath();
      ctx.moveTo(cx - r, cy + r * 0.7);
      ctx.lineTo(cx, cy - r * 1.05);
      ctx.lineTo(cx + r, cy + r * 0.7);
      ctx.closePath();
      ctx.fill(); ctx.stroke();
      if (!p.volcan) {   // nieve en la cumbre
        ctx.fillStyle = 'rgba(255,255,255,.75)';
        ctx.beginPath();
        ctx.moveTo(cx - r * 0.34, cy - r * 0.28);
        ctx.lineTo(cx, cy - r * 1.05);
        ctx.lineTo(cx + r * 0.34, cy - r * 0.28);
        ctx.closePath();
        ctx.fill();
      }
      if (celda >= 9 && p.nombre) {
        const cuerpo = Math.max(9, Math.min(pluma * 0.62, 14));
        ctx.font = `italic ${cuerpo}px Georgia, "Times New Roman", serif`;
        ctx.textAlign = 'center';
        ctx.textBaseline = 'top';
        ctx.lineJoin = 'round';
        ctx.strokeStyle = 'rgba(233,220,190,.9)';
        ctx.lineWidth = 3;
        ctx.strokeText(p.nombre, cx, cy + r * 0.85);
        ctx.fillStyle = '#5a4a33';
        ctx.fillText(p.nombre, cx, cy + r * 0.85);
      }
    }
  }

  /* -------------------------------------------------- adornos de la carta */
  function marco(ctx, x, y, ancho, alto) {
    ctx.strokeStyle = TINTA;
    ctx.lineWidth = 2.5;
    ctx.strokeRect(x - 5.5, y - 5.5, ancho + 11, alto + 11);
    ctx.lineWidth = 1;
    ctx.strokeRect(x - 1.5, y - 1.5, ancho + 3, alto + 3);
    ctx.strokeRect(x - 9.5, y - 9.5, ancho + 19, alto + 19);
  }

  function rosa(ctx, cx, cy, r) {
    if (r < 9) return;
    ctx.save();
    ctx.strokeStyle = TINTA;
    ctx.fillStyle = TINTA;
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.arc(cx, cy, r, 0, Math.PI * 2);
    ctx.stroke();
    for (let k = 0; k < 4; k++) {
      const a = (Math.PI / 2) * k - Math.PI / 2;
      const b = a + Math.PI / 2;
      ctx.beginPath();
      ctx.moveTo(cx + Math.cos(a) * r, cy + Math.sin(a) * r);
      ctx.lineTo(cx + Math.cos(b - Math.PI / 4) * r * 0.24,
                 cy + Math.sin(b - Math.PI / 4) * r * 0.24);
      ctx.lineTo(cx + Math.cos(b) * r, cy + Math.sin(b) * r);
      ctx.closePath();
      ctx.fillStyle = k % 2 ? 'rgba(74,59,40,.35)' : TINTA;
      ctx.fill();
    }
    ctx.fillStyle = TINTA;
    ctx.font = `600 ${Math.max(8, r * 0.5)}px Georgia, "Times New Roman", serif`;
    ctx.textAlign = 'center';
    ctx.fillText('N', cx, cy - r - 3);
    ctx.restore();
  }

  function escala(ctx, x, y, celda, ancho) {
    // Un tramo redondo de casillas que quepa holgado.
    let casillas = 10;
    for (const c of [50, 20, 10, 5]) { if (c * celda < 150) { casillas = c; break; } }
    const largo = casillas * celda;
    ctx.save();
    ctx.strokeStyle = TINTA;
    ctx.fillStyle = TINTA;
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(x, y - 4); ctx.lineTo(x, y); ctx.lineTo(x + largo, y);
    ctx.lineTo(x + largo, y - 4);
    ctx.stroke();
    for (let k = 0; k < casillas; k += 2) {
      ctx.fillRect(x + k * celda, y - 3, celda, 3);
    }
    ctx.font = '600 10px Georgia, "Times New Roman", serif';
    ctx.textAlign = 'left';
    ctx.fillText(`${casillas} casillas`, x, y + 11);
    ctx.restore();
  }

  const motivo_ = () => porQueNo;

  return { preparar, capa, hayMapa, info, motivo: motivo_, terrenos, desconocidos,
           opcion, opciones, cuentaRios,
           cadenas,   // expuesto para la autocomprobación

           PAPEL, PAPEL_OSCURO, TINTA };
})();
