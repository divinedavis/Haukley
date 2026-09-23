module.exports = {
  preset: 'react-native',
  // The tvOS fork ships untranspiled Flow in @react-native-tvos/virtualized-lists.
  transformIgnorePatterns: [
    'node_modules/(?!((jest-)?react-native|@react-native(-community)?|@react-native-tvos)/)',
  ],
  // Title art is @2x-only, which Jest's resolver can't find; stub all images.
  moduleNameMapper: {
    '\\.(jpg|png)$': '<rootDir>/__mocks__/fileMock.js',
  },
};
