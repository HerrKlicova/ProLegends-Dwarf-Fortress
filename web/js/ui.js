/* Ayudas de interfaz: crear nodos, formatear y mostrar avisos. */
const UI = (() => {

  function el(etiqueta, atributos = {}, hijos = []) {
    const nodo = document.createElement(etiqueta);
    for (const [clave, valor] of Object.entries(atributos)) {
      if (valor === null || valor === undefined || valor === false) continue;
      if (clave === 'class') nodo.className = valor;
      else if (clave === 'html') nodo.innerHTML = valor;
      else if (clave === 'text') nodo.textContent = valor;
      else if (clave.startsWith('on') && typeof valor === 'function') {
        nodo.addEventListener(clave.slice(2), valor);
      } else if (clave === 'dataset') Object.assign(nodo.dataset, valor);
      else if (clave === 'style') nodo.setAttribute('style', valor);
      else nodo.setAttribute(clave, valor);
    }
    for (const hijo of [].concat(hijos)) {
      if (hijo === null || hijo === undefined || hijo === false) continue;
      nodo.appendChild(typeof hijo === 'string' ? document.createTextNode(hijo) : hijo);
    }
    return nodo;
  }

  const vaciar = (nodo) => { while (nodo.firstChild) nodo.removeChild(nodo.firstChild); };

  function poner(nodo, ...hijos) {
    vaciar(nodo);
    hijos.flat().forEach((h) => h && nodo.appendChild(h));
    return nodo;
  }

  /* Convierte 'site taken over' en 'Site taken over' legible sin inventar
     traducciones que no estan en los datos. */
  function tipoLegible(tipo) {
    if (!tipo) return '';
    return tipo.charAt(0).toUpperCase() + tipo.slice(1).replace(/_/g, ' ');
  }

  const anyo = (v) => (v === null || v === undefined || v === -1 ? '?' : v);

  function detallesTexto(detalles) {
    if (!detalles) return '';
    return Object.entries(detalles)
      .map(([k, v]) => `${k}: ${typeof v === 'object' ? JSON.stringify(v) : v}`)
      .join(' · ');
  }

  function aviso(mensaje, detalle, clase) {
    const caja = document.getElementById('aviso-global');
    poner(caja,
      el('div', {}, [
        el('strong', { text: mensaje }),
        detalle ? el('div', { class: 'nota', text: detalle }) : null,
      ]),
      el('button', { text: '×', onclick: () => caja.classList.add('oculto') })
    );
    caja.className = 'aviso' + (clase ? ' ' + clase : '');
  }

  const limpiarAviso = () => document.getElementById('aviso-global').classList.add('oculto');

  function fallo(e) {
    console.error(e);
    aviso(e.mensaje || 'Ha ocurrido un error.', e.detalle || '');
  }

  /* Ventana modal con promesa: resuelve true si se acepta. */
  function confirmar(titulo, cuerpo, textoAceptar = 'Aceptar') {
    return new Promise((resolver) => {
      const modal = document.getElementById('modal');
      document.getElementById('modal-titulo').textContent = titulo;
      poner(document.getElementById('modal-cuerpo'), ...[].concat(cuerpo));
      const aceptar = document.getElementById('modal-aceptar');
      const cancelar = document.getElementById('modal-cancelar');
      aceptar.textContent = textoAceptar;
      const cerrar = (valor) => {
        modal.classList.add('oculto');
        aceptar.onclick = null; cancelar.onclick = null;
        resolver(valor);
      };
      aceptar.onclick = () => cerrar(true);
      cancelar.onclick = () => cerrar(false);
      modal.classList.remove('oculto');
    });
  }

  function tabla(cabeceras, filas) {
    return el('div', { class: 'scroll' }, [
      el('table', { class: 'tabla' }, [
        el('thead', {}, [el('tr', {}, cabeceras.map((c) => el('th', { text: c })))]),
        el('tbody', {}, filas.map((f) => el('tr', {}, f.map(
          (c) => el('td', {}, [typeof c === 'string' || typeof c === 'number'
            ? document.createTextNode(String(c)) : (c || document.createTextNode('—'))])
        )))),
      ]),
    ]);
  }

  const datos = (pares) => el('dl', { class: 'datos' },
    pares.filter((p) => p && p[1] !== null && p[1] !== undefined && p[1] !== '')
      .flatMap(([k, v]) => [
        el('dt', { text: k }),
        el('dd', {}, [typeof v === 'object' ? v : document.createTextNode(String(v))]),
      ]));

  const bloque = (titulo, ...contenido) =>
    el('div', { class: 'bloque' }, [el('h4', { text: titulo }), ...contenido.flat()]);

  return { el, poner, vaciar, tipoLegible, anyo, detallesTexto, aviso, limpiarAviso,
           fallo, confirmar, tabla, datos, bloque };
})();
