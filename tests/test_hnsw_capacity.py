"""Tests for the #1222 HNSW capacity probe and BM25-only fallback.

The probe and fallback never load chromadb's HNSW segment, so all of
these tests synthesize the on-disk shape directly: a chroma.sqlite3 with
the relevant schema rows and an ``index_metadata.pickle`` matching what
chromadb 1.5.x writes (``{"id_to_label": {...}, ...}``).
"""

from __future__ import annotations

import os
import pickle
import sqlite3
import time

import pytest

from mempalace.backends.chroma import (
    _hnsw_element_count,
    _int64_array,
    _load_spark_guard,
    _spark_guard_check_consistency,
    _vector_segment_id,
    hnsw_capacity_status,
)
from mempalace.searcher import _bm25_only_via_sqlite


COLLECTION = "mempalace_drawers"


# ── Fixtures ──────────────────────────────────────────────────────────


def _seed_chroma_db(
    palace: str,
    sqlite_count: int,
    segment_id: str,
    sync_threshold: int | None = None,
    embeddings_under_metadata: bool = False,
) -> str:
    """Create a minimal chroma.sqlite3 with one collection + VECTOR segment.

    Mirrors the columns the probe queries: ``segments``, ``collections``,
    ``collection_metadata``, ``embeddings``, ``embedding_metadata``.
    Schema matches chromadb 1.5.x; column types are kept loose because
    we read with COUNT(*) and SELECT key, *_value rather than driver-
    specific casts.

    When ``sync_threshold`` is supplied, an ``hnsw:sync_threshold`` row
    is added to ``collection_metadata`` so the divergence floor scales
    accordingly. Omit to model an older palace that pre-dates PR #1191.

    ``embeddings_under_metadata`` (default ``False``, preserving every
    existing caller's behavior): when ``True``, ``embeddings.segment_id``
    points at the METADATA segment instead of the VECTOR one. Measured
    directly against a live chromadb 1.5.x palace: ``embeddings.segment_id``
    actually references the METADATA segment there, not VECTOR — this
    default-``False`` fixture predates that finding and happens to still
    work for the count-only checks (:func:`_sqlite_embedding_count` joins
    on collection, not segment scope), but the consistency-guard tests
    need the real METADATA association to exercise
    ``_sqlite_embedding_ids`` correctly. Returns the METADATA segment id
    either way, so callers needing it don't have to hardcode ``"seg-meta"``.
    """
    db_path = os.path.join(palace, "chroma.sqlite3")
    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(
            """
            CREATE TABLE collections (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL
            );
            CREATE TABLE collection_metadata (
                collection_id TEXT REFERENCES collections(id) ON DELETE CASCADE,
                key TEXT NOT NULL,
                str_value TEXT,
                int_value INTEGER,
                float_value REAL,
                bool_value INTEGER,
                PRIMARY KEY (collection_id, key)
            );
            CREATE TABLE segments (
                id TEXT PRIMARY KEY,
                collection TEXT NOT NULL,
                scope TEXT NOT NULL
            );
            CREATE TABLE embeddings (
                id INTEGER PRIMARY KEY,
                segment_id TEXT NOT NULL,
                embedding_id TEXT NOT NULL,
                seq_id BLOB NOT NULL,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE embedding_metadata (
                id INTEGER REFERENCES embeddings(id),
                key TEXT NOT NULL,
                string_value TEXT,
                int_value INTEGER,
                float_value REAL,
                bool_value INTEGER,
                PRIMARY KEY (id, key)
            );
            CREATE VIRTUAL TABLE embedding_fulltext_search
                USING fts5(string_value, tokenize='trigram');
            """
        )
        col_id = "col-test"
        meta_seg = "seg-meta"
        conn.execute("INSERT INTO collections (id, name) VALUES (?, ?)", (col_id, COLLECTION))
        if sync_threshold is not None:
            conn.execute(
                """INSERT INTO collection_metadata (collection_id, key, int_value)
                   VALUES (?, 'hnsw:sync_threshold', ?)""",
                (col_id, sync_threshold),
            )
        conn.execute(
            "INSERT INTO segments (id, collection, scope) VALUES (?, ?, 'VECTOR')",
            (segment_id, col_id),
        )
        conn.execute(
            "INSERT INTO segments (id, collection, scope) VALUES (?, ?, 'METADATA')",
            (meta_seg, col_id),
        )
        embeddings_segment_id = meta_seg if embeddings_under_metadata else segment_id
        for i in range(sqlite_count):
            conn.execute(
                """INSERT INTO embeddings (id, segment_id, embedding_id, seq_id)
                   VALUES (?, ?, ?, ?)""",
                (i + 1, embeddings_segment_id, f"d-{i}", b"\x00\x00\x00\x00\x00\x00\x00\x01"),
            )
        conn.commit()
    finally:
        conn.close()
    return meta_seg


