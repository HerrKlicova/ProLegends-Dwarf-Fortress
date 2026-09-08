# Registro de versiones

Todas las versiones de ProLegends, de la más reciente a la más antigua.

La numeración es `MAYOR.MENOR.PARCHE`:

- **PARCHE** (1.1.0 → 1.1.**1**): solo se arreglan fallos.
- **MENOR** (1.0.0 → 1.**1**.0): se añade algo nuevo, y lo de antes sigue funcionando igual.
- **MAYOR** (1.1.0 → **2**.0.0): algo cambia de forma que obliga a rehacer cosas.

---

## v1.4.1 — Los ríos dejan de cruzar el mundo de punta a punta

*Arreglo del mapa, encontrado en cuanto se probó con un mundo de verdad.*

**Arreglado**

- **Los ríos y las calzadas salían como un abanico de rayas** que atravesaba el
  mapa entero. El motivo: yo daba por hecho que las casillas de un río venían
  en el orden en que se recorre, y en los exports reales **no** es así — vienen
  como "las casillas que ocupa esto", ordenadas por filas. Unirlas por orden de
  lista trazaba una raya en cada salto. En mi mundo de pruebas el río sí era un
  recorrido ordenado, y por eso no se veía.
- Ahora **se reconstruye la red**: se mira qué casillas se tocan y se siguen las
  cadenas. Lo que no se toca, no se une. Funciona igual si el export las trae
  ordenadas que si las trae por filas.
- **Lo que cae fuera del mundo se descarta** en lugar de dibujarse fuera del
  marco.
- **Los sellos de los sitios se pisaban unos a otros** en un mundo poblado.
  Ahora caben en su casilla, con el halo más fino.
- **Los nombres salían amontonados e ilegibles.** Ahora solo aparecen cuando de
  verdad hay sitio para leerlos; por debajo de eso, hay que acercarse.

**Añadido**

- **Leyenda del terreno** en el panel de la izquierda: qué biomas hay en tu
  mundo, con qué color se ha pintado cada uno y qué porcentaje ocupa.
- Si aparece un tipo de terreno que todavía no tiene dibujo propio, **se dice**
  debajo del mapa y se pinta liso, en vez de disfrazarlo de otra cosa.
- La autocomprobación ahora prueba también el dibujo del mapa (con `node`, si
  lo tienes instalado): que un río desordenado se reconstruya, que dos tramos
  separados no se unan, que ningún tramo salte más de una casilla y que lo de
  fuera del mundo se descarte. El export de prueba escribe ahora los ríos por
  filas, como los de verdad, para no volver a probar contra un caso más fácil
  que el real.

---

## v1.4.0 — El mapa, dibujado con tus datos

*La grande. El mapa deja de ser una cuadrícula de puntos.*

Hasta ahora el mapa era funcional pero era un diagrama: cuadraditos de colores
flotando en negro. Ahora es un **atlas de pergamino**, con su mar, su costa, sus
montañas y sus ríos.

**Y sale entero de los XML que ya importas.** No hace falta que exportes mapas
detallados ni que copies ninguna imagen del juego: el `_legends_plus.xml` trae la
lista de casillas que ocupa cada región y el principal dice cómo se llama cada
una y de qué tipo es. Cruzando las dos cosas sale el mundo entero, casilla a
casilla, sin un solo hueco. Por eso la costa es exacta y no una aproximación.

**Añadido**

- **Mar y tierra de verdad**, con la costa dibujada a tinta y las líneas
  paralelas a la orilla de las cartas antiguas.
- **Cada bioma con su color y su símbolo**: las montañas se dibujan como
  montañas, con su ladera sombreada; los bosques como grupos de árboles; las
  selvas más tupidas; los desiertos punteados con sus dunas; las lomas,
  los pantanos, la estepa, la tundra y los glaciares, cada uno con el suyo.
