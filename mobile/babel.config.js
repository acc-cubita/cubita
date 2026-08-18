module.exports = function (api) {
  api.cache(true)
  return {
    presets: ['babel-preset-expo'],
    // Reanimated 4 پلاگینِ worklets را می‌خواهد و باید آخرین پلاگین باشد.
    plugins: ['react-native-worklets/plugin'],
  }
}
