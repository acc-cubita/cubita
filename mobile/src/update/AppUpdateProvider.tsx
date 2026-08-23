import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from 'react'
import { ActivityIndicator, Modal, Platform, ScrollView, StyleSheet, View } from 'react-native'
import { Ionicons } from '@expo/vector-icons'
import { AppText, Button } from '../ui'
import { colors, radius, spacing } from '../theme'
import {
  downloadApk,
  fetchManifest,
  hasUpdate,
  installApk,
  installedVersionName,
  type UpdateManifest,
} from './updater'

// چرخه‌ی حالتِ آپدیت که مودال از رویش رندر می‌شود.
type Phase =
  | { state: 'idle' } // چیزی نشان نده
  | { state: 'checking' } // بررسیِ دستی در جریان است
  | { state: 'available'; info: UpdateManifest }
  | { state: 'downloading'; info: UpdateManifest; percent: number }
  | { state: 'installing'; info: UpdateManifest }
  | { state: 'none' } // بررسیِ دستی: به‌روز است
  | { state: 'error'; message: string }

interface UpdateValue {
  phase: Phase
  installedVersion: string
  /** بررسیِ آپدیت. در حالتِ silent (خودکار)، نبودِ آپدیت یا خطا پیام نمی‌دهد. */
  check: (opts?: { silent?: boolean }) => Promise<void>
}

const UpdateContext = createContext<UpdateValue | null>(null)

export function AppUpdateProvider({ children }: { children: ReactNode }) {
  const [phase, setPhase] = useState<Phase>({ state: 'idle' })
  const busy = useRef(false)
  const infoRef = useRef<UpdateManifest | null>(null)

  const check = useCallback(async (opts?: { silent?: boolean }) => {
    const silent = opts?.silent ?? false
    if (Platform.OS !== 'android') {
      if (!silent) setPhase({ state: 'none' })
      return
    }
    if (busy.current) return
    busy.current = true
    if (!silent) setPhase({ state: 'checking' })
    try {
      const info = await fetchManifest()
      if (hasUpdate(info)) {
        infoRef.current = info
        setPhase({ state: 'available', info })
      } else {
        setPhase(silent ? { state: 'idle' } : { state: 'none' })
      }
    } catch {
      // شکستِ بررسی (نبودِ اینترنت/فید) نباید کارِ کاربر را قطع کند؛ در حالتِ خودکار بی‌صدا.
      setPhase(silent ? { state: 'idle' } : { state: 'error', message: 'بررسیِ به‌روزرسانی ناموفق بود. اینترنت را بررسی کنید.' })
    } finally {
      busy.current = false
    }
  }, [])

  const startInstall = useCallback(async () => {
    const info = infoRef.current
    if (!info) return
    setPhase({ state: 'downloading', info, percent: 0 })
    try {
      const uri = await downloadApk(info, (f) => setPhase({ state: 'downloading', info, percent: f }))
      setPhase({ state: 'installing', info })
      await installApk(uri)
      // نصب‌کننده باز شد؛ اگر کاربر لغو کند و برگردد، دوباره امکانِ اقدام داشته باشد.
      setPhase({ state: 'available', info })
    } catch {
      setPhase({ state: 'error', message: 'دانلود یا نصبِ به‌روزرسانی ناموفق بود. دوباره تلاش کنید.' })
    }
  }, [])

  const dismiss = useCallback(() => {
    // آپدیتِ اجباری قابلِ بستن نیست.
    if (phase.state === 'available' && phase.info.mandatory) return
    if (phase.state === 'downloading' || phase.state === 'installing') return
    setPhase({ state: 'idle' })
  }, [phase])

  // بررسیِ خودکار در بدو اجرا (بی‌صدا). با تأخیرِ کوتاه تا با راه‌اندازیِ اپ رقابت نکند.
  useEffect(() => {
    const t = setTimeout(() => void check({ silent: true }), 4000)
    return () => clearTimeout(t)
  }, [check])

  return (
    <UpdateContext.Provider value={{ phase, installedVersion: installedVersionName(), check }}>
      {children}
      <UpdateModal phase={phase} onInstall={startInstall} onDismiss={dismiss} onRetry={() => void check()} />
    </UpdateContext.Provider>
  )
}

