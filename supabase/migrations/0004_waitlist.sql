-- "Get notified at launch" signups from haukley.com. The site may only insert; reading the
-- list needs the service role. Duplicates are rejected by the unique index (the page treats
-- that as success, so it never reveals whether an address is already on the list).
create table public.waitlist (
  id bigint generated always as identity primary key,
  created_at timestamptz not null default now(),
  email text not null check (char_length(email) between 6 and 254
                             and email ~* '^[^@\s]+@[^@\s]+\.[^@\s]+$'),
  source text not null default 'web' check (source in ('web', 'filmmakers'))
);
create unique index waitlist_email_unique on public.waitlist (lower(email));

alter table public.waitlist enable row level security;
revoke all on public.waitlist from anon, authenticated;
grant all on public.waitlist to service_role;
grant insert on public.waitlist to anon;
create policy "site adds signups" on public.waitlist
  for insert to anon with check (created_at > now() - interval '1 minute');
