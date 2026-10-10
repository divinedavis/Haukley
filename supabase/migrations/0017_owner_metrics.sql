-- Haukley owner metrics (2026-10-10).
--
-- 1. Every catalog movie/show must exist in public.titles: start_playback refuses unknown ids
--    and ad_events.title_id references the table. The series, the Black Cinema films and
--    batch 3 were never seeded, so they got no playback ticket (ad events unverified).
--    tests/test_catalog.py now fails if a catalog id is missing from the migrations.
-- 2. public.playback_starts: one row per start_playback call (title, episode, platform,
--    time; no IP, no user), so "plays" are countable on every platform that asks for a ticket.
-- 3. public.owner_metrics(p_key, p_days): aggregate counts only, for the owner dashboard's
--    metrics agent. The key's SHA-256 lives in private.owner_metrics_keys (inserted out of
--    band, never in git); the plain key is in /etc/owner-metrics/env on 104.236.

insert into public.titles (id, kind, title) values
  ('the-general', 'movie', 'The General'),
  ('sherlock-jr', 'movie', 'Sherlock Jr.'),
  ('safety-last', 'movie', 'Safety Last!'),
  ('the-freshman', 'movie', 'The Freshman'),
  ('one-week', 'movie', 'One Week'),
  ('his-girl-friday', 'movie', 'His Girl Friday'),
  ('nosferatu', 'movie', 'Nosferatu'),
  ('phantom-of-the-opera', 'movie', 'The Phantom of the Opera'),
  ('night-of-the-living-dead', 'movie', 'Night of the Living Dead'),
  ('the-little-shop-of-horrors', 'movie', 'The Little Shop of Horrors'),
  ('carnival-of-souls', 'movie', 'Carnival of Souls'),
  ('metropolis', 'movie', 'Metropolis'),
  ('a-trip-to-the-moon', 'movie', 'A Trip to the Moon'),
  ('all-quiet-on-the-western-front', 'movie', 'All Quiet on the Western Front'),
  ('d-o-a', 'movie', 'D.O.A.'),
  ('man-with-a-movie-camera', 'movie', 'Man with a Movie Camera'),
  ('big-buck-bunny', 'movie', 'Big Buck Bunny'),
  ('sintel', 'movie', 'Sintel'),
  ('tears-of-steel', 'movie', 'Tears of Steel'),
  ('elephants-dream', 'movie', 'Elephants Dream'),
  ('cosmos-laundromat', 'movie', 'Cosmos Laundromat'),
  ('spring', 'movie', 'Spring'),
  ('sprite-fright', 'movie', 'Sprite Fright'),
  ('charge', 'movie', 'Charge'),
  ('our-hospitality', 'movie', 'Our Hospitality'),
  ('seven-chances', 'movie', 'Seven Chances'),
  ('steamboat-bill-jr', 'movie', 'Steamboat Bill, Jr.'),
  ('the-navigator', 'movie', 'The Navigator'),
  ('college', 'movie', 'College'),
  ('the-cameraman', 'movie', 'The Cameraman'),
  ('speedy', 'movie', 'Speedy'),
  ('animal-crackers', 'movie', 'Animal Crackers'),
  ('it', 'movie', 'It'),
  ('sunrise', 'movie', 'Sunrise'),
  ('the-hunchback-of-notre-dame', 'movie', 'The Hunchback of Notre Dame'),
  ('dr-jekyll-and-mr-hyde', 'movie', 'Dr. Jekyll and Mr. Hyde'),
  ('white-zombie', 'movie', 'White Zombie'),
  ('the-terror', 'movie', 'The Terror'),
  ('dementia-13', 'movie', 'Dementia 13'),
  ('night-tide', 'movie', 'Night Tide'),
  ('the-bat', 'movie', 'The Bat'),
  ('the-stranger', 'movie', 'The Stranger'),
  ('scarlet-street', 'movie', 'Scarlet Street'),
  ('kansas-city-confidential', 'movie', 'Kansas City Confidential'),
  ('the-hitch-hiker', 'movie', 'The Hitch-Hiker'),
  ('suddenly', 'movie', 'Suddenly'),
  ('the-big-combo', 'movie', 'The Big Combo'),
  ('blackmail', 'movie', 'Blackmail'),
  ('the-woman-in-green', 'movie', 'The Woman in Green'),
  ('the-big-trail', 'movie', 'The Big Trail'),
  ('angel-and-the-badman', 'movie', 'Angel and the Badman'),
  ('santa-fe-trail', 'movie', 'Santa Fe Trail'),
  ('the-mark-of-zorro', 'movie', 'The Mark of Zorro'),
  ('robin-hood', 'movie', 'Robin Hood'),
  ('the-thief-of-bagdad', 'movie', 'The Thief of Bagdad'),
  ('the-black-pirate', 'movie', 'The Black Pirate'),
  ('the-lost-world', 'movie', 'The Lost World'),
  ('wings', 'movie', 'Wings'),
  ('hells-angels', 'movie', 'Hell''s Angels'),
  ('the-big-parade', 'movie', 'The Big Parade'),
  ('meet-john-doe', 'movie', 'Meet John Doe'),
  ('a-star-is-born', 'movie', 'A Star Is Born'),
  ('the-crowd', 'movie', 'The Crowd'),
  ('rain', 'movie', 'Rain'),
  ('the-girl-from-chicago', 'movie', 'The Girl from Chicago'),
  ('veiled-aristocrats', 'movie', 'Veiled Aristocrats'),
  ('murder-in-harlem', 'movie', 'Murder in Harlem'),
  ('birthright-1938', 'movie', 'Birthright'),
  ('lying-lips', 'movie', 'Lying Lips'),
  ('the-blood-of-jesus', 'movie', 'The Blood of Jesus'),
  ('go-down-death', 'movie', 'Go Down, Death!'),
  ('dirty-gertie-from-harlem-usa', 'movie', 'Dirty Gertie from Harlem U.S.A.'),
  ('juke-joint', 'movie', 'Juke Joint'),
  ('souls-of-sin', 'movie', 'Souls of Sin'),
  ('go-west', 'movie', 'Go West'),
  ('battling-butler', 'movie', 'Battling Butler'),
  ('topper-returns', 'movie', 'Topper Returns'),
  ('made-for-each-other', 'movie', 'Made for Each Other'),
  ('quicksand', 'movie', 'Quicksand'),
  ('terror-by-night', 'movie', 'Terror by Night'),
  ('captain-kidd', 'movie', 'Captain Kidd'),
  ('of-human-bondage', 'movie', 'Of Human Bondage'),
  ('the-blue-angel', 'movie', 'The Blue Angel'),
  ('nanook-of-the-north', 'movie', 'Nanook of the North'),
  ('reefer-madness', 'movie', 'Reefer Madness'),
  ('salt-of-the-earth', 'movie', 'Salt of the Earth'),
  ('let-there-be-light', 'movie', 'Let There Be Light'),
  ('the-negro-soldier', 'movie', 'The Negro Soldier'),
  ('apollo-mission-films', 'show', 'Apollo: The Mission Films'),
  ('sherlock-holmes-1954', 'show', 'Sherlock Holmes'),
  ('rocky-jones-space-ranger', 'show', 'Rocky Jones, Space Ranger'),
  ('life-with-elizabeth', 'show', 'Life with Elizabeth'),
  ('flip-the-frog-1930', 'show', 'Flip the Frog'),
  ('why-we-fight', 'show', 'Why We Fight'),
  ('wwii-combat-reports', 'show', 'WWII Combat Reports'),
  ('caminandes', 'show', 'Caminandes'),
  ('blender-open-shorts', 'show', 'Blender Open Shorts')
