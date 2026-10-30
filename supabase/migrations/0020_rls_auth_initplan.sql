-- haukley: wrap auth.*() in (select ...) so RLS evaluates it once per
-- query, not once per row (advisor auth_rls_initplan). Same predicates.
-- Generated from live pg_policies 2026-10-30.

alter policy "own profiles" on public."profiles"
  using ((user_id = ( SELECT auth.uid() AS uid)))
  with check ((user_id = ( SELECT auth.uid() AS uid)));

alter policy "own progress" on public."watch_progress"
  using ((user_id = ( SELECT auth.uid() AS uid)))
  with check (((user_id = ( SELECT auth.uid() AS uid)) AND (EXISTS ( SELECT 1
   FROM profiles p
  WHERE ((p.id = watch_progress.profile_id) AND (p.user_id = ( SELECT auth.uid() AS uid)))))));

alter policy "own list" on public."my_list"
  using ((user_id = ( SELECT auth.uid() AS uid)))
  with check (((user_id = ( SELECT auth.uid() AS uid)) AND (EXISTS ( SELECT 1
   FROM profiles p
  WHERE ((p.id = my_list.profile_id) AND (p.user_id = ( SELECT auth.uid() AS uid)))))));
