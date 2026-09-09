import { useMemo, useState } from 'react'
import { Modal, Pressable, ScrollView, StyleSheet, View } from 'react-native'
import { Ionicons } from '@expo/vector-icons'

import type { MpOrder } from '../../api/types'
import { cashAmountFor, cashPercentFor, settlesOnDelivery } from '../../market/cod'
import { AppText, Button, TextField } from '../../ui'
import { colors, faMoney, radius, spacing } from '../../theme'
import { normalizeInt, toFaDigits } from '../../lib/format'

/**
 * ثبتِ تحویل توسطِ مأمورِ حمل.
 *
 * **چرا مبلغ می‌پرسد و نه درصد:** بک‌اند `cash_percent` می‌گیرد، ولی کسی که سرِ
 * درِ مغازه ایستاده مبلغ در دستش است. واداشتنش به محاسبه‌ی ذهنیِ درصد یعنی
 * دعوت به خطا — و خطا اینجا سندِ خزانه‌ی غلط در **دو** کسب‌وکار است. تبدیل در
 * `market/cod.ts` انجام و رفت‌وبرگشتش تست می‌شود.
 *
 * هر دو عدد همیشه روی صفحه‌اند (نقد و اعتباری) تا چیزی پشتِ یک درصد پنهان نماند.
 *
 * **و گاهی اصلاً مبلغ نمی‌پرسد.** اگر سفارش هنگامِ تأیید سند خورده باشد، بک‌اند
 * سرِ تحویل هیچ پولی جابه‌جا نمی‌کند و مبلغِ واردشده بی‌صدا دور ریخته می‌شود.
 * تشخیصش در `market/cod.ts::settlesOnDelivery` است. نسخه‌ی اولِ همین فرم این را
 * نمی‌دانست و پولی می‌پرسید که هیچ‌جا نمی‌نشست — با تستِ سرتاسری پیدا شد، نه با
 * خواندنِ کد.
 */
