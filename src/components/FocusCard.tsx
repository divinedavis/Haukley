import React, { useRef, useState } from 'react';
import {
  Animated,
  Image,
  ImageSourcePropType,
  Pressable,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import { colors, s } from '../theme';

type Props = {
  source: ImageSourcePropType;
  width: number;
  height: number;
  onPress: () => void;
  onFocus?: () => void;
  hasTVPreferredFocus?: boolean;
  label?: string;
  sublabel?: string;
  rank?: number;
  progress?: number;
};

// Apple TV style focus: the artwork lifts (scale + shadow), labels brighten.
export function FocusCard({
  source,
  width,
  height,
  onPress,
  onFocus,
  hasTVPreferredFocus,
  label,
  sublabel,
  rank,
  progress,
}: Props) {
  const [focused, setFocused] = useState(false);
  const scale = useRef(new Animated.Value(1)).current;

  const animate = (to: number) =>
    Animated.spring(scale, { toValue: to, friction: 7, tension: 90, useNativeDriver: true }).start();

  return (
    <View style={{ width }}>
      <Pressable
        onPress={onPress}
        hasTVPreferredFocus={hasTVPreferredFocus}
        onFocus={() => {
          setFocused(true);
          animate(1.1);
          onFocus?.();
        }}
        onBlur={() => {
          setFocused(false);
          animate(1);
        }}
      >
        <Animated.View
          style={[
            styles.art,
            { width, height, transform: [{ scale }] },
            focused && styles.artFocused,
          ]}
        >
          <Image source={source} style={styles.image} resizeMethod="resize" resizeMode="cover" />
          {progress !== undefined && (
            <View style={styles.progressWrap}>
              <View style={styles.progressTrack}>
                <View style={[styles.progressFill, { width: `${Math.max(progress, 0.03) * 100}%` }]} />
              </View>
            </View>
          )}
        </Animated.View>
      </Pressable>
      {(label || rank) && (
        <View style={[styles.labels, focused && styles.labelsFocused]}>
          <View style={styles.labelRow}>
            {rank !== undefined && <Text style={styles.rank}>{rank}</Text>}
            <View style={styles.labelText}>
              {label && (
                <Text numberOfLines={1} style={[styles.label, focused && styles.labelFocused]}>
                  {label}
                </Text>
              )}
              {sublabel && (
                <Text numberOfLines={1} style={styles.sublabel}>
                  {sublabel}
                </Text>
              )}
            </View>
          </View>
        </View>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  art: {
    borderRadius: s(12),
    overflow: 'hidden',
    backgroundColor: '#1c1c1e',
  },
  artFocused: {
    shadowColor: '#000',
    shadowOpacity: 0.7,
    shadowRadius: s(24),
    shadowOffset: { width: 0, height: s(18) },
    elevation: 16,
  },
  image: { width: '100%', height: '100%' },
  progressWrap: {
    position: 'absolute',
    left: s(18),
    right: s(18),
    bottom: s(16),
  },
  progressTrack: {
    height: s(6),
    borderRadius: s(3),
    backgroundColor: colors.progressTrack,
    overflow: 'hidden',
  },
  progressFill: { height: '100%', backgroundColor: colors.text },
  labels: { marginTop: s(14), opacity: 0.75 },
  labelsFocused: { marginTop: s(30), opacity: 1 },
  labelRow: { flexDirection: 'row', alignItems: 'center' },
  rank: {
    color: colors.text,
    fontSize: s(44),
    fontWeight: '800',
    marginRight: s(12),
    minWidth: s(28),
  },
  labelText: { flex: 1 },
  label: { color: colors.textDim, fontSize: s(24), fontWeight: '600' },
  labelFocused: { color: colors.text },
  sublabel: { color: colors.textFaint, fontSize: s(20), marginTop: s(2) },
});
