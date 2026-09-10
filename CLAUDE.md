# ProLegends — instrucciones de trabajo

Este fichero es para quien programe aquí (yo, Claude, o cualquier otro agente).
No es documentación de usuario: eso está en `README.md`.

---

## 1. Qué es esto y para quién

ProLegends es una aplicación **local** que sirve para explorar el archivo de
leyendas (`legends.xml` + `legends_plus.xml`) que exporta Dwarf Fortress.
Se arranca con doble clic, abre un servidor en `127.0.0.1` y se usa desde el
navegador. **Todo está en castellano**, interfaz y código incluidos.

**Quién la usa.** Una sola persona, que no programa. Sus palabras:

> «Soy usuario, no desarrollador: quiero ejecutarlo y usarlo, no mantenerlo.
> Toma tú las decisiones técnicas y no me preguntes por detalles de
> implementación.»

Consecuencias prácticas:

- **No se le pregunta por detalles técnicos.** Se decide y se explica después,
  en una línea, en castellano y sin jerga.
- **Sí se le pregunta** cuando la decisión es de gusto (colores, disposición) o
  cuando afecta a sus datos.
- Cualquier mensaje de error que pueda ver una persona se escribe **en
  castellano y diciendo qué hacer**, no qué ha fallado por dentro.
- Windows es su sistema principal; también usa un Mac. Los dos arranques
  (`start.bat`, `start.command`) tienen que seguir funcionando.

---

## 2. Reglas que no se rompen

Estas vienen del encargo original y siguen vigentes. No son preferencias: son
condiciones.

| # | Regla | Por qué |
|---|-------|---------|
| 1 | **El `.env` no se sube nunca.** Ni el fichero, ni la clave dentro de un log, un informe, un commit o un mensaje. | Es su clave de pago de la API de Anthropic. Ya se le expuso una vez en una captura y tuvo que revocarla. |
| 2 | **El XML no se carga en el navegador.** | Pesa entre 20 y 60 MB. Se procesa en Python, en streaming, y al navegador solo van JSON pequeños. |
| 3 | **Sin frameworks con compilación y sin pedir que instale Node.** | La interfaz es HTML, CSS y JavaScript a pelo. Nada de npm, bundlers ni pasos de build. |
| 4 | **No se codifica nada específico de un mundo.** | Ningún nombre de sitio, civilización o figura del mundo de nadie dentro del código. Todo sale del export. |
| 5 | **No se inventan campos.** Si un dato no está en el XML, no se enseña. | Es la promesa central del programa: lo que lees es lo que hay en tu partida. |
| 6 | **No se llama a la API de Anthropic sin que lo pida explícitamente.** | Cuesta dinero. Solo `POST /api/cronicas` llama, y primero mira si ya está guardada. |
| 7 | **Se trabaja siempre en `main`.** Sin ramas y sin pull requests. | Lo pidió así. Commits pequeños, mensaje descriptivo en castellano, y `git push` al terminar cada bloque que funcione. |

**Sobre la regla 5, el matiz que importa:** traducir un término conocido
(`DWARF` → «enano») no es inventar. Inventar es rellenar un hueco. Lo que no
esté en el diccionario se enseña **tal cual**, peinado pero sin traducir.
Y los **nombres propios que genera Dwarf Fortress no se traducen jamás**:
«Kolluslan» es «Kolluslan».

---

## 3. Cómo se entrega cada cambio

Lo pidió así y se cumple cada vez:

1. **Antes de tocar nada**: un resumen en castellano de lo que se va a hacer.
2. **Un número de versión** (`MAYOR.MENOR.PARCHE`).
3. Se programa, se comprueba, se hace commit y se hace push a `main`.
4. **Una línea en castellano** diciendo qué se ha subido.
5. **Un texto listo para pegar** en la release de GitHub.

La versión se toca en **tres sitios a la vez** o la autocomprobación falla:

- `app/__init__.py` → `__version__`
- `app/main.py` → `version=` de `FastAPI(...)`
- `web/js/app.js` → `VERSION_INTERFAZ`

Y se añade la entrada correspondiente en `CHANGELOG.md`.

---

## 4. Antes de dar algo por bueno

```bash
python3 tools/autocomprobacion.py      # 19 secciones; tiene que salir todo verde
```

Esa herramienta genera mundos de prueba con `tools/make_sample_export.py`, los
importa, dibuja el mapa, narra sucesos, levanta un servidor de verdad y
comprueba las cabeceras. **No hay `pytest`**: la carpeta `tests/` está vacía a
propósito, la autocomprobación es la red de seguridad.

Si el cambio toca la interfaz, además hay que **abrirla de verdad** en un
navegador y pasearla. Chromium está en el entorno:

```python
p.chromium.launch(executable_path="/opt/pw-browsers/chromium-1194/chrome-linux/chrome",
                  args=["--no-sandbox"])
```

Para probar con datos sin tocar los suyos:

```bash
python3 tools/make_sample_export.py /tmp/pl/imports --mundo prueba --token regionA
PROLEGENDS_HOME=/tmp/pl python3 -m app.cli importar
PROLEGENDS_HOME=/tmp/pl python3 -m uvicorn app.main:app --port 8099
```

**`PROLEGENDS_HOME` es obligatorio al probar.** Sin esa variable se escribe en
`Documentos/ProLegends`, que en su ordenador es donde viven sus crónicas.

---

## 5. Trampas conocidas del entorno

- Matar el servidor con `pkill -f "uvicorn app.main:app"` **mata también la
  shell**. Hay que escribirlo así: `pkill -f "uvicorn app.mai[n]:app"`.
- Ese `pkill` va **en su propia llamada**, nunca encadenado con el arranque del
  servidor siguiente: da error 144.
