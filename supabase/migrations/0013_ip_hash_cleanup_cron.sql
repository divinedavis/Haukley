-- The hashed-IP rate-limit counters (ad_rate_buckets from 0005, submission_rate_buckets
-- from 0006) were only pruned opportunistically, inside the next log_ad_events /
-- submit_film call. With no ads playing (no-fill VAST) that call may not come for weeks,
-- so a counter could outlive the "deleted after two days" the privacy policy promises.
-- An hourly pg_cron job makes the two-day limit hold regardless of traffic.

create extension if not exists pg_cron;

select cron.unschedule('haukley-ip-hash-cleanup')
 where exists (select 1 from cron.job where jobname = 'haukley-ip-hash-cleanup');
select cron.schedule(
  'haukley-ip-hash-cleanup',
  '17 * * * *',
  $$
  delete from public.ad_rate_buckets where window_start < now() - interval '2 days';
  delete from public.submission_rate_buckets where day < current_date - 2;
  $$
);
