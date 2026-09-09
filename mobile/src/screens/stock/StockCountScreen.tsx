import { memo, useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Alert, FlatList, Pressable, StyleSheet, TextInput, View } from 'react-native'
import { SafeAreaView } from 'react-native-safe-area-context'
import { useFocusEffect, useNavigation, useRoute, type RouteProp } from '@react-navigation/native'
import type { NativeStackNavigationProp } from '@react-navigation/native-stack'
import { onlineManager, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Ionicons } from '@expo/vector-icons'

import { cancelStockCount, fetchStockCount, postStockCount } from '../../api/stock'
import { isApiError } from '../../api/client'
import type { StockCountLine } from '../../api/types'
import { useAuth } from '../../auth/AuthContext'
import { canAccess } from '../../auth/access'
import { getDraft, rejectionFor, subscribeDrafts, setCount, syncSession } from '../../stock/countDraft'
import type { StockStackParams } from '../../navigation/types'
import { AppText, Button, Center } from '../../ui'
import { Segmented, StatusPill } from '../../ui/controls'
import { colors, faMoney, radius, spacing } from '../../theme'
import { faDate, faQty, normalizeDecimal, parseQty, toFaDigits } from '../../lib/format'

type Filter = 'all' | 'mine' | 'variance'

/** شمارشِ نوشته‌نشده پس از این مدت خودش می‌رود (کاربر نباید دکمه بزند). */
const AUTO_SYNC_MS = 1_500

/**
 * صفحه‌ی شمارش.
 *
 * ## دو چیزی که اینجا بی‌صدا غلط می‌شدند
 *
 * **۱. ثبتِ نهایی با شمارشِ روی گوشی.** «ثبت» یک سندِ تعدیلِ حسابداری می‌سازد.
 * اگر شمارش‌های این گوشی هنوز نرفته باشند، سند با اعدادِ *قدیمی* بسته می‌شود و
 * کارِ یک روزِ انباردار در دفتر اثری نمی‌گذارد — بدونِ هیچ خطایی. پس ثبت تا
 * وقتی چیزی ثبت‌نشده هست بسته است.
 *
 * **۲. عکسِ لحظه‌ی ایجاد.** `system_qty` هنگامِ ساختِ جلسه عکس‌برداری می‌شود، نه
 * هنگامِ ثبت. جلسه‌ای که چند روز باز مانده مغایرتش را با موجودیِ چند روز پیش
 * می‌سنجد. صفحه وقتی جلسه از امروز قدیمی‌تر است این را می‌گوید.
 */
