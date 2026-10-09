import type { ImageSourcePropType } from 'react-native';

export type Title = {
  /** 'live': a 24/7 channel (live HLS: no runtime, resume point, ads or episodes). */
  kind: 'movie' | 'show' | 'live';
  id: string;
  title: string;
  genre: string;
  year: number;
  rating: string;
  tagline: string;
  description: string;
  credits: string;
  /** Rights line: public domain, or the Creative Commons attribution the license requires. */
  license?: string;
  /** Viewer content advisory (e.g. "Depicts a lynching"), shown on the title page and at play start. */
  advisory?: string;
  runtime?: string | null;
  seasons?: number;
  poster: ImageSourcePropType;
  card: ImageSourcePropType;
  backdrop: ImageSourcePropType;
  stills?: ImageSourcePropType[];
  /** Real series carry their own episode list (with streams); placeholders don't. */
  episodes?: (Episode & { stream: string })[];
};

export type Episode = {
  number: number;
  name: string;
  minutes: number;
  summary: string;
};

export type Route =
  | { name: 'home' }
  | { name: 'detail'; id: string }
  | { name: 'player'; id: string; episode?: number; startAt?: number };
