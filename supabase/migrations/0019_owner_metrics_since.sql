-- Owner metrics take an exact range start (2026-10-10).
--
-- The dashboard labels "This month" as "Oct 1 -> now" but the agent asked for the last 30
-- days, so late September leaked into October's tiles. p_since (a UTC calendar day) now
-- sets the window exactly; p_days stays for callers that still send it.

drop function if exists public.owner_metrics(text, int, text[]);

create or replace function public.owner_metrics(p_key text, p_days int default null,
                                                p_exclude_addrs text[] default '{}',
                                                p_since date default null)
returns jsonb
language plpgsql
stable
security definer
set search_path = pg_catalog, public
as $$
declare
  -- p_since (a UTC day) wins: the dashboard's "This month" is the calendar month.
  since timestamptz := case when p_since is not null then (p_since::timestamp at time zone 'UTC')
                            when p_days is null then '-infinity'::timestamptz
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
revoke all on function public.owner_metrics(text, int, text[], date) from public, anon, authenticated;
grant execute on function public.owner_metrics(text, int, text[], date) to anon, service_role;