export function StockCountScreen() {
  const { params } = useRoute<RouteProp<StockStackParams, 'StockCount'>>()
  const nav = useNavigation<NativeStackNavigationProp<StockStackParams>>()
  const qc = useQueryClient()
  const { me } = useAuth()
  const canWrite = canAccess(me, 'stock')

  const sessionId = params.id
  const q = useQuery({ queryKey: ['stock-count', sessionId], queryFn: () => fetchStockCount(sessionId) })

  const [draft, setDraft] = useState<Record<string, string>>({})
  const [search, setSearch] = useState('')
  const [filter, setFilter] = useState<Filter>('all')
  const [syncing, setSyncing] = useState(false)
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null)

  useEffect(() => {
    void getDraft(sessionId).then(setDraft)
    return subscribeDrafts((all) => setDraft(all[sessionId] ?? {}))
  }, [sessionId])

  const flush = useCallback(async () => {
    if (!onlineManager.isOnline()) return
    setSyncing(true)
    try {
      const r = await syncSession(sessionId)
      if (r === 'synced') void qc.invalidateQueries({ queryKey: ['stock-count', sessionId] })
    } finally {
      setSyncing(false)
    }
  }, [qc, sessionId])

  // برگشت به صفحه و بازگشتِ شبکه، هر دو باید ثبت‌نشده‌ها را بفرستند.
  useFocusEffect(useCallback(() => { void flush() }, [flush]))
  useEffect(() => onlineManager.subscribe((online) => { if (online) void flush() }), [flush])

  const scheduleFlush = useCallback(() => {
    if (timer.current) clearTimeout(timer.current)
    timer.current = setTimeout(() => void flush(), AUTO_SYNC_MS)
  }, [flush])

  useEffect(() => () => { if (timer.current) clearTimeout(timer.current) }, [])

  const onChangeQty = useCallback(
    async (lineId: string, qty: string) => {
      await setCount(sessionId, lineId, qty)
      scheduleFlush()
    },
    [scheduleFlush, sessionId],
  )

  const session = q.data
  const pending = Object.keys(draft).length
  const rejected = rejectionFor(sessionId)
  const isOpen = session?.status === 'open'

  /** مغایرتِ *دیده‌شده* — با مقدارِ روی گوشی، نه فقط آنچه به سرور رسیده. */
  const varianceOf = useCallback(
    // `parseQty` هم اینجا: مقادیرِ پیش‌نویس همیشه لاتین‌اند (چون `commit` آنها را
    // نرمال می‌کند)، ولی تکیه بر آن قرارداد شکننده است — یک مسیرِ تازه که خام
    // بنویسد، این محاسبه را بی‌صدا NaN می‌کند.
    (l: StockCountLine): number => parseQty(String(draft[l.id] ?? l.counted_qty)) - Number(l.system_qty),
    [draft],
  )

  const rows = useMemo(() => {
    const all = session?.lines ?? []
    const term = search.trim()
    return all.filter((l) => {
      if (term && !l.item_name.includes(term) && !l.item_sku.includes(term)) return false
      if (filter === 'mine') return draft[l.id] !== undefined
      if (filter === 'variance') return Math.abs(varianceOf(l)) > 1e-9
      return true
    })
  }, [draft, filter, search, session?.lines, varianceOf])

  const totals = useMemo(() => {
    let lines = 0
    let value = 0
    for (const l of session?.lines ?? []) {
      const v = varianceOf(l)
      if (Math.abs(v) > 1e-9) {
        lines += 1
        value += v * Number(l.unit_cost)
      }
    }
    return { lines, value }
  }, [session?.lines, varianceOf])

  const post = useMutation({
    mutationFn: () => postStockCount(sessionId),
    onSuccess: (s) => {
      qc.setQueryData(['stock-count', sessionId], s)
      void qc.invalidateQueries({ queryKey: ['stock-counts'] })
      void qc.invalidateQueries({ queryKey: ['alerts'] })
      Alert.alert('ثبت شد', 'مغایرت‌ها به موجودی و سندِ حسابداری اعمال شدند.')
    },
    onError: (e) => Alert.alert('ثبت نشد', isApiError(e) ? e.message : 'خطای نامشخص'),
  })

  const cancel = useMutation({
    mutationFn: () => cancelStockCount(sessionId),
    onSuccess: (s) => {
      qc.setQueryData(['stock-count', sessionId], s)
      void qc.invalidateQueries({ queryKey: ['stock-counts'] })
      nav.goBack()
    },
    onError: (e) => Alert.alert('لغو نشد', isApiError(e) ? e.message : 'خطای نامشخص'),
  })

  const confirmPost = async () => {
    if (pending > 0) {
      await flush()
      if (Object.keys(await getDraft(sessionId)).length > 0) {
        Alert.alert(
          'اول شمارش‌ها را بفرستید',
          `${toFaDigits(pending)} شمارش هنوز روی این گوشی است. ثبتِ نهایی سندِ حسابداری می‌سازد؛ اگر الان بزنید، این شمارش‌ها در سند نمی‌آیند. وقتی اینترنت وصل شد دوباره تلاش کنید.`,
        )
        return
      }
    }
    Alert.alert(
      'ثبتِ نهاییِ انبارگردانی',
      `${toFaDigits(totals.lines)} کالا مغایرت دارد و ارزشِ خالصِ تعدیل ${faMoney(totals.value)} ریال است. با ثبت، موجودی اصلاح و سندِ حسابداری صادر می‌شود. این کار برگشت‌پذیر نیست.`,
      [
        { text: 'انصراف', style: 'cancel' },
        { text: 'ثبت کن', style: 'destructive', onPress: () => post.mutate() },
      ],
    )
  }

  const confirmCancel = () =>
    Alert.alert('لغوِ جلسه', 'شمارش‌های این جلسه دور ریخته می‌شوند و چیزی در دفتر ثبت نمی‌شود.', [
      { text: 'برگرد', style: 'cancel' },
      { text: 'لغو کن', style: 'destructive', onPress: () => cancel.mutate() },
    ])

  if (q.isLoading && !session) {
    return (
      <Center>
        <AppText variant="body" color={colors.textMuted}>
          در حال بارگذاری…
        </AppText>
      </Center>
    )
  }

  if (!session) {
    return (
      <Center>
        <AppText variant="body" color={colors.textMuted}>
          {isApiError(q.error) ? q.error.message : 'جلسه پیدا نشد.'}
        </AppText>
      </Center>
    )
  }

  const stale = session.status === 'open' && session.count_date !== new Date().toISOString().slice(0, 10)

  return (
    <SafeAreaView style={styles.safe} edges={['bottom']}>
      <View style={styles.head}>
        <View style={styles.headRow}>
          <View style={{ flex: 1 }}>
            <AppText variant="heading" numberOfLines={1}>
              {session.warehouse_name}
            </AppText>
            <AppText variant="caption" color={colors.textMuted}>
              {faDate(session.count_date)} · {toFaDigits(session.line_count)} کالا
            </AppText>
          </View>
          {isOpen ? (
            <StatusPill label="باز" tone="accent" />
          ) : (
            <StatusPill
              label={session.status === 'posted' ? 'ثبت‌شده' : 'لغوشده'}
              tone={session.status === 'posted' ? 'success' : 'muted'}
            />
          )}
        </View>

        <View style={styles.summary}>
          <Metric label="مغایرت‌دار" value={`${toFaDigits(totals.lines)} کالا`} />
          <Metric
            label="ارزشِ تعدیل"
            value={`${faMoney(totals.value)} ریال`}
            tone={totals.value === 0 ? undefined : totals.value > 0 ? colors.success : colors.danger}
          />
        </View>

        {stale ? (
          <Note tone="warning">
            این جلسه از {faDate(session.count_date)} باز است. موجودیِ سیستمی همان روز عکس‌برداری شده،
            پس حرکت‌های انبار بعد از آن در مغایرت دیده نمی‌شوند.
          </Note>
        ) : null}

        {rejected ? (
          <Note tone="danger">{rejected}</Note>
        ) : pending > 0 ? (
          <Note tone="warning">
            {toFaDigits(pending)} شمارش روی این گوشی است{syncing ? ' — در حالِ ارسال…' : ''}
          </Note>
        ) : null}

        {isOpen && canWrite ? (
          <Pressable
            onPress={() => nav.navigate('StockScan', { sessionId })}
            android_ripple={{ color: colors.surfaceAlt }}
            style={styles.scanBtn}
          >
            <Ionicons name="barcode-outline" size={20} color={colors.onAccent} />
            <AppText variant="body" weight="bold" color={colors.onAccent}>
              اسکنِ بارکد
            </AppText>
          </Pressable>
        ) : null}

        <TextInput
          placeholder="جست‌وجوی نام یا کدِ کالا…"
          placeholderTextColor={colors.textFaint}
          value={search}
          onChangeText={setSearch}
          style={styles.search}
        />
        <Segmented<Filter>
          value={filter}
          onChange={setFilter}
          options={[
            { key: 'all', label: 'همه' },
            { key: 'mine', label: 'شمرده‌ی من' },
            { key: 'variance', label: 'مغایرت‌دار' },
          ]}
        />
      </View>

      <FlatList
        data={rows}
        keyExtractor={(l) => l.id}
        contentContainerStyle={styles.list}
        keyboardShouldPersistTaps="handled"
        ListEmptyComponent={
          <Center>
            <AppText variant="body" color={colors.textMuted}>
              {filter === 'mine' ? 'روی این گوشی هنوز چیزی نشمرده‌اید.' : 'کالایی مطابقِ فیلتر نیست.'}
            </AppText>
          </Center>
        }
        renderItem={({ item }) => (
          <CountRow
            line={item}
            // `faQty` و نه `String(...)`: سرور «۱۲.۰۰۰» می‌دهد و نمایشِ خامش هم
            // ارقامِ لاتین دارد هم سه صفرِ بی‌معنی — در ردیفی که کنارش «سیستم:
            // ۱۲ عدد» فارسی نوشته شده.
            value={draft[item.id] ?? faQty(item.counted_qty)}
            dirty={draft[item.id] !== undefined}
            editable={isOpen && canWrite}
            onChange={onChangeQty}
          />
        )}
        ItemSeparatorComponent={() => <View style={{ height: spacing.sm }} />}
      />

      {isOpen && canWrite ? (
        <View style={styles.footer}>
          <View style={{ flex: 1 }}>
            <Button label="ثبتِ نهایی" onPress={() => void confirmPost()} loading={post.isPending} />
          </View>
          <Pressable
            onPress={confirmCancel}
            accessibilityRole="button"
            accessibilityLabel="لغوِ جلسه‌ی انبارگردانی"
            android_ripple={{ color: colors.surfaceAlt }}
            style={styles.cancelBtn}
          >
            <Ionicons name="trash-outline" size={20} color={colors.danger} />
          </Pressable>
        </View>
      ) : null}
    </SafeAreaView>
  )
}