on conflict (id) do update set kind = excluded.kind, title = excluded.title;

create table if not exists public.playback_starts (
  id bigint generated always as identity primary key,
  created_at timestamptz not null default now(),
  title_id text not null references public.titles (id) on delete cascade,
  episode smallint not null default 0 check (episode between 0 and 999),
  platform text not null
);
create index if not exists playback_starts_created on public.playback_starts (created_at);
alter table public.playback_starts enable row level security;
revoke all on public.playback_starts from public, anon, authenticated;
grant all on public.playback_starts to service_role;

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

  insert into public.playback_starts (title_id, episode, platform) values (v_title, v_episode, v_platform);

  return jsonb_build_object(
    'session_id', sess,
    'token', issued::text || '.' || private.playback_sig(sess, v_title, v_episode, v_platform, issued));
end;
$$;
revoke all on function public.start_playback(jsonb) from public, anon, authenticated;
grant execute on function public.start_playback(jsonb) to anon, service_role;

create table if not exists private.owner_metrics_keys (
  key_hash bytea primary key,
  added_at timestamptz not null default now()
);
revoke all on private.owner_metrics_keys from public, anon, authenticated;

create or replace function public.owner_metrics(p_key text, p_days int default null)
returns jsonb
language plpgsql
stable
security definer
set search_path = pg_catalog, public
as $$
declare
  since timestamptz := case when p_days is null then '-infinity'::timestamptz
                            else now() - make_interval(days => greatest(p_days, 1)) end;
