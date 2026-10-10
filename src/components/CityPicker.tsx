import React, { useEffect, useState } from 'react';
import { ActivityIndicator, BackHandler, ScrollView, StyleSheet, Text, TextInput, View } from 'react-native';
import { colors, layout, s } from '../theme';
import { AUTO, errorText, fetchCities, isZip, type City, type Place, type WeatherError } from '../weather';
import { Button } from './Button';

type Props = { current: Place | null; onPick: (p: Place) => void; onClose: () => void };

// Full-screen city chooser for the Haukley Weather page (a full screen, not an overlay, so
// remote focus can't wander to the page behind it). Back closes it.
export function CityPicker({ current, onPick, onClose }: Props) {
  const [cities, setCities] = useState<City[] | null>(null);
  const [error, setError] = useState<WeatherError | null>(null);
  const [zip, setZip] = useState(current?.kind === 'zip' ? current.zip : '');
  const [zipBad, setZipBad] = useState(false);
  const [zipFocused, setZipFocused] = useState(false);

  useEffect(() => {
    let alive = true;
    fetchCities().then(r => {
      if (!alive) {
        return;
      }
      if (r.ok) {
        setCities(r.data);
      } else {
        setError(r.error);
        setCities([]);
      }
    });
    return () => {
      alive = false;
    };
  }, []);

  // Registered after App's handler, so it runs first and keeps Back on this screen.
  useEffect(() => {
    const sub = BackHandler.addEventListener('hardwareBackPress', () => {
      onClose();
      return true;
    });
    return () => sub.remove();
  }, [onClose]);

  const submitZip = () => {
    if (isZip(zip)) {
      onPick({ kind: 'zip', zip: zip.trim() });
    } else {
      setZipBad(true);
    }
  };

  return (
    <View style={styles.screen} testID="city-picker">
      <Text style={styles.title}>Choose your weather</Text>
      <Text style={styles.sub}>Haukley guesses your city from your connection. Pick a city or enter a ZIP code to change it.</Text>
      <View style={styles.row}>
        <Button
          label="Use my area (automatic)"
          icon={current?.kind === 'auto' ? '✓' : '⌖'}
          hasTVPreferredFocus
          onPress={() => onPick(AUTO)}
        />
        <TextInput
          testID="zip-input"
          style={[styles.zip, zipFocused && styles.zipFocused]}
          onFocus={() => setZipFocused(true)}
          onBlur={() => setZipFocused(false)}
          value={zip}
          onChangeText={v => {
            setZip(v.replace(/\D/g, '').slice(0, 5));
            setZipBad(false);
          }}
          onSubmitEditing={submitZip}
          keyboardType="number-pad"
          returnKeyType="done"
          maxLength={5}
          placeholder="ZIP code"
          placeholderTextColor={zipFocused ? "rgba(0,0,0,0.45)" : colors.textFaint}
        />
        <Button label="Use ZIP" onPress={submitZip} />
      </View>
      {zipBad ? <Text style={styles.bad}>Enter a 5-digit US ZIP code.</Text> : null}
      <Text style={styles.section}>Cities</Text>
      {cities === null ? (
        <ActivityIndicator color={colors.text} style={{ marginTop: s(30) }} />
      ) : cities.length === 0 ? (
        <Text style={styles.bad}>{errorText(error ?? 'unavailable')}</Text>
      ) : (
        <ScrollView contentContainerStyle={styles.grid} showsVerticalScrollIndicator={false}>
          {cities.map(c => (
            <View key={c.slug} style={styles.cell}>
              <Button
                label={c.name}
                icon={current?.kind === 'city' && current.slug === c.slug ? '✓' : undefined}
                onPress={() => onPick({ kind: 'city', slug: c.slug, name: c.name })}
              />
            </View>
          ))}
        </ScrollView>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  screen: { ...StyleSheet.absoluteFillObject, backgroundColor: '#07060f', paddingHorizontal: layout.gutter, paddingTop: s(110) },
  title: { color: colors.text, fontSize: s(64), fontWeight: '800' },
  sub: { color: colors.textDim, fontSize: s(26), marginTop: s(10), maxWidth: s(1400) },
  row: { flexDirection: 'row', alignItems: 'center', marginTop: s(40) },
  zip: {
    width: s(260),
    height: s(76),
    borderRadius: s(38),
    paddingHorizontal: s(30),
    marginRight: s(20),
    backgroundColor: colors.pill,
    color: colors.text,
    fontSize: s(28),
    fontWeight: '700',
  },
  // TextInput has no built-in TV focus look: match the focused pill (white, dark text).
  zipFocused: { backgroundColor: colors.pillFocused, color: colors.onPillFocused },
  bad: { color: colors.textDim, fontSize: s(24), marginTop: s(16) },
  section: { color: colors.text, fontSize: s(34), fontWeight: '700', marginTop: s(44) },
  grid: { flexDirection: 'row', flexWrap: 'wrap', paddingTop: s(24), paddingBottom: s(120) },
  cell: { marginBottom: s(24) },
});
