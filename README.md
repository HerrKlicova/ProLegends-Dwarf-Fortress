# ProLegends

Explorador local del archivo de leyendas (*legends XML*) de **Dwarf Fortress**.
Subes los exports de cualquier mundo, la aplicación los procesa una vez y a
partir de ahí exploras el mapa año a año, las figuras históricas y tu fortaleza
desde el navegador.

No sube nada a internet: todo se queda en tu ordenador. La única excepción son
las crónicas narradas, y solo cuando tú las pides expresamente.

---

## Descargar

No hace falta saber nada de git ni instalar herramientas raras.

**[⬇ Descargar el proyecto (ZIP)](https://github.com/HerrKlicova/ProLegends-Dwarf-Fortress/archive/refs/heads/main.zip)**

Este repositorio es **privado**, así que el enlace te pedirá iniciar sesión en
GitHub con la cuenta que lo creó. Es normal. Si prefieres no usar el enlace:
entra en el repositorio, pulsa el botón verde **Code** y elige **Download ZIP**.

Descomprime el ZIP donde quieras. Es el mismo para Windows, macOS y Linux: no
hay versiones distintas del programa, solo cambia el fichero con el que se
arranca.

| Sistema | Fichero al que haces doble clic |
|---|---|
| Windows | `start.bat` |
| macOS | `start.command` |
| Linux | `start.sh` (o `bash start.sh` desde la terminal) |

### Dos avisos de la primera vez

- **Windows** puede sacar una pantalla azul de *Windows protegió tu PC* al
  abrir `start.bat`, porque es un archivo bajado de internet. Pulsa
  **Más información** y luego **Ejecutar de todas formas**. Solo pasa una vez.
- **macOS** puede decir que no puede abrir `start.command` por venir de un
  desarrollador no identificado. Pulsa el fichero con el **botón derecho**,
  elige **Abrir** y confirma. También es solo la primera vez. Si aun así no
  arranca, abre la aplicación **Terminal**, escribe `bash ` (con el espacio),
  arrastra el fichero `start.sh` a la ventana y pulsa Intro.

### Si más adelante bajas una versión nueva

Descomprímela en una carpeta aparte y **copia a la carpeta nueva estas dos
cosas de la vieja**, si las tienes:

- el fichero `.env` (tu clave de la API)
- la carpeta `data/db/` (la base de datos, para no reimportar los 45 MB)

Los XML de `data/imports/` puedes copiarlos también, o volver a dejarlos ahí.

---

## Cómo se usa (Windows)

1. Copia en la carpeta `data/imports/` los ficheros que genera Dwarf Fortress al
   exportar las leyendas. Son dos por export:

   ```
   region1-00101-07-24-legends.xml         (el principal, unos 45 MB)
   region1-00101-07-24-legends_plus.xml    (el extra de DFHack, unos 13 MB)
   ```

   Da igual cómo se llamen: la aplicación los ordena sola (ver abajo).

2. **Doble clic en `start.bat`.**

Eso es todo. La primera vez tarda un poco porque prepara el entorno de Python.
Después: ordena los ficheros, importa los exports nuevos (con barra de
progreso), arranca el servidor y abre el navegador solo.

Deja abierta la ventana negra mientras uses la aplicación. Para cerrarla, ciérrala
o pulsa `Ctrl+C`.

En macOS el equivalente es `start.command` (doble clic) y en Linux
`./start.sh`.

### Recuperar el proyecto en otro ordenador

```
git clone https://github.com/HerrKlicova/ProLegends-Dwarf-Fortress.git
```

Entra en la carpeta, copia ahí tu fichero `.env` (o duplica `.env.example` como
`.env` y pega tu clave) y haz doble clic en `start.bat`. Los exports XML y la base
de datos no viajan en el repositorio: vuelve a dejar los XML en `data/imports/` y
la aplicación los reimporta sola.

Si no quieres saber nada de git, baja simplemente el ZIP del apartado
**Descargar** de arriba: es exactamente lo mismo.

---

## Los ficheros se ordenan solos

Dwarf Fortress nombra los exports con el nombre de la **carpeta de la partida**,
que no dice nada:

```
region1-00101-07-24-legends.xml
region4-00023-11-02-legends.xml
```

La aplicación lee el nombre real del mundo —está en los primeros bytes del XML,
así que no hace falta leerse los 45 MB— y los deja así:

```
data/imports/
├── momuzosith/
│   ├── momuzosith-00101-07-24-legends.xml
│   └── momuzosith-00101-07-24-legends_plus.xml
└── tegurxosal/
    ├── tegurxosal-00023-11-02-legends.xml
    └── tegurxosal-00023-11-02-legends_plus.xml
```

Pasa solo al arrancar con `start.bat`. Desde la interfaz, el botón
**Importar exports** te enseña antes qué va a renombrar y puedes desmarcarlo.

**No se pierde nada.** Las reglas son:

- Los dos ficheros de un export se reconocen como pareja **aunque tengan
  nombres distintos**: basta con que estén en la misma carpeta y sean de la
  misma fecha. Esto pasa a menudo, porque al copiarlos o subirlos cada uno
  puede acabar con una marca de tiempo distinta delante.
- El mundo se decide **una vez por pareja**, mirando primero el fichero
  principal. El `_plus` de DFHack anuncia el nombre traducido del mundo en vez
  del interno, así que si cada fichero decidiese por su cuenta acabarían en
  carpetas distintas.
- Nunca se sobrescribe un fichero. Si el nombre nuevo ya estuviera cogido por
  otro fichero distinto, ese export se deja tal cual y te lo dice.
- Nunca se borra nada.
- Los dos ficheros de un export se mueven juntos: o los dos, o ninguno.
- Un `.xml` que no sea un export de legends no se toca.
- Renombrar un export **ya importado no obliga a reprocesarlo**: la base de
  datos se reapunta sola al nombre nuevo.

También desde la terminal, si prefieres verlo antes:

```
python -m app.cli ordenar             enseña qué haría, sin tocar nada
python -m app.cli ordenar --aplicar   lo hace
python -m app.cli ordenar --aplicar --sin-carpetas   renombra sin crear carpetas
```

---

## Qué puedes hacer

### Mapa del mundo
Rejilla del tamaño real del mundo (deducido de las coordenadas de los sitios, no
supuesto), con todos los sitios colocados.

- **Deslizador de año**: al moverlo, el mapa muestra el estado del mundo en ese
  año — quién poseía cada sitio entonces, qué estaba en ruinas y qué bestias
  seguían vivas y dónde. El botón ▶ recorre la historia entera sola.
- **Capas conmutables**: asentamientos, ruinas, guaridas de bestias, torres y
  sitios de nigromantes, bóvedas y sitios misteriosos, cuevas y tumbas.
- **Colores por raza y facción**, repartidos a partir de las razas que existan en
  ese mundo concreto.
- **Clic en un sitio** → ficha lateral: tipo, propietarios a lo largo del tiempo,
  estructuras, artefactos, figuras vinculadas y todos los eventos ocurridos allí.

### Figuras históricas
Buscador por nombre, con filtros de raza y de vivas/muertas. La ficha trae raza,
sexo, nacimiento, muerte y cómo murió, entidades a las que pertenece y pertenecía,
cargos, deidades y esferas, habilidades, secretos conocidos, artefactos que posee,
objetivos vitales y tramas de intriga. Todo enlazado: desde una figura saltas a
sitios, entidades y otras figuras. Incluye el ranking de **quién mató a quién**.

### Mi fortaleza
Detecta sola cuál es tu fortaleza (un sitio que aparece en un export y no estaba
en el anterior, o cuyo gobierno se creó en el año más reciente). Si hay duda, la
eliges a mano una vez y se recuerda.

- Resumen: año de fundación, censo, habitantes vivos y muertos, artefactos creados
  allí, caravanas recibidas y ataques registrados.
- **Novedades entre exports**: al importar un export nuevo del mismo mundo, muestra
  qué ha cambiado desde el anterior — artefactos nuevos, muertes, llegadas,
  ataques cerca y reclamaciones sobre tus artefactos.
- Avisos automáticos: sitios hostiles a menos de X casillas, megabestias vivas
  cercanas y guerras activas de tu civilización.

### Crónicas narradas (opcional, consume API)
Botones de *generar crónica* en tres sitios: un rango de años, una figura concreta
y tu fortaleza. La aplicación selecciona los hechos relevantes, los resume y le
pide a Claude que redacte una crónica en castellano con tono de texto histórico,
sin inventarse nada que no esté en los datos.

- La clave se lee de `.env` (nunca está en el código). Copia `.env.example` a
  `.env` y pon ahí tu `ANTHROPIC_API_KEY`.
- Antes de cada llamada **avisa de que va a consumir API** y dice cuántos hechos y
  cuánto contexto va a enviar.
- El resultado queda **guardado**: volver a pedir la misma crónica no cuesta nada.
  Solo se regenera si lo pides expresamente.

---

## Detalles del formato que la aplicación resuelve sola

Los XML de legends tienen varias trampas. Están todas contempladas:

| Problema | Solución |
|---|---|
| El XML viene en **CP437**, no en UTF-8 | Se decodifica como cp437 y se reentrega en UTF-8, reescribiendo la declaración del XML |
| **Bytes de control C0** dentro de los nombres | Se traducen a su símbolo real de CP437 (el `0x0F` es el ☼ de los objetos de calidad), en vez de borrarlos y perder el nombre |
| 45 MB no caben con `ET.parse()` | `iterparse` en streaming, liberando cada registro procesado: la memoria se mantiene plana |
| Unos exports usan `<name>` y otros `<n>` | Se aceptan las dos |
| El `_plus` complementa al principal | Se fusionan por ID: el principal da el nombre, el `_plus` la raza, el tipo, los secretos y las tramas |
| La propiedad de un sitio no es un campo | Se reconstruye recorriendo los eventos por año (`created site`, `site taken over`, `destroyed site`, `hf destroyed site`) y se guarda el histórico completo, que es lo que alimenta el deslizador |
| Las entidades forman jerarquías | Se sube por la cadena de `<child>` hasta la civilización raíz |
| El tamaño del mundo varía | Se deduce de las coordenadas observadas, no se asume ninguno |
| `&` sueltos sin escapar | Se escapan antes de parsear |

Nada está fijado a un mundo concreto: ni identificadores, ni nombres de
civilizaciones, ni tamaño de mapa. Puedes tener varios mundos y varias fechas del
mismo mundo a la vez, y elegir en el desplegable de arriba.

---

## Cómo está montado por dentro

```
app/
  parser/      XML -> registros            (lo único que sabe de etiquetas XML)
    xmlstream.py   lectura tolerante y en streaming
    discover.py    empareja los ficheros de data/imports/
    organizer.py   renombra y ordena por mundo y fecha
    legends.py     extracción de campos
    importer.py    orquesta la importación a SQLite
  model/       lo que hay que deducir
    entities.py    jerarquía de entidades
    ownership.py   propiedad de los sitios año a año
    fortress.py    detección, resumen, diff y avisos de tu fortaleza
  api/         endpoints HTTP              (la interfaz solo habla con esto)
  ai/          crónicas narradas
  schema.sql   esquema de la base de datos
web/           interfaz: HTML, CSS y JavaScript a pelo, sin compilar nada
data/
  imports/     tus XML (no van al repositorio)
  db/          la base de datos generada (no va al repositorio)
tools/         utilidades sueltas
```

El flujo es siempre en un sentido: **parser → modelo de datos → API interna →
vistas**. El XML se lee una vez; después todo son consultas a SQLite.

Cada tabla guarda además un `data_json` con el registro completo tal cual venía
del XML, y las secciones que todavía no tienen tabla propia caen en
`raw_records`. Así se pueden añadir vistas que lean campos que hoy no se usan
**sin volver a tocar el parser ni reimportar**.

### Cómo añadir una vista nueva

Tres pasos, sin tocar nada del parseo:

1. **Endpoint.** Crea `app/api/mi_vista.py` con un `APIRouter`, consulta lo que
   necesites de SQLite y devuelve un diccionario. Regístralo en
   `app/api/__init__.py` con `router.include_router(mi_vista.router)`.

2. **Página.** Añade la sección en `web/index.html` (una `<section
   id="vista-mivista" class="vista oculta">` y un botón en la barra de pestañas
   con `data-vista="mivista"`), y crea `web/js/mivista.js` con un objeto que
   exponga `cargar()`. Enlázalo con un `<script>` al final del HTML.

3. **Conectar.** En `web/js/app.js`, dentro de `asegurarVista()`, añade la línea
   `else if (vista === 'mivista') await MiVista.cargar();`.

Y en `web/js/api.js` una línea con la ruta nueva, para que todas las llamadas
sigan pasando por el mismo sitio y los errores se muestren igual.

Cosas que ya están preparadas para crecer así: grafo de relaciones entre personas
(tabla `hf_links`), grafo de transmisión de secretos (`hf_traits` con `kind =
'secreto'`), red de conspiraciones (`hf_plots`, de los `intrigue_plot`) y
superposición de los mapas `.bmp` que DF exporta aparte (las coordenadas y el
tamaño del mundo ya están en `exports`).

---

## Comandos sueltos

No hacen falta para el uso normal, pero están:

```
python -m app.cli diagnostico     dice qué ve la aplicación en cada fichero
python -m app.cli ordenar         renombra y ordena los XML de data/imports/
python -m app.cli importar        procesa data/imports/ y vuelca a SQLite
python -m app.cli listar          muestra los mundos y exports importados
python -m app.cli servidor        arranca solo el servidor
python -m app.cli reiniciar-bd    borra la base de datos (los XML no se tocan)
```

Para probar sin tener a mano tus ficheros de 45 MB:

```
python tools/make_sample_export.py data/imports
```

genera dos exports de mentira de un mundo inventado, con las mismas trampas de
formato que los de verdad (el segundo contiene todo lo del primero más lo
ocurrido después, igual que hace Dwarf Fortress).

Y para comprobar de una vez que todo funciona de principio a fin:

```
python tools/autocomprobacion.py
```

Genera dos mundos, los importa, comprueba las trampas del formato, la jerarquía
de entidades, la propiedad año a año, las consultas de la interfaz, el diff entre
exports, el manejo de un XML corrupto y que la ordenación de ficheros no pisa
nada ni obliga a reimportar. Termina diciendo `RESULTADO: todo
correcto` o listando lo que falla.

---

## Si algo va mal

- **No se abre el navegador**: entra tú a `http://127.0.0.1:8420/`. Si el puerto
  está ocupado, cámbialo en `.env` (`PROLEGENDS_PORT`).
- **"No se ha encontrado Python"**: instálalo desde python.org y marca la casilla
  *Add python.exe to PATH* durante la instalación.
- **Un export da error de XML corrupto**: la aplicación lo dice en pantalla y
  sigue con los demás. Vuelve a exportar las leyendas desde el juego.
- **Quiero empezar de cero**: borra la carpeta `data/db/` y vuelve a arrancar.
- **Aparecen mundos raros, o dice que falta el `_plus` estando ahí**: casi
  siempre es que los dos ficheros del export llegaron con nombres distintos.
  Ejecuta `python -m app.cli diagnostico`: dice, fichero a fichero, qué mundo
  ha leído y qué parejas ha reconocido. Si los mundos duplicados vienen de
  pruebas anteriores, borra `data/db/` y vuelve a importar.

Los exports ya importados no se reprocesan: puedes dejar todos los ficheros en
`data/imports/` sin miedo. Si vuelves a exportar la misma fecha del mismo mundo
con contenido distinto, el nuevo sustituye al anterior en lugar de duplicarlo.

### Sobre los ficheros sin pareja

Un `-legends_plus.xml` suelto se ignora con un aviso: por sí solo no sirve de
nada. Un `-legends.xml` suelto **sí se importa**, también con un aviso, porque un
export sin DFHack es perfectamente utilizable; lo único que pierdes son los datos
extra del `_plus` (raza y tipo de entidad, secretos y tramas de intriga). Los
ficheros `.xml` que no acaben en `-legends.xml` ni en `-legends_plus.xml` se
ignoran con un aviso por consola.
