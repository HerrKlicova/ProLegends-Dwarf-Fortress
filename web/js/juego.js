/* Conexión con la carpeta de Dwarf Fortress.

   Dwarf Fortress deja los XML de leyendas en la misma carpeta donde está su
   ejecutable. Este bloque la encuentra, enseña qué exports hay dentro y trae
   los que marques a data/imports/. Vive dentro de la ventana de importar. */
const Juego = (() => {
  const el = UI.el;

  let caja = null;         // el nodo que este módulo repinta
  let estado = null;       // lo último que dijo /api/juego
  let candidatas = null;   // resultado de la búsqueda, si se ha hecho
  let marcados = new Set();
  let trabajando = '';     // texto a mostrar mientras algo tarda
  let alTraer = null;      // qué hacer cuando lleguen ficheros nuevos

  /* Devuelve el nodo ya montado; se rellena solo en cuanto responde la API. */
  function bloque(callback) {
    alTraer = callback;
    caja = el('div', { class: 'bloque' });
    pintar();
    refrescar();
    return caja;
  }

  async function refrescar() {
    try { estado = await API.juego(); }
    catch (e) { estado = { error: e.mensaje || 'no se ha podido consultar' }; }
    pintar();
  }

  function pintar() {
    if (!caja) return;
    UI.poner(caja,
      el('h4', { text: 'Desde Dwarf Fortress' }),
      ...(trabajando ? [el('p', { class: 'nota', text: trabajando })] : cuerpo()));
  }

  function cuerpo() {
    if (estado === null) return [el('p', { class: 'nota', text: 'Mirando...' })];
    if (estado.error) return [el('p', { class: 'nota', text: estado.error })];
    return estado.valida ? conCarpeta() : sinCarpeta();
  }

  /* ------------------------------------------- todavía no sabemos dónde está */
  function sinCarpeta() {
    const partes = [
      el('p', { class: 'nota', text:
        'Cuando exportas las leyendas, el juego deja los dos XML junto a su ' +
        'ejecutable. Si le dices dónde está, ProLegends los trae solo y no ' +
        'tienes que copiar nada a mano.' }),
      el('div', { class: 'botonera' }, [
        el('button', { class: 'boton primario', text: 'Buscar Dwarf Fortress',
                       onclick: buscar }),
        el('button', { class: 'boton', text: 'Elegir la carpeta a mano',
                       onclick: elegir }),
      ]),
    ];
    if (estado.recordada) {
      partes.push(el('p', { class: 'nota', text:
        `La carpeta que había guardada (${estado.recordada}) ya no existe. ` +
        'Puede que hayas movido el juego o que el disco no esté conectado.' }));
    }
    if (candidatas) {
      partes.push(candidatas.length
        ? el('div', { class: 'scroll' }, candidatas.map((c) => el('div', { class: 'novedad' }, [
            el('div', {}, [el('strong', { text: c.ruta })]),
            el('div', { class: 'nota', text:
              (c.exports ? `${c.exports} export(s) de leyendas dentro` : 'sin exports dentro') +
              (c.tiene_ejecutable ? ' · con el ejecutable' : '') }),
            el('button', { class: 'boton pequeno', text: 'Usar esta',
                           onclick: () => usar(c.ruta) }),
          ])))
        : el('p', { class: 'nota', text:
            'No se ha encontrado ninguna instalación en los sitios habituales. ' +
            'Elige la carpeta a mano: es la que tiene dentro "Dwarf Fortress.exe".' }));
    }
    partes.push(rutaAMano());
    return partes;
  }

  function rutaAMano() {
    const campo = el('input', { type: 'text', class: 'ruta',
      placeholder: 'D:\\Steam\\steamapps\\common\\Dwarf Fortress' });
    return el('div', { class: 'rango' }, [
      campo,
      el('button', { class: 'boton pequeno', text: 'Usar',
                     onclick: () => usar(campo.value) }),
    ]);
  }

  /* --------------------------------------------------- ya sabemos dónde está */
  function conCarpeta() {
    const exports = estado.exports || [];
    const nuevos = exports.filter((e) => !e.ya_en_imports);
    marcados = new Set([...marcados].filter((p) => nuevos.some((e) => e.prefijo === p)));

    const partes = [
      el('p', { class: 'ruta-mostrada' }, [
        el('strong', { text: estado.carpeta }),
        el('span', { class: 'nota', text:
          estado.tiene_ejecutable ? '  ·  ahí está el juego' : '' }),
      ]),
      el('div', { class: 'botonera' }, [
        el('button', { class: 'boton pequeno', text: 'Cambiar carpeta', onclick: elegir }),
        el('button', { class: 'boton pequeno', text: 'Olvidarla', onclick: olvidar }),
      ]),
    ];

    if (!exports.length) {
      partes.push(el('p', { class: 'nota', text:
        'En esa carpeta no hay ningún export de leyendas. Dentro del juego: ' +
        'Legends mode → Export detailed map/legends, y vuelve a mirar aquí.' }));
      return partes;
    }

    partes.push(el('div', { class: 'scroll' }, [
      el('table', { class: 'tabla' }, [
        el('thead', {}, [el('tr', {}, ['', 'Mundo', 'Fecha', 'Tamaño', 'Estado']
          .map((c) => el('th', { text: c })))]),
        el('tbody', {}, exports.map((e) => fila(e))),
      ]),
    ]));

    const boton = el('button', {
      class: 'boton primario', text: 'Traer los marcados', onclick: traer,
    });
    if (!marcados.size) boton.disabled = true;
    partes.push(el('div', { class: 'botonera' }, [
      boton,
      nuevos.length > 1 ? el('button', { class: 'boton pequeno', text: 'Marcar todos',
        onclick: () => { nuevos.forEach((e) => marcados.add(e.prefijo)); pintar(); } }) : null,
    ]));
    partes.push(el('p', { class: 'nota', text:
      'Se copian, no se mueven: los ficheros siguen en la carpeta del juego.' }));
    if ((estado.mapas || []).length) {
      partes.push(el('p', { class: 'nota', text:
        `De paso: ahí hay ${estado.mapas.length} imagen(es) de mapa. Todavía no se usan.` }));
    }
    return partes;
  }

  function fila(e) {
    const ya = e.ya_en_imports;
    const casilla = el('input', { type: 'checkbox' });
    casilla.checked = marcados.has(e.prefijo);
    casilla.disabled = !!ya;
    casilla.addEventListener('change', () => {
      if (casilla.checked) marcados.add(e.prefijo); else marcados.delete(e.prefijo);
      pintar();
    });
    const fecha = e.anyo === null || e.anyo === undefined
      ? e.prefijo
      : `año ${e.anyo}` + (e.mes ? `, ${String(e.mes).padStart(2, '0')}-${String(e.dia).padStart(2, '0')}` : '');
    return el('tr', {}, [
      el('td', {}, [casilla]),
      el('td', { text: e.mundo || e.prefijo }),
      el('td', { text: fecha }),
      el('td', { text: `${e.tamano_mb} MB` }),
      el('td', { text: ya ? 'ya la tienes' : (e.completo ? 'sin traer' : 'sin traer (falta el _plus)') }),
    ]);
  }

  /* ------------------------------------------------------------- acciones */
  async function buscar() {
    trabajando = 'Buscando Dwarf Fortress por los sitios habituales...';
    pintar();
    try {
      const r = await API.buscarJuego();
      candidatas = r.instalaciones || [];
      // Si solo hay una y tiene exports dentro, no hace falta preguntar.
      if (candidatas.length === 1 && candidatas[0].exports) {
        trabajando = '';
        await usar(candidatas[0].ruta);
        return;
      }
    } catch (e) { UI.fallo(e); }
    trabajando = '';
    pintar();
  }

  async function elegir() {
    trabajando = 'Se ha abierto una ventana en tu escritorio para elegir la carpeta. ' +
                 'Si no la ves, mira en la barra de tareas.';
    pintar();
    try {
      const r = await API.elegirJuego();
      if (r.estado === 'no_es_df') UI.aviso('Esa carpeta no parece la del juego.', r.aviso);
      else if (r.estado === 'ok') { estado = r; candidatas = null; }
    } catch (e) { UI.fallo(e); }
    trabajando = '';
    pintar();
    if (estado && !estado.valida) refrescar();
  }

  async function usar(ruta) {
    if (!ruta || !ruta.trim()) return;
    trabajando = 'Comprobando la carpeta...';
    pintar();
    try {
      estado = await API.fijarJuego(ruta.trim());
      candidatas = null;
    } catch (e) { UI.fallo(e); }
    trabajando = '';
    pintar();
  }

  async function olvidar() {
    try { await API.olvidarJuego(); } catch (e) { UI.fallo(e); }
    estado = null; candidatas = null; marcados = new Set();
    pintar();
    refrescar();
  }

  async function traer() {
    const prefijos = [...marcados];
    if (!prefijos.length) return;
    trabajando = 'Copiando... un export son unos 57 MB, tarda unos segundos.';
    pintar();
    try { await API.traerJuego(prefijos, estado.carpeta); }
    catch (e) { UI.fallo(e); trabajando = ''; pintar(); return; }

    await new Promise((listo) => {
      const tic = setInterval(async () => {
        let s;
        try { s = await API.estadoTraida(); } catch (e) { clearInterval(tic); listo(); return; }
        if (s.activo) {
          trabajando = (s.lineas || []).slice(-1)[0] || 'copiando...';
          pintar();
          return;
        }
        clearInterval(tic);
        if (s.error) UI.aviso('No se han podido traer los ficheros.', s.error);
        else {
          const r = s.resultado || {};
          if ((r.fallos || []).length) {
            UI.aviso('Algún fichero no se ha podido copiar.', r.fallos.join(' | '));
          }
        }
        listo();
      }, 800);
    });

    marcados = new Set();
    trabajando = '';
    await refrescar();
    if (alTraer) alTraer();
  }

  return { bloque };
})();