- En Playwright, una casilla que se vuelve a dibujar al cambiar se desengancha:
  hay que usar selectores (`pg.check("selector")`), no manejadores guardados.
- En Mac, el `.env` no se ve en el Finder porque empieza por punto:
  **Cmd + Shift + .** Es lo primero que hay que preguntar antes de buscar bugs.

---

## 6. Mapa del código

```
app/
  config.py       Rutas, .env y ajustes. Todo lo que depende del entorno vive aquí.
  main.py         Servidor FastAPI. Sirve /api y la interfaz estática.
  cli.py          Comandos de terminal: importar, geografia, diagnostico, reiniciar-bd.
  db.py           Conexión a SQLite y carga del esquema.
  schema.sql      29 tablas y 36 índices.
  ajustes.py      Ajustes que se recuerdan (carpeta de DF, fortaleza elegida).
  mudanza.py      Traslado, una sola vez, a la carpeta personal.
  juego.py        Encuentra la instalación de Dwarf Fortress y trae los exports.
  errors.py       Errores con mensaje en castellano.

  parser/
    xmlstream.py  Lectura en streaming, CP437 y bytes de control. El cimiento.
    legends.py    Todo lo que se sabe de la forma del XML. Nadie más debería saberlo.
    discover.py   Empareja legends.xml con su legends_plus.xml.
    organizer.py  Ordena data/imports/ por mundo y fecha.
    importer.py   Del XML a SQLite. Una sola transacción.
    inspeccion.py Los informes de "¿Algo no cuadra?".

  model/
    diccionario.py 21 tablas de términos de DF a castellano.
    narrador.py    155 plantillas que convierten un suceso en una frase.
    terreno.py     La rejilla de biomas, los ríos y las construcciones.
    entities.py    Jerarquía de entidades (quién depende de quién).
    ownership.py   Quién manda en cada sitio, año a año.
    fortress.py    Detección y análisis de "mi fortaleza".

  api/            31 endpoints. atlas, figures, fortress, worlds, juego, chronicle.
  ai/             Crónicas narradas. context.py elige los hechos, chronicler.py llama.

web/              Interfaz. Sin compilación: se edita y se recarga.
  js/atlas.js     El mapa de pergamino, dibujado en canvas.
  js/mapa.js      El panel del mapa y las fichas de sitio.
  js/ui.js        Piezas comunes (tablas, bloques, avisos).

tools/
  autocomprobacion.py   19 secciones. La red de seguridad.
  make_sample_export.py Genera exports falsos con la forma de los de verdad.
```

---

## 7. Cosas que NO se tocan sin pensarlo mucho

- **`app/parser/xmlstream.py`.** El mapeo de bytes C0 a glifos CP437 costó
  encontrarlo. Si se «limpia», los nombres con ☼ dejan de leerse y el XML deja
  de parsearse. No se toca sin una razón y sin comprobarlo.
- **La transacción única del importador.** Bajó una importación de 50 MB de
  32,2 s a 9,0 s. Ya se probó quitar los índices durante la carga: **va peor**,
  porque la fase de derivación los necesita. No repetir el experimento.
- **La cabecera `Cache-Control: no-cache`** de `InterfazSiempreFresca`. Sin ella,
  el usuario actualiza el programa y sigue viendo la interfaz vieja. Ya pasó.
- **`data/cronicas/`.** Es lo único que cuesta dinero y no se puede regenerar.
  No se borra, no se mete en la base de datos, no se sube a GitHub.
- **La carpeta personal (`Documentos/ProLegends`).** Nada de escribir dentro de
  la carpeta del programa: se borra entera al actualizar.
- **Los formatos del XML que ya se descubrieron.** Un punto de río son **cinco
  números** (`x,y,caudal,salida,altura`), no dos. Está en el código y en la
  autocomprobación; si algo parece raro, se mira el XML antes de tocar.

---

## 8. La lección que más ha costado

Los ríos salieron cuatro veces mal porque se diagnosticó **suponiendo** en vez
de mirar. El usuario lo dijo claro:

> «creo que tienes un mal entendido con lo ríos y deberías de comprobar el xml
> pertinente para arreglarlo»

Y tenía razón. De ahí salió el método que ahora es la norma:

**Cuando algo no cuadra, se mira el dato del usuario antes de tocar código.**

La herramienta para eso es el botón **«¿Algo no cuadra?»** del mapa (y
`python -m app.cli geografia`). Vuelca la geografía, los tipos de suceso con
recuento, los vínculos y las razas de **su** mundo. Si hace falta un dato nuevo
para diagnosticar algo, se **añade al informe** y se le pide que lo pegue; no se
adivina.

Corolario: **si un diagnóstico anterior era falso, se corrige en público**, en
el CHANGELOG. Ya se hizo una vez con los ríos.

---

## 9. Estilo del código

- Comentarios y nombres **en castellano**. Los identificadores que vienen del
  XML de DF se quedan en inglés (`hf_id`, `link_type`, `site_id`).
- Los comentarios explican **por qué**, no qué. Si un comentario se limita a
  repetir la línea, sobra.
- Nada de dependencias nuevas sin una razón fuerte. Ahora mismo son cuatro:
  `fastapi`, `uvicorn`, `python-dotenv`, `anthropic`.
- Las funciones de la interfaz devuelven elementos, no cadenas de HTML: así no
  hay que preocuparse de escapar nada.

---

## 10. Dónde mirar antes de empezar

- `ROADMAP.md` — qué toca después y por qué en ese orden.
- `CHANGELOG.md` — qué se hizo en cada versión y qué se arregló.
- `docs/referencia-legendsviewer.md` — análisis de LegendsViewer-Next, de donde
  salen varias ideas del plan y la lista de tipos de suceso.