export function useAppUpdate(): UpdateValue {
  const ctx = useContext(UpdateContext)
  if (!ctx) throw new Error('useAppUpdate باید داخلِ AppUpdateProvider استفاده شود')
  return ctx
}

// ——— مودالِ آپدیت ———

function UpdateModal({
  phase,
  onInstall,
  onDismiss,
  onRetry,
}: {
  phase: Phase
  onInstall: () => void
  onDismiss: () => void
  onRetry: () => void
}) {
  const visible = phase.state !== 'idle'
  const dismissable =
    phase.state === 'none' ||
    phase.state === 'error' ||
    (phase.state === 'available' && !phase.info.mandatory)

  return (
    <Modal visible={visible} transparent animationType="fade" onRequestClose={() => dismissable && onDismiss()}>
      <View style={styles.overlay}>
        <View style={styles.sheet}>
          <ModalBody phase={phase} onInstall={onInstall} onDismiss={onDismiss} onRetry={onRetry} />
        </View>
      </View>
    </Modal>
  )
}

function ModalBody({
  phase,
  onInstall,
  onDismiss,
  onRetry,
}: {
  phase: Phase
  onInstall: () => void
  onDismiss: () => void
  onRetry: () => void
}) {
  if (phase.state === 'idle') return null

  if (phase.state === 'checking') {
    return (
      <View style={styles.centerRow}>
        <ActivityIndicator color={colors.accent} />
        <AppText variant="body">در حال بررسیِ به‌روزرسانی…</AppText>
      </View>
    )
  }

  if (phase.state === 'none') {
    return (
      <View style={styles.body}>
        <IconBubble name="checkmark-circle" tint={colors.success} bg={colors.successSoft} />
        <AppText variant="heading">برنامه به‌روز است</AppText>
        <AppText variant="body" color={colors.textMuted} style={styles.center}>
          آخرین نسخه‌ی کوبیتا روی این دستگاه نصب است.
        </AppText>
        <Button label="بستن" variant="ghost" onPress={onDismiss} />
      </View>
    )
  }

  if (phase.state === 'error') {
    return (
      <View style={styles.body}>
        <IconBubble name="alert-circle" tint={colors.danger} bg={colors.dangerSoft} />
        <AppText variant="heading">خطا</AppText>
        <AppText variant="body" color={colors.textMuted} style={styles.center}>
          {phase.message}
        </AppText>
        <View style={styles.actions}>
          <View style={styles.flex}>
            <Button label="تلاش دوباره" onPress={onRetry} />
          </View>
          <View style={styles.flex}>
            <Button label="بستن" variant="ghost" onPress={onDismiss} />
          </View>
        </View>
      </View>
    )
  }

  // available | downloading | installing — همه اطلاعاتِ نسخه را دارند.
  const info = phase.info
  const downloading = phase.state === 'downloading'
  const installing = phase.state === 'installing'
  const pct = downloading ? Math.round(phase.percent * 100) : 0

  return (
    <View style={styles.body}>
      <IconBubble name="cloud-download-outline" tint={colors.accent} bg={colors.accentSoft} />
      <AppText variant="heading">نسخه‌ی جدیدِ کوبیتا</AppText>
      <View style={styles.versionRow}>
        <AppText variant="label" color={colors.textMuted}>
          نسخه‌ی {info.versionName}
        </AppText>
        {info.mandatory ? (
          <View style={styles.mandatoryChip}>
            <AppText variant="caption" color={colors.warning} weight="bold">
              به‌روزرسانیِ لازم
            </AppText>
          </View>
        ) : null}
      </View>

      {info.reinstall ? (
        <View style={styles.reinstallBox}>
          <AppText variant="label" color={colors.warning} weight="bold">
            این نسخه نصبِ دوباره می‌خواهد
          </AppText>
          <AppText variant="caption" color={colors.textMuted} style={styles.center}>
            به‌دلیلِ تغییرِ کلیدِ امنیتیِ برنامه، اندروید اجازه‌ی نصب روی نسخه‌ی فعلی را نمی‌دهد.
            پس از دانلود، اگر نصب انجام نشد یک‌بار «کوبیتا» را حذف و دوباره نصب کنید.
            اطلاعاتِ شما روی سرور است و از بین نمی‌رود.
          </AppText>
        </View>
      ) : null}

      {info.notes ? (
        <ScrollView style={styles.notes} contentContainerStyle={{ paddingVertical: spacing.xs }}>
          <AppText variant="body" color={colors.textMuted}>
            {info.notes}
          </AppText>
        </ScrollView>
      ) : null}

      {downloading || installing ? (
        <View style={styles.progressWrap}>
          <View style={styles.progressTrack}>
            <View style={[styles.progressFill, { width: installing ? '100%' : `${pct}%` }]} />
          </View>
          <AppText variant="caption" color={colors.textMuted} style={styles.center}>
            {installing ? 'در حال بازکردنِ نصب‌کننده…' : `در حال دانلود… ${pct.toLocaleString('fa-IR')}٪`}
          </AppText>
        </View>
      ) : (
        <View style={styles.actions}>
          <View style={styles.flex}>
            <Button label="دانلود و نصب" onPress={onInstall} icon={<Ionicons name="download-outline" size={18} color={colors.onAccent} />} />
          </View>
          {info.mandatory ? null : (
            <View style={styles.flex}>
              <Button label="بعداً" variant="ghost" onPress={onDismiss} />
            </View>
          )}
        </View>
      )}
    </View>
  )
}

