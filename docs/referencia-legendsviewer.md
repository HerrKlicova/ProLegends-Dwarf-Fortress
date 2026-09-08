# LegendsViewer-Next: análisis y qué merece la pena copiarle

> Estudio del proyecto [Kromtec/LegendsViewer-Next](https://github.com/Kromtec/LegendsViewer-Next)
> hecho sobre el código fuente completo (descarga del 6 de septiembre de 2026).
> Sirve de referencia para decidir qué construir en ProLegends y en qué orden.

---

## 1. Qué es

Es el heredero del **LegendsViewer** clásico, reescrito para la versión de Steam
de Dwarf Fortress. Hace lo mismo que nosotros —leer los XML de leyendas y
dejarte explorarlos— pero lleva años de ventaja en cantidad de contenido.

**Licencia MIT**, así que copiar ideas (y hasta código, citando) es legítimo.

### Cómo está hecho

| | LegendsViewer-Next | ProLegends |
|---|---|---|
| Servidor | C# / .NET 10 | Python 3 / FastAPI |
| Interfaz | Vue 3 + TypeScript + Vuetify | HTML/CSS/JS sin compilar |
| Mapa | SkiaSharp (servidor) + Leaflet | Canvas 2D propio |
| Gráficas | Chart.js | — |
| Grafos | Cytoscape (dagre, cola) | — |
| Almacenamiento | todo en memoria + marcadores JSON | SQLite |
| Idioma | inglés | español |
| Líneas de código | ~60.000 (34k servidor + 26k interfaz) | ~10.400 |

Que ellos tengan seis veces más código **no significa que vayan seis veces
mejor**: la mayor parte es un tipo de trabajo muy repetitivo (143 clases de
evento, 50 catálogos, 48 pantallas) que se hace una vez y no se toca más.

---

## 2. Lo que hacen mejor que nosotros

### 2.1 Narran los eventos en lenguaje humano ⭐⭐⭐

Lo más importante que le he encontrado. Tienen **143 clases de evento**, una por
cada tipo que emite Dwarf Fortress, y cada una sabe convertirse en una frase.
Ejemplo real de su código (`HFDied.cs`):

```csharp
case DeathCause.DragonsFire:  "burned up in {matador}'s dragon fire"
case DeathCause.Murdered:     "was murdered by {matador}"
case DeathCause.Shot:         "was shot and killed by {matador}"
case DeathCause.Struck:       "was struck down by {matador}"
```

Son **13.000 líneas** solo de narración de eventos. Donde nosotros enseñamos
`hf died · cause: STRUCK · slayer_hfid: 4412`, ellos escriben *"Urist McDwarf
fue abatido por Sanhkos el Terrible en las Colinas Doradas"*.

También tienen **50 catálogos** (`Enums/`) que traducen los códigos internos:
`SiteType`, `DeathCause`, `StructureType`, `IntrigueMethod`, `SecretGoal`,
`OccasionType`... cada uno con su descripción legible.

> **Esto es exactamente nuestra v1.5.0.** Es el mayor salto de calidad
> disponible, y encima en español no lo tiene nadie.

### 2.2 Colecciones de eventos ⭐⭐⭐

No tratan los eventos sueltos: los **agrupan en sucesos** con ficha propia.
Tienen 19 tipos:

`Battle` · `War` · `Raid` · `SiteConquered` · `Duel` · `Abduction` · `Theft` ·
`BeastAttack` · `Insurrection` · `Purge` · `Persecution` · `Journey` ·
`Occasion` · `Ceremony` · `Competition` · `Performance` · `Procession` ·
`EntityOverthrown` · `Coup`

Una batalla no es un evento: es un suceso con atacante, defensor, vencedor,
bajas de cada bando, lista de participantes y los eventos que la componen. El
XML ya trae esto (`<historical_event_collection>`). Nosotros lo importamos a
las tablas `event_collections` y `collection_events`, y hasta tenemos el
endpoint `/exports/{id}/colecciones` funcionando — pero **ninguna pantalla lo
usa todavía**. El trabajo está hecho a medias: falta la parte que se ve.

### 2.3 Récords del mundo ⭐⭐⭐

Una pantalla entera de rankings, en 6 categorías y ~22 tarjetas:

- **Guerra**: mayores asesinos, batallas más sangrientas, mejores duelistas, peores masacres
- **Soberanos**: reinados más largos y más cortos, sitios más disputados, imperios más grandes
- **Saber y artes**: mayores eruditos, autores más prolíficos, obras más copiadas
- **Intriga**: maestros del disfraz, redes de conspiración más notorias
- **Longevidad**: los más viejos vivos, los más viajados, artefactos más antiguos
- **Geografía**: regiones mayores, cavernas mayores, regiones más sangrientas, ríos más largos, picos más altos

Con un banner arriba de "titulares" (*la criatura más letal del mundo*, *el
reinado más largo*, *la batalla más sangrienta*).

Es puro azúcar y es **justo lo que hace que un mundo apetezca explorar**.
Nosotros ya tenemos "quién mató a quién": esto es esa idea llevada al final.

### 2.4 Grafos: árboles genealógicos y guerras ⭐⭐

- **Árbol genealógico** de cualquier figura (Cytoscape + dagre), con iconos
  distintos para líderes, nigromantes, vampiros, hombres bestia y fantasmas.
- **Grafo de guerras** entre entidades (Cytoscape + cola).
- **Línea temporal de monarcas** por cargo: quién gobernó qué y cuándo, en
  barras.

### 2.5 Objetos del mundo que nosotros ni tocamos ⭐⭐

Tienen ficha y listado para: **estructuras** (templos, tumbas, mazmorras...),
**contenidos escritos** (¡los libros del mundo, con su autor y sus copias!),
**formas artísticas** (poesía, música, danza), **ríos**, **picos**,
**masas de tierra**, **regiones subterráneas** (cavernas), **eras**.

Nosotros ya guardamos casi todo eso en `raw_records` sin usarlo.

### 2.6 Tablas paginadas con filtros ⭐⭐

Cada tipo de objeto tiene su pantalla de listado con filtros compuestos
(`propiedad + operador + valor`), búsqueda de texto, orden por columna y
paginación en el servidor. Nosotros solo tenemos búsqueda en figuras.

### 2.7 Mapa por profundidad ⭐

El mapa se puede ver a nivel de superficie o de **cavernas 1, 2, 3 y el
inframundo**. El dato está en `underground_regions`, que ya importamos.

### 2.8 Capa de guerra sobre el mapa ⭐⭐

Flechas de atacante a defensor, marcadores de batalla con bajas de cada bando,
y todo pinchable. Encaja de maravilla con nuestro deslizador de año.

### 2.9 Marcadores de mundos ⭐

Pantalla inicial con **todos los mundos abiertos alguna vez**, cada uno con
miniatura de su mapa y sus fechas, y aviso si hay un export más reciente sin
cargar.

### 2.10 Un tercer fichero: `world_sites_and_pops.txt` ⭐

Además de los dos XML, leen el volcado de texto que genera DF con las
**poblaciones por sitio y por raza** y los **cargos oficiales de cada sitio**.
Es un fichero pequeño y da información que no está en las leyendas.

---

## 3. Lo que nosotros hacemos mejor

No es un consuelo: son cosas que ellos no tienen y que conviene no perder.

1. **El deslizador de año.** Su mapa es estático. El nuestro te enseña el mundo
   en cualquier año: quién poseía cada sitio, qué estaba en ruinas, qué bestias
   vivían. Es nuestra seña de identidad y no la tiene nadie.
2. **La comparación entre exports.** Ellos detectan que hay un export más nuevo,
   pero no te dicen **qué ha cambiado**. Nuestro parte de novedades de la
   fortaleza no existe en su programa.
3. **Las crónicas narradas por IA.** No tienen nada parecido.
4. **El mapa.** El suyo son cuadrados de color plano (un color por bioma con una
   variación aleatoria por región) sobre los que superponen marcadores de
   Leaflet. El nuestro es un atlas dibujado: costa a tinta, símbolos por bioma,
   ríos con grosor según su caudal, picos, calzadas, cartela y rosa de los
   vientos.
5. **Los acentos y los símbolos.** Su lector de XML sustituye **todos** los
   bytes de control por espacios (`FilteredStream.cs`), así que pierde el ☼ de
   los objetos de calidad. Nosotros los traducimos a su símbolo real de CP437.
   Y detectamos si el fichero es CP437 o UTF-8 en vez de suponerlo.
6. **Instalación.** Ellos necesitan .NET 10 y Node para desarrollar. Nosotros,
   doble clic. Y nuestros datos viven fuera del programa, así que actualizar no
   cuesta nada.
7. **Está en español.** El suyo no, y no hay ningún visor de leyendas en
   español.

---

## 4. Lo que NO copiaría

- **Su forma de dibujar el mapa.** El nuestro ya es mejor.
- **El marco de trabajo.** Vue + Vuetify + TypeScript significa paso de
  compilación, `npm`, y una carpeta de dependencias enorme. Va contra la regla
  de "doble clic y funciona".
- **Tenerlo todo en memoria.** Ellos cargan el mundo entero en RAM y lo pierden
  al cerrar. Nuestro SQLite es más lento de llenar pero se consulta al instante
  y sobrevive al reinicio.
- **El icono de "objetivo" del mapa** (círculos amarillos, cruces de punta a
  punta): funciona, pero es feo.

---

## 5. Plan: qué construir y en qué orden

Ordenado por **valor entre esfuerzo**, no por dificultad.

| Nº | Qué | De dónde sale | Esfuerzo |
|---|---|---|---|
| 1 | **Diccionario y narración de eventos** | catálogos + una frase por tipo | grande, pero por partes |
| 2 | **Sucesos: batallas, guerras, saqueos, duelos...** | tabla `event_collections`, ya importada | medio |
| 3 | **Récords del mundo** | consultas sobre lo que ya hay | medio |
| 4 | **Listados con filtros** para sitios, artefactos, entidades | consultas sobre lo que ya hay | medio |
| 5 | **Capa de guerra en el mapa**, con el deslizador de año | eventos + colecciones | medio |
| 6 | **Árbol genealógico** | tabla `hf_links`, ya importada | medio |
| 7 | **Fichas nuevas**: estructuras, libros, formas artísticas | `raw_records`, ya importado | pequeño cada una |
| 8 | **Mapa de cavernas** | `underground_regions`, ya importado | pequeño |
| 9 | **Regiones malditas** en el mapa | campo `evilness` de cada región | pequeño |
| 10 | **Poblaciones por sitio** | tercer fichero `world_sites_and_pops.txt` | pequeño |
| 11 | **Pantalla de mundos** con miniatura | lo que ya hay | pequeño |

**Lo importante:** los puntos 2, 3, 4, 6, 7, 8 y 9 **no necesitan reimportar
nada ni tocar el parser**. Todo eso ya está guardado en la base de datos desde
la primera importación, en `data_json` y `raw_records`. Era exactamente para
esto para lo que se diseñó así.

### Cómo encaja con la hoja de ruta que ya teníamos

- **v1.5.0** (diccionario de legibilidad) → se confirma como la siguiente, y
  ahora sabemos qué alcance darle: catálogos + narración por tipo de evento.
- **v1.6.0** (interfaz) → añadir listados con filtros y la pantalla de mundos.
- **v1.7.0** (mapa, segunda mitad) → añadir capa de guerra, cavernas y regiones
  malditas.
- **v1.8.0** (crónicas) → las crónicas mejoran solas cuando los eventos se
  narran bien: el texto que se le manda a la IA deja de ser `hf died STRUCK`.
- **v1.9.0 (nueva)** → sucesos: batallas, guerras y demás colecciones.
- **v2.0.0 (nueva)** → récords del mundo y árboles genealógicos.

---

## 6. Detalles técnicos que conviene recordar

Cosas concretas que he sacado del código y que ahorran trabajo cuando toque:

- **Colores de civilización**: reparten el círculo cromático entre las razas y
  luego entre las civilizaciones de cada raza. Es lo mismo que hacemos nosotros;
  buena señal.
- **Variación por región**: al color base del bioma le suman un desplazamiento
  aleatorio de ±15 sembrado con el `id` de la región, así dos bosques vecinos no
  son idénticos. Nosotros lo hacemos con ruido por casilla; su idea de sembrar
  con el id también sirve para que cada región tenga su tono propio.
- **Tamaños de casilla del mapa**: 2, 4 y 10 píxeles, con las tres versiones
  cacheadas.
- **Marcadores**: `Bookmark` se identifica por `nombre_mundo + nombre_region`
  (sin fecha), para que el mismo mundo en distintas fechas sea el mismo
  marcador. Nosotros usamos el prefijo del fichero; su idea es más estable.
- **Filtros**: `{propiedad, operador, valor}` con operadores
  `Equals/NotEquals/Contains/GreaterThan/LessThan`. Modelo simple y suficiente.
- **Paginación**: devuelven `{items, total, totalFiltrado, tamañoPagina,
  numeroPagina, totalPaginas}`.
- **Los eventos guardan a qué colección pertenecen** (`PrintParentCollection`),
  así cada frase puede terminar con "durante la Batalla de X".

---

## 7. Conclusión

No es un rival: es un mapa del tesoro. Nos dice **qué se puede hacer con estos
datos** y confirma que casi todo lo que falta ya lo tenemos guardado.

Su ventaja es la cantidad de trabajo acumulado en narrar eventos y en montar
fichas para cada cosa. Es trabajo mecánico, no ingenio: se puede recorrer.

Nuestra ventaja es el enfoque —el tiempo como eje, las novedades entre
partidas, el mapa como atlas, las crónicas— y que está pensado para usarse sin
saber nada de programación. Eso no se copia en una tarde.
