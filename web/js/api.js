/* Acceso a la API interna. Todo pasa por aquí, para que los errores se
   muestren siempre igual y en castellano. */
const API = (() => {

  async function pedir(ruta, opciones = {}) {
    let respuesta;
    try {
      respuesta = await fetch(ruta, {
        headers: { 'Content-Type': 'application/json' },
        ...opciones,
      });
    } catch (e) {
      throw new ErrorApp(
        'No se ha podido contactar con el servidor local.',
        'Comprueba que la ventana negra de start.bat sigue abierta.'
      );
    }
    let datos = null;
    const texto = await respuesta.text();
    if (texto) {
      try { datos = JSON.parse(texto); } catch (e) { datos = { error: texto }; }
    }
    if (!respuesta.ok) {
      throw new ErrorApp(
        (datos && (datos.error || datos.detail)) || `Error ${respuesta.status}`,
        (datos && datos.detalle) || ''
      );
    }
    return datos;
  }

  class ErrorApp extends Error {
    constructor(mensaje, detalle) {
      super(mensaje);
      this.mensaje = mensaje;
      this.detalle = detalle || '';
    }
  }

  const get = (ruta) => pedir(ruta);
  const post = (ruta, cuerpo) => pedir(ruta, { method: 'POST', body: JSON.stringify(cuerpo || {}) });

  return {
    ErrorApp, get, post,
    mundos:        ()                 => get('/api/mundos'),
    pendientes:    ()                 => get('/api/importar/pendientes'),
    importar:      (prefijo, ordenar) => post('/api/importar',
                                            { prefijo: prefijo || null, ordenar: ordenar !== false }),
    estadoImport:  ()                 => get('/api/importar/estado'),
    juego:         ()                 => get('/api/juego'),
    buscarJuego:   ()                 => get('/api/juego/buscar'),
    fijarJuego:    (ruta)             => post('/api/juego/carpeta', { ruta }),
    olvidarJuego:  ()                 => post('/api/juego/olvidar'),
    elegirJuego:   ()                 => post('/api/juego/elegir'),
    traerJuego:    (prefijos, ruta)   => post('/api/juego/traer', { prefijos, ruta }),
    estadoTraida:  ()                 => get('/api/juego/traer/estado'),
    export:        (id)               => get(`/api/exports/${id}`),
    mapa:          (id)               => get(`/api/exports/${id}/mapa`),
    terreno:       (id)               => get(`/api/exports/${id}/terreno`),
    geografia:     (id)               => get(`/api/exports/${id}/geografia`),
    sitio:         (id, sid)          => get(`/api/exports/${id}/sitios/${sid}`),
    entidad:       (id, eid)          => get(`/api/exports/${id}/entidades/${eid}`),
    figuras:       (id, q)            => get(`/api/exports/${id}/figuras?${q}`),
    figura:        (id, hf)           => get(`/api/exports/${id}/figuras/${hf}`),
    matadores:     (id)               => get(`/api/exports/${id}/matadores?limite=60`),
    artefactos:    (id, q)            => get(`/api/exports/${id}/artefactos?${q || ''}`),
    fortaleza:     (mid)              => get(`/api/mundos/${mid}/fortaleza`),
    elegirFort:    (mid, sid)         => post(`/api/mundos/${mid}/fortaleza`, { site_id: sid }),
    diff:          (mid, d, h)        => get(`/api/mundos/${mid}/diff?desde=${d}&hasta=${h}`),
    estadoCronica: ()                 => get('/api/cronicas/estado'),
    prepararCron:  (cuerpo)           => post('/api/cronicas/preparar', cuerpo),
    generarCron:   (cuerpo)           => post('/api/cronicas', cuerpo),
    cronicas:      (mid)              => get(`/api/mundos/${mid}/cronicas`),
    cronica:       (mid, amb, clave)  => get(`/api/mundos/${mid}/cronicas/${amb}/${encodeURIComponent(clave)}`),
  };
})();