- **Ríos** trazados como líneas curvas, no como escaleras de casillas, y más
  gruesos cuanto más largo es su curso.
- **Calzadas, puentes y túneles**, cada uno con su trazo.
- **Picos con nombre**, con su nieve o su boca de volcán si el export dice que
  es un volcán.
- **Zoom y desplazamiento**: rueda para acercar, arrastrar para mover, doble
  clic para volver a encajar el mundo entero. Los símbolos y el grosor de la
  pluma no crecen al ampliar, como en un atlas de papel: lo que cambia es
  cuánto terreno cabe.
- **Los nombres aparecen al acercarte**, y se apartan entre ellos: antes que
  amontonar etiquetas ilegibles, se deja alguna sin poner, empezando por las
  menos importantes.
- **Cartela** con el nombre del mundo y el año que estás mirando, **rosa de los
  vientos**, **escala** en casillas y marco.
- Los sitios ya no son cuadrados: cada clase tiene su silueta (casa, torre,
  boca de cueva, tumba) sellada en tinta con un halo de papel para que se lea
  sobre cualquier terreno, y las ruinas son dos muros caídos.
- **El deslizador de año encaja de maravilla**: la geografía se dibuja una sola
  vez y se reutiliza, así que recorrer los años cuesta 0,3 milésimas de segundo
  por fotograma aunque el mapa sea un dibujo completo.

**Arreglado**

- **El tamaño del mundo estaba mal.** Se deducía solo de dónde había sitios, y
  eso se queda corto: en un mundo hay mar y montaña donde no vive nadie. Ahora
  lo dicen las regiones, que sí cubren el mundo entero. Se corrige solo al
  arrancar, sin reimportar nada.

**Lo que no se hace, a propósito**

- Si tu export no trae las coordenadas de las regiones (por ejemplo si te falta
  el `_legends_plus.xml`), **no se dibuja una costa inventada**: se dice que no
  se puede y se explica por qué, y el mapa se queda como estaba.
- Dwarf Fortress no da la altura de cada casilla en las leyendas, así que el
  relieve se representa con símbolos de montaña y loma, que es lo que los datos
  permiten decir, en vez de con un sombreado inventado.

**No hay que reimportar nada.** Todo esto estaba ya guardado desde la primera
importación; solo hacía falta saber leerlo.

---

## v1.3.2 — La mudanza mira también en la versión anterior

*Arreglo del arreglo de la 1.3.1.*

**Arreglado**

- **La mudanza automática no encontraba nada.** Buscaba solo dentro de su
  propia carpeta, cosa que funciona si actualizas sobrescribiendo, pero no si
  descomprimes la versión nueva en una carpeta aparte, que es lo normal y lo
  que dice el propio README: las crónicas de la versión anterior estaban en
  otra carpeta de la que la nueva no sabía nada.
- Ahora **busca también las copias anteriores de ProLegends** que haya al lado,
  en Descargas, en el Escritorio y en Documentos, y rescata de ellas lo que te
  falte. Sigue sin tocar el disco entero: solo mira carpetas cuyo nombre lleve
  "ProLegends" y que de verdad tengan un ProLegends dentro.
- Si encuentra varias, empieza por la más reciente y las repasa todas, así que
  no se pierde nada aunque tengas tres versiones sueltas por ahí.
- Como antes: **las crónicas se copian**, nunca se mueven, y las originales se
  quedan donde estaban de respaldo. Te dice en la ventana negra de qué carpeta
  ha sacado cada cosa.

---

## v1.3.1 — Actualizar deja de dar guerra

*Tres arreglos, todos de cosas que estorbaban al actualizar.*

**Arreglado: la interfaz se quedaba en la versión anterior**

Al bajar la 1.3.0 y abrirla, seguía saliendo la ventana de importar de la
versión vieja, sin el apartado *Desde Dwarf Fortress*. No era cosa tuya: el
servidor no le decía nada al navegador sobre la caché, y el navegador, como la
dirección es siempre la misma (`127.0.0.1`), reutilizaba el HTML y el
JavaScript que ya tenía guardados.

