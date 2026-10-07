-- The haukley.com "Get notified" form inserted straight into public.waitlist with the
-- publishable key, with no limit on how many rows one client could add (audit L1). Replace
-- that with a rate-limited SECURITY DEFINER RPC, like submit_film (0006):
--   POST /rest/v1/rpc/join_waitlist {"email": "...", "source": "web"|"filmmakers"}
-- Limits: 10 signups per client IP per day (sha256 of cf-connecting-ip, pruned after 2 days
-- by the haukley-ip-hash-cleanup cron). Email length/format and source are checked by the
-- table's constraints. An address already on the list returns success, so the form never
-- reveals who signed up.

create table if not exists public.waitlist_rate_buckets (
  ip_hash text not null,
  day date not null,
  n int not null default 0,
  primary key (ip_hash, day)
);
alter table public.waitlist_rate_buckets enable row level security;
revoke all on public.waitlist_rate_buckets from anon, authenticated;
grant all on public.waitlist_rate_buckets to service_role;

create or replace function public.join_waitlist(jsonb)
returns void
language plpgsql
volatile
security definer
set search_path = pg_catalog, public
as $$
declare
  b jsonb := $1;
  ip text;
  used int;
  v_email text;
begin
  if b is null or jsonb_typeof(b) <> 'object' then
    raise exception 'body must be an object' using errcode = '22023';
  end if;
  v_email := btrim(b ->> 'email');
  if v_email is null or char_length(v_email) > 254 then
    raise exception 'invalid email' using errcode = '22023';
  end if;

  ip := coalesce(nullif(current_setting('request.headers', true)::json ->> 'cf-connecting-ip', ''), 'unknown');
  insert into public.waitlist_rate_buckets as r (ip_hash, day, n)
  values (encode(extensions.digest(ip, 'sha256'), 'hex'), current_date, 1)
  on conflict (ip_hash, day) do update set n = r.n + 1
  returning r.n into used;
  if used > 10 then
    raise exception 'rate limit exceeded' using errcode = 'P0001', hint = '429';
  end if;

  begin
    insert into public.waitlist (email, source)
    values (v_email, coalesce(nullif(b ->> 'source', ''), 'web'));
  exception
    when unique_violation then null;  -- already on the list: same answer as a new signup
    when check_violation or not_null_violation then
      raise exception 'invalid signup' using errcode = '22023';
  end;
end;
$$;
revoke all on function public.join_waitlist(jsonb) from public, anon, authenticated;
grant execute on function public.join_waitlist(jsonb) to anon, service_role;

-- Close the direct path.
drop policy if exists "site adds signups" on public.waitlist;
revoke insert on public.waitlist from anon;

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
  delete from public.waitlist_rate_buckets where day < current_date - 2;
  $$
);

notify pgrst, 'reload schema';
