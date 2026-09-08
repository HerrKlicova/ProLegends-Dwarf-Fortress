/* Arranque y coordinacion de vistas. */
const App = (() => {
  const el = UI.el;

  /* Versión de ESTA interfaz. El servidor dice la suya en /salud; si no
     coinciden es que el navegador ha servido de su caché la interfaz de una
     versión anterior, y hay que avisar en vez de dejar que parezca que la
     actualización no ha hecho nada. */
  const VERSION_INTERFAZ = '1.4.4';
  let estado = { mundos: [], mundoId: null, exportId: null, vista: 'mapa', cargadas: new Set() };

  const mundoId = () => estado.mundoId;
  const exportId = () => estado.exportId;

  function mundoActual() { return estado.mundos.find((m) => m.id === estado.mundoId) || null; }
  function exportActual() {
    const m = mundoActual();
    return (m && m.exports.find((e) => e.id === estado.exportId)) || {};
  }

  async function inicio() {
    Mapa.conectar();
    Figuras.conectar();
    document.querySelectorAll('#pestanyas button').forEach((b) =>
      b.addEventListener('click', () => pestanya(b.dataset.vista)));
    document.getElementById('sel-mundo').addEventListener('change', async (e) => {
      estado.mundoId = Number(e.target.value);
      pintarExports();
      await cambiarExport();
    });
    document.getElementById('sel-export').addEventListener('change', async (e) => {
      estado.exportId = Number(e.target.value);
      await cambiarExport();
    });
    document.getElementById('btn-importar').addEventListener('click', importar);
    await recargarMundos(true);
    await comprobarVersion();
  }

  async function comprobarVersion() {
    let salud;
    try { salud = await API.get('/salud'); } catch (e) { return; }
    document.getElementById('version').textContent = 'v' + salud.version;
    if (salud.version === VERSION_INTERFAZ) return;
    UI.aviso(
      `Estás viendo una interfaz antigua (la ${VERSION_INTERFAZ}); el programa es la ${salud.version}.`,
      'La ha sacado el navegador de su memoria. Pulsa Ctrl+F5 (en Mac, Cmd+Shift+R) '
      + 'para recargarla del todo y verás la versión nueva.');
  }

  async function recargarMundos(primeraVez) {
    let datos;
    try { datos = await API.mundos(); }
    catch (e) { UI.fallo(e); return; }
    estado.mundos = datos.mundos;

    if (datos.fallidos && datos.fallidos.length) {
      UI.aviso('Algún export no se pudo importar.',
        datos.fallidos.map((f) => `${f.prefix}: ${f.message || 'motivo desconocido'}`).join(' | '));
    }
    if (!estado.mundos.length) {
      sinDatos();
      return;
    }
    if (!estado.mundos.some((m) => m.id === estado.mundoId)) {
      estado.mundoId = estado.mundos[0].id;
      estado.exportId = null;
    }
    pintarMundos();
    pintarExports();
    await cambiarExport();
    if (primeraVez) UI.limpiarAviso();
  }

  function pintarMundos() {
    const sel = document.getElementById('sel-mundo');
    UI.poner(sel, ...estado.mundos.map((m) =>
      el('option', { value: String(m.id), text: m.altnombre ? `${m.nombre} — ${m.altnombre}` : m.nombre })));
    sel.value = String(estado.mundoId);
  }

  function pintarExports() {
    const m = mundoActual();
    const sel = document.getElementById('sel-export');
    if (!m) { UI.poner(sel); return; }
    UI.poner(sel, ...m.exports.map((e) =>
      el('option', { value: String(e.id), text: `año ${e.anyo ?? '?'} — ${e.prefix}` })));
    if (!m.exports.some((e) => e.id === estado.exportId)) {
      estado.exportId = m.exports[m.exports.length - 1].id;
    }
    sel.value = String(estado.exportId);
    const e = exportActual();
    document.getElementById('subtitulo').textContent =
      `${m.nombre} · mapa de ${e.ancho ?? '?'}x${e.alto ?? '?'} casillas · ` +
      Object.entries(e.resumen || {}).map(([k, v]) => `${v} ${k}`).join(', ');
    if (e.aviso) UI.aviso('Aviso del import de este export', e.aviso);
  }

  async function cambiarExport() {
    estado.cargadas = new Set();
    try {
      await Mapa.cargar(estado.exportId);
      estado.cargadas.add('mapa');
    } catch (e) { UI.fallo(e); }
    await asegurarVista(estado.vista);
  }

  async function asegurarVista(vista) {
    if (estado.cargadas.has(vista)) return;
    try {
      if (vista === 'figuras') await Figuras.inicializar();
      else if (vista === 'fortaleza') await Fortaleza.cargar();
      else if (vista === 'cronicas') await Cronicas.cargar();
      estado.cargadas.add(vista);
    } catch (e) { UI.fallo(e); }
  }

  function pestanya(vista) {
    estado.vista = vista;
    document.querySelectorAll('#pestanyas button').forEach((b) =>
      b.classList.toggle('activa', b.dataset.vista === vista));
    document.querySelectorAll('main .vista').forEach((s) =>
      s.classList.toggle('oculta', s.id !== 'vista-' + vista));
    if (vista === 'mapa') Mapa.redibujar();
    asegurarVista(vista);
  }

  async function irAFigura(hfId) {
    pestanya('figuras');
    await asegurarVista('figuras');
    Figuras.abrir(hfId);
  }

  function verEntidad(entityId) { Figuras.verEntidad(entityId); }

  async function verSitio(siteId) {
    pestanya('mapa');
    await Mapa.abrirSitio(siteId);
  }

  /* -------------------------------------------------------- importación */
  /* La ventana tiene dos partes: de dónde salen los ficheros (la carpeta de
     Dwarf Fortress) y qué hay ya en data/imports esperando a procesarse. */
  async function importar() {
    const cajaImports = el('div', { class: 'bloque' });
    const casillaOrdenar = el('input', { type: 'checkbox', checked: 'checked' });

    async function pintarImports() {
      let pendientes;
      try { pendientes = await API.pendientes(); }
      catch (e) {
        UI.poner(cajaImports, el('h4', { text: 'En data/imports' }),
                 el('p', { class: 'nota', text: e.mensaje || 'no se ha podido consultar' }));
        return;
      }
      const orden = pendientes.orden || { cambios: [], bloqueados: [], avisos: [] };
      // Sin exports, el único aviso es "aquí no hay nada", que ya se dice arriba.
      const sobrantes = pendientes.exports.length
        ? [...new Set((pendientes.avisos || []).concat(orden.avisos || []))]
        : [];

      UI.poner(cajaImports,
        el('h4', { text: 'En data/imports' }),
        el('p', { class: 'nota', text: pendientes.carpeta }),

        pendientes.exports.length
          ? UI.tabla(['Export', 'Ficheros', 'Tamaño', 'Estado'], pendientes.exports.map((p) => [
              p.prefix,
              [p.principal, p.plus].filter(Boolean).join(' + ') || '—',
              `${p.tamano_mb} MB`,
              p.importado ? 'ya importado' : (p.completo ? 'pendiente' : 'pendiente (sin _plus)'),
            ]))
          : el('p', { class: 'nota', text:
              'Aquí no hay nada todavía. Trae un export desde la carpeta del juego, ' +
              'o copia a mano los ficheros -legends.xml y -legends_plus.xml.' }),

        orden.cambios.length ? el('div', { class: 'bloque' }, [
          el('h4', { text: `Se ordenarán ${orden.cambios.length} export(s)` }),
          el('label', { class: 'capa' }, [
            casillaOrdenar,
            el('span', { text: 'Renombrar según el mundo y la fecha, y repartir por carpetas' }),
          ]),
          el('div', { class: 'scroll' }, orden.cambios.map((g) => el('div', { class: 'novedad' }, [
            el('strong', { text: g.mundo || 'mundo desconocido' }),
            g.fecha ? el('span', { text: `  ·  ${g.fecha}` }) : null,
            ...g.ficheros.filter((f) => f.cambia).map((f) =>
              el('div', { class: 'nota', text: `${f.de}  →  ${f.a}` })),
            g.aviso ? el('div', { class: 'nota', text: g.aviso }) : null,
          ]))),
          el('p', { class: 'nota', text:
            'No se sobrescribe ni se borra nada: si un nombre ya estuviera cogido, ese export se deja como está.' }),
        ]) : null,

        orden.bloqueados.length ? el('div', { class: 'alerta suave' }, [
          el('strong', { text: 'Algún export no se puede ordenar: ' }),
          el('span', { text: orden.bloqueados.map((g) => g.aviso).filter(Boolean).join(' | ') }),
        ]) : null,

        sobrantes.length ? el('pre', { class: 'consola', text: sobrantes.join('\n') }) : null,
        el('p', { class: 'nota', text:
          'Los exports ya importados se saltan solos. Un fichero de 45 MB puede tardar un par de minutos.' }),
      );
    }

    await pintarImports();
    const cuerpo = [Juego.bloque(pintarImports), cajaImports];
    const ok = await UI.confirmar('Traer e importar exports', cuerpo, 'Importar ahora');
    if (!ok) return;

    const ordenar = casillaOrdenar.checked;
    try { await API.importar(null, ordenar); } catch (e) { UI.fallo(e); return; }
    UI.aviso('Importando... el detalle se ve en la ventana negra de start.bat.', '');
    seguirImportacion();
  }

  function seguirImportacion() {
    const tic = setInterval(async () => {
      let estadoImp;
      try { estadoImp = await API.estadoImport(); } catch (e) { clearInterval(tic); return; }
      if (estadoImp.activo) {
        const ultima = (estadoImp.lineas || []).slice(-1)[0] || 'procesando...';
        UI.aviso('Importando exports...', ultima);
        return;
      }
      clearInterval(tic);
      if (estadoImp.error) { UI.aviso('La importación ha fallado.', estadoImp.error); return; }
      const r = estadoImp.resultado || {};
      const partes = [];
      if ((r.importados || []).length) partes.push(`${r.importados.length} importados`);
      if ((r.omitidos || []).length) partes.push(`${r.omitidos.length} ya estában`);
      if ((r.errores || []).length) partes.push(`${r.errores.length} con error`);
      UI.aviso('Importación terminada.',
        partes.join(', ') + ((r.errores || []).length
          ? ' — ' + r.errores.map((x) => `${x.prefix}: ${x.error}`).join(' | ') : ''),
        (r.errores || []).length ? '' : 'ok');
      await recargarMundos(false);
    }, 1200);
  }

  function sinDatos() {
    UI.poner(document.getElementById('sel-mundo'), el('option', { text: 'sin mundos' }));
    UI.poner(document.getElementById('sel-export'), el('option', { text: '—' }));
    document.getElementById('subtitulo').textContent = 'Todavía no hay ningún mundo importado';
    UI.aviso('No hay ningún mundo importado.',
      'Pulsa "Importar exports": desde ahí puedes traerlos directamente de la carpeta '
      + 'de Dwarf Fortress, o copiarlos tú a data/imports/.');
    UI.poner(document.getElementById('panel-sitio'),
      el('p', { class: 'vacio', text: 'Sin datos.' }));
  }

  return { inicio, pestanya, mundoId, exportId, exportActual, mundoActual,
           irAFigura, verEntidad, verSitio, recargarMundos };
})();

window.addEventListener('DOMContentLoaded', App.inicio);
