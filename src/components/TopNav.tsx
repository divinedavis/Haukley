import React, { useState } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import { colors, s } from '../theme';

export type Tab = 'home' | 'movies' | 'shows';
const TABS: { key: Tab; label: string }[] = [
  { key: 'home', label: 'Home' },
  { key: 'movies', label: 'Movies' },
  { key: 'shows', label: 'TV Shows' },
];

type Props = { tab: Tab; onChange: (t: Tab) => void; onFocus: () => void };

// Centered pill tab bar that floats over the hero, like the Apple TV app.
export function TopNav({ tab, onChange, onFocus }: Props) {
  return (
    <View style={styles.wrap} pointerEvents="box-none">
      <View style={styles.bar}>
        {TABS.map(t => (
          <NavItem
            key={t.key}
            label={t.label}
            selected={t.key === tab}
            onPress={() => onChange(t.key)}
            onFocus={() => {
              onFocus();
              onChange(t.key);
            }}
          />
        ))}
      </View>
      <Text style={styles.brand}>
        Haukley<Text style={styles.dot}>.</Text>
      </Text>
    </View>
  );
}

function NavItem({ label, selected, onPress, onFocus }: { label: string; selected: boolean; onPress: () => void; onFocus: () => void }) {
  const [focused, setFocused] = useState(false);
  return (
    <Pressable
      onPress={onPress}
      onFocus={() => {
        setFocused(true);
        onFocus();
      }}
      onBlur={() => setFocused(false)}
      style={[styles.item, focused && styles.itemFocused]}
    >
      <Text style={[styles.label, selected && styles.labelSelected, focused && styles.labelFocused]}>{label}</Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  wrap: { position: 'absolute', top: s(40), left: 0, right: 0, alignItems: 'center', zIndex: 10 },
  bar: {
    flexDirection: 'row',
    backgroundColor: 'rgba(30,30,32,0.55)',
    borderRadius: s(40),
    padding: s(6),
  },
  item: { paddingHorizontal: s(30), height: s(60), borderRadius: s(30), justifyContent: 'center' },
  itemFocused: { backgroundColor: colors.pillFocused },
  label: { color: colors.textDim, fontSize: s(26), fontWeight: '600' },
  labelSelected: { color: colors.text },
  labelFocused: { color: colors.onPillFocused },
  dot: { color: colors.accent },
  brand: {
    position: 'absolute',
    left: s(90),
    top: s(14),
    color: colors.text,
    fontSize: s(30),
    fontWeight: '800',
    letterSpacing: -s(0.5),
  },
});