def _write_pickle(palace: str, segment_id: str, hnsw_count: int) -> None:
    """Write an index_metadata.pickle matching chromadb 1.5.x's shape.

    1.5.x ``__reduce_ex__`` serializes the PersistentData instance as a
    plain dict; we replicate that so the safe unpickler in
    ``_hnsw_element_count`` reads the same bytes shape it would in
    production.
    """
    seg_dir = os.path.join(palace, segment_id)
    os.makedirs(seg_dir, exist_ok=True)
    pickle_path = os.path.join(seg_dir, "index_metadata.pickle")
    state = {
        "dimensionality": 384,
        "total_elements_added": hnsw_count,
        "max_seq_id": None,
        "id_to_label": {f"d-{i}": i for i in range(hnsw_count)},
        "label_to_id": {i: f"d-{i}" for i in range(hnsw_count)},
        "id_to_seq_id": {},
    }
    with open(pickle_path, "wb") as f:
        pickle.dump(state, f, pickle.HIGHEST_PROTOCOL)


# ── _vector_segment_id ────────────────────────────────────────────────


def test_vector_segment_id_returns_uuid(tmp_path):
    seg = "11111111-2222-3333-4444-555555555555"
    _seed_chroma_db(str(tmp_path), sqlite_count=10, segment_id=seg)
    assert _vector_segment_id(str(tmp_path), COLLECTION) == seg


def test_vector_segment_id_no_palace(tmp_path):
    assert _vector_segment_id(str(tmp_path), COLLECTION) is None


def test_vector_segment_id_unknown_collection(tmp_path):
    seg = "11111111-2222-3333-4444-555555555555"
    _seed_chroma_db(str(tmp_path), sqlite_count=10, segment_id=seg)
    assert _vector_segment_id(str(tmp_path), "nope") is None


# ── _hnsw_element_count ───────────────────────────────────────────────


def test_hnsw_element_count_reads_pickle(tmp_path):
    seg = "seg-001"
    _seed_chroma_db(str(tmp_path), sqlite_count=100, segment_id=seg)
    _write_pickle(str(tmp_path), seg, hnsw_count=42)
    assert _hnsw_element_count(str(tmp_path), seg) == 42


def test_hnsw_element_count_missing_pickle(tmp_path):
    seg = "seg-001"
    _seed_chroma_db(str(tmp_path), sqlite_count=100, segment_id=seg)
    # Segment dir doesn't even exist — no flush ever happened.
    assert _hnsw_element_count(str(tmp_path), seg) is None


def test_hnsw_element_count_rejects_arbitrary_class(tmp_path):
    """Pickled references to unallowed classes must not deserialize.

    Guards against a tampered ``index_metadata.pickle`` triggering code
    execution. The unpickler allowlist is the only protection between
    the file and arbitrary import-time side effects. We hand-craft the
    pickle bytes (rather than ``pickle.dump`` a local class) because
    pickle can't serialize locally-defined classes — but the bytes form
    that names an arbitrary stdlib class is a faithful proxy for the
    tampered-file threat we want to test.
    """
    import pickle as _pickle

    seg = "seg-evil"
    seg_dir = tmp_path / seg
    seg_dir.mkdir()
    pickle_path = seg_dir / "index_metadata.pickle"
    # GLOBAL opcode pointing at os.system, then STOP. If the unpickler
    # didn't enforce the allowlist, find_class would resolve os.system
    # and pickle would set up the call. The allowlist must reject it
    # before find_class returns anything.
    payload = b"c" + b"os\nsystem\n" + _pickle.STOP
    pickle_path.write_bytes(payload)
    assert _hnsw_element_count(str(tmp_path), seg) is None


# ── hnsw_capacity_status ──────────────────────────────────────────────


def test_capacity_status_ok_when_balanced(tmp_path):
    seg = "seg-001"
    _seed_chroma_db(str(tmp_path), sqlite_count=1000, segment_id=seg)
    _write_pickle(str(tmp_path), seg, hnsw_count=950)
    info = hnsw_capacity_status(str(tmp_path), COLLECTION)
    assert info["status"] == "ok"
    assert info["diverged"] is False
    assert info["sqlite_count"] == 1000
    assert info["hnsw_count"] == 950


def test_capacity_status_flags_severe_divergence(tmp_path):
    """Reproduces #1222: sqlite has 192k, HNSW frozen at ~16k."""
    seg = "seg-1222"
    _seed_chroma_db(str(tmp_path), sqlite_count=20_000, segment_id=seg)
    _write_pickle(str(tmp_path), seg, hnsw_count=2_000)
    info = hnsw_capacity_status(str(tmp_path), COLLECTION)
    assert info["status"] == "diverged"
    assert info["diverged"] is True
    assert info["divergence"] == 18_000
    assert "repair" in info["message"].lower()


