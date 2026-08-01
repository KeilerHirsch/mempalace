with Interfaces.C;

package body Consistency
  with SPARK_Mode => On
is
   use type Interfaces.C.long_long;


   function Check_Consistency
     (Sqlite_Ids  : Label_Array;
      Hnsw_Labels : Label_Array) return Verdict
   is
   begin
      --  Different length ⇒ different sets ⇒ Divergent immediately.
      if Sqlite_Ids'Length /= Hnsw_Labels'Length then
         return Divergent;
      end if;

      --  Equal length: walk both in lock-step. On sorted+deduped input,
      --  any elementwise mismatch means the sets differ.
      for K in 0 .. Sqlite_Ids'Length - 1 loop
         --  Invariant: every prefix scanned so far matched elementwise.
         --  This is exactly the Sets_Equal predicate restricted to the
         --  scanned prefix — the prover chains it to the post-condition.
         pragma Loop_Invariant
           (for all P in 0 .. K - 1 =>
              Sqlite_Ids (Sqlite_Ids'First + P)
                = Hnsw_Labels (Hnsw_Labels'First + P));

         if Sqlite_Ids (Sqlite_Ids'First + K)
              /= Hnsw_Labels (Hnsw_Labels'First + K)
         then
            return Divergent;
         end if;
      end loop;

      --  Fell through: lengths equal and all elements matched.
      return Consistent;
   end Check_Consistency;

end Consistency;
