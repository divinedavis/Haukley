-- Viewer profiles on the web app ("Who's watching?"): up to 5 per account, optionally Kids.
-- Continue Watching and My List become per-profile. Both tables were empty when this ran.

create table public.profiles (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null default auth.uid() references auth.users (id) on delete cascade,
  name text not null check (char_length(btrim(name)) between 1 and 30),
  avatar smallint not null default 0 check (avatar between 0 and 11),
  is_kids boolean not null default false,
  created_at timestamptz not null default now()
);
create index profiles_user on public.profiles (user_id);
alter table public.profiles enable row level security;
grant select, insert, update, delete on public.profiles to authenticated;
grant all on public.profiles to service_role;
create policy "own profiles" on public.profiles
  for all to authenticated
  using (user_id = auth.uid()) with check (user_id = auth.uid());

create function public.profiles_cap()
returns trigger
language plpgsql
set search_path = pg_catalog, public
as $$
begin
  if (select count(*) from public.profiles where user_id = new.user_id) >= 5 then
    raise exception 'profile limit reached' using errcode = 'P0001';
  end if;
  return new;
end;
$$;
revoke all on function public.profiles_cap() from public, anon, authenticated;
create trigger profiles_cap before insert on public.profiles
  for each row execute function public.profiles_cap();

-- Per-profile progress and list. RLS still keys on user_id; the profile must be the caller's.
alter table public.watch_progress
  add column profile_id uuid not null references public.profiles (id) on delete cascade;
alter table public.watch_progress drop constraint watch_progress_pkey;
alter table public.watch_progress add primary key (profile_id, title_id, episode);
drop policy "own progress" on public.watch_progress;
create policy "own progress" on public.watch_progress
  for all to authenticated
  using (user_id = auth.uid())
  with check (user_id = auth.uid()
              and exists (select 1 from public.profiles p where p.id = profile_id and p.user_id = auth.uid()));

alter table public.my_list
  add column profile_id uuid not null references public.profiles (id) on delete cascade;
alter table public.my_list drop constraint my_list_pkey;
alter table public.my_list add primary key (profile_id, title_id);
drop policy "own list" on public.my_list;
create policy "own list" on public.my_list
  for all to authenticated
  using (user_id = auth.uid())
  with check (user_id = auth.uid()
              and exists (select 1 from public.profiles p where p.id = profile_id and p.user_id = auth.uid()));

notify pgrst, 'reload schema';
