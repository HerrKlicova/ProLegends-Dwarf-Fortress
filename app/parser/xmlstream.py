"""Lectura tolerante y en streaming de los XML de legends.

Los exports de Dwarf Fortress tienen tres peculiaridades que rompen cualquier
parser XML estandar:

1. Estan codificados en CP437 (la pagina de codigos del MS-DOS original), no en
   UTF-8, aunque la declaracion del XML lo anuncie de formas variadas.
2. Dentro de los nombres aparecen bytes de control C0 (0x00-0x1F). En CP437 esos
   bytes NO son caracteres de control sino simbolos con significado (el 0x0F es
   el famoso ``☼`` de los objetos de calidad), pero para un parser XML son
   tokens invalidos y provocan ``not well-formed (invalid token)``.
3. Pesan decenas de megabytes, asi que hay que leerlos en streaming.

Este modulo resuelve los tres problemas de una vez con un objeto tipo fichero
que entrega bytes UTF-8 ya saneados, apto para ``ElementTree.iterparse``.
"""

from __future__ import annotations

import io
import re
from pathlib import Path
from typing import Callable, Iterator, Optional
from xml.etree import ElementTree as ET

from ..errors import CorruptXMLError

# Traduccion de los bytes 0x00-0x1F a su glifo real en CP437.
# Se conservan tabulador, salto de línea y retorno de carro porque son validos
# en XML; el resto se convierte al símbolo Unicode equivalente para no perder
# información de los nombres (DF los usa de verdad). El 0x00 se descarta.
_C0_GLYPHS = {
    0x00: None,      # NUL: se elimina
    0x01: "☺",  # ☺
    0x02: "☻",  # ☻
    0x03: "♥",  # ♥
    0x04: "♦",  # ♦
    0x05: "♣",  # ♣
    0x06: "♠",  # ♠
    0x07: "•",  # •
    0x08: "◘",  # ◘
    0x09: "\t",      # valido en XML, se conserva
    0x0A: "\n",      # valido en XML, se conserva
    0x0B: "♂",  # ♂
    0x0C: "♀",  # ♀
    0x0D: "\r",      # valido en XML, se conserva
    0x0E: "♫",  # ♫
    0x0F: "☼",  # ☼
    0x10: "►",  # ►
    0x11: "◄",  # ◄
    0x12: "↕",  # ↕
    0x13: "‼",  # ‼
    0x14: "¶",  # ¶
    0x15: "§",  # §
    0x16: "▬",  # ▬
    0x17: "↨",  # ↨
    0x18: "↑",  # ↑
    0x19: "↓",  # ↓
    0x1A: "→",  # →
    0x1B: "←",  # ←
    0x1C: "∟",  # ∟
    0x1D: "↔",  # ↔
    0x1E: "▲",  # ▲
    0x1F: "▼",  # ▼
}

# También hay que neutralizar los caracteres prohibidos del rango C1 y el 0x7F
# que a veces se cuelan: en CP437 el 0x7F es la casita ⌂.
_C0_GLYPHS[0x7F] = "⌂"  # ⌂

_TRANSLATION = {code: glyph for code, glyph in _C0_GLYPHS.items()}

# Un '&' que no abre una entidad valida rompe el parseo. DF los emite crudos de
# vez en cuando dentro de nombres de obras escritas.
_BARE_AMP = re.compile(r"&(?!#[0-9]+;|#[xX][0-9A-Fa-f]+;|[A-Za-z][A-Za-z0-9._-]*;)")

_XML_DECL = re.compile(r"^\s*<\?xml[^>]*\?>", re.IGNORECASE)

CHUNK_SIZE = 1 << 20  # 1 MiB


