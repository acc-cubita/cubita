import { useEffect, useRef, useState } from 'react'
import { Pressable, StyleSheet, View } from 'react-native'
import { CameraView, useCameraPermissions, type BarcodeType } from 'expo-camera'
import { Ionicons } from '@expo/vector-icons'

import { AppText, Button, Center, TextField } from '../ui'
import { colors, radius, spacing } from '../theme'
import { createScanGate } from './gate'
import { toLatinDigits } from '../lib/format'

/**
 * اسکنرِ بارکد — دوربینِ تمام‌صفحه با ورودیِ دستیِ همیشه‌حاضر.
 *
 * **چرا ورودیِ دستی همیشه هست و نه فقط وقتی دوربین رد شد:** برچسبِ پاره،
 * جعبه‌ی زیرِ نور مستقیم، یا بارکدِ چاپ‌شده‌ی بد در انبار عادی است. اسکنری که
 * راهِ دومی نداشته باشد، انباردار را وسطِ کار بن‌بست می‌کند.
 *
 * انواعِ بارکد عمداً محدود است: `qr` و `datamatrix` و `pdf417` در انبارِ کالای
 * خرده‌فروشی تقریباً هرگز روی کالا نیستند، ولی روی هر برچسبِ پستی و کارتِ ویزیت
 * هستند — بازکردنشان یعنی اسکنِ تصادفیِ چیزی که کالا نیست.
 */
const BARCODE_TYPES: BarcodeType[] = ['ean13', 'ean8', 'upc_a', 'upc_e', 'code128', 'code39', 'code93', 'itf14']

export function BarcodeScanner({
  onScan,
  hint,
  paused = false,
}: {
  onScan: (code: string) => void
  /** یک خط راهنما زیرِ کادر — مثلاً آخرین چیزی که اسکن شد. */
  hint?: string
  /** وقتی نتیجه‌ی اسکنِ قبلی روی صفحه باز است، دوربین نباید بشمارد. */
  paused?: boolean
}) {
  const [permission, requestPermission] = useCameraPermissions()
  const [torch, setTorch] = useState(false)
  const [manual, setManual] = useState('')
  const gate = useRef(createScanGate()).current

  // یک‌بار خودش اجازه می‌خواهد؛ کاربر نباید دنبالِ دکمه بگردد.
  useEffect(() => {
    if (permission && !permission.granted && permission.canAskAgain) void requestPermission()
  }, [permission, requestPermission])

  const submitManual = () => {
    const code = toLatinDigits(manual).trim()
    if (!code) return
    setManual('')
    gate.reset() // ورودیِ دستی خواستِ صریحِ کاربر است؛ مهلتِ ضدِتکرار نباید جلویش را بگیرد.
    onScan(code)
  }

  const camera =
    permission?.granted ? (
      <View style={styles.cameraWrap}>
        <CameraView
          style={StyleSheet.absoluteFill}
          facing="back"
          enableTorch={torch}
          barcodeScannerSettings={{ barcodeTypes: BARCODE_TYPES }}
          onBarcodeScanned={
            paused
              ? undefined
              : ({ data }) => {
                  if (gate.accept(data)) onScan(data)
                }
          }
        />
        <View style={styles.reticle} pointerEvents="none" />
        <Pressable
          onPress={() => setTorch((t) => !t)}
          android_ripple={{ color: colors.surfaceAlt, borderless: true }}
          style={styles.torch}
        >
          <Ionicons name={torch ? 'flashlight' : 'flashlight-outline'} size={22} color={torch ? colors.accent : '#fff'} />
        </Pressable>
      </View>
    ) : (
      <Center>
        <Ionicons name="camera-outline" size={40} color={colors.textFaint} />
        <AppText variant="body" color={colors.textMuted} style={styles.centerText}>
          {permission?.canAskAgain === false
            ? 'دسترسی به دوربین رد شده است. از تنظیماتِ اندروید می‌توانید دوباره اجازه بدهید — یا همین‌جا بارکد را دستی وارد کنید.'
            : 'برای اسکن به دوربین نیاز است.'}
        </AppText>
        {permission?.canAskAgain !== false ? (
          <Button label="اجازه‌ی دوربین" onPress={() => void requestPermission()} variant="ghost" />
        ) : null}
      </Center>
    )

  return (
    <View style={styles.screen}>
      {camera}
      <View style={styles.panel}>
        {hint ? (
          <AppText variant="caption" color={colors.textMuted} numberOfLines={2}>
            {hint}
          </AppText>
        ) : null}
        <View style={styles.manualRow}>
          <View style={{ flex: 1 }}>
            <TextField
              placeholder="یا بارکد را دستی وارد کنید…"
              value={manual}
              onChangeText={setManual}
              keyboardType="numeric"
              onSubmitEditing={submitManual}
              returnKeyType="search"
            />
          </View>
          <Pressable
            onPress={submitManual}
            disabled={!manual.trim()}
            android_ripple={{ color: colors.surfaceAlt }}
            style={[styles.manualBtn, !manual.trim() && { opacity: 0.4 }]}
          >
            <Ionicons name="arrow-back" size={20} color={colors.onAccent} />
          </Pressable>
        </View>
      </View>
    </View>
  )
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: colors.bg },
  cameraWrap: { flex: 1, backgroundColor: '#000' },
  reticle: {
    position: 'absolute',
    left: '12%',
    right: '12%',
    top: '30%',
    height: '25%',
    borderWidth: 2,
    borderColor: colors.accent,
    borderRadius: radius.md,
  },
  torch: {
    position: 'absolute',
    top: spacing.lg,
    left: spacing.lg,
    width: 44,
    height: 44,
    borderRadius: radius.pill,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: 'rgba(0,0,0,0.45)',
  },
  centerText: { textAlign: 'center' },
  panel: {
    gap: spacing.sm,
    padding: spacing.lg,
    backgroundColor: colors.surface,
    borderTopWidth: 1,
    borderTopColor: colors.border,
  },
  manualRow: { flexDirection: 'row', alignItems: 'flex-end', gap: spacing.sm },
  manualBtn: {
    width: 52,
    height: 52,
    borderRadius: radius.md,
    backgroundColor: colors.accent,
    alignItems: 'center',
    justifyContent: 'center',
  },
})
