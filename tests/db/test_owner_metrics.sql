-- 0017: start_playback logs a play (no IP), every catalog series/batch-3 id is a real title,
-- and owner_metrics returns aggregates only for a key whose SHA-256 is registered.
-- 0018: plays carry an HMAC of the caller address so the owner's own addresses can be left
-- out, internal (owner/test) accounts and unverified ads are excluded from the counts.
do $$
declare
  before int;
  r jsonb;
  ok boolean;
begin
  -- titles that were missing before 0017 now get tickets
  perform public.start_playback('{"title_id":"why-we-fight","episode":1,"platform":"roku"}'::jsonb);
  select count(*) into before from public.playback_starts where title_id = 'go-west' and platform = 'web';
  r := public.start_playback('{"title_id":"go-west","platform":"web"}'::jsonb);
  if r ->> 'token' is null then raise exception 'no token for go-west'; end if;
  if (select count(*) from public.playback_starts where title_id = 'go-west' and platform = 'web') <> before + 1 then
    raise exception 'start_playback did not log the play';
  end if;
  if exists (select 1 from information_schema.columns where table_name = 'playback_starts'
             and column_name ilike '%ip%') then
    raise exception 'playback_starts must not store an IP';
  end if;

  -- wrong key is refused
  ok := false;
  begin
    perform public.owner_metrics('not-a-key', 30);
  exception when insufficient_privilege then ok := true;
  end;
  if not ok then raise exception 'owner_metrics accepted a bad key'; end if;

  -- a registered key gets counts, including the play above
  insert into private.owner_metrics_keys (key_hash) values (extensions.digest('test-key-0017', 'sha256'));
  r := public.owner_metrics('test-key-0017', 1);
  if not exists (select 1 from jsonb_array_elements(r -> 'top_titles') t where t ->> 'title_id' = 'go-west') then
    raise exception 'owner_metrics top_titles missing go-west: %', r -> 'top_titles';
  end if;
  if (r ->> 'accounts') is null or (r -> 'web_watch' ->> 'hours') is null then
    raise exception 'owner_metrics missing fields: %', r;
  end if;
  if r::text ~* '@|ip_hash|addr_hash' then raise exception 'owner_metrics leaked personal data'; end if;
  if (select addr_hash from public.playback_starts where title_id = 'go-west' order by id desc limit 1) is null then
    raise exception 'start_playback did not store the address HMAC';
  end if;

  -- 0018: the caller's address (here 'unknown', no request headers) can be excluded
  r := public.owner_metrics('test-key-0017', 1, array['unknown']);
  if exists (select 1 from jsonb_array_elements(r -> 'top_titles') t where t ->> 'title_id' = 'go-west') then
    raise exception 'excluded address still counted: %', r -> 'top_titles';
  end if;
  if (r ->> 'plays_excluded')::int < 1 then raise exception 'plays_excluded not reported: %', r; end if;
  if (r ->> 'internal_accounts') is null or (r ->> 'ads_unverified') is null then
    raise exception 'owner_metrics missing 0018 fields: %', r;
  end if;
  if (r ->> 'accounts')::int <> (select count(*) from auth.users u where not private.is_internal(u.id)) then
    raise exception 'accounts must leave out internal users';
  end if;

  -- anon can call it, but cannot read the tables behind it
  if not has_function_privilege('anon', 'public.owner_metrics(text, integer, text[])', 'execute') then
    raise exception 'anon cannot execute owner_metrics';
  end if;
  if has_table_privilege('anon', 'public.playback_starts', 'select') then
    raise exception 'anon can read playback_starts';
  end if;
  raise exception 'ALL_PASS';
end $$;
