-- Trim the Data API grants on the per-viewer tables to what the web app uses.
--
-- Found in the 2026-09-27 RLS sweep: Supabase's stock default privileges had
-- left `anon` holding INSERT/UPDATE/DELETE/TRUNCATE on profiles, my_list and
-- watch_progress, and `authenticated` holding TRUNCATE/TRIGGER/REFERENCES on
-- them. 0007/0008 only ever granted the authenticated CRUD they needed; the
-- rest came from the defaults. RLS (policies are `to authenticated` only)
-- already refuses every anon row write — verified live, anon reads return
-- 0 rows — but TRUNCATE is not subject to RLS at all, and the grant layer is
-- meant to be the second line if a policy is ever loosened.
--
-- web/watch/app.js only touches these tables once signed in:
--   profiles        select, insert, update, delete
--   watch_progress  select, upsert (insert + update)
--   my_list         select, insert, delete   (no update, as 0007 intended)
-- anon keeps SELECT so a read racing a session refresh returns 0 rows through
-- RLS instead of a hard 42501.

revoke insert, update, delete, truncate, trigger, references
  on public.profiles, public.my_list, public.watch_progress
  from anon;
revoke truncate, trigger, references
  on public.profiles, public.my_list, public.watch_progress
  from authenticated;
revoke update on public.my_list from authenticated;

-- Stop the next new table from inheriting the same grants.
alter default privileges in schema public
  revoke insert, update, delete, truncate, trigger, references on tables from anon;
alter default privileges in schema public
  revoke truncate, trigger, references on tables from authenticated;
alter default privileges for role postgres in schema public
  revoke insert, update, delete, truncate, trigger, references on tables from anon;
alter default privileges for role postgres in schema public
  revoke truncate, trigger, references on tables from authenticated;