- Ahora la interfaz se sirve con `no-cache`: el navegador la sigue guardando,
  pero pregunta antes de usarla. Si no ha cambiado, el servidor responde "sigue
  igual" y no se transfiere nada. En local eso no cuesta nada.
- Por si acaso vuelve a pasar (un navegador raro, un antivirus por medio), la
  interfaz lleva escrita su propia versión y la compara con la del programa: si
  no coinciden, sale un aviso que te dice literalmente que pulses Ctrl+F5, en
  lugar de dejarte pensando que la actualización no ha hecho nada.
- **La versión se ve ahora arriba, al lado del nombre**, para poder mirarla de
  un vistazo.

**Arreglado: importar tardaba de más**

- Un export de 50 MB pasa de **32 a 9 segundos**. Los tuyos, que son algo más
  pequeños, deberían quedarse por debajo de eso.
- El motivo era tonto: las filas se escribían en tandas de 2000, pero cada
  tanda se confirmaba por su cuenta. Confirmar 244 veces costaba más que
  escribir. Ahora todo el volcado va en una sola operación.
- De regalo, si una importación falla a mitad ya no quedan filas sueltas de un
  export incompleto: o entra entero, o no entra nada.

**Arreglado: tenías que mover tus cosas a mano en cada versión**

Esto era lo más peligroso: bastaba con despistarse una vez para perder crónicas
que habían costado dinero.

- **Tus cosas ya no viven dentro de la carpeta del programa.** Ahora están en
  `Documentos\ProLegends`: las crónicas, la base de datos, tu clave de la API,
  los ajustes y los propios XML.
- Eso significa que **bajar una versión nueva ya no requiere copiar nada**.
  Descomprimes, doble clic, y ahí está todo: tus crónicas, tus mundos ya
  importados (sin reimportar los 45 MB) y tu clave.
- La mudanza se hace sola la primera vez que arrancas la 1.3.1. **Las crónicas
  se copian, no se mueven**: las de la carpeta vieja se quedan de respaldo. Los
  XML sí se mueven, porque pesan y no tiene sentido tenerlos por duplicado.
- La carpeta del programa se puede borrar entera sin miedo.
- Si prefieres tenerlo todo en otro sitio (un disco externo, un pincho), se
  puede cambiar con la variable de entorno `PROLEGENDS_HOME`.

---

## v1.3.0 — La aplicación va a buscar los exports al juego

*Función nueva.*

Hasta ahora había que ir a la carpeta de Dwarf Fortress, buscar los dos XML
entre las DLL del juego y arrastrarlos a `data/imports/`. Ya no.

**Añadido**

- **ProLegends encuentra sola dónde tienes instalado Dwarf Fortress.** Mira el
  registro de Steam, sus bibliotecas de otros discos (`libraryfolders.vdf`) y
  los sitios habituales fuera de Steam. No rastrea el disco entero: solo mira
  donde tiene sentido, así que tarda un instante.
- **Botón para elegir la carpeta a mano**, que abre el diálogo de carpetas de
  Windows de toda la vida, por si la detección falla o tienes el juego en un
  sitio raro. También se puede pegar la ruta directamente.
- **Listado de los exports que hay en la carpeta del juego**, con el nombre del
  mundo, el año de la partida, el tamaño y si ya lo tienes o no. Marcas los que
  quieras y se traen solos.
- **Se copian, no se mueven**: tus ficheros siguen intactos en la carpeta del
  juego. Si algo falla a mitad, se deshace lo copiado de ese export.
- **La carpeta se recuerda**, así que esto se configura una sola vez. Se guarda
  en `data/ajustes.json`, que no sube al repositorio porque solo vale para tu
  ordenador.
