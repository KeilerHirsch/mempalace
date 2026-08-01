--  MemPalace consistency guard — SPARK core (proved by gnatprove).
--
--  Purpose: the second line of defence in the FMEA/redundancy doctrine.
--  chromadb's HNSW persist is not process-safe; two unlocked writers
--  race and lose labels silently (root cause PROVEN 2026-08-01:
--  without lock diff=32, with lock diff=0). The Python race-fix is the
--  first line. This guard makes divergence impossible to pass silently:
--  every read is gated on a proved consistency check that compares the
--  full label set, not just the count (count matches while ids differ
--  when chromadb recycles labels through upsert/delete).
--
--  The whole package is SPARK_Mode => On so gnatprove proves absence of
--  runtime errors AND the functional post-conditions to Gold.

with Interfaces.C;

package Consistency
  with SPARK_Mode => On
is

   --  A label is a 64-bit hash of chromadb's internal HNSW element id /
   --  sqlite embedding_id (both UUID strings). 32 bits was rejected: at
   --  323k+ elements a birthday-bound collision on a 32-bit hash is not
   --  negligible. long_long (not C's plain `long`, which is 4 bytes on
   --  Windows/LLP64) is 8 bytes on every target.
   subtype Label is Interfaces.C.long_long;

   --  Make the relational/equality operators on Label directly visible
   --  so the predicates and body can compare labels without qualifying.
   use type Interfaces.C.long_long;

   type Label_Array is array (Positive range <>) of Label;

   type Verdict is (Consistent, Divergent);

   --  True when A is STRICTLY ascending: for I < J, A(I) < A(J). Strict
   --  ordering (< not <=) subsumes deduplication — a strictly-ascending
   --  array cannot repeat a value, so this single predicate expresses
   --  both "sorted" and "no duplicates". Do NOT relax to <= : that would
   --  admit duplicates and reopen the set-equality gap. The caller
   --  (Python) sorts + dedups before the C-ABI crossing; a violation
   --  fails this precondition rather than producing a wrong verdict.
   function Is_Strictly_Ascending (A : Label_Array) return Boolean
   is (for all I in A'Range =>
         (for all J in A'Range =>
            (if I < J then A (I) < A (J))))
   with Ghost;

   --  Two sorted arrays are equal-as-sets exactly when same length and
   --  elementwise equal. On sorted+deduped input this is set equality.
   function Sets_Equal (A, B : Label_Array) return Boolean
   is (A'Length = B'Length
       and then (for all K in 0 .. A'Length - 1 =>
                   A (A'First + K) = B (B'First + K)))
   with Ghost;

   --  The consistency check. Precondition: both inputs sorted ascending.
   --  Postcondition nails the guard to set equality — this is what the
   --  prover verifies, so the verdict can never disagree with the sets.
   function Check_Consistency
     (Sqlite_Ids  : Label_Array;
      Hnsw_Labels : Label_Array) return Verdict
   with
     Pre  => Is_Strictly_Ascending (Sqlite_Ids)
             and then Is_Strictly_Ascending (Hnsw_Labels),
     Post => (Check_Consistency'Result = Consistent)
             = Sets_Equal (Sqlite_Ids, Hnsw_Labels);

   --  Read gate: fail-closed. A read is permitted ONLY when the last
   --  consistency check returned Consistent. Anything else (Divergent,
   --  unknown) denies the read. Post proves the fail-closed property:
   --  Permitted implies Consistent.
   function Read_Gate (Last : Verdict) return Boolean
   is (Last = Consistent)
   with Post => (if Read_Gate'Result then Last = Consistent);

end Consistency;
