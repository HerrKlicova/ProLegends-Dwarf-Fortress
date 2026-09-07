"""Descubrimiento y emparejado de exports en data/imports/.

Dwarf Fortress genera dos ficheros por export:

    <mundo>-<anyo>-<mes>-<dia>-legends.xml        (principal)
    <mundo>-<anyo>-<mes>-<dia>-legends_plus.xml   (extra de DFHack)

Se emparejan por el prefijo comun. Los sueltos se avisan por consola y se
ignoran, salvo que se pida explicitamente importarlos.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

MAIN_SUFFIX = "-legends.xml"
PLUS_SUFFIX = "-legends_plus.xml"

# region1-00101-07-24  ->  token=region1, anyo=00101, mes=07, día=24
_PREFIX_RE = re.compile(r"^(?P<token>.+?)-(?P<year>\d{2,6})-(?P<month>\d{1,2})-(?P<day>\d{1,2})$")


@dataclass
class ExportPair:
    prefix: str
    main: Optional[Path] = None
    plus: Optional[Path] = None
    file_token: str = ""
    game_year: Optional[int] = None
    game_month: Optional[int] = None
    game_day: Optional[int] = None
    warnings: list[str] = field(default_factory=list)

    @property
    def complete(self) -> bool:
        return self.main is not None and self.plus is not None

    @property
    def usable(self) -> bool:
        """Sin el principal no hay nada que hacer: el _plus solo complementa."""
        return self.main is not None

    @property
    def sort_key(self) -> tuple:
        return (
            self.game_year if self.game_year is not None else 0,
            self.game_month or 0,
            self.game_day or 0,
            self.prefix,
        )

    def fingerprint(self) -> str:
        """Huella para no reprocesar dos veces el mismo export.

        Se calcula con el prefijo y el tamano de cada fichero: si vuelves a
        exportar el mismo mundo en la misma fecha, el contenido -y por tanto el
        tamano- sera practicamente identico; si cambia, se reimporta.
        """
        parts = [self.prefix]
        for path in (self.main, self.plus):
            parts.append(f"{path.name}:{path.stat().st_size}" if path else "-")
        return hashlib.sha1("|".join(parts).encode("utf-8")).hexdigest()

    def describe(self) -> str:
        fecha = ""
        if self.game_year is not None:
            fecha = f" (año {self.game_year}, {self.game_day:02d}/{self.game_month:02d})"
        return f"{self.prefix}{fecha}"


def _parse_prefix(prefix: str) -> tuple[str, Optional[int], Optional[int], Optional[int]]:
    m = _PREFIX_RE.match(prefix)
    if not m:
        return prefix, None, None, None
    return (
        m.group("token"),
        int(m.group("year")),
        int(m.group("month")),
        int(m.group("day")),
    )


def _rescatar_huerfanos(pairs: dict, avisos: list[str]) -> None:
    """Empareja ficheros de un mismo export que no comparten prefijo.

    Al copiar o subir los ficheros, cada uno puede acabar con un prefijo
    distinto (una marca de tiempo delante, por ejemplo), y entonces el
    emparejado por nombre no los reconoce como pareja aunque estén juntos.

    Si en una misma carpeta hay exactamente un principal suelto y un _plus
    suelto de la MISMA fecha, son la pareja: no hay otra combinación posible.
    Con más de uno de cada no se adivina nada y se dejan como están.
    """
    por_fecha: dict[tuple, dict[str, list]] = {}
    for clave, par in pairs.items():
        carpeta = clave[0]
        if par.main is not None and par.plus is not None:
            continue
        if par.game_year is None:
            continue
        cubo = por_fecha.setdefault(
            (carpeta, par.game_year, par.game_month, par.game_day),
            {"main": [], "plus": []},
        )
        cubo["main" if par.main is not None else "plus"].append((clave, par))

    for (_carpeta, anyo, mes, dia), cubo in por_fecha.items():
        if len(cubo["main"]) != 1 or len(cubo["plus"]) != 1:
            continue
        (clave_main, par_main), (clave_plus, par_plus) = cubo["main"][0], cubo["plus"][0]
        par_main.plus = par_plus.plus
        pairs.pop(clave_plus, None)
        avisos.append(
            f"Emparejados '{par_main.main.name}' y '{par_plus.plus.name}': "
            f"tienen nombres distintos pero son del mismo export "
            f"(año {anyo}, {dia:02d}/{mes:02d}) y están en la misma carpeta."
        )


def discover(imports_dir: Path) -> tuple[list[ExportPair], list[str]]:
    """Devuelve (pares_utilizables, avisos)."""
    imports_dir = Path(imports_dir)
    avisos: list[str] = []
    if not imports_dir.exists():
        return [], [f"La carpeta {imports_dir} no existe."]

    pairs: dict[tuple, ExportPair] = {}
    otros: list[str] = []

    # Se busca también dentro de subcarpetas, porque el organizador reparte los
    # exports en una carpeta por mundo.
    for path in sorted(imports_dir.rglob("*")):
        if not path.is_file():
            continue
        name = path.name
        if name.endswith(PLUS_SUFFIX):
            prefix = name[: -len(PLUS_SUFFIX)]
            slot = "plus"
        elif name.endswith(MAIN_SUFFIX):
            prefix = name[: -len(MAIN_SUFFIX)]
            slot = "main"
        else:
            if path.suffix.lower() == ".xml":
                otros.append(str(path.relative_to(imports_dir)))
            continue

        # Los dos ficheros de un export tienen que estar en la misma carpeta:
        # así dos mundos distintos no se mezclan aunque compartan prefijo.
        clave = (str(path.parent), prefix)
        pair = pairs.get(clave)
        if pair is None:
            token, year, month, day = _parse_prefix(prefix)
            pair = ExportPair(
                prefix=prefix,
                file_token=token,
                game_year=year,
                game_month=month,
                game_day=day,
            )
            pairs[clave] = pair
        setattr(pair, slot, path)

    for name in otros:
        avisos.append(
            f"Ignorado '{name}': no acaba en '-legends.xml' ni en '-legends_plus.xml'."
        )

    _rescatar_huerfanos(pairs, avisos)

    utilizables: list[ExportPair] = []
    for pair in sorted(pairs.values(), key=lambda p: p.sort_key):
        if pair.main is None:
            avisos.append(
                f"Ignorado '{pair.plus.name}': falta su pareja "
                f"'{pair.prefix}{MAIN_SUFFIX}'. Un _plus por si solo no sirve."
            )
            continue
        if pair.plus is None:
            aviso = (
                f"Del export '{pair.prefix}' solo se ha encontrado el fichero "
                "principal; falta el segundo, el que acaba en '-legends_plus.xml'. "
                "Se puede usar igualmente, pero sin los datos que solo trae ese "
                "fichero: la raza y el tipo de cada civilización, los secretos que "
                "conoce cada figura y las tramas de intriga. Si lo tienes, déjalo "
                "en la misma carpeta que el principal y vuelve a importar."
            )
            avisos.append(aviso)
            pair.warnings.append(aviso)
        if pair.game_year is None:
            aviso = (
                f"Aviso en '{pair.prefix}': el nombre no sigue el patron "
                "<mundo>-<anyo>-<mes>-<día>-legends.xml, no se puede deducir la fecha."
            )
            avisos.append(aviso)
            pair.warnings.append(aviso)
        utilizables.append(pair)

    if not utilizables and not avisos:
        avisos.append(f"No hay ningún export en {imports_dir}.")

    return utilizables, avisos