- La ventana de **Importar exports** se ha partido en dos partes claras:
  *Desde Dwarf Fortress* (de dónde salen los ficheros) y *En data/imports* (qué
  hay ya esperando a procesarse). Al traer un export, la segunda parte se
  actualiza sola.
- Nuevo comando de terminal, por si prefieres eso:

  ```
  python -m app.cli juego            busca el juego y enseña qué exports tiene
  python -m app.cli juego --traer    los copia a data/imports/
  python -m app.cli juego --carpeta "D:/Steam/steamapps/common/Dwarf Fortress"
  ```

- De paso se localizan las imágenes de mapa (`.bmp`) que el juego deje ahí. Aún
  no se usan; hará falta saberlo para el mapa nuevo.

**Sigue funcionando igual que antes**

Si prefieres copiar los ficheros a mano a `data/imports/`, todo va exactamente
como iba. Esto es un atajo, no un cambio de forma de trabajar.

---

## v1.2.1 — Los nombres con acentos dejan de salir rotos

*Arreglo.*

Al analizar exports reales por primera vez apareció un fallo que llevaba ahí
desde el principio.

**Arreglado**

- **Se detecta en qué está escrito el export en lugar de suponerlo.** Dwarf
  Fortress escribió durante años en CP437, pero los exports actuales de DFHack
  vienen en UTF-8. La aplicación daba CP437 por sentado, así que un nombre como
  `Olngö Horrordrain` se guardaba como `Olng├╢ Horrordrain`. En un solo export
  había 280 líneas afectadas.
- La detección **no se fía de lo que el fichero declare**, porque los hay que
  mienten: se comprueba el contenido. Si la muestra se decodifica como UTF-8
  estricto y tiene caracteres especiales, es UTF-8; si no, CP437.
- Se lee de forma incremental, de modo que un carácter partido entre dos trozos
  del fichero no se pierde.

**Si ya habías importado con la versión anterior**, borra `data/db/` y vuelve a
importar para que los nombres se guarden bien. Las crónicas de `data/cronicas/`
no se tocan.

---

## v1.2.0 — Las crónicas se guardan aparte y ordenadas

*Función nueva, y un arreglo importante.*

**Arreglado (importante)**

- **Las crónicas ya no viven dentro de la base de datos.** Estaban ahí, así que
  borrar `data/db/` —o ejecutar `reiniciar-bd`— se las llevaba por delante. Son
  lo único de la aplicación que cuesta dinero y que no se puede volver a
  obtener gratis, de modo que ahora se guardan aparte, como ficheros de texto
  en `data/cronicas/<mundo>/`.
- Las crónicas que ya tuvieras guardadas en la base de datos **se rescatan
  solas** al arrancar la versión nueva: no se pierde nada.
- `reiniciar-bd` avisa de que las crónicas no se tocan.

**Añadido**

- Cada crónica es un fichero `.md` con su cabecera (mundo, ámbito, modelo,
  fecha, tokens) y el texto debajo. **Se puede abrir con el Bloc de notas** sin
  abrir el programa, y para llevárselas a otro ordenador basta con copiar la
  carpeta.
- **La pestaña de crónicas se ha reorganizado.** A la izquierda, las guardadas
  agrupadas en *Rangos de años*, *Figuras históricas* y *Lugares y fortalezas*,
  cada grupo plegable y con su cuenta; a la derecha, la que elijas. Abrir una ya
  generada no cuesta nada.
- Debajo de cada crónica se indica en qué fichero está guardada.

---

## v1.1.4 — El aviso de la clave dice qué fichero ha leído

*Arreglos.*

Con la clave pegada en el Bloc de notas, la aplicación seguía diciendo que la
línea estaba vacía, y no había forma de saber por qué. Las dos causas se
confunden con facilidad: que el editor no haya guardado todavía, o que se esté
editando el `.env` de otra carpeta.

**Arreglado**

