-- Replace the apps' direct INSERT on ad_events (unbounded; the rows feed estimated_payouts)
-- with a rate-limited SECURITY DEFINER RPC: POST /rest/v1/rpc/log_ad_events.
-- The body is either one event object (RN, iPhone) or an array of them (Roku batches), the
-- same shapes the apps already posted to /rest/v1/ad_events, so clients only change the URL.
--
-- Limits (a real viewer hits none of them; a VMAP pre/mid/post movie is ~6-10 events):
--   * batch   <= 20 events per call
--   * session <= 100 events per session_id, ever
--   * client IP <= 300 events per hour (IP from Cloudflare's cf-connecting-ip, which the
--     client cannot set; only a sha256 of it is stored, in a table nobody but the owner reads)
-- Over-limit calls raise 429-style errors (P0001) and insert nothing.

create table public.ad_rate_buckets (
  ip_hash text not null,
  window_start timestamptz not null,
  events int not null default 0,
  primary key (ip_hash, window_start)
);
alter table public.ad_rate_buckets enable row level security;
revoke all on public.ad_rate_buckets from anon, authenticated;
grant all on public.ad_rate_buckets to service_role;

create index if not exists ad_events_session on public.ad_events (session_id);

create function public.log_ad_events(jsonb)
returns void
language plpgsql
volatile
security definer
set search_path = pg_catalog, public
as $$
declare
  body jsonb := $1;
  evs jsonb;
  n int;
  ip text;
  bucket timestamptz := date_trunc('hour', now());
  used int;
  sess uuid;
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
  insert into public.ad_rate_buckets as b (ip_hash, window_start, events)
  values (encode(extensions.digest(ip, 'sha256'), 'hex'), bucket, n)
  on conflict (ip_hash, window_start) do update set events = b.events + excluded.events
  returning b.events into used;
  if used > 300 then
    raise exception 'rate limit exceeded' using errcode = 'P0001', hint = '429';
  end if;

  -- Per-session cap (each distinct session in the batch).
  for sess in select distinct (e ->> 'session_id')::uuid from jsonb_array_elements(evs) e loop
    if (select count(*) from public.ad_events where session_id = sess)
       + (select count(*) from jsonb_array_elements(evs) e where (e ->> 'session_id')::uuid = sess) > 100 then
      raise exception 'session event limit exceeded' using errcode = 'P0001', hint = '429';
    end if;
  end loop;

  -- Column checks/FKs on ad_events still validate every field; created_at is server-set.
  insert into public.ad_events (title_id, episode, platform, event, ad_id, session_id)
  select e ->> 'title_id',
         coalesce((e ->> 'episode')::smallint, 0),
         e ->> 'platform',
         e ->> 'event',
         left(e ->> 'ad_id', 200),
         (e ->> 'session_id')::uuid
  from jsonb_array_elements(evs) e;

  -- Opportunistic cleanup of old buckets.
  delete from public.ad_rate_buckets where window_start < now() - interval '2 days';
end;
$$;

revoke execute on function public.log_ad_events(jsonb) from public, anon, authenticated;
grant execute on function public.log_ad_events(jsonb) to anon, service_role;

-- Close the old unbounded path.
drop policy if exists "apps log ad events" on public.ad_events;
revoke insert on public.ad_events from anon;

notify pgrst, 'reload schema';