/** یک ردیفِ شمارش. متنِ در حالِ تایپ محلی است تا هر کلید یک نوشتنِ دیسک نشود. */
const CountRow = memo(function CountRow({
  line,
  value,
  dirty,
  editable,
  onChange,
}: {
  line: StockCountLine
  value: string
  dirty: boolean
  editable: boolean
  onChange: (lineId: string, qty: string) => void
}) {
  const [text, setText] = useState(value)
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null)

  useEffect(() => () => { if (timer.current) clearTimeout(timer.current) }, [])

  const commit = (raw: string) => {
    const clean = normalizeDecimal(raw)
    if (clean === '') return
    onChange(line.id, clean)
  }

  // `parseQty` و نه `Number(...)`: فیلد ارقامِ فارسی دارد و `Number('۱۲')` برابرِ
  // NaN است. آن‌وقت `Math.abs(NaN) > 1e-9` نادرست می‌شود و ردیفِ مغایرت‌دار
  // بی‌صدا «بدونِ اختلاف» نشان داده می‌شود.
  const variance = parseQty(text) - Number(line.system_qty)
  const hasVariance = Math.abs(variance) > 1e-9

  return (
    <View style={[styles.row, dirty && styles.rowDirty]}>
      <View style={{ flex: 1, gap: 2 }}>
        <AppText variant="body" weight="semibold" numberOfLines={1}>
          {line.item_name}
        </AppText>
        <AppText variant="caption" color={colors.textMuted}>
          {line.item_sku} · سیستم: {faQty(line.system_qty)} {line.unit}
        </AppText>
        {hasVariance ? (
          <AppText variant="caption" color={variance > 0 ? colors.success : colors.danger}>
            {variance > 0 ? 'اضافی' : 'کسری'} {faQty(Math.abs(variance))} {line.unit}
          </AppText>
        ) : null}
      </View>
      <TextInput
        value={text}
        editable={editable}
        onChangeText={(t) => {
          setText(t)
          if (timer.current) clearTimeout(timer.current)
          timer.current = setTimeout(() => commit(t), 600)
        }}
        onEndEditing={() => commit(text)}
        keyboardType="decimal-pad"
        selectTextOnFocus
        accessibilityLabel={`تعدادِ شمرده‌شده‌ی ${line.item_name}`}
        style={[styles.qty, !editable && { opacity: 0.5 }]}
      />
    </View>
  )
})

