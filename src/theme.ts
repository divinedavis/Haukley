import { Dimensions } from 'react-native';

// Layout is designed on a 1920x1080 canvas (tvOS points). Android TV reports
// 960x540 dp on a 1080p panel, so every size goes through s().
const { width } = Dimensions.get('window');
const factor = width / 1920;

export const s = (n: number) => Math.round(n * factor * 100) / 100;

export const colors = {
  bg: '#000000',
  text: '#FFFFFF',
  accent: '#8B6CFF',
  /** The red LIVE tag (same red as the channel's on-air tag and the tile art). */
  live: '#E63946',
  textDim: 'rgba(255,255,255,0.62)',
  textFaint: 'rgba(255,255,255,0.4)',
  pill: 'rgba(255,255,255,0.16)',
  pillFocused: '#FFFFFF',
  onPillFocused: '#000000',
  progressTrack: 'rgba(255,255,255,0.3)',
};

// Apple TV side margin and row rhythm.
export const layout = {
  gutter: s(90),
  rowGap: s(36),
  posterW: s(260),
  posterH: s(390),
  cardW: s(548),
  cardH: s(308),
};
