-- 0015: an OAuth identity may not be attached to a user who has an email/password identity.
-- Raises ALL_PASS at the end so the fake users are rolled back.
do $test$
declare
  pw uuid := gen_random_uuid();
  g uuid := gen_random_uuid();
begin
  insert into auth.users (id, instance_id, aud, role, email, created_at, updated_at)
  values (pw, '00000000-0000-0000-0000-000000000000', 'authenticated', 'authenticated', 'guard-pw@example.invalid', now(), now()),
         (g,  '00000000-0000-0000-0000-000000000000', 'authenticated', 'authenticated', 'guard-g@example.invalid', now(), now());
  insert into auth.identities (provider_id, user_id, identity_data, provider, created_at, updated_at)
  values (pw::text, pw, jsonb_build_object('sub', pw::text, 'email', 'guard-pw@example.invalid'), 'email', now(), now());

  -- Google onto the password account: refused
  begin
    insert into auth.identities (provider_id, user_id, identity_data, provider, created_at, updated_at)
    values ('google-sub-1', pw, '{"sub":"google-sub-1","email":"guard-pw@example.invalid","email_verified":true}', 'google', now(), now());
    assert false, 'google identity linked onto a password account';
  exception when insufficient_privilege then null;
  end;

  -- a brand-new Google user: allowed
  insert into auth.identities (provider_id, user_id, identity_data, provider, created_at, updated_at)
  values ('google-sub-2', g, '{"sub":"google-sub-2","email":"guard-g@example.invalid","email_verified":true}', 'google', now(), now());
  assert (select count(*) from auth.identities where user_id = g) = 1, 'new google user blocked';

  raise exception 'ALL_PASS';
end
$test$;