function Metric({ label, value, tone }: { label: string; value: string; tone?: string }) {
  return (
    <View style={styles.metric}>
      <AppText variant="caption" color={colors.textMuted}>
        {label}
      </AppText>
      <AppText variant="body" weight="bold" color={tone}>
        {value}
      </AppText>
    </View>
  )
}

function Note({ tone, children }: { tone: 'warning' | 'danger'; children: React.ReactNode }) {
  const fg = tone === 'danger' ? colors.danger : colors.warning
  const bg = tone === 'danger' ? colors.dangerSoft : colors.warningSoft
  return (
    <View style={[styles.note, { backgroundColor: bg }]}>
      <AppText variant="caption" color={fg}>
        {children}
      </AppText>
    </View>
  )
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: colors.bg },
  head: { padding: spacing.lg, paddingBottom: spacing.sm, gap: spacing.sm },
  headRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.md },
  summary: { flexDirection: 'row', gap: spacing.sm },
  metric: {
    flex: 1,
    gap: 2,
    padding: spacing.md,
    backgroundColor: colors.surface,
    borderRadius: radius.md,
  },
  note: { padding: spacing.md, borderRadius: radius.md },
  scanBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: spacing.sm,
    minHeight: 48,
    paddingVertical: spacing.sm,
    borderRadius: radius.md,
    backgroundColor: colors.accent,
  },
  search: {
    backgroundColor: colors.surfaceAlt,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.md,
    paddingHorizontal: spacing.md,
    minHeight: 46,
    paddingVertical: spacing.sm,
    color: colors.text,
    textAlign: 'right',
  },
  list: { paddingHorizontal: spacing.lg, paddingBottom: spacing.lg, flexGrow: 1 },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.md,
    padding: spacing.md,
    backgroundColor: colors.surface,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors.border,
  },
  rowDirty: { borderColor: colors.accent },
  qty: {
    // **کف، نه اندازه‌ی ثابت.** با فونتِ بزرگِ سیستم عددِ داخلِ این کادر از هر دو
    // سو بریده می‌شد — و این همان فیلدی است که سندِ تعدیلِ حسابداری از رویش
    // ساخته می‌شود. عددی که خوانده نشود از عددِ غلط بهتر نیست.
    minWidth: 84,
    minHeight: 46,
    paddingVertical: spacing.xs,
    paddingHorizontal: spacing.sm,
    borderRadius: radius.sm,
    backgroundColor: colors.surfaceAlt,
    borderWidth: 1,
    borderColor: colors.border,
    color: colors.text,
    textAlign: 'center',
    fontWeight: '700',
  },
  footer: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
    padding: spacing.lg,
    paddingTop: spacing.sm,
    borderTopWidth: 1,
    borderTopColor: colors.border,
    backgroundColor: colors.surface,
  },
  cancelBtn: {
    width: 52,
    height: 52,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors.danger,
    alignItems: 'center',
    justifyContent: 'center',
  },
})