begin
  if p_key is null or not exists (select 1 from private.owner_metrics_keys
                                  where key_hash = extensions.digest(p_key, 'sha256')) then
    raise exception 'forbidden' using errcode = '42501';
  end if;
  return jsonb_build_object(
    'generated_at', now(),
    'plays_daily', coalesce((select jsonb_agg(x order by x.d, x.platform) from (
        select created_at::date d, platform, count(*) n from public.playback_starts
        where created_at >= since group by 1, 2) x), '[]'::jsonb),
    'plays_first', (select min(created_at) from public.playback_starts),
    'top_titles', coalesce((select jsonb_agg(x order by x.plays desc, x.title) from (
        select s.title_id, t.title, count(*) plays from public.playback_starts s
        join public.titles t on t.id = s.title_id
        where s.created_at >= since group by 1, 2 order by 3 desc, 2 limit 15) x), '[]'::jsonb),
    'ads_daily', coalesce((select jsonb_agg(x order by x.d, x.platform) from (
        select created_at::date d, platform,
               count(*) filter (where event = 'ad_started') started,
               count(*) filter (where event = 'ad_completed') completed,
               count(distinct session_id) sessions,
               count(*) filter (where verified) verified
        from public.ad_events where created_at >= since group by 1, 2) x), '[]'::jsonb),
    'signups_daily', coalesce((select jsonb_agg(x order by x.d) from (
        select created_at::date d, count(*) n from auth.users
        where created_at >= since group by 1) x), '[]'::jsonb),
    'accounts', (select count(*) from auth.users),
    'profiles', (select count(*) from public.profiles),
    'kids_profiles', (select count(*) from public.profiles where is_kids),
    'web_watch', (select jsonb_build_object(
        'rows', count(*),
        'viewers', count(distinct user_id),
        'hours', round(coalesce(sum(least(position_s, duration_s)), 0) / 3600.0, 2),
        'finished', count(*) filter (where position_s >= 0.9 * duration_s))
      from public.watch_progress where updated_at >= since),
    'my_list_adds', (select count(*) from public.my_list where added_at >= since),
    'waitlist', (select count(*) from public.waitlist),
    'film_submissions', (select count(*) from public.film_submissions),
    'catalog_titles', (select count(*) from public.titles));
end;
$$;
revoke all on function public.owner_metrics(text, int) from public, anon, authenticated;
grant execute on function public.owner_metrics(text, int) to anon, service_role;
