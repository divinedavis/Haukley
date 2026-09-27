-- The LG (webOS) and Samsung (Tizen) TV apps log ad events as platforms 'lg' and 'samsung'.
alter table public.ad_events drop constraint ad_events_platform_check;
alter table public.ad_events add constraint ad_events_platform_check
  check (platform in ('firetv', 'androidtv', 'tvos', 'roku', 'ios', 'web', 'lg', 'samsung'));
