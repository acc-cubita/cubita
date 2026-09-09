import { useRef, useState } from 'react'
import { FlatList, KeyboardAvoidingView, Platform, Pressable, StyleSheet, TextInput, View } from 'react-native'
import { SafeAreaView } from 'react-native-safe-area-context'
import type { RouteProp } from '@react-navigation/native'
import { useRoute } from '@react-navigation/native'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Ionicons } from '@expo/vector-icons'
import {
  getConnectionMessages,
  getOrderMessages,
  postConnectionMessage,
  postOrderMessage,
} from '../../api/marketplace'
import type { MpMessage } from '../../api/types'
import { AppText, Center } from '../../ui'
import { colors, radius, spacing } from '../../theme'
import type { MarketStackParams } from '../../navigation/types'
import { useAuth } from '../../auth/AuthContext'
import { canAccess } from '../../auth/access'

const faTime = (iso: string) =>
  new Date(iso).toLocaleTimeString('fa-IR', { hour: '2-digit', minute: '2-digit' })

export function ChatScreen() {
  const { params } = useRoute<RouteProp<MarketStackParams, 'Chat'>>()
  const { scope, id } = params
  const qc = useQueryClient()
  const listRef = useRef<FlatList<MpMessage>>(null)
  const [text, setText] = useState('')
  const [sending, setSending] = useState(false)
  // خواندنِ رشته روی بک‌اند مجوز نمی‌خواهد، ولی *فرستادن* `marketplace:create`
  // می‌خواهد. مأمورِ حمل آن را ندارد — پیش از این کادرِ نوشتن را می‌دید، تایپ
  // می‌کرد و روی «ارسال» ۴۰۳ می‌گرفت.
  const { me } = useAuth()
  const canSend = canAccess(me, 'marketChat')

  // پولینگِ ~۴ ثانیه‌ای برای تحویلِ زنده (بدونِ WebSocket).
  const q = useQuery({
    queryKey: ['mp-messages', scope, id],
    queryFn: () => (scope === 'connection' ? getConnectionMessages(id) : getOrderMessages(id)),
    refetchInterval: 4000,
  })

  const myRole = q.data?.my_role
  const messages = q.data?.messages ?? []

  async function send() {
    const body = text.trim()
    if (!body || sending) return
    setSending(true)
    setText('')
    try {
      if (scope === 'connection') await postConnectionMessage(id, body)
      else await postOrderMessage(id, body)
      await q.refetch()
      void qc.invalidateQueries({ queryKey: ['mp-unread'] })
    } catch {
      setText(body) // اگر نرفت، متن را برگردان تا کاربر دوباره بزند
    } finally {
      setSending(false)
    }
  }

  return (
    <SafeAreaView style={styles.safe} edges={['bottom']}>
      <KeyboardAvoidingView
        style={styles.flex}
        behavior={Platform.OS === 'ios' ? 'padding' : undefined}
        keyboardVerticalOffset={90}
      >
        {q.isLoading ? (
          <Center>
            <AppText variant="body" color={colors.textMuted}>در حال دریافت…</AppText>
          </Center>
        ) : (
          <FlatList
            ref={listRef}
            data={messages}
            keyExtractor={(m) => m.id}
            contentContainerStyle={styles.list}
            onContentSizeChange={() => listRef.current?.scrollToEnd({ animated: false })}
            ListEmptyComponent={
              <Center>
                <AppText variant="body" color={colors.textMuted}>
                  هنوز پیامی رد‌وبدل نشده. اولین پیام را بفرستید.
                </AppText>
              </Center>
            }
            renderItem={({ item }) => <Bubble msg={item} mine={item.sender_role === myRole} />}
          />
        )}

        {!canSend ? (
          <View style={styles.readOnly}>
            <AppText variant="caption" color={colors.textMuted}>
              با نقشِ شما فقط خواندنِ گفتگو ممکن است.
            </AppText>
          </View>
        ) : (
        <View style={styles.composer}>
          <TextInput
            value={text}
            onChangeText={setText}
            placeholder="پیام…"
            placeholderTextColor={colors.textFaint}
            style={styles.input}
            multiline
          />
          <Pressable
            onPress={send}
            disabled={!text.trim() || sending}
            accessibilityRole="button"
            accessibilityLabel="ارسالِ پیام"
            accessibilityState={{ disabled: !text.trim() || sending, busy: sending }}
            android_ripple={{ color: 'rgba(0,0,0,0.15)', radius: 24 }}
            style={[styles.sendBtn, (!text.trim() || sending) && { opacity: 0.5 }]}
          >
            <Ionicons name="arrow-up" size={22} color={colors.onAccent} />
          </Pressable>
        </View>
        )}
      </KeyboardAvoidingView>
    </SafeAreaView>
  )
}

function Bubble({ msg, mine }: { msg: MpMessage; mine: boolean }) {
  return (
    <View style={[styles.bubbleWrap, { alignItems: mine ? 'flex-end' : 'flex-start' }]}>
      <View style={[styles.bubble, mine ? styles.mine : styles.theirs]}>
        <AppText variant="body" color={mine ? colors.onAccent : colors.text}>
          {msg.body}
        </AppText>
        <AppText variant="caption" color={mine ? 'rgba(26,20,0,0.6)' : colors.textFaint} style={styles.time}>
          {faTime(msg.created_at)}
        </AppText>
      </View>
    </View>
  )
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: colors.bg },
  flex: { flex: 1 },
  list: { padding: spacing.md, gap: spacing.sm, flexGrow: 1 },
  bubbleWrap: { width: '100%' },
  bubble: { maxWidth: '82%', borderRadius: radius.md, paddingHorizontal: spacing.md, paddingVertical: spacing.sm },
  mine: { backgroundColor: colors.accent, borderTopRightRadius: 4 },
  theirs: { backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.border, borderTopLeftRadius: 4 },
  time: { marginTop: 2, textAlign: 'left' },
  readOnly: {
    alignItems: 'center',
    padding: spacing.md,
    borderTopWidth: 1,
    borderTopColor: colors.border,
    backgroundColor: colors.surface,
  },
  composer: {
    flexDirection: 'row',
    alignItems: 'flex-end',
    gap: spacing.sm,
    padding: spacing.sm,
    borderTopWidth: 1,
    borderTopColor: colors.border,
    backgroundColor: colors.surface,
  },
  input: {
    flex: 1,
    maxHeight: 120,
    minHeight: 44,
    backgroundColor: colors.surfaceAlt,
    borderRadius: radius.md,
    paddingHorizontal: spacing.md,
    paddingTop: spacing.sm,
    color: colors.text,
    fontSize: 15,
    textAlign: 'right',
  },
  sendBtn: {
    width: 44,
    height: 44,
    borderRadius: radius.pill,
    backgroundColor: colors.accent,
    alignItems: 'center',
    justifyContent: 'center',
  },
})
