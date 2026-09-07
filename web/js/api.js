/* Acceso a la API interna. Todo pasa por aqui, para que los errores se
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
    importar:      (prefijo)          => post('/api/importar', { prefijo: prefijo || null }),
    estadoImport:  ()                 => get('/api/importar/estado'),
    export:        (id)               => get(`/api/exports/${id}`),
    mapa:          (id)               => get(`/api/exports/${id}/mapa`),
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
  };
})();
