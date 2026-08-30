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
import { fetchManifest, hasUpdate, installedVersionName, openStorePage, type UpdateManifest } from './updater'

// چرخه‌ی حالتِ آپدیت که مودال از رویش رندر می‌شود.
type Phase =
  | { state: 'idle' } // چیزی نشان نده
  | { state: 'checking' } // بررسیِ دستی در جریان است
  | { state: 'available'; info: UpdateManifest }
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

  // به‌روزرسانی از راهِ خودِ فروشگاه انجام می‌شود، نه درونِ اپ — اپ فقط در را باز
  // می‌کند. هیچ دانلودی اینجا رخ نمی‌دهد و هیچ دسترسیِ نصبی لازم نیست.
  const openStore = useCallback(async () => {
    try {
      await openStorePage()
    } catch {
      setPhase({ state: 'error', message: 'بازکردنِ صفحه‌ی برنامه ناموفق بود.' })
    }
  }, [])

  const dismiss = useCallback(() => {
    // آپدیتِ اجباری قابلِ بستن نیست.
    if (phase.state === 'available' && phase.info.mandatory) return
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
      <UpdateModal phase={phase} onOpenStore={() => void openStore()} onDismiss={dismiss} onRetry={() => void check()} />
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
  onOpenStore,
  onDismiss,
  onRetry,
}: {
  phase: Phase
  onOpenStore: () => void
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
          <ModalBody phase={phase} onOpenStore={onOpenStore} onDismiss={onDismiss} onRetry={onRetry} />
        </View>
      </View>
    </Modal>
  )
}

function ModalBody({
  phase,
  onOpenStore,
  onDismiss,
  onRetry,
}: {
  phase: Phase
  onOpenStore: () => void
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

  // available — تنها حالتی که اطلاعاتِ نسخه دارد.
  const info = phase.info

  return (
    <View style={styles.body}>
      <IconBubble name="sparkles-outline" tint={colors.accent} bg={colors.accentSoft} />
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

      {info.notes ? (
        <ScrollView style={styles.notes} contentContainerStyle={{ paddingVertical: spacing.xs }}>
          <AppText variant="body" color={colors.textMuted}>
            {info.notes}
          </AppText>
        </ScrollView>
      ) : null}

      <AppText variant="caption" color={colors.textMuted} style={styles.center}>
        به‌روزرسانی از صفحه‌ی برنامه در بازار انجام می‌شود.
      </AppText>

      <View style={styles.actions}>
        <View style={styles.flex}>
          <Button
            label="رفتن به بازار"
            onPress={onOpenStore}
            icon={<Ionicons name="open-outline" size={18} color={colors.onAccent} />}
          />
        </View>
        {info.mandatory ? null : (
          <View style={styles.flex}>
            <Button label="بعداً" variant="ghost" onPress={onDismiss} />
          </View>
        )}
      </View>
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
  actions: { flexDirection: 'row', gap: spacing.md, alignSelf: 'stretch', marginTop: spacing.xs },
  flex: { flex: 1 },
})
