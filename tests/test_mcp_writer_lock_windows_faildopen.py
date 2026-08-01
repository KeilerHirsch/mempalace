"""REPRO (PR-Beweis): der fail-open-Pfad bei kaputtem Lock-MECHANISMUS laesst
mutating tools UNGESCHUETZT schreiben -> Race -> HNSW-Divergenz.

Der bestehende test_peer_writer_lock_setup_failure_is_cached prueft nur den
Cache-ZUSTAND (ok=True, _MCP_WRITER_LOCK_FAILED=True). DIESER Test prueft die
KONSEQUENZ: _mcp_peer_writer_refusal gibt fuer ein MUTATING tool None zurueck
= erlaubt den Write, obwohl KEIN Lock gehalten wird.

Kontext: auf Windows ist msvcrt-Locking fragiler als POSIX-flock, der
Nicht-MineAlreadyRunning-Exception-Pfad wird dort real getroffen -> fail-open
aktiviert sich -> stiller Index-Verlust. Auf Linux fast toter Code.
"""


def _reset(mcp_server, monkeypatch):
    monkeypatch.delenv(mcp_server._MCP_ALLOW_PEER_WRITER_ENV, raising=False)
    monkeypatch.setattr(mcp_server, "_MCP_WRITER_LOCK_CM", None)
    monkeypatch.setattr(mcp_server, "_MCP_WRITER_READ_ONLY", False)
    monkeypatch.setattr(mcp_server, "_MCP_WRITER_LOCK_FAILED", False)
    monkeypatch.setattr(mcp_server, "_MCP_WRITER_LOCK_ERROR", "")


def test_broken_lock_mechanism_lets_mutating_tool_write_unprotected(monkeypatch):
    """A lock-MECHANISM failure (e.g. Windows msvcrt OSError) must NOT silently
    permit an unprotected mutating write. Today it does: refusal returns None."""
    from mempalace import mcp_server, palace

    def broken_mine_palace_lock(palace_path):
        # Simulates a Windows msvcrt.locking OSError — NOT MineAlreadyRunning.
        raise OSError("msvcrt.locking failed: Errno 13 permission denied")

    _reset(mcp_server, monkeypatch)
    monkeypatch.setattr(palace, "mine_palace_lock", broken_mine_palace_lock)

    refusal = mcp_server._mcp_peer_writer_refusal(1, "mempalace_add_drawer")

    # CURRENT (buggy) behaviour: refusal is None -> the write proceeds with NO lock.
    # DESIRED (after fix): a lock-mechanism failure should fail-closed for
    # mutating tools (refuse), because an unheld lock means a concurrent writer
    # can race the HNSW persist and silently drop index entries.
    assert refusal is not None, (
        "fail-open: broken lock mechanism let a mutating write through "
        "unprotected — concurrent writer can now silently diverge the HNSW index"
    )


def test_broken_lock_mechanism_still_allows_readonly_tools(monkeypatch):
    """Read-only tools must stay allowed even when the lock mechanism is broken —
    the fix must be scoped to MUTATING tools only, not a blanket refusal."""
    from mempalace import mcp_server, palace

    def broken_mine_palace_lock(palace_path):
        raise OSError("msvcrt.locking failed")

    _reset(mcp_server, monkeypatch)
    monkeypatch.setattr(palace, "mine_palace_lock", broken_mine_palace_lock)

    # a non-mutating tool: refusal path returns None immediately (tool not in _MUTATING_TOOLS)
    refusal = mcp_server._mcp_peer_writer_refusal(1, "mempalace_search")
    assert refusal is None
