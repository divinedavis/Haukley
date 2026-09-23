-- Per-title ad tracking for the filmmaker revenue split.
-- Apps may only INSERT ad events; reads and payout math are service_role only.
-- The ad server's own revenue report (keyed by title_id) is the source of truth for
-- payouts; these counts are the cross-check and cover Roku's split inventory.

create table public.titles (
  id text primary key,
  kind text not null check (kind in ('movie', 'show')),
  title text not null,
  rev_share numeric(4, 3) not null default 0.500 check (rev_share between 0 and 1)
);

create table public.ad_events (
  id bigint generated always as identity primary key,
  created_at timestamptz not null default now(),
  title_id text not null references public.titles (id),
  episode smallint not null default 0 check (episode between 0 and 999),
  platform text not null check (platform in ('firetv', 'androidtv', 'tvos', 'roku')),
  event text not null check (event in ('ad_started', 'ad_completed')),
  ad_id text check (char_length(ad_id) <= 200),
  session_id uuid not null
);
create index ad_events_title_month on public.ad_events (title_id, created_at);

alter table public.titles enable row level security;
alter table public.ad_events enable row level security;

-- Supabase's default privileges hand anon/authenticated full DML on new tables; strip them.
revoke all on public.titles from anon, authenticated;
revoke all on public.ad_events from anon, authenticated;
grant all on public.titles to service_role;
grant all on public.ad_events to service_role;

grant insert on public.ad_events to anon;
create policy "apps log ad events" on public.ad_events
  for insert to anon with check (created_at > now() - interval '1 minute');

-- Monthly counts per title and platform.
create view public.monthly_ad_counts with (security_invoker = true) as
select date_trunc('month', e.created_at)::date as month,
       e.title_id,
       t.title,
       e.platform,
       count(*) filter (where e.event = 'ad_started') as ads_started,
       count(*) filter (where e.event = 'ad_completed') as ads_completed,
       count(distinct e.session_id) as viewing_sessions
from public.ad_events e
join public.titles t on t.id = e.title_id
group by 1, 2, 3, 4;

revoke all on public.monthly_ad_counts from anon, authenticated;
grant select on public.monthly_ad_counts to service_role;

-- Estimated filmmaker payout for a month at an assumed net CPM (dollars per 1,000 ads).
-- Replace with actual ad-server revenue per title once the ad account is live.
create function public.estimated_payouts(p_month date, p_net_cpm numeric)
returns table (title_id text, title text, ads bigint, gross numeric, filmmaker_share numeric)
language sql stable security invoker set search_path = public as $$
  select c.title_id, c.title, sum(c.ads_completed)::bigint,
         round(sum(c.ads_completed) * p_net_cpm / 1000, 2),
         round(sum(c.ads_completed) * p_net_cpm / 1000 * t.rev_share, 2)
  from public.monthly_ad_counts c
  join public.titles t on t.id = c.title_id
  where c.month = date_trunc('month', p_month)::date
  group by c.title_id, c.title, t.rev_share
  order by 5 desc;
$$;
revoke execute on function public.estimated_payouts(date, numeric) from public, anon, authenticated;
grant execute on function public.estimated_payouts(date, numeric) to service_role;
