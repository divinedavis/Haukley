-- Owner metrics count real viewers only (2026-10-10).
--
-- The first dashboard numbers were all ours: the 10 "accounts" were the owner plus test
-- accounts made for the /watch journey tests, and every ad event was a sample-ad test run.
--
-- 1. Internal accounts: any address at haukley.com (test accounts) plus the user ids in
--    private.internal_users (the owner's own account; filled out of band, not in git).
--    They are left out of accounts, signups, profiles and web watch time.
-- 2. Ads: only verified events (a server-signed playback ticket, migration 0014) count as
--    real; the unticketed pre-launch test events are reported separately as "unverified".
-- 3. Plays: playback_starts now keeps an HMAC of the caller's address (keyed by a secret in
--    private.metrics_salt; never the address itself), so the metrics agent can pass the
--    owner's known addresses and have their plays left out. Rows before this have no hash.

create table if not exists private.internal_users (
  user_id uuid primary key,
  note text,
  added_at timestamptz not null default now()
);
revoke all on private.internal_users from public, anon, authenticated;

create table if not exists private.metrics_salt (
  id boolean primary key default true check (id),
  salt bytea not null default extensions.gen_random_bytes(32)
);
insert into private.metrics_salt (id) values (true) on conflict do nothing;
revoke all on private.metrics_salt from public, anon, authenticated;

create or replace function private.addr_hash(addr text)
returns text
language sql
stable
security definer
set search_path = pg_catalog
as $$
  select encode(extensions.hmac(convert_to(addr, 'UTF8'), (select salt from private.metrics_salt), 'sha256'), 'hex')
$$;
revoke all on function private.addr_hash(text) from public, anon, authenticated;

create or replace function private.is_internal(uid uuid)
returns boolean
language sql
stable
security definer
set search_path = pg_catalog, public
as $$
  select exists (select 1 from private.internal_users where user_id = uid)
      or exists (select 1 from auth.users where id = uid and lower(email) like '%@haukley.com')
$$;
revoke all on function private.is_internal(uuid) from public, anon, authenticated;

alter table public.playback_starts add column if not exists addr_hash text;

create or replace function public.start_playback(jsonb)
returns jsonb
language plpgsql
volatile
security definer
set search_path = pg_catalog, public
as $$
declare
  b jsonb := $1;
  v_title text;
  v_episode int;
  v_platform text;
  ip text;
  used int;
  sess uuid := gen_random_uuid();
  issued bigint := floor(extract(epoch from now()))::bigint;
begin
  if b is null or jsonb_typeof(b) <> 'object' then
    raise exception 'body must be an object' using errcode = '22023';
  end if;
  v_title := b ->> 'title_id';
  v_platform := b ->> 'platform';
  begin
    v_episode := coalesce((b ->> 'episode')::int, 0);
  exception when others then
    raise exception 'bad episode' using errcode = '22023';
  end;
  if v_episode not between 0 and 999
     or v_platform is null
     or v_platform not in ('firetv', 'androidtv', 'tvos', 'roku', 'ios', 'web', 'lg', 'samsung')
     or not exists (select 1 from public.titles where id = v_title) then
    raise exception 'unknown title or platform' using errcode = '22023';
  end if;

  ip := coalesce(nullif(current_setting('request.headers', true)::json ->> 'cf-connecting-ip', ''), 'unknown');
  insert into public.playback_rate_buckets as r (ip_hash, window_start, n)
  values (encode(extensions.digest(ip, 'sha256'), 'hex'), date_trunc('hour', now()), 1)
  on conflict (ip_hash, window_start) do update set n = r.n + 1
  returning r.n into used;
  if used > 120 then
    raise exception 'rate limit exceeded' using errcode = 'P0001', hint = '429';
  end if;

  insert into public.playback_starts (title_id, episode, platform, addr_hash)
  values (v_title, v_episode, v_platform, private.addr_hash(ip));

  return jsonb_build_object(
    'session_id', sess,
    'token', issued::text || '.' || private.playback_sig(sess, v_title, v_episode, v_platform, issued));