def test_capacity_status_tolerates_flush_lag(tmp_path):
    """A few hundred entries behind sqlite is normal post-mine state."""
    seg = "seg-lag"
    _seed_chroma_db(str(tmp_path), sqlite_count=5_000, segment_id=seg)
    _write_pickle(str(tmp_path), seg, hnsw_count=4_500)
    info = hnsw_capacity_status(str(tmp_path), COLLECTION)
    assert info["diverged"] is False
    assert info["status"] == "ok"


def test_capacity_status_does_not_flag_unflushed_with_large_sqlite(tmp_path):
    """No pickle + many sqlite rows is inconclusive, not divergence."""
    seg = "seg-noflush"
    _seed_chroma_db(str(tmp_path), sqlite_count=10_000, segment_id=seg)
    info = hnsw_capacity_status(str(tmp_path), COLLECTION)
    assert info["diverged"] is False
    assert info["status"] == "unknown"
    assert info["divergence"] is None
    assert info["hnsw_count"] is None
    assert "capacity unavailable" in info["message"]
    assert "leaving vector search enabled" in info["message"]


def test_mcp_probe_does_not_disable_vectors_for_unflushed_metadata(tmp_path, monkeypatch):
    """The MCP preflight must not route all searches to BM25 on this signal."""
    from mempalace import mcp_server

    seg = "seg-mcp-noflush"
    _seed_chroma_db(str(tmp_path), sqlite_count=10_000, segment_id=seg)

    class _Cfg:
        palace_path = str(tmp_path)
        collection_name = "mempalace_drawers"

    monkeypatch.setattr(mcp_server, "_config", _Cfg())
    monkeypatch.setattr(mcp_server, "_vector_disabled", True)
    monkeypatch.setattr(mcp_server, "_vector_disabled_reason", "old divergence")

    mcp_server._refresh_vector_disabled_flag()

    assert mcp_server._vector_disabled is False
    assert mcp_server._vector_disabled_reason == ""
    assert mcp_server._vector_capacity_status["status"] == "unknown"
    assert "leaving vector search enabled" in mcp_server._vector_capacity_status["message"]


def test_capacity_status_quiet_for_empty_palace(tmp_path):
    info = hnsw_capacity_status(str(tmp_path), COLLECTION)
    assert info["diverged"] is False
    assert info["status"] == "unknown"


# ── Divergence threshold scales with hnsw:sync_threshold ───────────────


def test_capacity_status_tolerates_lag_under_large_sync_threshold(tmp_path):
    """Regression for the PR #1191 / PR #1227 conflict.

    Palaces created via mempalace's _HNSW_BLOAT_GUARD (sync_threshold=
    50_000) naturally accumulate up to ~50K queued entries between
    flushes. The pickle-vs-sqlite probe must scale its tolerance to
    ``2 × sync_threshold`` so this expected lag is not flagged as
    corruption — otherwise vector search disables for ~80% of the
    write cycle on any actively-mined ≥100K palace.
    """
    seg = "seg-bloat-guard"
    _seed_chroma_db(str(tmp_path), sqlite_count=100_000, segment_id=seg, sync_threshold=50_000)
    _write_pickle(str(tmp_path), seg, hnsw_count=50_000)
    info = hnsw_capacity_status(str(tmp_path), COLLECTION)
    # 50K divergence is exactly one flush window — well within 2× = 100K.
    assert info["diverged"] is False, info["message"]
    assert info["status"] == "ok"
    assert info["divergence"] == 50_000


def test_capacity_status_still_flags_real_corruption_under_large_sync(tmp_path):
    """The dynamic floor must still catch genuine #1222-style corruption.

    sqlite at 200K with HNSW frozen at 16K is the original #1222 shape —
    any reasonable threshold should flag it, regardless of whether the
    collection was created with sync_threshold=1000 or 50_000.
    """
    seg = "seg-1222-with-bloat-guard"
    _seed_chroma_db(str(tmp_path), sqlite_count=200_000, segment_id=seg, sync_threshold=50_000)
    _write_pickle(str(tmp_path), seg, hnsw_count=16_384)
    info = hnsw_capacity_status(str(tmp_path), COLLECTION)
    # 183,616 missing — far past 2 × 50K = 100K floor and 10% of 200K = 20K.
    assert info["diverged"] is True
    assert info["status"] == "diverged"
    assert info["divergence"] == 183_616


