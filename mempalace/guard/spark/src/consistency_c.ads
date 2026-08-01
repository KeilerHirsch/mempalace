--  C-ABI boundary for the SPARK consistency guard.
--
--  This is the ONE unproved crossing (SPARK_Mode => Off): raw C pointers
--  cannot carry SPARK's array bounds, so the marshalling lives here and
--  the proved core (package Consistency) stays pure. Everything of value
--  is proved on the far side of this thin wrapper; the wrapper only
--  rebuilds bounded Ada arrays from (ptr, len) and calls the proved
--  function. Python binds these via ctypes.

with Interfaces.C;

package Consistency_C
  with SPARK_Mode => Off
is

   --  Returns:
   --     1  = Consistent (sets equal)
   --     0  = Divergent  (sets differ — a real consistency finding)
   --    -1  = Invalid input (malformed FFI call: null pointer with a
   --          claimed positive length, or negative length). Kept DISTINCT
   --          from Divergent so an on-call reader never mistakes a caller
   --          bug for a chromadb consistency incident (review MED-2).
   --  Inputs are pointers to int64 (long_long) arrays that Python has
   --  already sorted strictly ascending and deduped (the proved core's
   --  precondition). Lengths stay 32-bit int — a count never needs 64
   --  bits, only the label values (64-bit hashes) do.
   function Check_Consistency_C
     (Sqlite_Ptr  : access Interfaces.C.long_long;
      Sqlite_Len  : Interfaces.C.int;
      Hnsw_Ptr    : access Interfaces.C.long_long;
      Hnsw_Len    : Interfaces.C.int) return Interfaces.C.int
   with
     Export        => True,
     Convention    => C,
     External_Name => "check_consistency";

   --  Fail-closed read gate exposed to C: 1 = read permitted, 0 = denied.
   --  Permitted only when Last_Verdict = 1 (Consistent).
   function Read_Gate_C
     (Last_Verdict : Interfaces.C.int) return Interfaces.C.int
   with
     Export        => True,
     Convention    => C,
     External_Name => "read_gate";

end Consistency_C;
