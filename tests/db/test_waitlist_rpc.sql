-- 0016: waitlist signups only through the rate-limited join_waitlist RPC. Rolls back via ALL_PASS.
do $test$
declare c int;
begin
  perform set_config('request.headers', '{"cf-connecting-ip":"198.51.100.90"}', true);
  perform public.join_waitlist('{"email":"wl-probe@example.com","source":"web"}');
  perform public.join_waitlist('{"email":"WL-probe@example.com","source":"web"}');  -- duplicate: silent
  select count(*) into c from public.waitlist where lower(email) = 'wl-probe@example.com';
  assert c = 1, 'signup/duplicate: ' || c;

  begin perform public.join_waitlist('{"email":"not-an-email"}'); assert false, 'bad email accepted';
  exception when sqlstate '22023' then null; end;
  begin perform public.join_waitlist(jsonb_build_object('email', repeat('a', 250) || '@x.com')); assert false, 'long email accepted';
  exception when sqlstate '22023' then null; end;
  begin perform public.join_waitlist('{"email":"wl2@example.com","source":"spam"}'); assert false, 'bad source accepted';
  exception when sqlstate '22023' then null; end;

  -- 10 per IP per day (2 used above; refused calls roll back their count, as in PostgREST)
  for i in 1..8 loop perform public.join_waitlist(jsonb_build_object('email', 'wl-n' || i || '@example.com')); end loop;
  begin perform public.join_waitlist('{"email":"wl-over@example.com"}'); assert false, 'rate limit missing';
  exception when sqlstate 'P0001' then null; end;

  assert not has_table_privilege('anon', 'public.waitlist', 'INSERT'), 'anon can still insert directly';
  assert has_function_privilege('anon', 'public.join_waitlist(jsonb)', 'EXECUTE'), 'anon cannot join';
  raise exception 'ALL_PASS';
end
$test$;