def test_capacity_status_default_threshold_when_no_sync_metadata(tmp_path):
    """Older palaces without ``hnsw:sync_threshold`` fall back to 2000 floor.

    Pre-PR-#1191 collections only carry ``hnsw:space``. The probe must
    use chromadb's own default sync_threshold of 1000 → floor of 2000,
    matching pre-fix behavior.
    """
    seg = "seg-legacy"
    # No sync_threshold supplied — collection_metadata stays empty.
    _seed_chroma_db(str(tmp_path), sqlite_count=10_000, segment_id=seg)
    _write_pickle(str(tmp_path), seg, hnsw_count=7_500)
    info = hnsw_capacity_status(str(tmp_path), COLLECTION)
    # 2,500 divergence > max(2000 floor, 10% of 10K = 1000) → DIVERGED
    assert info["diverged"] is True
    assert info["divergence"] == 2_500


def test_unflushed_path_also_uses_dynamic_floor(tmp_path):
    """The never-flushed branch must scale with sync_threshold too.

    A 30K-drawer collection under sync_threshold=50_000 hasn't reached
    its first flush yet — pickle is absent. Pre-fix this would flag
    DIVERGED (30K > fixed 2000 floor); post-fix the 30K stays under
    the dynamic 100K floor.
    """
    seg = "seg-preflush-large"
    _seed_chroma_db(str(tmp_path), sqlite_count=30_000, segment_id=seg, sync_threshold=50_000)
    info = hnsw_capacity_status(str(tmp_path), COLLECTION)
    assert info["hnsw_count"] is None
    assert info["diverged"] is False, info["message"]


# ── BM25-only sqlite fallback ─────────────────────────────────────────


def _seed_drawers(palace: str, segment_id: str, drawers: list[tuple[str, dict, str]]) -> None:
    """Insert (text, metadata, embedding_id) tuples into a seeded palace.

    Replaces the bare ``embeddings`` rows from ``_seed_chroma_db`` so the
    sqlite count matches what we insert here.
    """
    db_path = os.path.join(palace, "chroma.sqlite3")
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("DELETE FROM embeddings")
        for i, (text, meta, eid) in enumerate(drawers, start=1):
            conn.execute(
                """INSERT INTO embeddings (id, segment_id, embedding_id, seq_id)
                   VALUES (?, ?, ?, ?)""",
                (i, segment_id, eid, b"\x00" * 8),
            )
            conn.execute(
                """INSERT INTO embedding_metadata (id, key, string_value)
                   VALUES (?, 'chroma:document', ?)""",
                (i, text),
            )
            conn.execute(
                "INSERT INTO embedding_fulltext_search (rowid, string_value) VALUES (?, ?)",
                (i, text),
            )
            for k, v in meta.items():
                if isinstance(v, int):
                    conn.execute(
                        """INSERT INTO embedding_metadata (id, key, int_value)
                           VALUES (?, ?, ?)""",
                        (i, k, v),
                    )
                else:
                    conn.execute(
                        """INSERT INTO embedding_metadata (id, key, string_value)
                           VALUES (?, ?, ?)""",
                        (i, k, str(v)),
                    )
        conn.commit()
    finally:
        conn.close()


def _set_drawer_created_at(palace: str, timestamps: dict[int, str]) -> None:
    db_path = os.path.join(palace, "chroma.sqlite3")
    conn = sqlite3.connect(db_path)
    try:
        for emb_id, created_at in timestamps.items():
            conn.execute("UPDATE embeddings SET created_at = ? WHERE id = ?", (created_at, emb_id))
        conn.commit()
    finally:
        conn.close()


@pytest.fixture
def palace_with_drawers(tmp_path):
    seg = "seg-bm25"
    _seed_chroma_db(str(tmp_path), sqlite_count=0, segment_id=seg)
    drawers = [
        (
            "ChromaDB segfault on every tool call after HNSW divergence",
            {"wing": "ops", "room": "incidents", "source_file": "/x/incident.md"},
            "d-1",
        ),
        (
            "Memory palace technique using rooms and drawers for recall",
            {"wing": "design", "room": "metaphor", "source_file": "/x/design.md"},
            "d-2",
        ),
        (
            "Repair rebuild backs up only the sqlite database",
            {"wing": "ops", "room": "runbook", "source_file": "/x/repair.md"},
            "d-3",
        ),
    ]
    _seed_drawers(str(tmp_path), seg, drawers)
    return tmp_path


def test_bm25_fallback_returns_matches(palace_with_drawers):
    out = _bm25_only_via_sqlite("segfault chromadb", str(palace_with_drawers), n_results=5)
    assert out["fallback"] == "bm25_only_via_sqlite"
    assert len(out["results"]) >= 1
    top = out["results"][0]
    # The incident drawer is the closest BM25 match for these terms.
    assert "segfault" in top["text"].lower()
    assert top["matched_via"] == "bm25_sqlite"
    # Vector fields are intentionally absent in fallback mode.
    assert top["similarity"] is None
    assert top["distance"] is None


