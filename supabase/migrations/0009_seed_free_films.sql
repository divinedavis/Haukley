-- The real launch library (public-domain / CC-BY films). Generated from scripts/catalog.json.
-- ad_events.title_id references titles, so every playable title needs a row here.
insert into public.titles (id, kind, title) values
  ('the-general', 'movie', 'The General'),
  ('sherlock-jr', 'movie', 'Sherlock Jr.'),
  ('safety-last', 'movie', 'Safety Last!'),
  ('the-freshman', 'movie', 'The Freshman'),
  ('one-week', 'movie', 'One Week'),
  ('his-girl-friday', 'movie', 'His Girl Friday'),
  ('nosferatu', 'movie', 'Nosferatu'),
  ('phantom-of-the-opera', 'movie', 'The Phantom of the Opera'),
  ('night-of-the-living-dead', 'movie', 'Night of the Living Dead'),
  ('the-little-shop-of-horrors', 'movie', 'The Little Shop of Horrors'),
  ('carnival-of-souls', 'movie', 'Carnival of Souls'),
  ('metropolis', 'movie', 'Metropolis'),
  ('a-trip-to-the-moon', 'movie', 'A Trip to the Moon'),
  ('all-quiet-on-the-western-front', 'movie', 'All Quiet on the Western Front'),
  ('d-o-a', 'movie', 'D.O.A.'),
  ('man-with-a-movie-camera', 'movie', 'Man with a Movie Camera'),
  ('big-buck-bunny', 'movie', 'Big Buck Bunny'),
  ('sintel', 'movie', 'Sintel'),
  ('tears-of-steel', 'movie', 'Tears of Steel'),
  ('elephants-dream', 'movie', 'Elephants Dream'),
  ('cosmos-laundromat', 'movie', 'Cosmos Laundromat'),
  ('spring', 'movie', 'Spring'),
  ('sprite-fright', 'movie', 'Sprite Fright'),
  ('charge', 'movie', 'Charge')
on conflict (id) do update set title = excluded.title;
