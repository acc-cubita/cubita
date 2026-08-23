import { useEffect, useState } from 'react'
import { Alert, KeyboardAvoidingView, Platform, Pressable, ScrollView, StyleSheet, View } from 'react-native'
import { useNavigation, useRoute, type RouteProp } from '@react-navigation/native'
import type { NativeStackNavigationProp } from '@react-navigation/native-stack'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Ionicons } from '@expo/vector-icons'
import { createSalesInvoice, fetchWarehouses } from '../api/invoices'
import { isApiError } from '../api/client'
import type { HomeStackParams } from '../navigation/types'
import { AppText, Button, Card, TextField } from '../ui'
import { colors, faMoney, faNum, radius, spacing } from '../theme'

// فاکتورِ فروشِ سریع — همان قراردادِ دسکتاپ/وب (POST /api/sales-invoices).
// فرمِ موبایلیِ تک‌صفحه‌ای: طرف‌حساب (اختیاری) + ردیف‌ها + مالیات → ثبت.

interface Line {
  item_id: string
  name: string
  unit: string
  qty: string
  unit_price: string
}

function todayIso(): string {
  const d = new Date()
  const p = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`
}

/** ارقامِ فارسی/جداکننده → عددِ خام. اعشار (برای تعداد) حفظ می‌شود. */
function normalizeNum(raw: string): string {
  const fa = '۰۱۲۳۴۵۶۷۸۹'
  const out = raw
    .split('')
    .map((ch) => (fa.includes(ch) ? String(fa.indexOf(ch)) : ch))
    .filter((ch) => (ch >= '0' && ch <= '9') || ch === '.')
    .join('')
  // فقط یک نقطه‌ی اعشار
  const i = out.indexOf('.')
  return i === -1 ? out : out.slice(0, i + 1) + out.slice(i + 1).replace(/\./g, '')
}

const num = (s: string) => Number(normalizeNum(s) || 0)

export function NewInvoiceScreen() {
  const nav = useNavigation<NativeStackNavigationProp<HomeStackParams>>()
  const route = useRoute<RouteProp<HomeStackParams, 'NewInvoice'>>()
  const qc = useQueryClient()

  const [contact, setContact] = useState<{ id: string; name: string } | null>(null)
  const [lines, setLines] = useState<Line[]>([])
  const [taxRate, setTaxRate] = useState('')
  const [description, setDescription] = useState('')

  const picked = route.params?.pickedContact
  useEffect(() => {
    if (picked) setContact(picked)
  }, [picked])

  // کالای انتخاب‌شده → ردیفِ تازه با قیمتِ فروشِ پیش‌فرض.
  // پارامتر پس از مصرف پاک می‌شود؛ بدونِ آن، هر رندرِ بعدی ردیفِ تکراری می‌ساخت.
  const pickedItem = route.params?.pickedItem
  useEffect(() => {
    if (!pickedItem) return
    setLines((prev) => [
      ...prev,
      {
        item_id: pickedItem.id,
        name: pickedItem.name,
        unit: pickedItem.unit,
        qty: '1',
        unit_price: String(pickedItem.sales_price ?? '0'),
      },
    ])
    nav.setParams({ pickedItem: undefined })
    // فقط به هویتِ کالای تازه وابسته است: با پاک شدنِ پارامتر دوباره اجرا نمی‌شود.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pickedItem?.id])

  const whQ = useQuery({ queryKey: ['warehouses'], queryFn: fetchWarehouses })
  const warehouse = (whQ.data ?? []).find((w) => w.is_active) ?? (whQ.data ?? [])[0] ?? null

  const netTotal = lines.reduce((sum, l) => sum + num(l.qty) * num(l.unit_price), 0)
  const taxTotal = (netTotal * num(taxRate)) / 100
  const grand = netTotal + taxTotal

  const setLine = (idx: number, patch: Partial<Line>) =>
    setLines((prev) => prev.map((l, i) => (i === idx ? { ...l, ...patch } : l)))
  const removeLine = (idx: number) => setLines((prev) => prev.filter((_, i) => i !== idx))

  const save = useMutation({
    mutationFn: () =>
      createSalesInvoice({
        invoice_date: todayIso(),
        warehouse_id: warehouse!.id,
        contact_id: contact?.id ?? null,
        description: description.trim(),
        tax_rate: normalizeNum(taxRate) || '0',
        lines: lines.map((l) => ({
          item_id: l.item_id,
          qty: normalizeNum(l.qty),
          unit_price: normalizeNum(l.unit_price),
        })),
      }),
    onSuccess: (inv) => {
      void qc.invalidateQueries({ queryKey: ['sales-summary'] })
      void qc.invalidateQueries({ queryKey: ['sales-dashboard'] })
      void qc.invalidateQueries({ queryKey: ['alerts'] })
      const total = Number(inv.total_amount) + Number(inv.tax_amount) + Number(inv.rounding)
      Alert.alert(
        'فاکتور ثبت شد',
        `شماره ${inv.number != null ? faNum(inv.number) : '—'} — ${faMoney(total)} ریال`,
        [{ text: 'باشه', onPress: () => nav.goBack() }],
      )
    },
    onError: (e) => {
      Alert.alert('ثبت نشد', isApiError(e) ? e.message : 'خطای نامشخص در ثبتِ فاکتور')
    },
  })

  const linesValid = lines.length > 0 && lines.every((l) => num(l.qty) > 0 && num(l.unit_price) >= 0)
  const canSave = linesValid && warehouse !== null && !save.isPending

  return (
    <KeyboardAvoidingView style={styles.screen} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
      <ScrollView contentContainerStyle={styles.content} keyboardShouldPersistTaps="handled">
        {/* طرف‌حساب (اختیاری — فروشِ نقدیِ گذری) */}
        <Card>
          <AppText variant="label" color={colors.textMuted}>
            مشتری (اختیاری)
          </AppText>
          <View style={styles.pickerRow}>
            <Pressable
              onPress={() => nav.navigate('ContactPicker', { returnTo: 'NewInvoice' })}
              android_ripple={{ color: colors.surfaceAlt }}
              style={styles.picker}
            >
              <Ionicons name="person-circle-outline" size={22} color={contact ? colors.accent : colors.textFaint} />
              <AppText variant="body" color={contact ? colors.text : colors.textFaint} style={{ flex: 1 }} numberOfLines={1}>
                {contact?.name ?? 'فروشِ نقدی (بدونِ مشتری)'}
              </AppText>
              <Ionicons name="chevron-back" size={18} color={colors.textFaint} />
            </Pressable>
            {contact ? (
              <Pressable onPress={() => setContact(null)} hitSlop={8} style={styles.clearBtn}>
                <Ionicons name="close-circle" size={20} color={colors.textFaint} />
              </Pressable>
            ) : null}
          </View>
        </Card>

        {/* ردیف‌ها */}
        <Card>
          <View style={styles.linesHead}>
            <AppText variant="heading">اقلام</AppText>
            <Pressable
              onPress={() => nav.navigate('ItemPicker')}
              android_ripple={{ color: colors.surfaceAlt }}
              style={styles.addBtn}
            >
              <Ionicons name="add-circle" size={18} color={colors.accent} />
              <AppText variant="label" color={colors.accent}>
                افزودنِ کالا
              </AppText>
            </Pressable>
          </View>

          {lines.length === 0 ? (
            <AppText variant="body" color={colors.textMuted} style={{ marginTop: spacing.sm }}>
              هنوز کالایی اضافه نشده.
            </AppText>
          ) : (
            lines.map((l, idx) => (
              <View key={`${l.item_id}-${idx}`} style={styles.lineCard}>
                <View style={styles.lineHead}>
                  <AppText variant="body" weight="semibold" numberOfLines={1} style={{ flex: 1 }}>
                    {l.name}
                  </AppText>
                  <Pressable onPress={() => removeLine(idx)} hitSlop={8}>
                    <Ionicons name="trash-outline" size={18} color={colors.danger} />
                  </Pressable>
                </View>
                <View style={styles.lineInputs}>
                  <View style={{ flex: 1 }}>
                    <TextField
                      label={`تعداد (${l.unit})`}
                      value={l.qty}
                      onChangeText={(v) => setLine(idx, { qty: v })}
                      keyboardType="decimal-pad"
                    />
                  </View>
                  <View style={{ flex: 1.4 }}>
                    <TextField
                      label="قیمتِ واحد"
                      value={l.unit_price}
                      onChangeText={(v) => setLine(idx, { unit_price: v })}
                      keyboardType="number-pad"
                    />
                  </View>
                </View>
                <AppText variant="label" color={colors.textMuted} style={{ marginTop: spacing.xs }}>
                  جمعِ ردیف: {faMoney(num(l.qty) * num(l.unit_price))} ریال
                </AppText>
              </View>
            ))
          )}
        </Card>

        {/* مالیات و شرح */}
        <Card>
          <TextField
            label="نرخِ مالیات بر ارزش افزوده (٪)"
            value={taxRate}
            onChangeText={setTaxRate}
            keyboardType="decimal-pad"
            placeholder="۰"
          />
          <View style={{ marginTop: spacing.md }}>
            <TextField label="شرح (اختیاری)" value={description} onChangeText={setDescription} />
          </View>
        </Card>

        {/* جمعِ زنده */}
        <Card>
          <SumRow label="جمعِ خالص" value={faMoney(netTotal)} />
          <SumRow label="مالیات" value={faMoney(taxTotal)} />
          <View style={styles.divider} />
          <SumRow label="مبلغِ نهایی" value={`${faMoney(grand)} ریال`} strong />
        </Card>

        {warehouse === null && !whQ.isLoading ? (
          <AppText variant="caption" color={colors.warning}>
            انباری تعریف نشده — از برنامه‌ی دسکتاپ/وب یک انبار بسازید.
          </AppText>
        ) : null}

        <Button
          label="ثبتِ فاکتور"
          onPress={() => save.mutate()}
          disabled={!canSave}
          loading={save.isPending}
          icon={<Ionicons name="checkmark-circle-outline" size={18} color={colors.onAccent} />}
        />
      </ScrollView>
    </KeyboardAvoidingView>
  )
}

function SumRow({ label, value, strong }: { label: string; value: string; strong?: boolean }) {
  return (
    <View style={styles.sumRow}>
      <AppText variant={strong ? 'body' : 'label'} color={strong ? colors.text : colors.textMuted}>
        {label}
      </AppText>
      <AppText variant={strong ? 'heading' : 'label'} color={strong ? colors.accent : colors.text}>
        {value}
      </AppText>
    </View>
  )
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: colors.bg },
  content: { padding: spacing.lg, gap: spacing.md },
  pickerRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm },
  picker: {
    flex: 1,
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
  clearBtn: { marginTop: spacing.sm },
  linesHead: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  addBtn: { flexDirection: 'row', alignItems: 'center', gap: spacing.xs },
  lineCard: {
    marginTop: spacing.md,
    padding: spacing.md,
    backgroundColor: colors.surfaceAlt,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors.border,
  },
  lineHead: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm },
  lineInputs: { flexDirection: 'row', gap: spacing.md, marginTop: spacing.sm },
  sumRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingVertical: spacing.xs,
  },
  divider: { height: 1, backgroundColor: colors.border, marginVertical: spacing.sm },
})
