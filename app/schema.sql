-- =====================================================================
-- Esquema de ProLegends
-- ---------------------------------------------------------------------
-- Cada export de legends es una FOTO del mundo en una fecha concreta, asi
-- que casi todas las tablas llevan export_id: eso permite tener varios
-- mundos y varias fechas del mismo mundo conviviendo, y comparar (diff)
-- dos exports sin ambiguedad.
--
-- Los identificadores locales del XML (site_id, hf_id, ...) NO son unicos
-- entre exports: la clave siempre es (export_id, id_local).
--
-- Toda tabla guarda ademas un data_json con el registro completo tal cual
-- venia del XML. Asi se pueden anadir vistas nuevas leyendo campos que hoy
-- no se usan, sin volver a tocar el parser ni reimportar.
-- =====================================================================

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS schema_info (
    key   TEXT PRIMARY KEY,
    value TEXT
);

-- --------------------------------------------------------------- mundos
CREATE TABLE IF NOT EXISTS worlds (
    id         INTEGER PRIMARY KEY,
    name       TEXT NOT NULL UNIQUE,
    altname    TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS exports (
    id           INTEGER PRIMARY KEY,
    world_id     INTEGER REFERENCES worlds(id) ON DELETE CASCADE,
    prefix       TEXT NOT NULL,          -- region1-00101-07-24
    file_token   TEXT,                   -- region1
    game_year    INTEGER,
    game_month   INTEGER,
    game_day     INTEGER,
    main_file    TEXT,
    plus_file    TEXT,
    main_size    INTEGER,
    plus_size    INTEGER,
    fingerprint  TEXT NOT NULL UNIQUE,   -- evita reprocesar lo ya importado
    imported_at  TEXT,
    status       TEXT NOT NULL DEFAULT 'pendiente',
    message      TEXT,
    min_x INTEGER, min_y INTEGER, max_x INTEGER, max_y INTEGER,
    world_width  INTEGER,
    world_height INTEGER,
    min_year     INTEGER,
    max_year     INTEGER,
    counts_json  TEXT
);
CREATE INDEX IF NOT EXISTS ix_exports_world ON exports(world_id, game_year, game_month, game_day);

CREATE TABLE IF NOT EXISTS world_meta (
    export_id INTEGER NOT NULL REFERENCES exports(id) ON DELETE CASCADE,
    key       TEXT NOT NULL,
    value     TEXT,
    PRIMARY KEY (export_id, key)
);

-- --------------------------------------------------------------- sitios
CREATE TABLE IF NOT EXISTS sites (
    export_id    INTEGER NOT NULL REFERENCES exports(id) ON DELETE CASCADE,
    site_id      INTEGER NOT NULL,
    name         TEXT,
    type         TEXT,
    coord_x      INTEGER,
    coord_y      INTEGER,
    rectangle    TEXT,
    civ_id       INTEGER,          -- del _plus: civilizacion fundadora
    cur_owner_id INTEGER,          -- del _plus: gobierno de sitio actual
    owner_id     INTEGER,          -- reconstruido cronologicamente
    root_civ_id  INTEGER,          -- civilizacion raiz del propietario
    state        TEXT,             -- activo | ruinas | desconocido
    founded_year INTEGER,
    data_json    TEXT,
    PRIMARY KEY (export_id, site_id)
);
CREATE INDEX IF NOT EXISTS ix_sites_coord ON sites(export_id, coord_x, coord_y);
CREATE INDEX IF NOT EXISTS ix_sites_type  ON sites(export_id, type);
CREATE INDEX IF NOT EXISTS ix_sites_name  ON sites(export_id, name);

CREATE TABLE IF NOT EXISTS site_structures (
    export_id    INTEGER NOT NULL REFERENCES exports(id) ON DELETE CASCADE,
    site_id      INTEGER NOT NULL,
    structure_id INTEGER NOT NULL,
    name         TEXT,
    type         TEXT,
    subtype      TEXT,
    data_json    TEXT,
    PRIMARY KEY (export_id, site_id, structure_id)
);

-- Historico de propietarios reconstruido a partir de los eventos.
CREATE TABLE IF NOT EXISTS site_ownership (
    export_id       INTEGER NOT NULL REFERENCES exports(id) ON DELETE CASCADE,
    site_id         INTEGER NOT NULL,
    year            INTEGER NOT NULL,
    seconds72       INTEGER NOT NULL DEFAULT 0,
    owner_entity_id INTEGER,
    state           TEXT NOT NULL,      -- activo | ruinas
    event_id        INTEGER,
    event_type      TEXT,
    source          TEXT NOT NULL       -- evento | inicial
);
CREATE INDEX IF NOT EXISTS ix_ownership ON site_ownership(export_id, site_id, year, seconds72);
CREATE INDEX IF NOT EXISTS ix_ownership_year ON site_ownership(export_id, year);

-- ------------------------------------------------------------ entidades
CREATE TABLE IF NOT EXISTS entities (
    export_id INTEGER NOT NULL REFERENCES exports(id) ON DELETE CASCADE,
    entity_id INTEGER NOT NULL,
    name      TEXT,
    type      TEXT,
    race      TEXT,
    parent_id INTEGER,
    root_id   INTEGER,
    depth     INTEGER DEFAULT 0,
    data_json TEXT,
    PRIMARY KEY (export_id, entity_id)
);
CREATE INDEX IF NOT EXISTS ix_entities_root ON entities(export_id, root_id);
CREATE INDEX IF NOT EXISTS ix_entities_type ON entities(export_id, type);

CREATE TABLE IF NOT EXISTS entity_children (
    export_id INTEGER NOT NULL REFERENCES exports(id) ON DELETE CASCADE,
    parent_id INTEGER NOT NULL,
    child_id  INTEGER NOT NULL,
    PRIMARY KEY (export_id, parent_id, child_id)
);

CREATE TABLE IF NOT EXISTS entity_sites (
    export_id INTEGER NOT NULL REFERENCES exports(id) ON DELETE CASCADE,
    entity_id INTEGER NOT NULL,
    site_id   INTEGER NOT NULL,
    link_type TEXT
);
CREATE INDEX IF NOT EXISTS ix_entity_sites ON entity_sites(export_id, entity_id);
CREATE INDEX IF NOT EXISTS ix_entity_sites_site ON entity_sites(export_id, site_id);

CREATE TABLE IF NOT EXISTS entity_positions (
    export_id   INTEGER NOT NULL REFERENCES exports(id) ON DELETE CASCADE,
    entity_id   INTEGER NOT NULL,
    position_id INTEGER NOT NULL,
    name        TEXT,
    name_male   TEXT,
    name_female TEXT,
    data_json   TEXT,
    PRIMARY KEY (export_id, entity_id, position_id)
);

CREATE TABLE IF NOT EXISTS entity_position_assignments (
    export_id     INTEGER NOT NULL REFERENCES exports(id) ON DELETE CASCADE,
    entity_id     INTEGER NOT NULL,
    assignment_id INTEGER NOT NULL,
    position_id   INTEGER,
    hfid          INTEGER,
    data_json     TEXT,
    PRIMARY KEY (export_id, entity_id, assignment_id)
);
CREATE INDEX IF NOT EXISTS ix_assign_hf ON entity_position_assignments(export_id, hfid);

-- --------------------------------------------------- figuras historicas
CREATE TABLE IF NOT EXISTS historical_figures (
    export_id        INTEGER NOT NULL REFERENCES exports(id) ON DELETE CASCADE,
    hf_id            INTEGER NOT NULL,
    name             TEXT,
    race             TEXT,
    caste            TEXT,
    birth_year       INTEGER,
    birth_seconds    INTEGER,
    death_year       INTEGER,
    death_seconds    INTEGER,
    alive            INTEGER DEFAULT 0,   -- death_year == -1
    appeared         INTEGER,
    associated_type  TEXT,
    is_deity         INTEGER DEFAULT 0,
    is_force         INTEGER DEFAULT 0,
    is_ghost         INTEGER DEFAULT 0,
    is_animated      INTEGER DEFAULT 0,
    is_adventurer    INTEGER DEFAULT 0,
    kills            INTEGER DEFAULT 0,   -- calculado desde los eventos
    data_json        TEXT,
    PRIMARY KEY (export_id, hf_id)
);
CREATE INDEX IF NOT EXISTS ix_hf_name  ON historical_figures(export_id, name);
CREATE INDEX IF NOT EXISTS ix_hf_race  ON historical_figures(export_id, race);
CREATE INDEX IF NOT EXISTS ix_hf_alive ON historical_figures(export_id, alive);
CREATE INDEX IF NOT EXISTS ix_hf_kills ON historical_figures(export_id, kills DESC);

CREATE TABLE IF NOT EXISTS hf_entity_links (
    export_id     INTEGER NOT NULL REFERENCES exports(id) ON DELETE CASCADE,
    hf_id         INTEGER NOT NULL,
    entity_id     INTEGER,
    link_type     TEXT,
    link_strength INTEGER,
    former        INTEGER DEFAULT 0
);
CREATE INDEX IF NOT EXISTS ix_hfent_hf  ON hf_entity_links(export_id, hf_id);
CREATE INDEX IF NOT EXISTS ix_hfent_ent ON hf_entity_links(export_id, entity_id);

CREATE TABLE IF NOT EXISTS hf_links (
    export_id     INTEGER NOT NULL REFERENCES exports(id) ON DELETE CASCADE,
    hf_id         INTEGER NOT NULL,
    other_hf_id   INTEGER,
    link_type     TEXT,
    link_strength INTEGER
);
CREATE INDEX IF NOT EXISTS ix_hflinks ON hf_links(export_id, hf_id);

CREATE TABLE IF NOT EXISTS hf_skills (
    export_id INTEGER NOT NULL REFERENCES exports(id) ON DELETE CASCADE,
    hf_id     INTEGER NOT NULL,
    skill     TEXT,
    total_ip  INTEGER
);
CREATE INDEX IF NOT EXISTS ix_hfskills ON hf_skills(export_id, hf_id);

-- Valores simples y repetibles: esferas, objetivos, secretos conocidos...
CREATE TABLE IF NOT EXISTS hf_traits (
    export_id INTEGER NOT NULL REFERENCES exports(id) ON DELETE CASCADE,
    hf_id     INTEGER NOT NULL,
    kind      TEXT NOT NULL,   -- sphere | goal | secreto | interaccion | identidad
    value     TEXT
);
CREATE INDEX IF NOT EXISTS ix_hftraits ON hf_traits(export_id, hf_id, kind);

CREATE TABLE IF NOT EXISTS hf_site_links (
    export_id INTEGER NOT NULL REFERENCES exports(id) ON DELETE CASCADE,
    hf_id     INTEGER NOT NULL,
    site_id   INTEGER,
    link_type TEXT,
    sub_id    INTEGER
);
CREATE INDEX IF NOT EXISTS ix_hfsite    ON hf_site_links(export_id, hf_id);
CREATE INDEX IF NOT EXISTS ix_hfsite_st ON hf_site_links(export_id, site_id);

CREATE TABLE IF NOT EXISTS hf_plots (
    export_id INTEGER NOT NULL REFERENCES exports(id) ON DELETE CASCADE,
    hf_id     INTEGER NOT NULL,
    plot_idx  INTEGER NOT NULL,
    type      TEXT,
    agreement_id INTEGER,
    parent_plot_hfid INTEGER,
    data_json TEXT,
    PRIMARY KEY (export_id, hf_id, plot_idx)
);

-- ------------------------------------------------------------ artefactos
CREATE TABLE IF NOT EXISTS artifacts (
    export_id     INTEGER NOT NULL REFERENCES exports(id) ON DELETE CASCADE,
    artifact_id   INTEGER NOT NULL,
    name          TEXT,
    item          TEXT,
    item_type     TEXT,
    item_subtype  TEXT,
    mat           TEXT,
    site_id       INTEGER,
    holder_hfid   INTEGER,
    structure_local_id INTEGER,
    page_number   INTEGER,
    writing       TEXT,
    data_json     TEXT,
    PRIMARY KEY (export_id, artifact_id)
);
CREATE INDEX IF NOT EXISTS ix_art_site   ON artifacts(export_id, site_id);
CREATE INDEX IF NOT EXISTS ix_art_holder ON artifacts(export_id, holder_hfid);
CREATE INDEX IF NOT EXISTS ix_art_name   ON artifacts(export_id, name);

-- --------------------------------------------------------------- eventos
CREATE TABLE IF NOT EXISTS events (
    export_id        INTEGER NOT NULL REFERENCES exports(id) ON DELETE CASCADE,
    event_id         INTEGER NOT NULL,
    year             INTEGER,
    seconds72        INTEGER,
    type             TEXT,
    site_id          INTEGER,
    civ_id           INTEGER,
    site_civ_id      INTEGER,
    attacker_civ_id  INTEGER,
    defender_civ_id  INTEGER,
    hfid             INTEGER,
    slayer_hfid      INTEGER,
    entity_id        INTEGER,
    artifact_id      INTEGER,
    structure_id     INTEGER,
    subregion_id     INTEGER,
    data_json        TEXT,
    PRIMARY KEY (export_id, event_id)
);
CREATE INDEX IF NOT EXISTS ix_ev_year   ON events(export_id, year);
CREATE INDEX IF NOT EXISTS ix_ev_type   ON events(export_id, type, year);
CREATE INDEX IF NOT EXISTS ix_ev_site   ON events(export_id, site_id, year);
CREATE INDEX IF NOT EXISTS ix_ev_hf     ON events(export_id, hfid);
CREATE INDEX IF NOT EXISTS ix_ev_slayer ON events(export_id, slayer_hfid);
CREATE INDEX IF NOT EXISTS ix_ev_civ    ON events(export_id, civ_id);
CREATE INDEX IF NOT EXISTS ix_ev_art    ON events(export_id, artifact_id);

CREATE TABLE IF NOT EXISTS event_collections (
    export_id      INTEGER NOT NULL REFERENCES exports(id) ON DELETE CASCADE,
    collection_id  INTEGER NOT NULL,
    type           TEXT,
    name           TEXT,
    start_year     INTEGER,
    end_year       INTEGER,
    site_id        INTEGER,
    attacking_enid INTEGER,
    defending_enid INTEGER,
    data_json      TEXT,
    PRIMARY KEY (export_id, collection_id)
);
CREATE INDEX IF NOT EXISTS ix_col_type ON event_collections(export_id, type);
CREATE INDEX IF NOT EXISTS ix_col_site ON event_collections(export_id, site_id);

CREATE TABLE IF NOT EXISTS collection_events (
    export_id     INTEGER NOT NULL REFERENCES exports(id) ON DELETE CASCADE,
    collection_id INTEGER NOT NULL,
    event_id      INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_colev ON collection_events(export_id, collection_id);

-- ------------------------------------------------------- geografia y mas
CREATE TABLE IF NOT EXISTS regions (
    export_id INTEGER NOT NULL REFERENCES exports(id) ON DELETE CASCADE,
    region_id INTEGER NOT NULL,
    name      TEXT,
    type      TEXT,
    underground INTEGER DEFAULT 0,
    depth     INTEGER,
    data_json TEXT,
    PRIMARY KEY (export_id, region_id, underground)
);

CREATE TABLE IF NOT EXISTS entity_populations (
    export_id INTEGER NOT NULL REFERENCES exports(id) ON DELETE CASCADE,
    pop_id    INTEGER NOT NULL,
    race      TEXT,
    count     INTEGER,
    civ_id    INTEGER,
    data_json TEXT,
    PRIMARY KEY (export_id, pop_id)
);

CREATE TABLE IF NOT EXISTS written_contents (
    export_id INTEGER NOT NULL REFERENCES exports(id) ON DELETE CASCADE,
    wc_id     INTEGER NOT NULL,
    title     TEXT,
    type      TEXT,
    author_hfid INTEGER,
    form      TEXT,
    data_json TEXT,
    PRIMARY KEY (export_id, wc_id)
);

-- Cajon generico: cualquier seccion del XML que todavia no tenga tabla
-- propia se guarda aqui tal cual. Sirve para anadir vistas nuevas sin
-- volver a tocar el parser.
CREATE TABLE IF NOT EXISTS raw_records (
    export_id INTEGER NOT NULL REFERENCES exports(id) ON DELETE CASCADE,
    section   TEXT NOT NULL,
    record_id INTEGER,
    data_json TEXT
);
CREATE INDEX IF NOT EXISTS ix_raw ON raw_records(export_id, section);

-- ------------------------------------------------------- mi fortaleza
CREATE TABLE IF NOT EXISTS fortress_choice (
    world_id  INTEGER PRIMARY KEY REFERENCES worlds(id) ON DELETE CASCADE,
    site_id   INTEGER NOT NULL,
    chosen_by TEXT NOT NULL,      -- automatico | manual
    updated_at TEXT
);

-- -------------------------------------------------- cronicas de IA (fase 2)
CREATE TABLE IF NOT EXISTS chronicles (
    id           INTEGER PRIMARY KEY,
    world_id     INTEGER REFERENCES worlds(id) ON DELETE CASCADE,
    export_id    INTEGER,
    scope_type   TEXT NOT NULL,   -- years | figure | fortress
    scope_key    TEXT NOT NULL,
    model        TEXT,
    context_hash TEXT,
    title        TEXT,
    text         TEXT,
    tokens_in    INTEGER,
    tokens_out   INTEGER,
    created_at   TEXT,
    UNIQUE (world_id, scope_type, scope_key)
);