def test_bm25_fallback_filters_by_wing(palace_with_drawers):
    out = _bm25_only_via_sqlite(
        "memory palace recall", str(palace_with_drawers), wing="design", n_results=5
    )
    assert all(r["wing"] == "design" for r in out["results"])


def test_bm25_fallback_applies_wing_before_fts_candidate_limit(tmp_path):
    seg = "seg-bm25-fts-limit"
    _seed_chroma_db(str(tmp_path), sqlite_count=0, segment_id=seg)
    _seed_drawers(
        str(tmp_path),
        seg,
        [
            (
                "shared token outside target wing",
                {"wing": "ops", "room": "incidents", "source_file": "/x/ops.md"},
                "d-1",
            ),
            (
                "shared token inside target wing",
                {"wing": "project", "room": "diary", "source_file": "/x/project.md"},
                "d-2",
            ),
        ],
    )

    out = _bm25_only_via_sqlite("shared token", str(tmp_path), wing="project", max_candidates=1)

    assert out["total_before_filter"] == 1
    assert len(out["results"]) == 1
    assert out["results"][0]["wing"] == "project"


def test_bm25_fallback_applies_room_before_fts_candidate_limit(tmp_path):
    seg = "seg-bm25-room-limit"
    _seed_chroma_db(str(tmp_path), sqlite_count=0, segment_id=seg)
    _seed_drawers(
        str(tmp_path),
        seg,
        [
            (
                "shared token wrong room",
                {"wing": "project", "room": "scratch", "source_file": "/x/scratch.md"},
                "d-1",
            ),
            (
                "shared token right room",
                {"wing": "project", "room": "diary", "source_file": "/x/diary.md"},
                "d-2",
            ),
        ],
    )

    out = _bm25_only_via_sqlite(
        "shared token",
        str(tmp_path),
        wing="project",
        room="diary",
        max_candidates=1,
    )

    assert out["total_before_filter"] == 1
    assert len(out["results"]) == 1
    assert out["results"][0]["wing"] == "project"
    assert out["results"][0]["room"] == "diary"


def test_bm25_fallback_applies_wing_before_recency_candidate_limit(tmp_path):
    seg = "seg-bm25-recency-limit"
    _seed_chroma_db(str(tmp_path), sqlite_count=0, segment_id=seg)
    _seed_drawers(
        str(tmp_path),
        seg,
        [
            (
                "target drawer for short query",
                {"wing": "project", "room": "diary", "source_file": "/x/project.md"},
                "d-1",
            ),
            (
                "newer drawer outside target wing",
                {"wing": "ops", "room": "incidents", "source_file": "/x/ops.md"},
                "d-2",
            ),
        ],
    )
    _set_drawer_created_at(
        str(tmp_path),
        {
            1: "2026-01-01 00:00:00",
            2: "2026-02-01 00:00:00",
        },
    )

    out = _bm25_only_via_sqlite("a", str(tmp_path), wing="project", max_candidates=1)

    assert out["total_before_filter"] == 1
    assert len(out["results"]) == 1
    assert out["results"][0]["wing"] == "project"


def test_bm25_fallback_returns_empty_when_filtered_wing_has_no_candidates(tmp_path):
    seg = "seg-bm25-empty-filter"
    _seed_chroma_db(str(tmp_path), sqlite_count=0, segment_id=seg)
    _seed_drawers(
        str(tmp_path),
        seg,
        [
            (
                "shared token outside target wing",
                {"wing": "ops", "room": "incidents", "source_file": "/x/ops.md"},
                "d-1",
            ),
        ],
    )

    out = _bm25_only_via_sqlite("shared token", str(tmp_path), wing="project", max_candidates=1)

    assert out["total_before_filter"] == 0
    assert out["results"] == []


def test_bm25_fallback_no_palace(tmp_path):
    out = _bm25_only_via_sqlite("anything", str(tmp_path))
    assert "error" in out


def test_bm25_fallback_handles_short_query(palace_with_drawers):
    """Single-character tokens are unmatchable in trigram FTS5 — must
    not crash, must fall back to the recency window."""
    out = _bm25_only_via_sqlite("a", str(palace_with_drawers), n_results=5)
    # Falls back to recency window; returns whatever it can rank.
    assert out["fallback"] == "bm25_only_via_sqlite"
    assert isinstance(out["results"], list)


# ── repair.status CLI command ─────────────────────────────────────────


