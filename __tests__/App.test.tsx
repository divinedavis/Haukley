/**
 * @format
 */

import React from 'react';
import ReactTestRenderer from 'react-test-renderer';
import App from '../App';
import { FEATURED, ROWS, TITLES, UP_NEXT, getTitle, streamFor } from '../src/catalog';

jest.useFakeTimers();

test('renders correctly', async () => {
  await ReactTestRenderer.act(() => {
    ReactTestRenderer.create(<App />);
  });
});

test('every row and featured item points at a real title', () => {
  const rowItems = Object.values(ROWS).flatMap(rows =>
    rows.flatMap(r => (r.type === 'upNext' ? r.items.map(i => i.title) : r.items)),
  );
  for (const t of [...FEATURED, ...UP_NEXT.map(u => u.title), ...rowItems]) {
    expect(getTitle(t.id)).toBe(t);
  }
});

test('titles are unique and shows have episode stills', () => {
  expect(new Set(TITLES.map(t => t.id)).size).toBe(TITLES.length);
  for (const t of TITLES.filter(x => x.kind === 'show')) {
    expect(t.stills).toHaveLength(8);
  }
});

test('streams are HTTPS', () => {
  for (const t of TITLES) {
    expect(streamFor(t.id)).toMatch(/^https:\/\//);
  }
});