end;
$$;
revoke all on function public.start_playback(jsonb) from public, anon, authenticated;
grant execute on function public.start_playback(jsonb) to anon, service_role;

drop function if exists public.owner_metrics(text, int);

create or replace function public.owner_metrics(p_key text, p_days int default null,
                                                p_exclude_addrs text[] default '{}')
returns jsonb
language plpgsql
stable
security definer
set search_path = pg_catalog, public
as $$
declare
  since timestamptz := case when p_days is null then '-infinity'::timestamptz
                            else now() - make_interval(days => greatest(p_days, 1)) end;
  skip text[];
begin
  if p_key is null or not exists (select 1 from private.owner_metrics_keys
                                  where key_hash = extensions.digest(p_key, 'sha256')) then
    raise exception 'forbidden' using errcode = '42501';
  end if;
  skip := coalesce((select array_agg(private.addr_hash(a)) from unnest(coalesce(p_exclude_addrs, '{}')) a), '{}');
  return jsonb_build_object(
    'generated_at', now(),
    'plays_daily', coalesce((select jsonb_agg(x order by x.d, x.platform) from (
        select created_at::date d, platform, count(*) n from public.playback_starts
        where created_at >= since and (addr_hash is null or addr_hash <> all (skip))
        group by 1, 2) x), '[]'::jsonb),
    'plays_first', (select min(created_at) from public.playback_starts),
    'plays_excluded', (select count(*) from public.playback_starts
                       where created_at >= since and addr_hash = any (skip)),
    'top_titles', coalesce((select jsonb_agg(x order by x.plays desc, x.title) from (
        select s.title_id, t.title, count(*) plays from public.playback_starts s
        join public.titles t on t.id = s.title_id
        where s.created_at >= since and (s.addr_hash is null or s.addr_hash <> all (skip))
        group by 1, 2 order by 3 desc, 2 limit 15) x), '[]'::jsonb),
    -- Real ads only: a verified event carries a server-signed playback ticket.
    'ads_daily', coalesce((select jsonb_agg(x order by x.d, x.platform) from (
        select created_at::date d, platform,
               count(*) filter (where event = 'ad_started') started,
               count(*) filter (where event = 'ad_completed') completed,
               count(distinct session_id) sessions,
               count(*) verified
        from public.ad_events where created_at >= since and verified group by 1, 2) x), '[]'::jsonb),
    'ads_unverified', (select count(*) from public.ad_events where created_at >= since and not verified),
    'signups_daily', coalesce((select jsonb_agg(x order by x.d) from (
        select created_at::date d, count(*) n from auth.users u
        where created_at >= since and not private.is_internal(u.id) group by 1) x), '[]'::jsonb),
    'accounts', (select count(*) from auth.users u where not private.is_internal(u.id)),
    'internal_accounts', (select count(*) from auth.users u where private.is_internal(u.id)),
    'profiles', (select count(*) from public.profiles p where not private.is_internal(p.user_id)),
    'kids_profiles', (select count(*) from public.profiles p where is_kids and not private.is_internal(p.user_id)),
    'web_watch', (select jsonb_build_object(
        'rows', count(*),
        'viewers', count(distinct user_id),
        'hours', round(coalesce(sum(least(position_s, duration_s)), 0) / 3600.0, 2),
        'finished', count(*) filter (where position_s >= 0.9 * duration_s))
      from public.watch_progress w where updated_at >= since and not private.is_internal(w.user_id)),
    'my_list_adds', (select count(*) from public.my_list m where added_at >= since and not private.is_internal(m.user_id)),
    'waitlist', (select count(*) from public.waitlist),
    'film_submissions', (select count(*) from public.film_submissions),
    'catalog_titles', (select count(*) from public.titles));
end;
$$;
revoke all on function public.owner_metrics(text, int, text[]) from public, anon, authenticated;
grant execute on function public.owner_metrics(text, int, text[]) to anon, service_role;