def test_repair_status_reports_diverged(tmp_path, capsys):
    """The status command prints DIVERGED and recommends the from-sqlite
    rebuild (not a re-mine), since a diverged index means the rows are
    intact in sqlite but the HNSW segment is out of sync (#1843)."""
    from mempalace.repair import status as repair_status

    seg = "seg-status"
    _seed_chroma_db(str(tmp_path), sqlite_count=20_000, segment_id=seg)
    _write_pickle(str(tmp_path), seg, hnsw_count=2_000)
    out = repair_status(palace_path=str(tmp_path))
    captured = capsys.readouterr().out
    assert "DIVERGED" in captured
    assert "mempalace repair --mode from-sqlite --archive-existing" in captured
    assert "Do not re-mine" in captured
    assert out["drawers"]["diverged"] is True


def test_repair_status_quiet_on_healthy_palace(tmp_path, capsys):
    from mempalace.repair import status as repair_status

    seg = "seg-status-ok"
    _seed_chroma_db(str(tmp_path), sqlite_count=500, segment_id=seg)
    _write_pickle(str(tmp_path), seg, hnsw_count=480)
    repair_status(palace_path=str(tmp_path))
    captured = capsys.readouterr().out
    assert "DIVERGED" not in captured
    assert "Recommended" not in captured


# ── tool_status sqlite fallback (#1222 short-circuit) ─────────────────


def test_tool_status_via_sqlite_returns_breakdown(palace_with_drawers, monkeypatch):
    """When _vector_disabled is set, tool_status reads counts from sqlite
    instead of opening a chromadb client."""
    from mempalace import mcp_server

    # _config.palace_path is a read-only property; swap the whole object
    # for a tiny stand-in so we don't have to monkey with the real
    # MempalaceConfig.
    class _Cfg:
        palace_path = str(palace_with_drawers)
        collection_name = "mempalace_drawers"

    monkeypatch.setattr(mcp_server, "_config", _Cfg())
    monkeypatch.setattr(mcp_server, "_vector_disabled", True)
    monkeypatch.setattr(mcp_server, "_vector_disabled_reason", "test divergence")

    out = mcp_server._tool_status_via_sqlite()
    assert out["vector_disabled"] is True
    assert out["vector_disabled_reason"] == "test divergence"
    assert out["total_drawers"] == 3
    # Wing breakdown comes from the seeded palace_with_drawers fixture:
    # ops×2 (incident + repair runbook), design×1 (metaphor).
    assert out["wings"].get("ops") == 2
    assert out["wings"].get("design") == 1


def test_capacity_status_flags_small_gap_with_explicit_low_sync_threshold(tmp_path):
    """New palaces use a low explicit sync threshold, so 57 missing rows is unsafe."""
    seg = "seg-1816-explicit-low-sync"
    _seed_chroma_db(str(tmp_path), sqlite_count=1768, segment_id=seg, sync_threshold=2)
    _write_pickle(str(tmp_path), seg, hnsw_count=1711)

    info = hnsw_capacity_status(str(tmp_path), COLLECTION)

    assert info["divergence"] == 57
    assert info["threshold"] == 4
    assert info["status"] == "diverged"
    assert info["diverged"] is True
    assert "repair" in info["message"].lower()


def test_capacity_status_flags_stale_below_floor_divergence(tmp_path):
    """A persistent below-floor sqlite>HNSW gap must not be treated as fresh lag."""
    from mempalace.backends import chroma

    seg = "seg-1816-stale-below-floor"
    _seed_chroma_db(str(tmp_path), sqlite_count=1768, segment_id=seg)
    _write_pickle(str(tmp_path), seg, hnsw_count=1711)

    pickle_path = tmp_path / seg / "index_metadata.pickle"
    old = time.time() - chroma._HNSW_PERSISTENT_DIVERGENCE_GRACE_SECONDS - 10
    os.utime(pickle_path, (old, old))

    info = hnsw_capacity_status(str(tmp_path), COLLECTION)

    assert info["divergence"] == 57
    assert info["threshold"] >= 2000
    assert info["status"] == "diverged"
    assert info["diverged"] is True
    assert "persisted below" in info["message"]


def test_capacity_status_ok_with_stale_metadata_under_explicit_threshold(tmp_path):
    """An idle database with an explicit sync threshold and a gap within tolerance must remain OK."""
    seg = "seg-1816-stale-ok"
    _seed_chroma_db(str(tmp_path), sqlite_count=1712, segment_id=seg, sync_threshold=2)
    _write_pickle(str(tmp_path), seg, hnsw_count=1711)
    pickle_path = tmp_path / seg / "index_metadata.pickle"
    old = time.time() - 400.0
    os.utime(pickle_path, (old, old))
    info = hnsw_capacity_status(str(tmp_path), COLLECTION)
    assert info["divergence"] == 1
    assert info["threshold"] == 4
    assert info["status"] == "ok"
    assert info["diverged"] is False


