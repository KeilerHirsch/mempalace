"""Synthetic divergence fixture for the SPARK consistency guard PoC.

Rebuilds the race-divergence signature as pure label-set fixtures and
drives the proved SPARK core across the C-ABI (ctypes). No chromadb, no
palace mutation — this isolates the guard's verdict logic from the race
itself. The race is PROVEN elsewhere (repro4/repro5); here we prove the
GUARD catches every divergence shape, including the one a count check
misses (same count, different ids — chromadb label recycling).

Each label set is what Python hands the guard: sorted ascending int64.
The guard's precondition (Is_Sorted) is satisfied by sorting here.

Exit 0 = all guard assertions held. Non-zero = guard misbehaved.
"""

from __future__ import annotations

import ctypes
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DLL_PATH = os.path.join(HERE, "lib", "libguard.dll")

# libguard.dll links the GNAT runtime dynamically (libgnat-16.dll,
# libgcc_s_seh-1.dll). Since Python 3.8, PATH no longer drives the
# dependent-DLL search on Windows — the directory must be registered
# explicitly via os.add_dll_directory. This is the Windows-native gotcha
# the Linux maintainer never hits.
GNAT_RUNTIME = os.path.join(os.path.expanduser("~"), ".alire", "libexec", "spark", "bin")


def _load() -> ctypes.CDLL:
    if not os.path.isfile(DLL_PATH):
        sys.exit(f"FAIL: guard DLL not built at {DLL_PATH}")
    if os.path.isdir(GNAT_RUNTIME):
        os.add_dll_directory(GNAT_RUNTIME)
    lib = ctypes.CDLL(DLL_PATH)
    # int check_consistency(int64* sqlite, int slen, int64* hnsw, int hlen)
    # Labels are int64 (ctypes.c_int64, NOT c_long — c_long is 4 bytes on
    # Windows/LLP64). Lengths stay plain c_int; a count never needs 64 bits.
    lib.check_consistency.restype = ctypes.c_int
    lib.check_consistency.argtypes = [
        ctypes.POINTER(ctypes.c_int64),
        ctypes.c_int,
        ctypes.POINTER(ctypes.c_int64),
        ctypes.c_int,
    ]
    # int read_gate(int last_verdict)
    lib.read_gate.restype = ctypes.c_int
    lib.read_gate.argtypes = [ctypes.c_int]
    return lib


_INT64_MIN = -(2**63)
_INT64_MAX = 2**63 - 1


def _arr(vals: list[int]):
    """Sorted+deduped int64 array + length, as the guard expects.

    An empty set is passed as (NULL, 0) — the honest representation of
    "no elements" — so the empty cases actually exercise the C-ABI's
    null-pointer handling instead of a dummy 1-element buffer.

    ctypes does NOT raise on out-of-range int64 values — it silently
    wraps two's-complement (2**63 -> -2**63, 2**64 -> 0). Left
    unchecked, two distinct hash outputs could wrap to the same wire
    value and the guard would wrongly call them consistent — exactly
    the failure class this guard exists to catch, except upstream of
    the proved SPARK core. Reject out-of-range values explicitly
    instead of trusting ctypes' silent wraparound.
    """
    clean = sorted(set(vals))
    for v in clean:
        if not (_INT64_MIN <= v <= _INT64_MAX):
            raise ValueError(
                f"label {v} out of signed int64 range "
                f"[{_INT64_MIN}, {_INT64_MAX}] — ctypes would silently "
                "wrap this, not raise"
            )
    n = len(clean)
    if n == 0:
        return None, ctypes.POINTER(ctypes.c_int64)(), 0  # NULL, len 0
    buf = (ctypes.c_int64 * n)(*clean)
    ptr = ctypes.cast(buf, ctypes.POINTER(ctypes.c_int64))
    return buf, ptr, n  # keep buf alive


def check(lib, sqlite: list[int], hnsw: list[int]) -> int:
    _b1, p1, n1 = _arr(sqlite)
    _b2, p2, n2 = _arr(hnsw)
    return lib.check_consistency(p1, n1, p2, n2)


def check_raw(lib, p1, n1, p2, n2) -> int:
    """Call the C-ABI directly with caller-supplied pointers/lengths,
    to exercise malformed-input paths the sorted-set helper cannot."""
    return lib.check_consistency(p1, n1, p2, n2)