class SanitizedXMLStream(io.RawIOBase):
    """Fichero virtual que entrega el XML de legends ya saneado y en UTF-8.

    Se lee del disco por trozos, de modo que nunca hay mas de un par de
    megabytes en memoria por muy grande que sea el export.
    """

    def __init__(self, path: Path, chunk_size: int = CHUNK_SIZE) -> None:
        self.path = Path(path)
        self.total_bytes = self.path.stat().st_size
        self.raw_bytes_read = 0
        self._fh = open(self.path, "rb")
        self._chunk_size = chunk_size
        self._buffer = b""
        self._carry = ""       # texto retenido por posible entidad partida
        self._first_chunk = True
        self._eof = False

    # -- API de fichero ---------------------------------------------------
    def readable(self) -> bool:
        return True

    def read(self, size: int = -1) -> bytes:  # type: ignore[override]
        if size is None or size < 0:
            parts = []
            while True:
                data = self.read(self._chunk_size)
                if not data:
                    break
                parts.append(data)
            return b"".join(parts)

        while len(self._buffer) < size and not self._eof:
            self._fill()
        out, self._buffer = self._buffer[:size], self._buffer[size:]
        return out

    def readinto(self, b) -> int:  # type: ignore[override]
        data = self.read(len(b))
        b[: len(data)] = data
        return len(data)

    def close(self) -> None:
        try:
            self._fh.close()
        finally:
            super().close()

    # -- Interno ----------------------------------------------------------
    def _fill(self) -> None:
        raw = self._fh.read(self._chunk_size)
        if not raw:
            self._eof = True
            text = self._carry
            self._carry = ""
            if text:
                self._buffer += self._encode(text)
            return

        self.raw_bytes_read += len(raw)
        if self._first_chunk and raw[:3] == b"\xef\xbb\xbf":
            raw = raw[3:]
        text = raw.decode("cp437", errors="replace")

        if self._first_chunk:
            self._first_chunk = False
            # La declaracion anuncia CP437; como ya entregamos UTF-8, hay que
            # reescribirla o expat intentara decodificar dos veces.
            if _XML_DECL.match(text):
                text = _XML_DECL.sub('<?xml version="1.0" encoding="UTF-8"?>', text, count=1)
            else:
                text = '<?xml version="1.0" encoding="UTF-8"?>\n' + text

        text = self._carry + text
        self._carry = ""

        # Retener una cola corta si el trozo puede haber partido una entidad
        # (&amp; cortado a la mitad) o una etiqueta.
        tail_start = max(0, len(text) - 24)
        cut = max(text.rfind("&", tail_start), text.rfind("<", tail_start))
        if cut != -1 and ";" not in text[cut:] and ">" not in text[cut:]:
            self._carry = text[cut:]
            text = text[:cut]

        self._buffer += self._encode(text)

    @staticmethod
    def _encode(text: str) -> bytes:
        text = text.translate(_TRANSLATION)
        text = _BARE_AMP.sub("&amp;", text)
        return text.encode("utf-8", errors="replace")


def local_name(tag: str) -> str:
    """Devuelve el nombre de la etiqueta sin espacio de nombres."""
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def normalize_key(tag: str) -> str:
    """Normaliza nombres de etiqueta.

    Algunos exports escriben ``<n>`` donde otros escriben ``<name>``; se aceptan
    los dos y se guarda siempre como ``name``.
    """
    key = local_name(tag)
    if key == "n":
        return "name"
    return key


def elem_to_dict(elem: ET.Element) -> dict:
    """Convierte un elemento en un diccionario plano.

    - Las etiquetas repetidas se agrupan en una lista.
    - Los hijos con estructura propia se convierten recursivamente.
    - Las etiquetas vacias (banderas como ``<deity/>``) valen ``True``.
    """
    out: dict = {}
    for child in elem:
        key = normalize_key(child.tag)
        if len(child):
            value: object = elem_to_dict(child)
        else:
            text = (child.text or "").strip()
            value = text if text else True
        if key in out:
            existing = out[key]
            if isinstance(existing, list):
                existing.append(value)
            else:
                out[key] = [existing, value]
        else:
            out[key] = value
    return out


def iter_sections(
    path: Path,
    progress: Optional[Callable[[int, int], None]] = None,
    progress_every: int = 4 << 20,
) -> Iterator[tuple[str, Optional[ET.Element], Optional[str]]]:
    """Recorre el XML en streaming y va soltando registros.

    Produce tuplas ``(seccion, elemento, valor_escalar)``:

    - Para cada registro (``<site>``, ``<historical_figure>``...) devuelve
      ``(nombre_de_seccion, elemento, None)``. El elemento se libera justo
      despues de cederlo, asi que hay que consumirlo en el momento.
    - Para los campos sueltos de la raiz (``<name>``, ``<altname>``) devuelve
      ``(nombre_campo, None, texto)``.

    La memoria se mantiene plana: los registros ya procesados se eliminan del
    arbol conforme se avanza.
    """
    stream = SanitizedXMLStream(path)
    last_report = 0
    try:
        context = ET.iterparse(stream, events=("start", "end"))
        stack: list[ET.Element] = []
        section_elem: Optional[ET.Element] = None
        section_name = ""
        section_had_records = False
        try:
            for event, elem in context:
                if event == "start":
                    stack.append(elem)
                    if len(stack) == 2:
                        section_elem = elem
                        section_name = normalize_key(elem.tag)
                        section_had_records = False
                    continue

                depth = len(stack)
                stack.pop()

                if depth == 3:
                    # Registro dentro de una seccion.
                    section_had_records = True
                    yield section_name, elem, None
                    if section_elem is not None:
                        section_elem.clear()
                elif depth == 2:
                    name = normalize_key(elem.tag)
                    text = (elem.text or "").strip()
                    # Un campo suelto de la raíz (<name>, <altname>) frente a una
                    # seccion contenedora: la seccion ya ha soltado registros.
                    if not section_had_records and text:
                        yield name, None, text
                    elem.clear()
                    section_elem = None
                    section_had_records = False
                elif depth == 1:
                    elem.clear()

                if progress is not None and stream.raw_bytes_read - last_report >= progress_every:
                    last_report = stream.raw_bytes_read
                    progress(stream.raw_bytes_read, stream.total_bytes)
        except ET.ParseError as exc:
            raise CorruptXMLError(path.name, f"Error de XML en {exc}") from exc

        if progress is not None:
            progress(stream.total_bytes, stream.total_bytes)
    finally:
        stream.close()
