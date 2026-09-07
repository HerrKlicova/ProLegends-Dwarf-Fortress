# Plan de mejoras

Documento de trabajo. No es una promesa de fechas: es el orden en que conviene
hacer las cosas y por qué. Se va tachando conforme se implementa, y lo hecho
pasa al [CHANGELOG.md](CHANGELOG.md).

Estado actual: **v1.2.0**.

---

## Cómo se ha decidido el orden

Tres criterios, en este orden:

1. **Lo que desbloquea otras cosas va antes.** Conectar con la carpeta de Dwarf
   Fortress no es lo más vistoso, pero es lo que pone a nuestro alcance los
   mapas `.bmp` que el juego exporta, y sin ellos el mapa bonito se queda a
   medias.
2. **Lo que se ve va pronto.** No tiene sentido dejar el mapa para el final
   cuando es lo que más te importa, así que se parte en dos: la mitad que
   transforma el aspecto va temprano; los refinamientos, después.
3. **Lo compartido se hace una sola vez.** El diccionario que traduce la jerga
   de DF (`MAINTAIN_ENTITY_STATUS`, `STRUCK`, `DWARF`) sirve tanto para que la
   interfaz se entienda como para que las crónicas dejen de ser sosas. Se hace
   una vez y lo aprovechan las dos.

---

## Paso 0 — Ver qué trae tu mundo de verdad

**Sin esto no se puede planificar el mapa en serio.** Todo lo que he construido
hasta ahora se ha probado contra exports que genero yo, no contra los tuyos.
Para el mapa eso ya no vale: hay que saber qué información geográfica trae
realmente tu `legends_plus.xml`.

La buena noticia es que **no hay que reimportar nada**. El importador guarda
cada registro entero en `data_json`, y las secciones sin tabla propia caen en
`raw_records`. Es decir: lo que tu mundo tenga, ya está guardado; solo hay que
mirarlo.

Lo que hay que averiguar:

| Pregunta | Por qué importa |
|---|---|
| ¿Las regiones traen `<coords>` con la lista de casillas? | Si sí, se puede pintar el mapa de biomas nosotros mismos, sin depender de ficheros externos |
| ¿Hay `landmasses`, `rivers`, `mountain_peaks`? | Son las costas, los ríos y las montañas: la diferencia entre un mapa y una cuadrícula de puntos |
| ¿Qué `.bmp` exporta tu Dwarf Fortress y dónde? | Es el mapa que dibuja el propio juego; usarlo como fondo es la mayor fidelidad posible por el menor esfuerzo |

**Trabajo:** ampliar `diagnostico` con un apartado de geografía que liste qué
secciones y qué campos hay. Es media hora, y de su resultado depende cuál de
los tres caminos del mapa tomamos.

---

## v1.3.0 — Conexión con Dwarf Fortress

> Que no tengas que ir a buscar ficheros a mano nunca más.

**El problema.** Ahora mismo exportas las leyendas, te vas a la carpeta de DF,
buscas dos ficheros entre docenas, y los arrastras a `data/imports/`. Funciona,
pero es de andar por casa.

**Qué se hace.**

- **Detección automática de la carpeta de DF.** Para la versión de Steam se
  puede leer `libraryfolders.vdf`, que es donde Steam anota todas sus
  bibliotecas, incluidas las de otros discos. Para las versiones sueltas
  (itch.io, classic), una búsqueda acotada de `Dwarf Fortress.exe` en los sitios
  habituales, con profundidad limitada para que no tarde una eternidad.
- **Selección manual** para cuando la detección falle: un botón que abre el
  diálogo de carpetas **nativo de Windows**. Esto se puede hacer porque el
  servidor corre en tu propio ordenador, así que puede abrir una ventana de
  verdad. Es lo que da la sensación de programa serio en lugar de página web.
  Como último recurso, un campo donde pegar la ruta.
- **Listado de exports encontrados**, con su mundo y su fecha ya leídos de la
  cabecera, y casillas para elegir cuáles traerse.
- **Copiar, no mover**, por defecto. Mover ficheros de la carpeta de otro
  programa es la clase de cosa que luego no sabes deshacer. Habrá opción de
  mover para quien la quiera.
- **Se recuerda la carpeta**, así que solo se configura una vez.
- **De paso se localizan los `.bmp`** que DF exporta junto a las leyendas. No se
  usan todavía, pero quedan fichados para el mapa.

**Qué hay que decidir contigo.** Si la detección encuentra varias instalaciones
de DF, ¿elegimos la más reciente o preguntamos siempre?

**Riesgos.** El diálogo nativo necesita `tkinter`, que viene con Python en
Windows pero podría faltar en instalaciones raras; habrá que comprobarlo y dejar
el campo de texto como alternativa.

