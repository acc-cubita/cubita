import { useState } from 'react'
import { StyleSheet, View } from 'react-native'
import type { RouteProp } from '@react-navigation/native'
import { useRoute } from '@react-navigation/native'
import { useQuery } from '@tanstack/react-query'
import { Ionicons } from '@expo/vector-icons'
import { fetchContactStatement, fetchCreditStatus, KIND_LABEL } from '../../api/contacts'
import { shareStatementPdf } from '../../lib/pdf'
import { MoneyRow, ReportScaffold, Section } from '../../ui/report'
import { AppText, Button, Card } from '../../ui'
import { colors, faMoney, spacing } from '../../theme'
import type { ContactsStackParams } from '../../navigation/types'

export function ContactDetailScreen() {
  const { params } = useRoute<RouteProp<ContactsStackParams, 'ContactDetail'>>()
  const { id } = params
  const stmtQ = useQuery({ queryKey: ['statement', id], queryFn: () => fetchContactStatement(id) })
  const creditQ = useQuery({ queryKey: ['credit', id], queryFn: () => fetchCreditStatus(id) })
  const [sharing, setSharing] = useState(false)

  const s = stmtQ.data
  const credit = creditQ.data
  const closing = Number(s?.closing_balance ?? 0)

  async function onShare() {
    if (!s) return
    setSharing(true)
    try {
      await shareStatementPdf(s)
    } catch {
      // اگر اشتراک لغو/ناموفق شد، کاری لازم نیست
    } finally {
      setSharing(false)
    }
  }

  return (
    <ReportScaffold loading={stmtQ.isLoading} fetching={stmtQ.isFetching} error={stmtQ.error} onRefresh={stmtQ.refetch}>
      <Card>
        <AppText variant="label" color={colors.textMuted}>ماندهٔ حساب</AppText>
        <AppText
          variant="title"
          color={closing > 0 ? colors.accent : closing < 0 ? colors.success : colors.text}
          style={{ marginTop: spacing.xs }}
        >
          {faMoney(Math.abs(closing))}
        </AppText>
        <AppText variant="caption" color={colors.textMuted}>
          {closing > 0 ? 'بدهکار به شما (طلبِ شما)' : closing < 0 ? 'بستانکار (بدهیِ شما)' : 'تسویه'}
        </AppText>

        {credit && Number(credit.credit_limit) > 0 ? (
          <View style={styles.creditBox}>
            <MoneyRow label="سقفِ اعتبار" amount={credit.credit_limit} muted />
            <MoneyRow label="ماندهٔ بازِ اعتبار" amount={credit.available} muted />
            {credit.over_limit ? (
              <View style={styles.overRow}>
                <Ionicons name="warning" size={16} color={colors.danger} />
                <AppText variant="label" color={colors.danger}>از سقفِ اعتبار عبور کرده است</AppText>
              </View>
            ) : null}
          </View>
        ) : null}

        <View style={{ marginTop: spacing.md }}>
          <Button
            label={sharing ? 'در حال آماده‌سازی…' : 'اشتراکِ کارتِ حساب (PDF)'}
            variant="ghost"
            loading={sharing}
            onPress={onShare}
            icon={<Ionicons name="share-outline" size={18} color={colors.text} />}
          />
        </View>
      </Card>

      <Section title="گردشِ حساب">
        <MoneyRow label="ماندهٔ ابتدای دوره" amount={s?.opening_balance ?? 0} muted />
        {s?.lines.length ? (
          s.lines.map((l, i) => (
            <View key={`${l.kind}-${l.number}-${i}`} style={styles.line}>
              <View style={{ flex: 1 }}>
                <AppText variant="body" numberOfLines={1}>
                  {KIND_LABEL[l.kind] ?? l.kind}
                  {l.number != null ? ` #${l.number.toLocaleString('fa-IR')}` : ''}
                </AppText>
                <AppText variant="caption" color={colors.textFaint}>{l.txn_date}</AppText>
              </View>
              <View style={{ alignItems: 'flex-end' }}>
                <AppText variant="body" weight="semibold" color={Number(l.debit) ? colors.text : colors.success}>
                  {Number(l.debit) ? `+${faMoney(l.debit)}` : `−${faMoney(l.credit)}`}
                </AppText>
                <AppText variant="caption" color={colors.textFaint}>مانده {faMoney(l.balance)}</AppText>
              </View>
            </View>
          ))
        ) : (
          <AppText variant="body" color={colors.textMuted}>تراکنشی ثبت نشده است.</AppText>
        )}
      </Section>
    </ReportScaffold>
  )
}

const styles = StyleSheet.create({
  creditBox: { marginTop: spacing.md, borderTopWidth: 1, borderTopColor: colors.border, paddingTop: spacing.sm },
  overRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm, marginTop: spacing.xs },
  line: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.md,
    paddingVertical: spacing.sm,
    borderTopWidth: 1,
    borderTopColor: colors.border,
  },
})
