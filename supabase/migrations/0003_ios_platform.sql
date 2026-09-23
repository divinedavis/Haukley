-- The iPhone app logs ad events as platform 'ios'.
alter table public.ad_events drop constraint ad_events_platform_check;
alter table public.ad_events add constraint ad_events_platform_check
  check (platform in ('firetv', 'androidtv', 'tvos', 'roku', 'ios'));