function IconBubble({ name, tint, bg }: { name: keyof typeof Ionicons.glyphMap; tint: string; bg: string }) {
  return (
    <View style={[styles.bubble, { backgroundColor: bg }]}>
      <Ionicons name={name} size={30} color={tint} />
    </View>
  )
}

const styles = StyleSheet.create({
  overlay: {
    flex: 1,
    backgroundColor: colors.overlay,
    alignItems: 'center',
    justifyContent: 'center',
    padding: spacing.xl,
  },
  sheet: {
    width: '100%',
    maxWidth: 420,
    backgroundColor: colors.surface,
    borderRadius: radius.lg,
    borderWidth: 1,
    borderColor: colors.border,
    padding: spacing.xl,
  },
  body: { alignItems: 'center', gap: spacing.md },
  centerRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: spacing.md, paddingVertical: spacing.sm },
  center: { textAlign: 'center' },
  bubble: { width: 60, height: 60, borderRadius: radius.pill, alignItems: 'center', justifyContent: 'center' },
  versionRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm },
  mandatoryChip: {
    backgroundColor: colors.warningSoft,
    paddingHorizontal: spacing.sm,
    paddingVertical: 2,
    borderRadius: radius.pill,
  },
  notes: { maxHeight: 140, alignSelf: 'stretch' },
  reinstallBox: {
    alignSelf: 'stretch',
    gap: spacing.xs,
    padding: spacing.md,
    borderRadius: radius.md,
    backgroundColor: colors.warningSoft,
    borderWidth: 1,
    borderColor: colors.warning,
    alignItems: 'center',
  },
  progressWrap: { alignSelf: 'stretch', gap: spacing.sm, marginTop: spacing.xs },
  progressTrack: { height: 8, borderRadius: radius.pill, backgroundColor: colors.surfaceAlt, overflow: 'hidden' },
  progressFill: { height: '100%', borderRadius: radius.pill, backgroundColor: colors.accent },
  actions: { flexDirection: 'row', gap: spacing.md, alignSelf: 'stretch', marginTop: spacing.xs },
  flex: { flex: 1 },
})