- El aviso dice ahora **cuántos caracteres ocupa el fichero que ha leído y
  cuándo se guardó por última vez**. Basta con comparar ese número con el que
  muestra el Bloc de notas abajo a la derecha: si no coinciden, los cambios no
  están guardados, o el fichero abierto es otro.
- El comando `diagnostico` muestra los mismos dos datos.

---

## v1.1.3 — La clave de la API se lee pase lo que pase

*Arreglos.*

Había tres formas de poner bien la clave y que la aplicación siguiera diciendo
que faltaba, sin explicar por qué.

**Arreglado**

- **Ya no hace falta reiniciar.** La clave se leía una sola vez al arrancar, así
  que si editabas el `.env` con el programa abierto, no se enteraba. Ahora se
  relee en el momento: pegas la clave, guardas, recargas la página y ya está.
- **El `.env.txt` del Bloc de notas.** Al guardar, el Bloc de notas añade `.txt`
  sin avisar; el fichero pasaba a llamarse `.env.txt` y la aplicación no lo veía
  ni decía nada. Ahora lo detecta y te dice que le cambies el nombre.
- **Otras codificaciones.** Si el fichero se guardaba como *Unicode* en vez de
  UTF-8, el arranque fallaba. Ahora se prueban varias codificaciones.
- Espacios de más y comillas alrededor de la clave ya no molestan.
- El aviso de la pantalla dice **exactamente** cuál de los casos anteriores es:
  que no existe el fichero, que existe pero la línea está vacía, que la línea no
  está, que sobra un `.env.txt`, o que la clave no tiene la pinta habitual.

**Añadido**

- `python -m app.cli diagnostico` dice ahora si encuentra la clave, en qué
  fichero, cuántos caracteres tiene y qué modelo va a usar. La clave sale
  tapada (solo el principio y el final), así que se puede pegar sin miedo.
- Cambiar el modelo en el `.env` también surte efecto sin reiniciar.

---

## v1.1.2 — Poner la clave de la API se explica sola

*Arreglos.*

Al ir a poner la clave de Anthropic no quedaba claro cuál de los dos ficheros
había que tocar ni dónde escribirla.

**Arreglado**

- Cuando falta la clave, el aviso dice ahora **la ruta completa del fichero**
  que hay que abrir y qué línea rellenar, en vez de "copia .env.example a .env".
  Y distingue dos casos: que el fichero no exista todavía, o que exista pero
  esté sin rellenar.
- `.env.example` explica en su primera línea que **es solo un ejemplo y no se
  edita**, que el fichero bueno es la copia llamada `.env`, y enseña cómo queda
  la línea de la clave una vez rellenada. Además ya lleva tildes.

---

## v1.1.1 — Ordenación con exports reales, y tildes

*Arreglos.*

Tres fallos que solo aparecieron al usar exports de verdad. Los tres están
reproducidos y tienen su propia prueba para que no vuelvan.

**Arreglado**

- **Los dos ficheros de un export no se reconocían como pareja si sus nombres
  no coincidían.** Al copiarlos o subirlos, cada uno puede acabar con una marca
  de tiempo distinta delante. La aplicación decía entonces que faltaba el
  `-legends_plus.xml` teniéndolo al lado, y lo descartaba. Ahora, si en una
  carpeta hay un principal suelto y un `_plus` suelto de la misma fecha, se
  emparejan. Con más de uno de cada no se adivina nada.
- **La pareja acababa partida en dos carpetas.** El `_plus` de DFHack anuncia el
  nombre traducido del mundo y el principal el interno, así que cada fichero se
  iba a la suya. Ahora el mundo se decide una sola vez por pareja, mirando
  primero el fichero principal.
- **En los exports sin nombre de mundo se colaba el nombre de la primera
  región.** El lector de cabecera cogía el primer `<name>` que encontrase. Ahora
  solo acepta las etiquetas que cuelgan directamente de `<df_world>`, y si no
  hay nombre de mundo lo dice en vez de inventarse uno. El importador, además,
  lo busca en la cabecera de los dos ficheros antes de recurrir al nombre del
  fichero.
