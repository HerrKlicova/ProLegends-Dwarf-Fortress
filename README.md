# ProLegends

Explorador local del archivo de leyendas (*legends XML*) de **Dwarf Fortress**.
Subes los exports de cualquier mundo, la aplicación los procesa una vez y a
partir de ahí exploras el mapa año a año, las figuras históricas y tu fortaleza
desde el navegador.

No sube nada a internet: todo se queda en tu ordenador. La única excepción son
las crónicas narradas, y solo cuando tú las pides expresamente.

El historial de versiones, con lo que cambia en cada una, está en
[CHANGELOG.md](CHANGELOG.md).

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

Descomprímela y doble clic. **No hay que copiar nada.**

Desde la 1.3.1 tus crónicas, tu clave, tus ajustes y tu base de datos viven en
`Documentos\ProLegends`, fuera del programa, así que la versión nueva los
encuentra sola y no hay que reimportar los 45 MB. La carpeta de la versión
vieja se puede borrar entera.

(Si vienes de la 1.3.0 o anterior, la primera vez que arranques se traslada
todo solo, y las crónicas se copian dejando las originales de respaldo.)

---

## Cómo se usa (Windows)

1. **Doble clic en `start.bat`.**

2. Pulsa **Importar exports** y, en *Desde Dwarf Fortress*, pulsa
   **Buscar Dwarf Fortress**. La aplicación encuentra el juego, te enseña los
   exports que tienes dentro y se los trae ella misma.

Eso es todo. La primera vez tarda un poco porque prepara el entorno de Python.
Después: ordena los ficheros, importa los exports nuevos (con barra de
progreso), arranca el servidor y abre el navegador solo.

Deja abierta la ventana negra mientras uses la aplicación. Para cerrarla, ciérrala
o pulsa `Ctrl+C`.

En macOS el equivalente es `start.command` (doble clic) y en Linux
`./start.sh`.

### Traer los exports desde el juego

Al exportar las leyendas, Dwarf Fortress **deja los dos XML junto a su
ejecutable**, mezclados con las DLL:

```
D:\Steam\steamapps\common\Dwarf Fortress\
├── Dwarf Fortress.exe
├── region1-00103-10-15-legends.xml         (el principal, unos 45 MB)
└── region1-00103-10-15-legends_plus.xml    (el extra de DFHack, unos 13 MB)
```

En la ventana de **Importar exports**, el apartado *Desde Dwarf Fortress* se
encarga de todo:

- **Buscar Dwarf Fortress** mira el registro de Steam, sus bibliotecas de otros
  discos y los sitios habituales fuera de Steam. No rastrea el disco entero.
- Si no lo encuentra, **Elegir la carpeta a mano** abre el diálogo de carpetas
  de Windows. También puedes pegar la ruta en la casilla.
- Verás la lista de exports con su mundo, su año y su tamaño. Marcas los que
  quieras y **Traer los marcados** los copia a tu carpeta de exports.
- **Se copian, no se mueven**: los originales siguen en la carpeta del juego.
- La carpeta se recuerda, así que esto se hace una sola vez. Queda apuntada en
  `data/ajustes.json`, que no sube a GitHub porque solo vale para tu ordenador.