def main() -> int:
    lib = _load()
    failures = 0

    def expect(name: str, got: int, want: int):
        nonlocal failures
        ok = got == want
        mark = "PASS" if ok else "FAIL"
        print(f"  [{mark}] {name}: got={got} want={want}")
        if not ok:
            failures += 1

    def expect_raises(name: str, fn, exc_type: type[BaseException]):
        nonlocal failures
        try:
            fn()
        except exc_type:
            ok = True
        except Exception as exc:  # noqa: BLE001 - reporting the actual wrong type is the point
            ok = False
            print(f"  [FAIL] {name}: raised {type(exc).__name__}, want {exc_type.__name__}")
        else:
            ok = False
            print(f"  [FAIL] {name}: raised nothing, want {exc_type.__name__}")
        if ok:
            print(f"  [PASS] {name}: raised {exc_type.__name__}")
        else:
            failures += 1

    print("SPARK consistency guard — synthetic divergence fixture\n")

    # 1) Identical sets -> Consistent (1).
    expect("identical sets -> consistent", check(lib, [1, 2, 3, 4, 5], [1, 2, 3, 4, 5]), 1)

    # 2) COUNT divergence: race lost label 3 from HNSW -> Divergent (0).
    #    This is the diff=32 signature (HNSW short of sqlite).
    expect(
        "count divergence (lost label) -> divergent", check(lib, [1, 2, 3, 4, 5], [1, 2, 4, 5]), 0
    )

    # 3) SAME COUNT, DIFFERENT IDS -> Divergent (0). The strict case a
    #    pure count check (sqlite_count == hnsw_count) would call OK.
    #    chromadb recycles labels via upsert/delete, so equal cardinality
    #    with a swapped id is real corruption. This is why we chose the
    #    label-set compare over the count compare.
    expect(
        "same count / different ids -> divergent", check(lib, [1, 2, 3, 4, 5], [1, 2, 3, 4, 6]), 0
    )

    # 4) Empty vs empty -> Consistent. Now passed as (NULL, 0) on both
    #    sides, so this exercises the C-ABI null-pointer + zero-length
    #    path, not a dummy buffer.
    expect("empty(NULL,0) vs empty(NULL,0) -> consistent", check(lib, [], []), 1)

    # 5) Empty vs non-empty -> Divergent. Left side is (NULL, 0).
    expect("empty(NULL,0) vs non-empty -> divergent", check(lib, [], [1]), 0)

    print("\nint64 range (the reason this fixture was widened from int32):")
    # 6) Values that overflow int32 but differ only above bit 32 -> Divergent.
    #    A 32-bit-truncating C-ABI would see these as equal; this is the
    #    exact bug class the int32 -> int64 widening fixes.
    big1 = 2**40 + 7
    big2 = 2**40 + 2**32 + 7
    expect("identical values > 2**32 -> consistent", check(lib, [big1], [big1]), 1)
    expect(
        "values > 2**32 differing only above bit32 -> divergent",
        check(lib, [big1], [big2]),
        0,
    )
    # 7) Max/min in-range signed int64 -> Consistent. Confirms the boundary
    #    itself round-trips, not just "somewhere in the middle of the range".
    expect(
        "max signed int64 (2**63-1) -> consistent",
        check(lib, [_INT64_MAX], [_INT64_MAX]),
        1,
    )
    expect(
        "min signed int64 (-2**63) -> consistent",
        check(lib, [_INT64_MIN], [_INT64_MIN]),
        1,
    )
    # 8) Out-of-range value -> _arr() must raise, not silently wrap
    #    two's-complement (ctypes does that silently; see _arr()'s guard).
    expect_raises(
        "out-of-range value (positive) -> _arr() raises ValueError",
        lambda: _arr([_INT64_MAX + 1]),
        ValueError,
    )
    expect_raises(
        "out-of-range value (negative) -> _arr() raises ValueError",
        lambda: _arr([_INT64_MIN - 1]),
        ValueError,
    )

    print("\nMalformed input (invalid, distinct from divergent = -1):")
    # 9) NULL pointer with a claimed POSITIVE length -> Invalid (-1),
    #    NOT Divergent. A caller bug must not read as a data incident.
    null_ptr = ctypes.POINTER(ctypes.c_int64)()
    _b, good_ptr, good_n = _arr([1, 2, 3])
    expect(
        "null ptr + len>0 (sqlite side) -> invalid",
        check_raw(lib, null_ptr, 3, good_ptr, good_n),
        -1,
    )
    expect(
        "null ptr + len>0 (hnsw side) -> invalid", check_raw(lib, good_ptr, good_n, null_ptr, 3), -1
    )
    # 10) Negative length -> Invalid (-1).
    expect("negative length -> invalid", check_raw(lib, good_ptr, -1, good_ptr, good_n), -1)

    print("\nRead gate (fail-closed):")
    # 11) Read gate permits only on Consistent (verdict 1).
    expect("read_gate(consistent=1) -> permit", lib.read_gate(1), 1)
    # 12) Read gate denies on Divergent (verdict 0).
    expect("read_gate(divergent=0) -> deny", lib.read_gate(0), 0)
    # 13) Read gate denies on any non-1 verdict (unknown state) -> deny.
    expect("read_gate(unknown=7) -> deny", lib.read_gate(7), 0)

    print()
    if failures:
        print(f"RESULT: {failures} guard assertion(s) FAILED")
        return 1
    print("RESULT: all guard assertions held — guard catches every divergence shape, fail-closed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
