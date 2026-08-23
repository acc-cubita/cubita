import { useEffect, useState } from 'react'
import { Alert, KeyboardAvoidingView, Platform, Pressable, ScrollView, StyleSheet, View } from 'react-native'
import { useNavigation, useRoute, type RouteProp } from '@react-navigation/native'
import type { NativeStackNavigationProp } from '@react-navigation/native-stack'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Ionicons } from '@expo/vector-icons'
import { createPayment, createReceipt, fetchBankAccounts } from '../api/treasury'
import { isApiError } from '../api/client'
import type { HomeStackParams } from '../navigation/types'
import { AppText, Button, Card, TextField } from '../ui'
import { colors, faMoney, radius, spacing } from '../theme'

// ثبتِ دریافت/پرداختِ خزانه — «ثبتِ داده در حرکت». همان قراردادِ دسکتاپ/وب
// (POST /api/treasury/{receipts|payments})، ولی فرمِ کاملاً موبایلیِ تک‌صفحه‌ای.

/** تاریخِ امروز به‌صورتِ YYYY-MM-DD در وقتِ محلی (نه UTC — وگرنه شب‌ها یک روز عقب می‌افتد). */
function todayIso(): string {
  const d = new Date()
  const p = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`
}

/** فقط رقم نگه می‌دارد (کاربر ممکن است جداکننده یا رقمِ فارسی بزند). */
function normalizeAmount(raw: string): string {
  const fa = '۰۱۲۳۴۵۶۷۸۹'
  return raw
    .split('')
    .map((ch) => (fa.includes(ch) ? String(fa.indexOf(ch)) : ch))
    .filter((ch) => ch >= '0' && ch <= '9')
    .join('')
}

export function TreasuryScreen() {
  const nav = useNavigation<NativeStackNavigationProp<HomeStackParams>>()
  const route = useRoute<RouteProp<HomeStackParams, 'Treasury'>>()
  const qc = useQueryClient()
  const kind = route.params.type
  const isReceipt = kind === 'receipt'

  const [contact, setContact] = useState<{ id: string; name: string } | null>(null)
  const [amount, setAmount] = useState('')
  const [method, setMethod] = useState<'cash' | 'bank'>('cash')
  const [bankId, setBankId] = useState<string | null>(null)
  const [description, setDescription] = useState('')

  // طرف‌حسابِ انتخاب‌شده از صفحه‌ی picker برمی‌گردد.
  const picked = route.params.pickedContact
  useEffect(() => {
    if (picked) setContact(picked)
  }, [picked])

  const banksQ = useQuery({ queryKey: ['bank-accounts'], queryFn: fetchBankAccounts })
  const banks = banksQ.data ?? []

  const save = useMutation({
    mutationFn: () => {
      const body = {
        transaction_date: todayIso(),
        contact_id: contact!.id,
        amount: normalizeAmount(amount),
        method,
        bank_account_id: method === 'bank' ? bankId : null,
        description: description.trim(),
      }
      return isReceipt ? createReceipt(body) : createPayment(body)
    },
    onSuccess: (txn) => {
      // داشبورد/هشدارها/کارتِ حساب همه تغییر کرده‌اند.
      void qc.invalidateQueries({ queryKey: ['sales-summary'] })
      void qc.invalidateQueries({ queryKey: ['alerts'] })
      void qc.invalidateQueries({ queryKey: ['contacts'] })
      Alert.alert(
        isReceipt ? 'دریافت ثبت شد' : 'پرداخت ثبت شد',
        `${faMoney(txn.amount)} ریال — ${txn.contact_name}`,
        [{ text: 'باشه', onPress: () => nav.goBack() }],
      )
    },
    onError: (e) => {
      Alert.alert('ثبت نشد', isApiError(e) ? e.message : 'خطای نامشخص در ثبتِ تراکنش')
    },
  })

  const amountNum = Number(normalizeAmount(amount) || 0)
  const canSave =
    contact !== null && amountNum > 0 && (method === 'cash' || bankId !== null) && !save.isPending

  return (
    <KeyboardAvoidingView
      style={styles.screen}
      behavior={Platform.OS === 'ios' ? 'padding' : undefined}
    >
      <ScrollView contentContainerStyle={styles.content} keyboardShouldPersistTaps="handled">
        {/* طرف‌حساب */}
        <Card>
          <AppText variant="label" color={colors.textMuted}>
            {isReceipt ? 'دریافت از' : 'پرداخت به'}
          </AppText>
          <Pressable
            onPress={() => nav.navigate('ContactPicker')}
            android_ripple={{ color: colors.surfaceAlt }}
            style={styles.picker}
          >
            <Ionicons name="person-circle-outline" size={22} color={contact ? colors.accent : colors.textFaint} />
            <AppText variant="body" color={contact ? colors.text : colors.textFaint} style={{ flex: 1 }} numberOfLines={1}>
              {contact?.name ?? 'انتخابِ طرف‌حساب'}
            </AppText>
            <Ionicons name="chevron-back" size={18} color={colors.textFaint} />
          </Pressable>
        </Card>

        {/* مبلغ */}
        <Card>
          <TextField
            label="مبلغ (ریال)"
            value={amount}
            onChangeText={setAmount}
            keyboardType="number-pad"
            placeholder="۰"
          />
          {amountNum > 0 ? (
            <AppText variant="label" color={colors.accent} style={{ marginTop: spacing.sm }}>
              {faMoney(amountNum)} ریال
            </AppText>
          ) : null}
        </Card>

        {/* روش */}
        <Card>
          <AppText variant="label" color={colors.textMuted}>
            روشِ {isReceipt ? 'دریافت' : 'پرداخت'}
          </AppText>
          <View style={styles.segment}>
            <SegmentBtn label="نقدی" icon="cash-outline" active={method === 'cash'} onPress={() => setMethod('cash')} />
            <SegmentBtn label="بانکی" icon="card-outline" active={method === 'bank'} onPress={() => setMethod('bank')} />
          </View>

          {method === 'bank' ? (
            <View style={{ marginTop: spacing.md, gap: spacing.sm }}>
              <AppText variant="label" color={colors.textMuted}>
                حسابِ بانکی
              </AppText>
              {banks.length === 0 ? (
                <AppText variant="caption" color={colors.warning}>
                  حسابِ بانکی‌ای تعریف نشده — از برنامه‌ی دسکتاپ/وب اضافه کنید.
                </AppText>
              ) : (
                banks.map((b) => (
                  <Pressable
                    key={b.id}
                    onPress={() => setBankId(b.id)}
                    android_ripple={{ color: colors.surfaceAlt }}
                    style={[styles.bankRow, bankId === b.id && styles.bankRowActive]}
                  >
                    <Ionicons
                      name={bankId === b.id ? 'radio-button-on' : 'radio-button-off'}
                      size={18}
                      color={bankId === b.id ? colors.accent : colors.textFaint}
                    />
                    <AppText variant="body" numberOfLines={1} style={{ flex: 1 }}>
                      {b.name}
                    </AppText>
                  </Pressable>
                ))
              )}
            </View>
          ) : null}
        </Card>

        {/* شرح */}
        <Card>
          <TextField
            label="شرح (اختیاری)"
            value={description}
            onChangeText={setDescription}
            placeholder="بابتِ…"
          />
        </Card>

        <Button
          label={isReceipt ? 'ثبتِ دریافت' : 'ثبتِ پرداخت'}
          onPress={() => save.mutate()}
          disabled={!canSave}
          loading={save.isPending}
          icon={<Ionicons name="checkmark-circle-outline" size={18} color={colors.onAccent} />}
        />
      </ScrollView>
    </KeyboardAvoidingView>
  )
}

function SegmentBtn({
  label,
  icon,
  active,
  onPress,
}: {
  label: string
  icon: keyof typeof Ionicons.glyphMap
  active: boolean
  onPress: () => void
}) {
  return (
    <Pressable
      onPress={onPress}
      android_ripple={{ color: colors.surfaceAlt }}
      style={[styles.segmentBtn, active && styles.segmentBtnActive]}
    >
      <Ionicons name={icon} size={18} color={active ? colors.onAccent : colors.textMuted} />
      <AppText variant="label" color={active ? colors.onAccent : colors.textMuted}>
        {label}
      </AppText>
    </Pressable>
  )
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: colors.bg },
  content: { padding: spacing.lg, gap: spacing.md },
  picker: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
    marginTop: spacing.sm,
    paddingVertical: spacing.md,
    paddingHorizontal: spacing.md,
    backgroundColor: colors.surfaceAlt,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors.border,
  },
  segment: { flexDirection: 'row', gap: spacing.sm, marginTop: spacing.sm },
  segmentBtn: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: spacing.xs,
    paddingVertical: spacing.md,
    borderRadius: radius.md,
    backgroundColor: colors.surfaceAlt,
    borderWidth: 1,
    borderColor: colors.border,
  },
  segmentBtnActive: { backgroundColor: colors.accent, borderColor: colors.accent },
  bankRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
    paddingVertical: spacing.md,
    paddingHorizontal: spacing.md,
    borderRadius: radius.md,
    backgroundColor: colors.surfaceAlt,
    borderWidth: 1,
    borderColor: colors.border,
  },
  bankRowActive: { borderColor: colors.accent },
})