**Si prefieres hacerlo a mano**, sigue funcionando igual que siempre: copia los
dos ficheros a `Documentos\ProLegends\imports\` y pulsa **Importar exports**.
Da igual cómo se
llamen; la aplicación los ordena sola (ver abajo).

### Dónde vive lo tuyo

Tus cosas **no están dentro de la carpeta del programa**, sino aquí:

```
Documentos\ProLegends\
├── imports/       los XML de leyendas
├── db/            la base de datos (se regenera importando)
├── cronicas/      las crónicas narradas, un fichero de texto cada una
├── ajustes.json   dónde tienes Dwarf Fortress, cuál es tu fortaleza
└── .env           tu clave de la API
```

Se hace así para que **bajar una versión nueva no te obligue a copiar nada**:
descomprimes, doble clic, y ahí siguen tus crónicas, tus mundos ya importados y
tu clave. La carpeta del programa se puede borrar entera sin perder nada.

La primera vez que arrancas una versión 1.3.2 o posterior, tus cosas se
trasladan solas: busca dentro de esta copia y también en las copias anteriores
de ProLegends que tengas al lado, en Descargas, en el Escritorio o en
Documentos. Las crónicas **se copian**, así que las antiguas se quedan de
respaldo donde estaban, y en la ventana negra te dice de dónde ha sacado cada
cosa.

Si prefieres tenerlo en otro sitio (un disco externo, un pincho USB), define la
variable de entorno `PROLEGENDS_HOME` con la ruta que quieras.

### Recuperar el proyecto en otro ordenador

```
git clone https://github.com/HerrKlicova/ProLegends-Dwarf-Fortress.git
```

Entra en la carpeta y haz doble clic en `start.bat`. Si ese ordenador ya tenía
ProLegends, no hay que hacer nada más: tus crónicas, tu clave y tus mundos están
en `Documentos\ProLegends` y los encuentra solo. Si es un ordenador nuevo, pon
tu clave en el `.env` y trae los exports desde la carpeta de Dwarf Fortress.

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
Documentos/ProLegends/imports/
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
Un atlas de pergamino del mundo entero, **dibujado a partir de tus XML**. No hace
falta que exportes mapas detallados ni que copies ninguna imagen del juego.

- **Mar, costa y biomas de verdad.** El `_legends_plus.xml` trae la lista de
  casillas que ocupa cada región y el principal dice cómo se llama y de qué tipo
  es; cruzando las dos cosas sale el mundo casilla a casilla, sin un solo hueco,
  así que la costa es exacta. Las montañas se dibujan como montañas, los bosques
  como árboles y los desiertos con sus dunas.
- **Ríos, calzadas, puentes, túneles y picos con nombre**, cada uno con su trazo.
- **Deslizador de año**: al moverlo, el mapa muestra el estado del mundo en ese
  año — quién poseía cada sitio entonces, qué estaba en ruinas y qué bestias
  seguían vivas y dónde. El botón ▶ recorre la historia entera sola.
- **Zoom y desplazamiento**: rueda para acercar, arrastrar para mover, doble clic
  para encajar el mundo entero. Los nombres van apareciendo al acercarte, y se
  apartan entre ellos para que no se amontonen.
- **Capas conmutables**: asentamientos, ruinas, guaridas de bestias, torres y
  sitios de nigromantes, bóvedas y sitios misteriosos, cuevas y tumbas.
- **Colores por raza y facción**, repartidos a partir de las razas que existan en
  ese mundo concreto.
- **Clic en un sitio** → ficha lateral: tipo, propietarios a lo largo del tiempo,
  estructuras, artefactos, figuras vinculadas y todos los eventos ocurridos allí.

Si a un export le faltan las coordenadas de las regiones, **no se inventa una
costa**: se dice que no se puede dibujar y por qué, y el mapa se queda en la
rejilla de siempre.

### Todo se cuenta en castellano

Los sucesos no se enseñan como los escribe Dwarf Fortress, sino contados:

> **159** — Iden Craftshailed murió por un golpe a manos de Uthhkos Lusbomith
> en Kolluslan.

Hay narración para 127 tipos de suceso y un diccionario de 418 términos (tipos
de sitio, causas de muerte, cargos, vínculos, oficios, habilidades, esferas,
biomas...). Con dos reglas: **no se inventa nada** —si el archivo no lo dice, la
frase no lo dice— y **no se esconde nada** —lo que no tiene traducción se enseña
tal cual, y el dato original está siempre a un clic con el interruptor *ver
también el dato en bruto*—.

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
- **Cada crónica se guarda como un fichero de texto** en `Documentos/ProLegends/cronicas/<mundo>/`.
  Se pueden leer con el Bloc de notas sin abrir el programa, y **no se pierden
  al borrar la base de datos**. La pestaña las agrupa por rangos de años,
  figuras históricas y lugares.
- Antes de cada llamada **avisa de que va a consumir API** y dice cuántos hechos y
  cuánto contexto va a enviar.
- El resultado queda **guardado**: volver a pedir la misma crónica no cuesta nada.
  Solo se regenera si lo pides expresamente.

---

## Detalles del formato que la aplicación resuelve sola

Los XML de legends tienen varias trampas. Están todas contempladas:

| Problema | Solución |
|---|---|
| Unos exports vienen en **CP437** y otros en **UTF-8** | Se mira el contenido de los primeros bytes para saber cuál es, sin fiarse de lo que el fichero declare, y todo se reentrega en UTF-8 |
| **Bytes de control C0** dentro de los nombres | Se traducen a su símbolo real de CP437 (el `0x0F` es el ☼ de los objetos de calidad), en vez de borrarlos y perder el nombre |
| 45 MB no caben con `ET.parse()` | `iterparse` en streaming, liberando cada registro procesado: la memoria se mantiene plana |
| Unos exports usan `<name>` y otros `<n>` | Se aceptan las dos |
| El `_plus` complementa al principal | Se fusionan por ID: el principal da el nombre, el `_plus` la raza, el tipo, los secretos y las tramas |
| La propiedad de un sitio no es un campo | Se reconstruye recorriendo los eventos por año (`created site`, `site taken over`, `destroyed site`, `hf destroyed site`) y se guarda el histórico completo, que es lo que alimenta el deslizador |
| Las entidades forman jerarquías | Se sube por la cadena de `<child>` hasta la civilización raíz |
| El tamaño del mundo varía | Se deduce de las coordenadas observadas (regiones y sitios), no se asume ninguno |
| El XML no trae ningún mapa | Se reconstruye con las casillas que declara cada región, que cubren el mundo entero |
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
    discover.py    empareja los ficheros de la carpeta de exports
    organizer.py   renombra y ordena por mundo y fecha
    legends.py     extracción de campos
    importer.py    orquesta la importación a SQLite
  model/       lo que hay que deducir
    entities.py    jerarquía de entidades
    ownership.py   propiedad de los sitios año a año
    fortress.py    detección, resumen, diff y avisos de tu fortaleza
    terreno.py     rejilla de biomas, ríos y calzadas del mundo
  api/         endpoints HTTP              (la interfaz solo habla con esto)
  ai/          crónicas narradas
  juego.py     encuentra la carpeta de Dwarf Fortress y trae sus exports
  ajustes.py   lo que la aplicación recuerda entre arranques
  mudanza.py   traslada tus cosas fuera del programa la primera vez
  schema.sql   esquema de la base de datos
web/           interfaz: HTML, CSS y JavaScript a pelo, sin compilar nada
tools/         utilidades sueltas

Documentos/ProLegends/   (fuera del programa, para que sobreviva a las actualizaciones)
  imports/     tus XML
  db/          la base de datos generada
  cronicas/    las crónicas de IA, un fichero de texto por crónica
  ajustes.json dónde tienes el juego y demás
  .env         tu clave de la API
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

No hacen falta para el uso normal —**todo lo importante está en la interfaz**—
pero están. En Windows se ejecutan con `venv\Scripts\python` desde la carpeta
del programa; en macOS y Linux, con `venv/bin/python`:

```
python -m app.cli geografia       vuelca qué traen los XML sobre el mapa
                                  (o el botón "¿El mapa no cuadra?" del mapa)
