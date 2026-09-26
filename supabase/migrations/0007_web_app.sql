-- The web app at haukley.com/watch/: signed-in viewers, synced Continue Watching and
-- My List, self-serve account deletion, and ad events logged as platform 'web'.

alter table public.ad_events drop constraint ad_events_platform_check;
alter table public.ad_events add constraint ad_events_platform_check
  check (platform in ('firetv', 'androidtv', 'tvos', 'roku', 'ios', 'web'));

-- One row per (viewer, title, episode). episode 0 = a movie.
create table public.watch_progress (
  user_id uuid not null default auth.uid() references auth.users (id) on delete cascade,
  title_id text not null references public.titles (id) on delete cascade,
  episode smallint not null default 0 check (episode between 0 and 99),
  position_s int not null check (position_s between 0 and 86400),
  duration_s int not null check (duration_s between 1 and 86400),
  updated_at timestamptz not null default now(),
  primary key (user_id, title_id, episode)
);
alter table public.watch_progress enable row level security;
grant select, insert, update, delete on public.watch_progress to authenticated;
grant all on public.watch_progress to service_role;
create policy "own progress" on public.watch_progress
  for all to authenticated
  using (user_id = auth.uid()) with check (user_id = auth.uid());

create table public.my_list (
  user_id uuid not null default auth.uid() references auth.users (id) on delete cascade,
  title_id text not null references public.titles (id) on delete cascade,
  added_at timestamptz not null default now(),
  primary key (user_id, title_id)
);
alter table public.my_list enable row level security;
grant select, insert, delete on public.my_list to authenticated;
grant all on public.my_list to service_role;
create policy "own list" on public.my_list
  for all to authenticated
  using (user_id = auth.uid()) with check (user_id = auth.uid());

-- Deletes the caller's account; watch_progress and my_list go with it (on delete cascade).
create function public.delete_account()
returns void
language plpgsql
volatile
security definer
set search_path = pg_catalog, public
as $$
begin
  if auth.uid() is null then
    raise exception 'not signed in' using errcode = '42501';
  end if;
  delete from auth.users where id = auth.uid();
end;
$$;
revoke all on function public.delete_account() from public, anon, authenticated;
grant execute on function public.delete_account() to authenticated;

notify pgrst, 'reload schema';
