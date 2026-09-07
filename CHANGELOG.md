# Registro de versiones

Todas las versiones de ProLegends, de la más reciente a la más antigua.

La numeración es `MAYOR.MENOR.PARCHE`:

- **PARCHE** (1.1.0 → 1.1.**1**): solo se arreglan fallos.
- **MENOR** (1.0.0 → 1.**1**.0): se añade algo nuevo, y lo de antes sigue funcionando igual.
- **MAYOR** (1.1.0 → **2**.0.0): algo cambia de forma que obliga a rehacer cosas.

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
