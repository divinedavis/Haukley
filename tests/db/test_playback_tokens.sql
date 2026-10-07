-- Live-DB test for 0014 (signed playback tokens). Runs as one DO block that raises
-- 'ALL_PASS' at the end, so every row it wrote is rolled back. Run: tests/db/run_db_tests.py
do $test$
declare
  t text := (select id from public.titles order by id limit 1);
  r jsonb;
  r2 jsonb;
  s uuid;
  tok text;
  c int;
begin
  perform set_config('request.headers', '{"cf-connecting-ip":"198.51.100.77"}', true);

  -- start_playback hands out a server-chosen session and a signed token
  r := public.start_playback(jsonb_build_object('title_id', t, 'episode', 0, 'platform', 'web'));
  s := (r ->> 'session_id')::uuid;
  tok := r ->> 'token';
  assert tok ~ '^[0-9]{10}\.[0-9a-f]{64}$', 'token shape: ' || coalesce(tok, 'null');

  -- unknown title / platform are refused
  begin
    perform public.start_playback('{"title_id":"no-such-title","platform":"web"}');
    assert false, 'unknown title accepted';
  exception when sqlstate '22023' then null;
  end;
  begin
    perform public.start_playback(jsonb_build_object('title_id', t, 'platform', 'pc'));
    assert false, 'unknown platform accepted';
  exception when sqlstate '22023' then null;
  end;

  -- a valid token + seq is counted
  perform public.log_ad_events(jsonb_build_object('title_id', t, 'episode', 0, 'platform', 'web',
    'event', 'ad_started', 'session_id', s, 'token', tok, 'seq', 1));
  select count(*) into c from public.ad_events where session_id = s and verified;
  assert c = 1, 'valid event not verified: ' || c;

  -- a retry of the same seq is dropped entirely
  perform public.log_ad_events(jsonb_build_object('title_id', t, 'episode', 0, 'platform', 'web',
    'event', 'ad_started', 'session_id', s, 'token', tok, 'seq', 1));
  select count(*) into c from public.ad_events where session_id = s;
  assert c = 1, 'retry was stored: ' || c;

  -- token for another title/episode/platform does not verify (stored, not counted)
  perform public.log_ad_events(jsonb_build_object('title_id', t, 'episode', 3, 'platform', 'web',
    'event', 'ad_completed', 'session_id', s, 'token', tok, 'seq', 2));
  perform public.log_ad_events(jsonb_build_object('title_id', t, 'episode', 0, 'platform', 'roku',
    'event', 'ad_completed', 'session_id', s, 'token', tok, 'seq', 3));
  select count(*) into c from public.ad_events where session_id = s and not verified;
  assert c = 2, 'mismatched token rows: ' || c;

  -- tampered signature does not verify
  perform public.log_ad_events(jsonb_build_object('title_id', t, 'episode', 0, 'platform', 'web',
    'event', 'ad_completed', 'session_id', gen_random_uuid(),
    'token', split_part(tok, '.', 1) || '.' || repeat('0', 64), 'seq', 1));
  assert not (select verified from public.ad_events order by id desc limit 1), 'forged token verified';

  -- old clients (no token): accepted, never counted
  perform public.log_ad_events(jsonb_build_array(
    jsonb_build_object('title_id', t, 'platform', 'roku', 'event', 'ad_started', 'session_id', gen_random_uuid()),
    jsonb_build_object('title_id', t, 'platform', 'roku', 'event', 'ad_completed', 'session_id', gen_random_uuid())));
  assert (select count(*) from public.ad_events where not verified and platform = 'roku' and created_at = now()) = 3,
    'tokenless batch not stored unverified';

  -- plausibility: at t=0 only 2 counted events of one type per session (a Roku batch of 3 -> 2 + 1)
  r2 := public.start_playback(jsonb_build_object('title_id', t, 'episode', 0, 'platform', 'roku'));
  perform public.log_ad_events(jsonb_build_array(
    jsonb_build_object('title_id', t, 'platform', 'roku', 'event', 'ad_completed', 'session_id', r2->>'session_id', 'token', r2->>'token', 'seq', 1),
    jsonb_build_object('title_id', t, 'platform', 'roku', 'event', 'ad_completed', 'session_id', r2->>'session_id', 'token', r2->>'token', 'seq', 2),
    jsonb_build_object('title_id', t, 'platform', 'roku', 'event', 'ad_completed', 'session_id', r2->>'session_id', 'token', r2->>'token', 'seq', 3)));
  select count(*) filter (where verified) into c from public.ad_events where session_id = (r2->>'session_id')::uuid;
  assert c = 2, 'plausibility cap: ' || c;

  -- per-IP-per-title daily cap: 150 counted events
  perform set_config('request.headers', '{"cf-connecting-ip":"198.51.100.78"}', true);
  insert into public.ad_title_buckets (ip_hash, title_id, day, n)
  values (encode(extensions.digest('198.51.100.78', 'sha256'), 'hex'), t, current_date, 150);
  r2 := public.start_playback(jsonb_build_object('title_id', t, 'episode', 0, 'platform', 'web'));
  perform public.log_ad_events(jsonb_build_object('title_id', t, 'platform', 'web', 'event', 'ad_started',
    'session_id', r2->>'session_id', 'token', r2->>'token', 'seq', 1));
  assert not (select verified from public.ad_events order by id desc limit 1), 'title cap not enforced';

  -- payouts read verified rows only
  select coalesce(sum(ads_completed), 0) into c from public.monthly_ad_counts
   where title_id = t and month = date_trunc('month', now())::date and platform = 'roku';
  assert c = (select count(*) from public.ad_events where verified and title_id = t and platform = 'roku'
              and event = 'ad_completed' and created_at >= date_trunc('month', now())), 'view counts unverified';

  -- the HMAC key is unreachable from API roles
  assert not has_schema_privilege('anon', 'private', 'USAGE'), 'anon can use private schema';
  assert not has_table_privilege('anon', 'private.playback_keys', 'SELECT'), 'anon can read key';
  assert has_function_privilege('anon', 'public.start_playback(jsonb)', 'EXECUTE'), 'anon cannot start';
  assert not has_function_privilege('authenticated', 'public.start_playback(jsonb)', 'EXECUTE'), 'authenticated can start';

  -- start_playback rate limit: 120 per IP per hour
  perform set_config('request.headers', '{"cf-connecting-ip":"198.51.100.79"}', true);
  insert into public.playback_rate_buckets (ip_hash, window_start, n)
  values (encode(extensions.digest('198.51.100.79', 'sha256'), 'hex'), date_trunc('hour', now()), 120);
  begin
    perform public.start_playback(jsonb_build_object('title_id', t, 'platform', 'web'));
    assert false, 'start_playback not rate limited';
  exception when sqlstate 'P0001' then null;
  end;

  raise exception 'ALL_PASS';
end
$test$;
