import React from 'react';
import { FlatList, StyleSheet, Text, View } from 'react-native';
import type { Row } from '../catalog';
import { colors, layout, s } from '../theme';
import { FocusCard } from './FocusCard';

type Props = {
  row: Row;
  onSelect: (id: string, episode?: number) => void;
  onFocusRow?: () => void;
};

// One horizontal shelf of artwork with its heading, Apple TV style.
export function Shelf({ row, onSelect, onFocusRow }: Props) {
  const landscape = row.type === 'card' || row.type === 'upNext';
  const w = landscape ? layout.cardW : layout.posterW;
  const h = landscape ? layout.cardH : layout.posterH;

  return (
    <View style={styles.row}>
      <Text style={styles.heading}>{row.title}</Text>
      <FlatList
        horizontal
        data={row.items as any[]}
        keyExtractor={(item: any, i) => `${row.key}-${item.id ?? item.title.id}-${i}`}
        showsHorizontalScrollIndicator={false}
        removeClippedSubviews={false}
        style={styles.list}
        contentContainerStyle={styles.content}
        ItemSeparatorComponent={Gap}
        renderItem={({ item, index }) => {
          if (row.type === 'upNext') {
            return (
              <FocusCard
                source={item.title.card}
                width={w}
                height={h}
                progress={item.progress}
                label={item.title.title}
                sublabel={item.label}
                onFocus={onFocusRow}
                onPress={() => onSelect(item.title.id, item.episode)}
              />
            );
          }
          return (
            <FocusCard
              source={landscape ? item.card : item.poster}
              width={w}
              height={h}
              rank={row.type === 'ranked' ? index + 1 : undefined}
              label={row.type === 'ranked' || landscape ? item.title : undefined}
              sublabel={landscape ? `${item.genre} · ${item.year}` : row.type === 'ranked' ? item.genre : undefined}
              onFocus={onFocusRow}
              onPress={() => onSelect(item.id)}
            />
          );
        }}
      />
    </View>
  );
}

const Gap = () => <View style={{ width: s(40) }} />;

const styles = StyleSheet.create({
  row: { marginBottom: layout.rowGap },
  heading: {
    color: colors.text,
    fontSize: s(34),
    fontWeight: '700',
    marginLeft: layout.gutter,
    marginBottom: s(4),
  },
  list: { overflow: 'visible' },
  content: {
    paddingHorizontal: layout.gutter,
    paddingTop: s(28),
    paddingBottom: s(20),
  },
});
