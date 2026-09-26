-- Filmmaker submissions from haukley.com/filmmakers. The site calls a rate-limited
-- SECURITY DEFINER RPC (POST /rest/v1/rpc/submit_film); nobody but the service role can
-- read or write the table directly.
--
-- Limits: 5 submissions per client IP per day (IP from Cloudflare's cf-connecting-ip, which
-- the client cannot set; only a sha256 of it is stored). Over-limit calls raise P0001.

create table public.film_submissions (
  id bigint generated always as identity primary key,
  created_at timestamptz not null default now(),
  status text not null default 'new' check (status in ('new', 'reviewing', 'accepted', 'declined')),
  name text not null check (char_length(name) between 1 and 120),
  email text not null check (char_length(email) between 6 and 254
                             and email ~* '^[^@\s]+@[^@\s]+\.[^@\s]+$'),
  film_title text not null check (char_length(film_title) between 1 and 200),
  screener_url text not null check (char_length(screener_url) <= 500 and screener_url ~* '^https://'),
  screener_password text check (char_length(screener_password) <= 100),
  format text not null check (format in ('feature', 'documentary', 'series', 'short')),
  genre text check (char_length(genre) <= 60),
  runtime_minutes int check (runtime_minutes between 1 and 1000),
  year int check (year between 1890 and 2100),
  rights_confirmed boolean not null check (rights_confirmed),
  notes text check (char_length(notes) <= 2000),
  ip_hash text not null
);

alter table public.film_submissions enable row level security;
revoke all on public.film_submissions from anon, authenticated;
grant all on public.film_submissions to service_role;

create table public.submission_rate_buckets (
  ip_hash text not null,
  day date not null,
  n int not null default 0,
  primary key (ip_hash, day)
);
alter table public.submission_rate_buckets enable row level security;
revoke all on public.submission_rate_buckets from anon, authenticated;
grant all on public.submission_rate_buckets to service_role;

create function public.submit_film(jsonb)
returns void
language plpgsql
volatile
security definer
set search_path = pg_catalog, public
as $$
declare
  b jsonb := $1;
  ip text;
  h text;
  used int;
begin
  if b is null or jsonb_typeof(b) <> 'object' then
    raise exception 'body must be an object' using errcode = '22023';
  end if;

  ip := coalesce(nullif(current_setting('request.headers', true)::json ->> 'cf-connecting-ip', ''), 'unknown');
  h := encode(extensions.digest(ip, 'sha256'), 'hex');
  insert into public.submission_rate_buckets as r (ip_hash, day, n)
  values (h, current_date, 1)
  on conflict (ip_hash, day) do update set n = r.n + 1
  returning r.n into used;
  if used > 5 then
    raise exception 'rate limit exceeded' using errcode = 'P0001', hint = '429';
  end if;

  delete from public.submission_rate_buckets where day < current_date - 2;

  -- Column checks validate every field; status, created_at and ip_hash are server-set.
  begin
    insert into public.film_submissions
      (name, email, film_title, screener_url, screener_password, format, genre,
       runtime_minutes, year, rights_confirmed, notes, ip_hash)
    values (
      btrim(b ->> 'name'), btrim(b ->> 'email'), btrim(b ->> 'film_title'),
      btrim(b ->> 'screener_url'), nullif(btrim(b ->> 'screener_password'), ''),
      b ->> 'format', nullif(btrim(b ->> 'genre'), ''),
      nullif(b ->> 'runtime_minutes', '')::int, nullif(b ->> 'year', '')::int,
      coalesce((b ->> 'rights_confirmed')::boolean, false),
      nullif(btrim(b ->> 'notes'), ''), h);
  exception
    -- Don't echo the failing row (it includes ip_hash) back to the caller.
    when check_violation or not_null_violation or invalid_text_representation
         or numeric_value_out_of_range or datatype_mismatch then
      raise exception 'invalid submission' using errcode = '22023';
  end;
end;
$$;

revoke all on function public.submit_film(jsonb) from public, anon, authenticated;
grant execute on function public.submit_film(jsonb) to anon, service_role;

notify pgrst, 'reload schema';
