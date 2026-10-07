-- Pre-account-takeover guard for when Google (or any OAuth) sign-in is switched on.
--
-- Sign-up is autoconfirmed (no email verification, by owner rule), so anyone can register a
-- password account under someone else's address. When that person later clicks "Continue
-- with Google", GoTrue auto-links the Google identity onto the existing account because the
-- emails match and Google verified its one - and the squatter still holds the password.
-- Hosted Supabase has no switch to turn automatic linking off, so this refuses it in the DB:
-- a non-email identity may not be added to a user that already has an email/password
-- identity. GoTrue rolls the sign-in back and redirects with error=server_error; the /watch
-- page tells the viewer to sign in with their password (or reset it) instead.
-- Brand-new OAuth users (no email identity) are unaffected. Manual linking
-- (security_manual_linking_enabled) stays OFF; if it is ever turned on, this trigger blocks
-- it too, which is the safe default.

create schema if not exists private;
revoke all on schema private from public, anon, authenticated;

create or replace function private.block_oauth_autolink()
returns trigger
language plpgsql
security definer
set search_path = pg_catalog
as $$
begin
  if new.provider <> 'email'
     and exists (select 1 from auth.identities i
                 where i.user_id = new.user_id and i.provider = 'email') then
    raise exception 'oauth identity cannot be linked to a password account'
      using errcode = '42501',
            hint = 'Sign in with email and password (or reset it) instead.';
  end if;
  return new;
end;
$$;
revoke all on function private.block_oauth_autolink() from public, anon, authenticated;

drop trigger if exists haukley_block_oauth_autolink on auth.identities;
create trigger haukley_block_oauth_autolink
  before insert on auth.identities
  for each row execute function private.block_oauth_autolink();
