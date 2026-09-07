"""Importador: del XML a SQLite.

Recorre el fichero principal y despues el _plus, fusionando por ID (los dos
comparten los identificadores de entidad, sitio, figura y evento, pero cada uno
trae campos distintos). Al terminar reconstruye lo que el XML no dice de forma
explicita: la jerarquia de entidades y la propiedad de cada sitio a lo largo de
los años.
"""

from __future__ import annotations

import json
import sqlite3
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Optional

from .. import db as dbmod
from ..errors import CorruptXMLError, ProLegendsError
from . import legends as L
from .discover import ExportPair, discover
from .progress import ConsoleProgress
from .xmlstream import elem_to_dict, iter_sections, normalize_key

BATCH = 2000

# Secciones que se guardan en memoria durante toda la importación porque son
# pequenas y hacen falta enteras para reconstruir jerarquias y propiedad.
SMALL_SECTIONS = {"sites", "entities", "artifacts", "regions", "underground_regions",
                  "entity_populations"}

# Secciones que no aportan nada y ocupan mucho: se descartan explicitamente.
SKIP_SECTIONS = {"creature_raw"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Importer:
    def __init__(
        self,
        conn: sqlite3.Connection,
        pair: ExportPair,
        verbose: bool = True,
        log: Optional[Callable[[str], None]] = None,
    ) -> None:
        self.conn = conn
        self.pair = pair
        self.verbose = verbose
        self.log = log or (lambda msg: print(msg))
        self.export_id: int = 0
        self.world_id: int = 0
        self.world_name: str = ""
        self.world_altname: str = ""
        self.meta: dict[str, str] = {}

        # Registros pequenos, fusionados en memoria.
        self.small: dict[str, dict[int, dict]] = {name: {} for name in SMALL_SECTIONS}
        # Contadores.
        self.counts: dict[str, int] = {}
        # Buffers de escritura.
        self._buf: dict[str, list] = {}

    # ------------------------------------------------------------ publico
    def run(self) -> Optional[int]:
        fingerprint = self.pair.fingerprint()
        existing = dbmod.one(
            self.conn, "SELECT id, status FROM exports WHERE fingerprint = ?", (fingerprint,)
        )
        if existing and existing["status"] == "ok":
            self.log(f"  ya importado, se omite: {self.pair.describe()}")
            return existing["id"]
        if existing:
            self._delete_export(existing["id"])

        started = time.time()
        self.log(f"\n> Importando {self.pair.describe()}")

        self.export_id = self._create_export_row(fingerprint)
        # Todo el volcado va en UNA transaccion. Antes cada tanda de 2000 filas
        # se confirmaba por su cuenta, y confirmar 244 veces costaba mas que
        # escribir: un export de 50 MB pasa de 32 a 9 segundos. Ademas, si algo
        # falla a mitad no quedan filas sueltas de un export incompleto.
        # La fila del export ya esta escrita y confirmada, asi que el rollback
        # no se la lleva y se puede marcar como fallida.
        propia = not self.conn.in_transaction
        if propia:
            self.conn.execute("BEGIN")
        try:
            self._parse_file(self.pair.main, "principal")
            if self.pair.plus:
                self._parse_file(self.pair.plus, "plus (DFHack)")
            self._flush_all()
            self._write_small_sections()
            self._derive()
            if propia:
                self.conn.execute("COMMIT")
            self._finalize(ok=True, message="; ".join(self.pair.warnings))
        except ProLegendsError as exc:
            self.conn.rollback()
            self._finalize(ok=False, message=exc.message + (" " + exc.detail if exc.detail else ""))
            raise
        except Exception as exc:  # pragma: no cover - red de seguridad
            self.conn.rollback()
            self._finalize(ok=False, message=f"Fallo inesperado: {exc}")
            raise ProLegendsError(
                f"No se ha podido importar '{self.pair.prefix}'.", str(exc)
            ) from exc

        elapsed = time.time() - started
        resumen = ", ".join(f"{v} {k}" for k, v in sorted(self.counts.items()) if v)
        self.log(f"  OK en {elapsed:.1f}s -> {resumen}")
        return self.export_id

    # ------------------------------------------------------ ciclo de vida
    def _create_export_row(self, fingerprint: str) -> int:
        # Un mismo prefijo (<mundo>-<anyo>-<mes>-<día>) identifica un export
        # concreto. Si se vuelve a exportar esa misma fecha con otro contenido,
        # sustituye al anterior en lugar de duplicarlo.
        self.conn.execute("DELETE FROM exports WHERE prefix = ?", (self.pair.prefix,))
        cur = self.conn.execute(
            """INSERT INTO exports
               (world_id, prefix, file_token, game_year, game_month, game_day,
                main_file, plus_file, main_size, plus_size, fingerprint, status)
               VALUES (NULL, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pendiente')""",
            (
                self.pair.prefix,
                self.pair.file_token,
                self.pair.game_year,
                self.pair.game_month,
                self.pair.game_day,
                str(self.pair.main) if self.pair.main else None,
                str(self.pair.plus) if self.pair.plus else None,
                self.pair.main.stat().st_size if self.pair.main else None,
                self.pair.plus.stat().st_size if self.pair.plus else None,
                fingerprint,
            ),
        )
        return int(cur.lastrowid)

    def _delete_export(self, export_id: int) -> None:
        self.conn.execute("DELETE FROM exports WHERE id = ?", (export_id,))

    TABLAS_RESUMEN = (
        ("sitios", "sites"),
        ("entidades", "entities"),
        ("figuras", "historical_figures"),
        ("eventos", "events"),
        ("artefactos", "artifacts"),
        ("batallas y guerras", "event_collections"),
        ("cambios de propiedad", "site_ownership"),
    )

    def _real_counts(self) -> dict:
        salida = {}
        for etiqueta, tabla in self.TABLAS_RESUMEN:
            try:
                salida[etiqueta] = self.conn.execute(
                    f"SELECT COUNT(*) FROM {tabla} WHERE export_id = ?", (self.export_id,)
                ).fetchone()[0]
            except sqlite3.Error:
                salida[etiqueta] = 0
        return salida

    def _finalize(self, ok: bool, message: str = "") -> None:
        if ok:
            self.counts = self._real_counts()
        self.conn.execute(
            "UPDATE exports SET status = ?, message = ?, imported_at = ?, counts_json = ? WHERE id = ?",
            (
                "ok" if ok else "error",
                message or None,
                _now(),
                json.dumps(self.counts, ensure_ascii=False),
                self.export_id,
            ),
        )

    # ------------------------------------------------------------ parseo
    def _parse_file(self, path: Optional[Path], etiqueta: str) -> None:
        if path is None:
            return
        size = path.stat().st_size
        bar = ConsoleProgress(f"{etiqueta}", size, enabled=self.verbose)

        def on_progress(done: int, total: int) -> None:
            bar.update(done)

        try:
            for section, elem, scalar in iter_sections(path, progress=on_progress):
                if elem is None:
                    self._handle_scalar(section, scalar or "")
                    continue
                if section in SKIP_SECTIONS:
                    continue
                self._handle_record(section, elem)
        except CorruptXMLError:
            if self.verbose:
                sys.stdout.write("\n")
            raise
        bar.finish()
        self._flush_all()

    def _handle_scalar(self, key: str, value: str) -> None:
        if not value:
            return
        if key == "name" and not self.world_name:
            self.world_name = value
        elif key == "altname" and not self.world_altname:
            self.world_altname = value
        self.meta.setdefault(key, value)

    def _handle_record(self, section: str, elem) -> None:
        record = elem_to_dict(elem)
        handler = getattr(self, f"_sec_{section}", None)
        if handler is not None:
            handler(record)
        elif section in self.small:
            self._merge_small(section, record)
        else:
            self._raw(section, record)
        self.counts[section] = self.counts.get(section, 0) + 1

    # ------------------------------------------- secciones "pequenas"
    def _merge_small(self, section: str, record: dict) -> None:
        rid = L.as_int(record.get("id"))
        if rid is None:
            self._raw(section, record)
            return
        store = self.small[section]
        store[rid] = L.deep_merge(store[rid], record) if rid in store else record

    _sec_sites = lambda self, r: self._merge_small("sites", r)                    # noqa: E731
    _sec_entities = lambda self, r: self._merge_small("entities", r)              # noqa: E731
    _sec_artifacts = lambda self, r: self._merge_small("artifacts", r)            # noqa: E731
    _sec_entity_populations = lambda self, r: self._merge_small("entity_populations", r)  # noqa: E731

    def _sec_regions(self, record: dict) -> None:
        self._merge_small("regions", record)

    def _sec_underground_regions(self, record: dict) -> None:
        self._merge_small("underground_regions", record)

    # ----------------------------------------------- secciones grandes
    def _sec_historical_figures(self, record: dict) -> None:
        self._push("hf", record)

    def _sec_historical_events(self, record: dict) -> None:
        self._push("event", record)

    def _sec_historical_event_collections(self, record: dict) -> None:
        self._push("collection", record)

    def _sec_written_contents(self, record: dict) -> None:
        self._push("wc", record)

    def _raw(self, section: str, record: dict) -> None:
        self._push("raw", (section, record))

    # ------------------------------------------------------- buffering
    def _push(self, kind: str, item: Any) -> None:
        buf = self._buf.setdefault(kind, [])
        buf.append(item)
        if len(buf) >= BATCH:
            self._flush(kind)

    def _flush_all(self) -> None:
        for kind in list(self._buf):
            self._flush(kind)

    def _flush(self, kind: str) -> None:
        items = self._buf.get(kind)
        if not items:
            return
        self._buf[kind] = []
        getattr(self, f"_write_{kind}")(items)

    # -------------------------------------------------------- escritura
    def _merge_existing(self, table: str, pk: str, records: list[dict]) -> list[dict]:
        """Fusiona los registros nuevos con lo que ya haya en la tabla.

        Es lo que permite que el _plus complete al principal: mismos IDs,
        campos distintos.
        """
        ids: list[int] = []
        keyed: dict[int, dict] = {}
        for rec in records:
            rid = L.as_int(rec.get("id"))
            if rid is None:
                continue
            if rid in keyed:
                keyed[rid] = L.deep_merge(keyed[rid], rec)
            else:
                keyed[rid] = rec
                ids.append(rid)
        if not keyed:
            return []
        placeholders = ",".join("?" * len(ids))
        rows = self.conn.execute(
            f"SELECT {pk} AS k, data_json FROM {table} "
            f"WHERE export_id = ? AND {pk} IN ({placeholders})",
            (self.export_id, *ids),
        ).fetchall()
        for row in rows:
            previo = json.loads(row["data_json"]) if row["data_json"] else {}
            keyed[row["k"]] = L.deep_merge(previo, keyed[row["k"]])
        return [keyed[i] for i in ids]

    def _write_hf(self, records: list[dict]) -> None:
        merged = self._merge_existing("historical_figures", "hf_id", records)
        filas, links_ent, links_hf, skills, traits, sites, plots = [], [], [], [], [], [], []
        for rec in merged:
            hf_id = L.as_int(rec.get("id"))
            death_year = L.as_int(rec.get("death_year"))
            filas.append(
                (
                    self.export_id,
                    hf_id,
                    L.as_text(rec.get("name")),
                    L.as_text(rec.get("race")),
                    L.as_text(rec.get("caste")),
                    L.as_int(rec.get("birth_year")),
                    L.as_int(rec.get("birth_seconds")),
                    death_year,
                    L.as_int(rec.get("death_seconds")),
                    1 if (death_year is None or death_year == -1) else 0,
                    L.as_int(rec.get("appeared")),
                    L.as_text(rec.get("associated_type")),
                    L.as_flag(rec.get("deity")),
                    L.as_flag(rec.get("force")),
                    L.as_flag(rec.get("ghost")),
                    L.as_flag(rec.get("animated")),
                    L.as_flag(rec.get("adventurer")),
                    L.jdump(rec),
                )
            )
            for link in L.as_list(rec.get("entity_link")):
                if isinstance(link, dict):
                    links_ent.append(
                        (self.export_id, hf_id, L.as_int(link.get("entity_id")),
                         L.as_text(link.get("link_type")), L.as_int(link.get("link_strength")), 0)
                    )
            for link in L.as_list(rec.get("entity_former_position_link")) + L.as_list(
                rec.get("entity_former_positon_link")
            ):
                if isinstance(link, dict):
                    links_ent.append(
                        (self.export_id, hf_id, L.as_int(link.get("entity_id")),
                         "antiguo cargo", None, 1)
                    )
            for link in L.as_list(rec.get("hf_link")):
                if isinstance(link, dict):
                    links_hf.append(
                        (self.export_id, hf_id, L.as_int(link.get("hfid")),
                         L.as_text(link.get("link_type")), L.as_int(link.get("link_strength")))
                    )
            for skill in L.as_list(rec.get("hf_skill")):
                if isinstance(skill, dict):
                    skills.append(
                        (self.export_id, hf_id, L.as_text(skill.get("skill")),
                         L.as_int(skill.get("total_ip")))
                    )
            for kind, key in (
                ("sphere", "sphere"),
                ("goal", "goal"),
                ("secreto", "interaction_knowledge"),
                ("interaccion", "active_interaction"),
                ("identidad", "used_identity_id"),
                ("profesion", "profession"),
            ):
                for value in L.as_list(rec.get(key)):
                    text = L.as_text(value)
                    if text:
                        traits.append((self.export_id, hf_id, kind, text))
            for link in L.as_list(rec.get("site_link")):
                if isinstance(link, dict):
                    sites.append(
                        (self.export_id, hf_id, L.as_int(link.get("site_id")),
                         L.as_text(link.get("link_type")), L.as_int(link.get("sub_id")))
                    )
            for idx, plot in enumerate(L.as_list(rec.get("intrigue_plot"))):
                if isinstance(plot, dict):
                    plots.append(
                        (self.export_id, hf_id, idx, L.as_text(plot.get("type")),
                         L.as_int(plot.get("agreement_id")),
                         L.as_int(plot.get("parent_plot_hfid")), L.jdump(plot))
                    )

        ids = [f[1] for f in filas]
        if ids:
            self._purge_children(ids, (
                ("hf_entity_links", "hf_id"), ("hf_links", "hf_id"), ("hf_skills", "hf_id"),
                ("hf_traits", "hf_id"), ("hf_site_links", "hf_id"), ("hf_plots", "hf_id"),
            ))
        self.conn.executemany(
            """INSERT OR REPLACE INTO historical_figures
               (export_id, hf_id, name, race, caste, birth_year, birth_seconds,
                death_year, death_seconds, alive, appeared, associated_type,
                is_deity, is_force, is_ghost, is_animated, is_adventurer, data_json)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            filas,
        )
        self.conn.executemany(
            "INSERT INTO hf_entity_links (export_id, hf_id, entity_id, link_type, link_strength, former) VALUES (?,?,?,?,?,?)",
            links_ent,
        )
        self.conn.executemany(
            "INSERT INTO hf_links (export_id, hf_id, other_hf_id, link_type, link_strength) VALUES (?,?,?,?,?)",
            links_hf,
        )
        self.conn.executemany(
            "INSERT INTO hf_skills (export_id, hf_id, skill, total_ip) VALUES (?,?,?,?)", skills
        )
        self.conn.executemany(
            "INSERT INTO hf_traits (export_id, hf_id, kind, value) VALUES (?,?,?,?)", traits
        )
        self.conn.executemany(
            "INSERT INTO hf_site_links (export_id, hf_id, site_id, link_type, sub_id) VALUES (?,?,?,?,?)",
            sites,
        )
        self.conn.executemany(
            "INSERT OR REPLACE INTO hf_plots (export_id, hf_id, plot_idx, type, agreement_id, parent_plot_hfid, data_json) VALUES (?,?,?,?,?,?,?)",
            plots,
        )

    def _purge_children(self, ids: list[int], tables: Iterable[tuple[str, str]]) -> None:
        placeholders = ",".join("?" * len(ids))
        for table, column in tables:
            self.conn.execute(
                f"DELETE FROM {table} WHERE export_id = ? AND {column} IN ({placeholders})",
                (self.export_id, *ids),
            )

    def _write_event(self, records: list[dict]) -> None:
        merged = self._merge_existing("events", "event_id", records)
        filas = []
        for rec in merged:
            tipo = L.as_text(rec.get("type"))
            filas.append(
                (
                    self.export_id,
                    L.as_int(rec.get("id")),
                    L.as_int(rec.get("year")),
                    L.as_int(rec.get("seconds72")),
                    tipo,
                    *[L.event_column(rec, col) for col in L.EVENT_COLUMNS],
                    L.jdump(rec),
                )
            )
        self.conn.executemany(
            """INSERT OR REPLACE INTO events
               (export_id, event_id, year, seconds72, type,
                site_id, civ_id, site_civ_id, attacker_civ_id, defender_civ_id,
                hfid, slayer_hfid, entity_id, artifact_id, structure_id, subregion_id,
                data_json)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            filas,
        )

    def _write_collection(self, records: list[dict]) -> None:
        merged = self._merge_existing("event_collections", "collection_id", records)
        filas, enlaces = [], []
        for rec in merged:
            cid = L.as_int(rec.get("id"))
            filas.append(
                (
                    self.export_id, cid,
                    L.as_text(rec.get("type")), L.as_text(rec.get("name")),
                    L.as_int(rec.get("start_year")), L.as_int(rec.get("end_year")),
                    L.as_int(rec.get("site_id")),
                    L.as_int(rec.get("attacking_enid")), L.as_int(rec.get("defending_enid")),
                    L.jdump(rec),
                )
            )
            for ev in L.as_list(rec.get("event")):
                eid = L.as_int(ev)
                if eid is not None:
                    enlaces.append((self.export_id, cid, eid))
        if filas:
            ids = [f[1] for f in filas]
            placeholders = ",".join("?" * len(ids))
            self.conn.execute(
                f"DELETE FROM collection_events WHERE export_id = ? AND collection_id IN ({placeholders})",
                (self.export_id, *ids),
            )
        self.conn.executemany(
            """INSERT OR REPLACE INTO event_collections
               (export_id, collection_id, type, name, start_year, end_year,
                site_id, attacking_enid, defending_enid, data_json)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            filas,
        )
        self.conn.executemany(
            "INSERT INTO collection_events (export_id, collection_id, event_id) VALUES (?,?,?)",
            enlaces,
        )

    def _write_wc(self, records: list[dict]) -> None:
        merged = self._merge_existing("written_contents", "wc_id", records)
        filas = [
            (
                self.export_id, L.as_int(rec.get("id")),
                L.as_text(rec.get("title")), L.as_text(rec.get("type")),
                L.as_int(rec.get("author_hfid")), L.as_text(rec.get("form")),
                L.jdump(rec),
            )
            for rec in merged
        ]
        self.conn.executemany(
            """INSERT OR REPLACE INTO written_contents
               (export_id, wc_id, title, type, author_hfid, form, data_json)
               VALUES (?,?,?,?,?,?,?)""",
            filas,
        )

    def _write_raw(self, items: list[tuple[str, dict]]) -> None:
        filas = [
            (self.export_id, section, L.as_int(rec.get("id")), L.jdump(rec))
            for section, rec in items
        ]
        self.conn.executemany(
            "INSERT INTO raw_records (export_id, section, record_id, data_json) VALUES (?,?,?,?)",
            filas,
        )

    # -------------------------------------------- volcado de lo pequeño
    def _write_small_sections(self) -> None:
        self._write_sites()
        self._write_entities()
        self._write_artifacts()
        self._write_regions()
        self._write_populations()

    def _write_sites(self) -> None:
        filas, estructuras = [], []
        for sid, rec in self.small["sites"].items():
            x, y = L.parse_coords(rec.get("coords"))
            filas.append(
                (
                    self.export_id, sid,
                    L.as_text(rec.get("name")), L.as_text(rec.get("type")),
                    x, y, L.as_text(rec.get("rectangle")),
                    L.as_int(rec.get("civ_id")), L.as_int(rec.get("cur_owner_id")),
                    L.jdump(rec),
                )
            )
            estructuras_rec = rec.get("structures")
            lista = []
            if isinstance(estructuras_rec, dict):
                lista = L.as_list(estructuras_rec.get("structure"))
            elif isinstance(estructuras_rec, list):
                for bloque in estructuras_rec:
                    if isinstance(bloque, dict):
                        lista.extend(L.as_list(bloque.get("structure")))
            vistos = set()
            for st in lista:
                if not isinstance(st, dict):
                    continue
                st_id = L.as_int(st.get("local_id"))
                if st_id is None:
                    st_id = L.as_int(st.get("id"))
                if st_id is None or st_id in vistos:
                    continue
                vistos.add(st_id)
                estructuras.append(
                    (self.export_id, sid, st_id, L.as_text(st.get("name")),
                     L.as_text(st.get("type")), L.as_text(st.get("subtype")), L.jdump(st))
                )
        self.conn.executemany(
            """INSERT OR REPLACE INTO sites
               (export_id, site_id, name, type, coord_x, coord_y, rectangle,
                civ_id, cur_owner_id, data_json)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            filas,
        )
        self.conn.executemany(
            """INSERT OR REPLACE INTO site_structures
               (export_id, site_id, structure_id, name, type, subtype, data_json)
               VALUES (?,?,?,?,?,?,?)""",
            estructuras,
        )

    def _write_entities(self) -> None:
        filas, hijos, enlaces, cargos, asignaciones = [], [], [], [], []
        for eid, rec in self.small["entities"].items():
            filas.append(
                (
                    self.export_id, eid,
                    L.as_text(rec.get("name")), L.as_text(rec.get("type")),
                    L.as_text(rec.get("race")), L.jdump(rec),
                )
            )
            for child in L.as_list(rec.get("child")):
                cid = L.as_int(child)
                if cid is not None:
                    hijos.append((self.export_id, eid, cid))
            for link in L.as_list(rec.get("site_link")):
                if isinstance(link, dict):
                    sid = L.as_int(link.get("site_id"))
                    if sid is not None:
                        enlaces.append((self.export_id, eid, sid, L.as_text(link.get("link_type"))))
            for pos in L.as_list(rec.get("entity_position")):
                if isinstance(pos, dict):
                    cargos.append(
                        (self.export_id, eid, L.as_int(pos.get("id")),
                         L.as_text(pos.get("name")), L.as_text(pos.get("name_male")),
                         L.as_text(pos.get("name_female")), L.jdump(pos))
                    )
            for asig in L.as_list(rec.get("entity_position_assignment")):
                if isinstance(asig, dict):
                    asignaciones.append(
                        (self.export_id, eid, L.as_int(asig.get("id")),
                         L.as_int(asig.get("position_id")), L.as_int(asig.get("histfig")),
                         L.jdump(asig))
                    )
        self.conn.executemany(
            """INSERT OR REPLACE INTO entities
               (export_id, entity_id, name, type, race, data_json) VALUES (?,?,?,?,?,?)""",
            filas,
        )
        self.conn.executemany(
            "INSERT OR REPLACE INTO entity_children (export_id, parent_id, child_id) VALUES (?,?,?)",
            hijos,
        )
        self.conn.executemany(
            "INSERT INTO entity_sites (export_id, entity_id, site_id, link_type) VALUES (?,?,?,?)",
            enlaces,
        )
        self.conn.executemany(
            """INSERT OR REPLACE INTO entity_positions
               (export_id, entity_id, position_id, name, name_male, name_female, data_json)
               VALUES (?,?,?,?,?,?,?)""",
            [c for c in cargos if c[2] is not None],
        )
        self.conn.executemany(
            """INSERT OR REPLACE INTO entity_position_assignments
               (export_id, entity_id, assignment_id, position_id, hfid, data_json)
               VALUES (?,?,?,?,?,?)""",
            [a for a in asignaciones if a[2] is not None],
        )

    def _write_artifacts(self) -> None:
        filas = []
        for aid, rec in self.small["artifacts"].items():
            item = rec.get("item") if isinstance(rec.get("item"), dict) else {}
            filas.append(
                (
                    self.export_id, aid,
                    L.as_text(rec.get("name")),
                    L.as_text(item.get("name_string")) or L.as_text(rec.get("item")),
                    L.as_text(rec.get("item_type")) or L.as_text(item.get("item_type")),
                    L.as_text(rec.get("item_subtype")) or L.as_text(item.get("item_subtype")),
                    L.as_text(rec.get("mat")) or L.as_text(item.get("mat")),
                    L.as_int(rec.get("site_id")),
                    L.as_int(rec.get("holder_hfid")),
                    L.as_int(rec.get("structure_local_id")),
                    L.as_int(rec.get("page_number")) or L.as_int(item.get("page_number")),
                    L.as_text(rec.get("writing")) or L.as_text(item.get("writing")),
                    L.jdump(rec),
                )
            )
        self.conn.executemany(
            """INSERT OR REPLACE INTO artifacts
               (export_id, artifact_id, name, item, item_type, item_subtype, mat,
                site_id, holder_hfid, structure_local_id, page_number, writing, data_json)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            filas,
        )

    def _write_regions(self) -> None:
        filas = []
        for underground, seccion in ((0, "regions"), (1, "underground_regions")):
            for rid, rec in self.small[seccion].items():
                filas.append(
                    (self.export_id, rid, L.as_text(rec.get("name")), L.as_text(rec.get("type")),
                     underground, L.as_int(rec.get("depth")), L.jdump(rec))
                )
        self.conn.executemany(
            """INSERT OR REPLACE INTO regions
               (export_id, region_id, name, type, underground, depth, data_json)
               VALUES (?,?,?,?,?,?,?)""",
            filas,
        )

    def _write_populations(self) -> None:
        filas = []
        for pid, rec in self.small["entity_populations"].items():
            filas.append(
                (self.export_id, pid, L.as_text(rec.get("race")), L.as_int(rec.get("count")),
                 L.as_int(rec.get("civ_id")), L.jdump(rec))
            )
        self.conn.executemany(
            """INSERT OR REPLACE INTO entity_populations
               (export_id, pop_id, race, count, civ_id, data_json) VALUES (?,?,?,?,?,?)""",
            filas,
        )

    # ------------------------------------------------------- derivados
    def _derive(self) -> None:
        from ..model import entities as ent_model
        from ..model import ownership as own_model

        self._attach_world()
        ent_model.rebuild_hierarchy(self.conn, self.export_id)
        own_model.rebuild_ownership(self.conn, self.export_id)
        self._count_kills()
        self._world_bounds()

    def _nombre_del_mundo(self) -> tuple[Optional[str], Optional[str]]:
        """Nombre del mundo, mirando tambien la cabecera de los dos ficheros.

        Hay exports cuyo fichero principal no trae el nombre del mundo; en esos
        casos lo pone el _plus de DFHack. Sin esta pasada el mundo acabaria
        llamandose como el fichero, que no dice nada.
        """
        from . import organizer

        nombre, altnombre = self.world_name or None, self.world_altname or None
        if nombre and altnombre:
            return nombre, altnombre
        for fichero in (self.pair.main, self.pair.plus):
            if fichero is None:
                continue
            cabecera = organizer.leer_cabecera(fichero)
            nombre = nombre or cabecera.get("nombre")
            altnombre = altnombre or cabecera.get("altnombre")
            if nombre and altnombre:
                break
        return nombre, altnombre

    def _attach_world(self) -> None:
        nombre, altnombre = self._nombre_del_mundo()
        if altnombre:
            self.world_altname = altnombre
        name = nombre or self.pair.file_token or self.pair.prefix
        row = dbmod.one(self.conn, "SELECT id FROM worlds WHERE name = ?", (name,))
        if row:
            self.world_id = row["id"]
            if self.world_altname:
                self.conn.execute(
                    "UPDATE worlds SET altname = COALESCE(altname, ?) WHERE id = ?",
                    (self.world_altname, self.world_id),
                )
        else:
            cur = self.conn.execute(
                "INSERT INTO worlds (name, altname, created_at) VALUES (?,?,?)",
                (name, self.world_altname or None, _now()),
            )
            self.world_id = int(cur.lastrowid)
        self.conn.execute(
            "UPDATE exports SET world_id = ? WHERE id = ?", (self.world_id, self.export_id)
        )
        self.conn.executemany(
            "INSERT OR REPLACE INTO world_meta (export_id, key, value) VALUES (?,?,?)",
            [(self.export_id, k, v) for k, v in self.meta.items()],
        )

    def _count_kills(self) -> None:
        self.conn.execute(
            """UPDATE historical_figures
                  SET kills = COALESCE((
                        SELECT COUNT(*) FROM events e
                         WHERE e.export_id = historical_figures.export_id
                           AND e.slayer_hfid = historical_figures.hf_id), 0)
                WHERE export_id = ?""",
            (self.export_id,),
        )

    def _world_bounds(self) -> None:
        # El tamaño del mundo se DEDUCE de las coordenadas observadas; no se
        # asume ninguno de los tamanos estandar de generación.
        row = self.conn.execute(
            """SELECT MIN(coord_x) mnx, MIN(coord_y) mny, MAX(coord_x) mxx, MAX(coord_y) mxy
                 FROM sites WHERE export_id = ? AND coord_x IS NOT NULL""",
            (self.export_id,),
        ).fetchone()
        years = self.conn.execute(
            "SELECT MIN(year) a, MAX(year) b FROM events WHERE export_id = ? AND year >= 0",
            (self.export_id,),
        ).fetchone()
        mnx, mny = row["mnx"], row["mny"]
        mxx, mxy = row["mxx"], row["mxy"]
        width = (mxx + 1) if mxx is not None else None
        height = (mxy + 1) if mxy is not None else None
        self.conn.execute(
            """UPDATE exports SET min_x=?, min_y=?, max_x=?, max_y=?,
                      world_width=?, world_height=?, min_year=?, max_year=?
                WHERE id = ?""",
            (mnx, mny, mxx, mxy, width, height, years["a"], years["b"], self.export_id),
        )


# ------------------------------------------------------------------ API alta
def import_all(
    conn: sqlite3.Connection,
    imports_dir: Optional[Path] = None,
    verbose: bool = True,
    log: Optional[Callable[[str], None]] = None,
    only_prefix: Optional[str] = None,
) -> dict:
    """Procesa todo lo que haya en data/imports/ y devuelve un resumen."""
    from .. import config

    log = log or (lambda msg: print(msg))
    imports_dir = Path(imports_dir or config.IMPORTS_DIR)
    pares, avisos = discover(imports_dir)
    for aviso in avisos:
        log(f"  [aviso] {aviso}")

    if only_prefix:
        pares = [p for p in pares if p.prefix == only_prefix]

    resultado = {"importados": [], "omitidos": [], "errores": [], "avisos": avisos}
    for par in pares:
        try:
            antes = dbmod.one(
                conn, "SELECT id FROM exports WHERE fingerprint = ? AND status = 'ok'",
                (par.fingerprint(),),
            )
            export_id = Importer(conn, par, verbose=verbose, log=log).run()
            if antes:
                resultado["omitidos"].append(par.prefix)
            else:
                resultado["importados"].append({"prefix": par.prefix, "export_id": export_id})
        except ProLegendsError as exc:
            log(f"  [ERROR] {par.prefix}: {exc.message}")
            resultado["errores"].append({"prefix": par.prefix, "error": exc.message,
                                         "detalle": exc.detail})
        except Exception as exc:  # pragma: no cover
            log(f"  [ERROR] {par.prefix}: {exc}")
            resultado["errores"].append({"prefix": par.prefix, "error": str(exc)})
    return resultado
