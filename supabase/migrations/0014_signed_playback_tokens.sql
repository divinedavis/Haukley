-- Ad events only count toward payouts when they carry a server-signed playback token.
--
-- Before: log_ad_events (0005) took any caller-chosen session_id/title_id, limited only by
-- 100 events per session and 300 per IP per hour, and every row fed estimated_payouts. A
-- script could mint sessions and inflate one film's count.
--
-- Now:
--   * POST /rest/v1/rpc/start_playback {title_id, episode, platform} -> {session_id, token}
--     The server picks the session id and signs session|title|episode|platform|issued_at with
--     an HMAC key that lives in the private schema (no API role can read it). 120 starts per
--     IP per hour.
--   * log_ad_events still accepts the old body (so shipped apps - iPhone 1.0.1, Fire TV 1.0,
--     LG/Samsung 1.0, Roku sideloads - never see an error), plus per-event "token" and "seq".
--     An event is VERIFIED (counted) only when all of these hold:
--       - the token's HMAC matches this event's session/title/episode/platform, < 8 h old
--       - (session, event, seq) is new - client retries are dropped, not double-counted
--       - the session has fewer counted events of this type than 2 + seconds_since_start/10
--         (an ad lasts >= ~6-15 s, so a real player can't outrun it)
--       - this IP has had < 150 counted events for this title today
--     Anything else is stored with verified = false: visible for debugging, never paid on.
--   * monthly_ad_counts / estimated_payouts count verified rows only.

create schema if not exists private;
revoke all on schema private from public, anon, authenticated;

create table if not exists private.playback_keys (
  id int primary key default 1 check (id = 1),
  secret bytea not null
);
revoke all on private.playback_keys from public, anon, authenticated;
insert into private.playback_keys (id, secret)
values (1, extensions.gen_random_bytes(32))
on conflict (id) do nothing;

create or replace function private.playback_sig(p_session uuid, p_title text, p_episode int,
                                                p_platform text, p_issued bigint)
returns text
language sql
stable
set search_path = pg_catalog
as $$
  select encode(extensions.hmac(
           convert_to(concat_ws('|', p_session::text, p_title, p_episode::text, p_platform, p_issued::text), 'UTF8'),
           (select secret from private.playback_keys where id = 1),
           'sha256'), 'hex');
$$;
revoke all on function private.playback_sig(uuid, text, int, text, bigint) from public, anon, authenticated;

alter table public.ad_events add column if not exists verified boolean not null default false;
alter table public.ad_events add column if not exists seq int check (seq between 0 and 10000);
create unique index if not exists ad_events_verified_dedupe
  on public.ad_events (session_id, event, seq) where verified;

create table if not exists public.playback_rate_buckets (
  ip_hash text not null,
  window_start timestamptz not null,
  n int not null default 0,
  primary key (ip_hash, window_start)
);
alter table public.playback_rate_buckets enable row level security;
revoke all on public.playback_rate_buckets from anon, authenticated;
grant all on public.playback_rate_buckets to service_role;

create table if not exists public.ad_title_buckets (
  ip_hash text not null,
  title_id text not null,
  day date not null,
  n int not null default 0,
  primary key (ip_hash, title_id, day)
);
alter table public.ad_title_buckets enable row level security;
revoke all on public.ad_title_buckets from anon, authenticated;
grant all on public.ad_title_buckets to service_role;

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

  return jsonb_build_object(
    'session_id', sess,
    'token', issued::text || '.' || private.playback_sig(sess, v_title, v_episode, v_platform, issued));
end;
$$;
revoke all on function public.start_playback(jsonb) from public, anon, authenticated;
grant execute on function public.start_playback(jsonb) to anon, service_role;

create or replace function public.log_ad_events(jsonb)
returns void
language plpgsql
volatile
security definer
set search_path = pg_catalog, public
as $$
declare
  body jsonb := $1;
  evs jsonb;
  e jsonb;
  n int;
  ip text;
  h text;
  bucket timestamptz := date_trunc('hour', now());
  now_s bigint := floor(extract(epoch from now()))::bigint;
  used int;
  sess uuid;
  v_title text;
  v_episode int;
  v_platform text;
  v_event text;
  v_seq int;
  tok text;
  issued bigint;
  counted int;
  ok boolean;
begin
  if body is null then
    raise exception 'empty body' using errcode = '22023';
  end if;
  evs := case jsonb_typeof(body) when 'array' then body when 'object' then jsonb_build_array(body) end;
  if evs is null then
    raise exception 'body must be an event or an array of events' using errcode = '22023';
  end if;
  n := jsonb_array_length(evs);
  if n = 0 then return; end if;
  if n > 20 then
    raise exception 'too many events in one call' using errcode = '22023';
  end if;

  -- Per-IP hourly bucket (atomic upsert; the row lock serialises concurrent calls).
  ip := coalesce(nullif(current_setting('request.headers', true)::json ->> 'cf-connecting-ip', ''), 'unknown');
  h := encode(extensions.digest(ip, 'sha256'), 'hex');
  insert into public.ad_rate_buckets as b (ip_hash, window_start, events)
  values (h, bucket, n)
  on conflict (ip_hash, window_start) do update set events = b.events + excluded.events
  returning b.events into used;
  if used > 300 then
    raise exception 'rate limit exceeded' using errcode = 'P0001', hint = '429';
  end if;

  -- Per-session cap (each distinct session in the batch).
  for sess in select distinct (x ->> 'session_id')::uuid from jsonb_array_elements(evs) x loop
    if (select count(*) from public.ad_events where session_id = sess)
       + (select count(*) from jsonb_array_elements(evs) x where (x ->> 'session_id')::uuid = sess) > 100 then
      raise exception 'session event limit exceeded' using errcode = 'P0001', hint = '429';
    end if;
  end loop;

  for e in select value from jsonb_array_elements(evs) loop
    sess := (e ->> 'session_id')::uuid;
    v_title := e ->> 'title_id';
    v_episode := coalesce((e ->> 'episode')::smallint, 0);
    v_platform := e ->> 'platform';
    v_event := e ->> 'event';
    tok := e ->> 'token';
    v_seq := null;
    ok := false;

    if tok ~ '^[0-9]{9,11}\.[0-9a-f]{64}$' and (e ->> 'seq') ~ '^[0-9]{1,5}$' then
      v_seq := (e ->> 'seq')::int;
      issued := split_part(tok, '.', 1)::bigint;
      if v_seq <= 10000
         and now_s - issued between -60 and 8 * 3600
         and split_part(tok, '.', 2) = private.playback_sig(sess, v_title, v_episode, v_platform, issued) then
        if exists (select 1 from public.ad_events
                   where verified and session_id = sess and event = v_event and seq = v_seq) then
          continue;  -- a client retry of an event already counted: drop it
        end if;
        select count(*) into counted from public.ad_events
         where verified and session_id = sess and event = v_event;
        if counted < 2 + greatest(now_s - issued, 0) / 10 then
          insert into public.ad_title_buckets as t (ip_hash, title_id, day, n)
          values (h, v_title, current_date, 1)
          on conflict (ip_hash, title_id, day) do update set n = t.n + 1
          returning t.n into used;
          ok := used <= 150;
        end if;
      end if;
    end if;

    -- Column checks/FKs on ad_events still validate every field; created_at is server-set.
    insert into public.ad_events (title_id, episode, platform, event, ad_id, session_id, verified, seq)
    values (v_title, v_episode, v_platform, v_event, left(e ->> 'ad_id', 200), sess, ok,
            case when ok then v_seq end)
    on conflict (session_id, event, seq) where verified do nothing;
  end loop;

  -- Opportunistic cleanup of old buckets.
  delete from public.ad_rate_buckets where window_start < now() - interval '2 days';
end;
$$;

revoke execute on function public.log_ad_events(jsonb) from public, anon, authenticated;
grant execute on function public.log_ad_events(jsonb) to anon, service_role;

-- Payout inputs: verified rows only. unverified_events is for spotting old clients / abuse.
create or replace view public.monthly_ad_counts with (security_invoker = true) as
select date_trunc('month', e.created_at)::date as month,
       e.title_id,
       t.title,
       e.platform,
       count(*) filter (where e.verified and e.event = 'ad_started') as ads_started,
       count(*) filter (where e.verified and e.event = 'ad_completed') as ads_completed,
       count(distinct e.session_id) filter (where e.verified) as viewing_sessions,
       count(*) filter (where not e.verified) as unverified_events
from public.ad_events e
join public.titles t on t.id = e.title_id
group by 1, 2, 3, 4;
revoke all on public.monthly_ad_counts from anon, authenticated;
grant select on public.monthly_ad_counts to service_role;

-- The IP-hash counters age out with the others (privacy policy: deleted after two days).
select cron.unschedule('haukley-ip-hash-cleanup')
 where exists (select 1 from cron.job where jobname = 'haukley-ip-hash-cleanup');
select cron.schedule(
  'haukley-ip-hash-cleanup',
  '17 * * * *',
  $$
  delete from public.ad_rate_buckets where window_start < now() - interval '2 days';
  delete from public.submission_rate_buckets where day < current_date - 2;
  delete from public.playback_rate_buckets where window_start < now() - interval '2 days';
  delete from public.ad_title_buckets where day < current_date - 2;
  $$
);

notify pgrst, 'reload schema';
