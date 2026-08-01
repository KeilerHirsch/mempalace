with Consistency;
with System;

package body Consistency_C
  with SPARK_Mode => Off
is
   use type Interfaces.C.int;
   use type Interfaces.C.long_long;
   use type Consistency.Verdict;

   --  Overlay type: a bounded array of C long_longs laid over the caller's
   --  buffer by address. This avoids Interfaces.C.Pointers' requirement
   --  for aliased element types while giving us a plain Label_Array to
   --  hand to the proved core.
   function To_Array
     (Ptr : access Interfaces.C.long_long;
      Len : Interfaces.C.int) return Consistency.Label_Array
   is
   begin
      if Len <= 0 or else Ptr = null then
         return Consistency.Label_Array'(1 .. 0 => 0);  -- empty
      end if;

      declare
         Overlay : Consistency.Label_Array (1 .. Positive (Len))
           with Import, Address => Ptr.all'Address;
      begin
         --  Copy out of the borrowed buffer into an owned array.
         return Consistency.Label_Array (Overlay);
      end;
   end To_Array;

   function Check_Consistency_C
     (Sqlite_Ptr  : access Interfaces.C.long_long;
      Sqlite_Len  : Interfaces.C.int;
      Hnsw_Ptr    : access Interfaces.C.long_long;
      Hnsw_Len    : Interfaces.C.int) return Interfaces.C.int
   is
   begin
      --  Invalid input (-1), kept distinct from Divergent (0): negative
      --  length, or a null pointer carrying a claimed positive length.
      --  This surfaces a malformed FFI call as a caller-contract error
      --  instead of silently folding it into a data-divergence verdict
      --  (review MED-2). Note: null + Len = 0 is a legitimate empty set,
      --  not invalid — only null + Len > 0 is contradictory.
      if Sqlite_Len < 0 or else Hnsw_Len < 0 then
         return -1;
      end if;
      if (Sqlite_Ptr = null and then Sqlite_Len > 0)
        or else (Hnsw_Ptr = null and then Hnsw_Len > 0)
      then
         return -1;
      end if;

      declare
         S : constant Consistency.Label_Array :=
           To_Array (Sqlite_Ptr, Sqlite_Len);
         H : constant Consistency.Label_Array :=
           To_Array (Hnsw_Ptr, Hnsw_Len);
      begin
         if Consistency.Check_Consistency (S, H) = Consistency.Consistent
         then
            return 1;
         else
            return 0;
         end if;
      end;
   end Check_Consistency_C;

   function Read_Gate_C
     (Last_Verdict : Interfaces.C.int) return Interfaces.C.int
   is
      Last : constant Consistency.Verdict :=
        (if Last_Verdict = 1 then Consistency.Consistent
         else Consistency.Divergent);
   begin
      if Consistency.Read_Gate (Last) then
         return 1;
      else
         return 0;
      end if;
   end Read_Gate_C;

end Consistency_C;