# ── _int64_array ──────────────────────────────────────────────────────
#
# _int64_array is a line-for-line port of the SPARK guard PoC fixture's
# _arr() helper — same range-validation fix an earlier ECC review found
# missing in the PoC (ctypes silently wraps two's-complement instead of
# raising on out-of-range input). These tests exercise the port directly,
# independent of the fixture's own tests.


def test_int64_array_empty_returns_null_pointer():
    buf, ptr, n = _int64_array([])
    assert buf is None
    assert n == 0


def test_int64_array_dedupes_and_sorts():
    buf, ptr, n = _int64_array([5, 1, 5, 3, 1])
    assert n == 3
    assert buf is not None
    assert list(buf) == [1, 3, 5]


def test_int64_array_accepts_boundary_values():
    int64_min = -(2**63)
    int64_max = 2**63 - 1
    buf, ptr, n = _int64_array([int64_min, int64_max])
    assert n == 2
    assert buf is not None
    assert list(buf) == [int64_min, int64_max]


def test_int64_array_rejects_positive_overflow():
    with pytest.raises(ValueError):
        _int64_array([2**63])


def test_int64_array_rejects_negative_underflow():
    with pytest.raises(ValueError):
        _int64_array([-(2**63) - 1])


# ── _spark_guard_check_consistency ───────────────────────────────────
#
# Skipped automatically when the SPARK guard DLL isn't loadable for this
# environment (non-Windows, the PoC not compiled, OR — the actual reason
# under this repo's test suite — conftest.py deliberately redirects HOME
# to an isolated temp dir before any mempalace import, so the guard's
# ~/.alire GNAT-runtime lookup can't find the real toolchain even though
# libguard.dll itself exists on disk). Root-caused directly: confirmed
# via DEBUG logging that ctypes.CDLL raises FileNotFoundError only under
# pytest, and that os.path.expanduser("~") resolves to conftest.py's
# _session_tmp there, not the real user profile. This is intentional
# test isolation, not a production bug (a real MCP server process has a
# correct HOME) — the skip is the honest outcome, not a workaround.
# _load_spark_guard() returning None is itself a legitimate, tested
# fallback path (see test_spark_guard_missing_dll_returns_none below).

_GUARD_UNAVAILABLE = _load_spark_guard() is None
_skip_no_guard = pytest.mark.skipif(
    _GUARD_UNAVAILABLE,
    reason=(
        "SPARK guard DLL not loadable in this environment (often: HOME is "
        "redirected by conftest.py's test isolation, so ~/.alire's GNAT "
        "runtime can't be found — not a missing-DLL problem)"
    ),
)


@_skip_no_guard
def test_spark_guard_matching_sets_are_consistent():
    ids = {"d-1", "d-2", "d-3"}
    result = _spark_guard_check_consistency(ids, set(ids))
    assert result is not None
    assert result["ok"] is True
    assert result["read_permitted"] is True
    assert result["missing_ids"]["in_sqlite_not_hnsw_count"] == 0
    assert result["missing_ids"]["in_hnsw_not_sqlite_count"] == 0


@_skip_no_guard
def test_spark_guard_sqlite_only_extra_id_is_divergent():
    sqlite_ids = {"d-1", "d-2", "d-3"}
    hnsw_ids = {"d-1", "d-2"}
    result = _spark_guard_check_consistency(sqlite_ids, hnsw_ids)
    assert result is not None
    assert result["ok"] is False
    assert result["read_permitted"] is False
    assert result["missing_ids"]["in_sqlite_not_hnsw"] == ["d-3"]
    assert result["missing_ids"]["in_hnsw_not_sqlite_count"] == 0


@_skip_no_guard
def test_spark_guard_hnsw_only_extra_id_is_divergent():
    sqlite_ids = {"d-1", "d-2"}
    hnsw_ids = {"d-1", "d-2", "d-3"}
    result = _spark_guard_check_consistency(sqlite_ids, hnsw_ids)
    assert result is not None
    assert result["ok"] is False
    assert result["missing_ids"]["in_hnsw_not_sqlite"] == ["d-3"]
    assert result["missing_ids"]["in_sqlite_not_hnsw_count"] == 0


@_skip_no_guard
def test_spark_guard_empty_sets_are_consistent():
    result = _spark_guard_check_consistency(set(), set())
    assert result is not None
    assert result["ok"] is True
    assert result["read_permitted"] is True