python -m app.cli juego           busca Dwarf Fortress y enseña sus exports
python -m app.cli juego --traer   copia a tu carpeta de exports los que falten
python -m app.cli diagnostico     dice qué ve la aplicación en cada fichero
python -m app.cli ordenar         renombra y ordena tus XML por mundo y fecha
python -m app.cli importar        procesa los XML nuevos y vuelca a SQLite
python -m app.cli listar          muestra los mundos y exports importados
python -m app.cli servidor        arranca solo el servidor
python -m app.cli reiniciar-bd    borra la base de datos (los XML no se tocan)
```

Para probar sin tener a mano tus ficheros de 45 MB:

```
python tools/make_sample_export.py "%USERPROFILE%\Documents\ProLegends\imports"
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
- **Quiero empezar de cero**: borra la carpeta `db/` de `Documentos\ProLegends`
  y vuelve a arrancar. Las crónicas no se tocan.
- **Aparecen mundos raros, o dice que falta el `_plus` estando ahí**: casi
  siempre es que los dos ficheros del export llegaron con nombres distintos.
  Ejecuta `python -m app.cli diagnostico`: dice, fichero a fichero, qué mundo
  ha leído y qué parejas ha reconocido. Si los mundos duplicados vienen de
  pruebas anteriores, borra la carpeta `db/` de `Documentos\ProLegends` y
  vuelve a importar.

Los exports ya importados no se reprocesan: puedes dejar todos los ficheros en
tu carpeta de exports sin miedo. Si vuelves a exportar la misma fecha del mismo mundo
con contenido distinto, el nuevo sustituye al anterior en lugar de duplicarlo.

### Sobre los ficheros sin pareja

Un `-legends_plus.xml` suelto se ignora con un aviso: por sí solo no sirve de
nada. Un `-legends.xml` suelto **sí se importa**, también con un aviso, porque un
export sin DFHack es perfectamente utilizable; lo único que pierdes son los datos
extra del `_plus` (raza y tipo de entidad, secretos y tramas de intriga). Los
ficheros `.xml` que no acaben en `-legends.xml` ni en `-legends_plus.xml` se
ignoran con un aviso por consola.