- El aviso de que falta el `_plus` explica qué se pierde y qué hacer.

**Añadido**

- Todo el texto que se ve lleva ya sus tildes y sus eñes. La consola de Windows
  se pasa a UTF-8 al arrancar, y si aun así no pudiera, se sustituye el carácter
  por `?` en vez de fallar.
- `python -m app.cli diagnostico`: vuelca qué mundo lee de cada fichero y qué
  parejas reconoce, para averiguar qué pasa sin mover ficheros de 45 MB.
- La autocomprobación crece con los tres casos de arriba y con una revisión de
  que ninguna llamada de la interfaz apunte a una ruta que no existe. Esta
  última pilló un fallo real durante el desarrollo.

**Si vienes de una versión anterior:** borra la carpeta `data/db/` antes de
arrancar. Los mundos mal creados por los fallos de arriba están guardados ahí y
no se arreglan solos.

---

## v1.1.0 — Los ficheros se ordenan solos

*Función nueva.*

Dwarf Fortress nombra los exports con el nombre de la carpeta de la partida
(`region1`, `region4`), que no dice de qué mundo son.

**Añadido**

- La aplicación lee el nombre real del mundo de los primeros 64 KB del XML —no
  hace falta leerse los 45 MB— y deja cada export en
  `data/imports/<mundo>/<mundo>-<año>-<mes>-<día>-legends.xml`.
- Pasa solo al arrancar con `start.bat`. Desde la interfaz, el botón *Importar
  exports* enseña antes qué va a renombrar, con una casilla para saltárselo.
- `python -m app.cli ordenar` enseña el plan sin tocar nada; hace falta
  `--aplicar` para que mueva algo.
- El descubrimiento de ficheros entra en subcarpetas, emparejando solo ficheros
  que estén en la misma, para que dos mundos no se mezclen.

**Salvaguardas**, porque aquí se tocan ficheros del usuario:

- No se sobrescribe nada y no se borra nada.
- Los dos ficheros de un export se mueven juntos o no se mueve ninguno.
- Un `.xml` que no sea un export de leyendas no se toca.
- Renombrar un export ya importado no obliga a reprocesar los 45 MB: la base de
  datos se reapunta sola al nombre nuevo.

**Arreglado**

- `.gitignore` ampliado a subcarpetas, para que un XML de 45 MB no acabase en el
  repositorio por estar dentro de `data/imports/<mundo>/`.

---

## v1.0.0 — Primera versión

Explorador local del archivo de leyendas de Dwarf Fortress.

- **Importador** en streaming que aguanta exports de 45 MB sin agotar la
  memoria. Probado con uno de 132 MB: 100 segundos y 113 MB de memoria.
  Resuelve la codificación CP437, los bytes de control C0 (el `0x0F` es el ☼ de
  los objetos de calidad), las etiquetas `<name>` y `<n>`, y la fusión del
  fichero principal con el `_plus` por identificador.
- **Mapa interactivo** del mundo con deslizador de año: al moverlo se ve quién
  poseía cada sitio entonces, qué estaba en ruinas y qué bestias seguían vivas.
  Capas conmutables y colores por raza y facción deducidos de los propios datos.
- **Explorador de figuras históricas** con buscador, fichas enlazadas entre sí y
  ranking de quién mató a quién.
- **Panel de fortaleza**: detección automática, resumen, novedades entre exports
  y avisos de sitios hostiles, bestias vivas cercanas y guerras activas.
- **Crónicas narradas** por IA, con aviso de coste antes de gastar y copia
  guardada para no pagar dos veces por el mismo texto.
- **Arranque de un solo clic**: `start.bat` en Windows, `start.command` en macOS
  y `start.sh` en Linux.