@_skip_no_guard
def test_spark_guard_non_ascii_embedding_ids():
    """embedding_id strings are not guaranteed ASCII (e.g. non-Latin wing/room names)."""
    ids = {"drawer_wissensarchiv_general_äöüß_01", "drawer_genealogie_general_попов_02"}
    result = _spark_guard_check_consistency(ids, set(ids))
    assert result is not None
    assert result["ok"] is True


@_skip_no_guard
def test_spark_guard_same_count_different_ids_is_divergent():
    """Equal cardinality with swapped members must NOT read as consistent.

    This is the exact case a naive count-only comparison would miss —
    the reason the guard compares set membership, not just len().
    """
    sqlite_ids = {"d-1", "d-2", "d-3"}
    hnsw_ids = {"d-1", "d-2", "d-4"}
    result = _spark_guard_check_consistency(sqlite_ids, hnsw_ids)
    assert result is not None
    assert result["ok"] is False
    assert len(sqlite_ids) == len(hnsw_ids)  # same count, by construction of this test


def test_spark_guard_missing_dll_returns_none(monkeypatch):
    """When the guard DLL isn't available, the probe returns None (fallback), never raises."""
    monkeypatch.setattr("mempalace.backends.chroma._load_spark_guard", lambda: None)
    result = _spark_guard_check_consistency({"d-1"}, {"d-1"})
    assert result is None


# ── hnsw_capacity_status: consistency integration ────────────────────


def test_capacity_status_consistency_default_is_none_and_fast(tmp_path):
    """include_consistency_check defaults to False: hnsw_capacity_status is
    called on every MCP server boot (mcp_server._refresh_vector_disabled_flag)
    and must stay fast there — measured at ~75s for the consistency check on
    a real 323k-element palace, vs sub-second for the count-only check. The
    guard must never run unless a caller explicitly opts in."""
    seg = "seg-consistency-default-off"
    _seed_chroma_db(str(tmp_path), sqlite_count=50, segment_id=seg, embeddings_under_metadata=True)
    _write_pickle(str(tmp_path), seg, hnsw_count=50)
    info = hnsw_capacity_status(str(tmp_path), COLLECTION)
    assert info["consistency"] is None


def test_capacity_status_consistency_populated_when_ids_match(tmp_path):
    seg = "seg-consistency-ok"
    _seed_chroma_db(str(tmp_path), sqlite_count=50, segment_id=seg, embeddings_under_metadata=True)
    _write_pickle(str(tmp_path), seg, hnsw_count=50)
    info = hnsw_capacity_status(str(tmp_path), COLLECTION, include_consistency_check=True)
    if info["consistency"] is None:
        pytest.skip("SPARK guard DLL not built in this environment")
    assert info["consistency"]["ok"] is True
    assert info["consistency"]["missing_ids"]["in_sqlite_not_hnsw_count"] == 0


def test_capacity_status_consistency_none_when_embeddings_not_under_metadata(tmp_path):
    """Old-shape fixture (embeddings under VECTOR, matching every other existing
    test in this file) yields an empty sqlite id set for the METADATA segment,
    so the guard's id sets never populate — consistency stays None rather than
    reporting a false "fully divergent" verdict on a fixture gap, not real data."""
    seg = "seg-consistency-none"
    _seed_chroma_db(str(tmp_path), sqlite_count=50, segment_id=seg)
    _write_pickle(str(tmp_path), seg, hnsw_count=50)
    info = hnsw_capacity_status(str(tmp_path), COLLECTION, include_consistency_check=True)
    assert info["consistency"] is None


def test_capacity_status_survives_consistency_check_raising(tmp_path, monkeypatch):
    """hnsw_capacity_status must never raise, even if the consistency check does.

    _spark_guard_check_consistency's own except-Exception wrapper already
    guarantees it never raises in practice (see the tests above) — this
    test probes past that contract via monkeypatch to confirm the OUTER
    hnsw_capacity_status call is itself defense-in-depth: the call site
    sits inside hnsw_capacity_status's existing top-level try/except (the
    same one that has always protected _vector_segment_id,
    _sqlite_embedding_count, etc.), so even a hypothetical future bug that
    reintroduces a raise inside the consistency check would still degrade
    to a safe "unknown" dict, not an exception reaching the caller.
    """
    seg = "seg-consistency-raises"
    _seed_chroma_db(str(tmp_path), sqlite_count=50, segment_id=seg, embeddings_under_metadata=True)
    _write_pickle(str(tmp_path), seg, hnsw_count=50)

    def _boom(*_args, **_kwargs):
        raise RuntimeError("simulated guard crash")

    monkeypatch.setattr("mempalace.backends.chroma._spark_guard_check_consistency", _boom)
    info = hnsw_capacity_status(str(tmp_path), COLLECTION, include_consistency_check=True)
    assert isinstance(info, dict)
    assert info["message"] == "HNSW capacity probe raised; skipping"