export function DeliverSheet({
  order,
  busy,
  onCancel,
  onConfirm,
}: {
  order: MpOrder
  busy: boolean
  onCancel: () => void
  onConfirm: (cashPercent: string) => void
}) {
  const total = Number(order.total)
  const withCash = settlesOnDelivery(order)
  const [raw, setRaw] = useState('')

  const { percent, cash, credit } = useMemo(() => {
    const entered = Number(normalizeInt(raw) || 0)
    const pct = cashPercentFor(entered, total)
    // آنچه نشان می‌دهیم همان چیزی است که بک‌اند خواهد ساخت، نه آنچه کاربر تایپ کرد.
    const c = cashAmountFor(Number(pct), total)
    return { percent: pct, cash: c, credit: total - c }
  }, [raw, total])

  return (
    <Modal visible transparent animationType="slide" onRequestClose={onCancel}>
      <View style={styles.backdrop}>
        <View style={styles.sheet}>
          <ScrollView contentContainerStyle={styles.body} keyboardShouldPersistTaps="handled">
            <View style={styles.head}>
              <Ionicons name="cube-outline" size={22} color={colors.accent} />
              <AppText variant="heading" style={{ flex: 1 }}>
                تحویلِ سفارش #{toFaDigits(order.order_number)}
              </AppText>
              <Pressable
                onPress={onCancel}
                accessibilityRole="button"
                accessibilityLabel="بستن"
                android_ripple={{ color: colors.surfaceAlt, borderless: true }}
              >
                <Ionicons name="close" size={22} color={colors.textMuted} />
              </Pressable>
            </View>

            <AppText variant="caption" color={colors.textMuted}>
              {order.retailer_name} · مبلغِ کل {faMoney(total)} ﷼
            </AppText>

            {withCash ? (
              <>
                <View style={styles.quick}>
                  <Chip label="بدونِ نقد" active={cash === 0} onPress={() => setRaw('')} />
                  <Chip
                    label="نقدِ کامل"
                    active={cash === total && total > 0}
                    onPress={() => setRaw(String(total))}
                  />
                </View>

                <TextField
                  label="مبلغِ نقدِ دریافتی (ریال)"
                  placeholder="۰"
                  value={raw}
                  onChangeText={setRaw}
                  keyboardType="numeric"
                />

                <View style={styles.split}>
                  <Row label="نقد" value={`${faMoney(cash)} ﷼`} tone={colors.success} />
                  <Row label="اعتباری (طلب)" value={`${faMoney(credit)} ﷼`} tone={colors.warning} />
                  <Row label="سهمِ نقد" value={`${toFaDigits(Number(percent).toFixed(1))}٪`} />
                </View>

                <View style={styles.warn}>
                  <AppText variant="caption" color={colors.warning}>
                    با ثبتِ تحویل، کالا به انبارِ فروشگاه وارد و سندِ خرید/فروشِ دو طرف صادر
                    می‌شود. این کار برگشت‌پذیر نیست.
                  </AppText>
                </View>
              </>
            ) : (
              <>
                <View style={styles.split}>
                  <Row
                    label="نقدِ تسویه‌شده هنگامِ تأیید"
                    value={`${faMoney(order.cash_amount)} ﷼`}
                    tone={colors.success}
                  />
                  <Row
                    label="اعتباری (طلب)"
                    value={`${faMoney(total - Number(order.cash_amount))} ﷼`}
                    tone={colors.warning}
                  />
                </View>
                <View style={styles.note}>
                  <AppText variant="caption" color={colors.textMuted}>
                    این سفارش هنگامِ تأیید سند خورده و تسویه‌اش انجام شده است. ثبتِ تحویل فقط
                    رسیدنِ بار را علامت می‌زند و مبلغی جابه‌جا نمی‌کند.
                  </AppText>
                </View>
              </>
            )}

            <Button
              label="ثبتِ تحویل"
              onPress={() => onConfirm(withCash ? percent : '0')}
              loading={busy}
            />
          </ScrollView>
        </View>
      </View>
    </Modal>
  )
}

function Chip({ label, active, onPress }: { label: string; active: boolean; onPress: () => void }) {
  return (
    <Pressable
      onPress={onPress}
      android_ripple={{ color: colors.surfaceAlt }}
      style={[styles.chip, active && { backgroundColor: colors.accent, borderColor: colors.accent }]}
    >
      <AppText variant="label" color={active ? colors.onAccent : colors.textMuted} weight="bold">
        {label}
      </AppText>
    </Pressable>
  )
}

function Row({ label, value, tone }: { label: string; value: string; tone?: string }) {
  return (
    <View style={styles.row}>
      <AppText variant="caption" color={colors.textMuted}>
        {label}
      </AppText>
      <AppText variant="body" weight="bold" color={tone}>
        {value}
      </AppText>
    </View>
  )
}

const styles = StyleSheet.create({
  backdrop: { flex: 1, backgroundColor: colors.overlay, justifyContent: 'flex-end' },
  sheet: {
    maxHeight: '90%',
    backgroundColor: colors.surface,
    borderTopLeftRadius: radius.lg,
    borderTopRightRadius: radius.lg,
    borderWidth: 1,
    borderColor: colors.border,
  },
  body: { padding: spacing.lg, gap: spacing.md },
  head: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm },
  quick: { flexDirection: 'row', gap: spacing.sm },
  chip: {
    flex: 1,
    alignItems: 'center',
    paddingVertical: spacing.sm,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors.borderStrong,
  },
  split: { gap: spacing.xs, padding: spacing.md, backgroundColor: colors.surfaceAlt, borderRadius: radius.md },
  row: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  warn: { padding: spacing.md, borderRadius: radius.md, backgroundColor: colors.warningSoft },
  note: { padding: spacing.md, borderRadius: radius.md, backgroundColor: colors.surfaceAlt },
})