**Tamaño.** Pequeño-medio. Una sesión.

---

## v1.4.0 — El mapa, primera mitad

> De cuadrícula con puntos de colores a mapa que apetece mirar.

**El problema.** Lo que hay ahora es funcional pero es un diagrama, no un mapa.
No hay tierra, ni mar, ni montañas: solo cuadraditos flotando en negro.

**Los tres caminos posibles**, según lo que diga el Paso 0:

**A — Fondo con los `.bmp` del propio juego.**
Máxima fidelidad y mínimo invento: es literalmente el mapa que dibuja Dwarf
Fortress. Se convierten a PNG en el servidor (se puede hacer con la librería
estándar de Python, sin añadir dependencias) y se usan de capa base. Requiere
que tengas exportados los mapas detallados, y la carpeta detectada en v1.3.
*Es el camino preferido si los ficheros están.*

**B — Pintado propio a partir de las regiones.**
Si tu `legends_plus.xml` trae las coordenadas de cada región, podemos pintar
nosotros los biomas con nuestra propia paleta. Más trabajo, pero control total
del estilo y no depende de ficheros externos.

**C — Mixto (lo más probable).**
El `.bmp` como base cuando esté disponible, el pintado propio como respaldo, y
**siempre** nuestra capa interactiva encima. La capa de arriba es la que
importa: sitios, propietarios, deslizador de año.

**Qué se hace, sea cual sea el camino.**

- **Iconos de verdad** en lugar de cuadrados: una torre parece una torre, una
  fortaleza parece una fortaleza, una guarida parece una guarida. Dibujados como
  vectores, así que se ven nítidos a cualquier tamaño.
- **Zoom y desplazamiento** con la rueda y arrastrando.
- **Etiquetas con los nombres**, apareciendo según el zoom y esquivándose entre
  ellas para que no se solapen.
- **Relieve**: sombreado a partir del mapa de elevación, si lo hay.
- **Ríos y costas** dibujados como líneas, no como píxeles sueltos.

**Qué hay que decidir contigo.** El estilo: ¿atlas de pergamino, con serifas y
tonos tierra? ¿O limpio y oscuro como ahora? Se puede hacer que sea conmutable,
pero conviene elegir uno como principal.

**Riesgos.** El camino A depende de que tengas los `.bmp`; el B, de que tu XML
traiga coordenadas de región. Si fallan los dos, el mapa mejora igual (iconos,
zoom, etiquetas) pero sin terreno de fondo. **Por eso el Paso 0 va antes.**

**Tamaño.** Grande. Dos o tres sesiones.

---

## v1.5.0 — Que se entienda

> El arreglo de fondo para lo de «la interfaz es infumable».

**El problema, dicho claro.** La aplicación te enseña el vocabulario interno de
Dwarf Fortress en crudo. Una línea de la ficha de una figura dice hoy:

```
159   Hf died   attacker_civ_id: 1 · cause: STRUCK · hfid: 105 · slayer_hfid: 121
```

Y debería decir:

> **Año 159** — Iden Craftshailed murió en Kolluslan, abatida por Uthhkos
> Lusbomith.

Ese salto es, con diferencia, lo que más cambia la sensación de usar el
programa. No es un problema de colores ni de tipografías: es que el texto no
está escrito para una persona.

**Qué se hace.**

- **Un diccionario de términos de DF a castellano**: tipos de evento, causas de
  muerte, razas, habilidades, objetivos vitales, cargos, tipos de sitio. Con
  regla estricta: **lo que no esté en el diccionario se muestra tal cual**, sin
  inventar traducciones ni ocultar datos.
- **Plantillas de narración por tipo de evento**, que convierten los
  identificadores en nombres y los ordenan en una frase.
- Un interruptor para ver el dato en bruto, para cuando quieras comprobar algo.

**Por qué va aquí y no antes.** Porque el mismo diccionario es la mitad del
arreglo de las crónicas (v1.8), y hacerlo una vez es mejor que hacerlo dos.

**Riesgos.** DF tiene cientos de tipos de evento. No se van a cubrir todos de
golpe: se empieza por los cincuenta más frecuentes, que cubrirán la inmensa
mayoría de lo que ves, y el resto sigue mostrándose como ahora.

**Tamaño.** Medio-grande, pero muy troceable. Se puede ir ampliando el
diccionario poco a poco.

---

## v1.6.0 — Interfaz

> Ya se entiende lo que pone; ahora que dé gusto moverse.

**Qué se hace.**

- **Buscador global**: una caja que busca a la vez en figuras, sitios,
  entidades y artefactos.
- **Historial de navegación**: poder volver atrás después de saltar de una
  figura a un sitio y de ahí a otra figura.
- **Direcciones enlazables**: que la barra del navegador refleje dónde estás,
  para poder guardar en favoritos la ficha de un personaje concreto.
- **Sistema visual coherente**: escala de tamaños de letra, espaciados y
  tarjetas consistentes; ahora mismo cada vista va un poco a su aire.
- **Tablas ordenables** y con filtro.
- **Estados vacíos y de carga decentes**, en lugar de un «Cargando...» pelado.

**Qué hay que decidir contigo.** Esto es lo más subjetivo de todo el plan. Lo
sensato es que te prepare dos o tres propuestas visuales y elijas, en vez de que
yo decida por mi cuenta y no te guste.

**Tamaño.** Medio.

---

## v1.7.0 — El mapa, segunda mitad

> Los remates que lo convierten en un atlas.

- **Territorios por civilización**: manchas de color con sus fronteras,
  calculadas por influencia desde los sitios de cada una. Ojo: esto es una
  **aproximación visual**, no un dato del juego, y así se dirá en pantalla.
- **Fronteras que cambian con el deslizador de año**: ver cómo un imperio crece
  y se derrumba es, probablemente, lo más bonito que puede hacer este programa.
- **Modo atlas**: pergamino, serifas, rosa de los vientos, escala y leyenda.
- **Exportar el mapa a PNG**, para guardarlo o compartirlo.
- **Capa de batallas**: dónde se libraron y con qué resultado.

**Tamaño.** Medio-grande.

---

## v1.8.0 — Crónicas que se dejen leer

> Ahora mismo enumeran. Tienen que contar.

**El problema.** La crónica de Iden Craftshailed dice lo que pasó, en orden, y
poco más. Y la culpa no es del modelo: es mía, por dos motivos.

1. **Le doy datos pelados.** El contexto que envío es una lista de
   `año | tipo | campo=valor`. Con eso solo se puede enumerar. El modelo no sabe
   quién era su marido, ni que su civilización estaba en guerra mientras ella
   crecía, ni qué clase de sitio era aquel en el que murió.
2. **Le he atado las manos.** Las instrucciones dicen «no inventes nada», «no
   rellenes», «sobrio». Confundí *no inventar hechos* con *no escribir bien*, y
   salió un parte administrativo.

**Qué se hace.**

- **Contexto mucho más rico**: relaciones familiares con nombre, quién la mató y
  quién murió a sus manos, los cargos con sus fechas, las guerras que vivió su
  civilización durante su vida, sus contemporáneos, qué clase de lugares
  frecuentó.
- **Términos ya traducidos** al enviarlos (aquí se reaprovecha el diccionario de
  v1.5): que el modelo lea «murió golpeada» y no `cause: STRUCK`.
- **Instrucciones distintas para cada ámbito**: la vida de una persona pide una
  forma; la crónica de un siglo, otra; la de una fortaleza, otra.
- **Permiso explícito para narrar**: puede conectar causas y consecuencias que
  la cronología sostenga, dar atmósfera a partir del tipo de lugar, y callar
  donde no haya datos. Lo que sigue prohibido es inventarse hechos.
- **Registro elegible**: crónica monástica, saga nórdica, informe de un viajero.
  Un desplegable antes de generar.
- **Modelo y esfuerzo configurables** desde el `.env`, con su aviso de coste.

**Cómo sabremos que ha mejorado.** Guardando las crónicas actuales y comparando
con las nuevas sobre los mismos personajes. Sin eso, «me parece que está mejor»
no vale.

**Riesgos.** Más contexto es más tokens y más dinero por crónica. El aviso
previo ya dice cuánto va a costar; habrá que vigilar que no se dispare.

**Tamaño.** Medio.

---

## Ideas aparcadas

No están descartadas, pero no compiten con lo de arriba:

- Grafo de relaciones entre personas.
- Grafo de transmisión de secretos: quién enseñó nigromancia a quién.
- Red de conspiraciones a partir de los `intrigue_plot`.
- Línea temporal navegable como vista propia.
- Comparar dos mundos entre sí.
- Modo presentación, para enseñar la historia de un mundo a alguien.

---

## Límites, dichos por adelantado

- **El mapa no puede tener más detalle del que Dwarf Fortress exporta.** Si el
  juego no dice dónde está un bosque, no lo sabremos. El techo lo pone el
  fichero, no la programación.
- **Sigue sin haber compilación ni Node.** Todo esto se puede hacer con canvas y
  JavaScript a pelo; no hace falta cambiar de tecnología y no se va a cambiar.
- **Lo de «bonito» es cuestión de gustos.** En las partes visuales prefiero
  enseñarte alternativas y que elijas, antes que decidir yo y acertar por
  casualidad.
- **Cada bloque se sube funcionando**, con su versión y su resumen. Nada de
  ramas a medias colgando durante semanas.
