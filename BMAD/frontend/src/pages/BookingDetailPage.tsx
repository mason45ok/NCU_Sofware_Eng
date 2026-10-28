import {
  Alert,
  Anchor,
  Button,
  Card,
  Group,
  Modal,
  NativeSelect,
  Rating,
  Stack,
  Table,
  Text,
  Textarea,
  TextInput,
  Title,
} from '@mantine/core';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useRef, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { api, newKey } from '../api/client';
import { useBooking } from '../api/queries';
import type { Booking, RefundQuote, RescheduleQuote } from '../api/types';
import { ErrorAlert, QueryState, StatusBadge, toast } from '../components/common';
import { SlotPicker, type PickedRange } from '../components/SlotPicker';
import { ACCESS_STATE, formatLocal, formatRange, money } from '../lib/format';

function useRefresh(id: number) {
  const qc = useQueryClient();
  return () => {
    qc.invalidateQueries({ queryKey: ['booking', id] });
    qc.invalidateQueries({ queryKey: ['my-bookings'] });
  };
}

/** 取消：確認前顯示預計退款金額與比例（FR-32）。 */
function CancelModal({ b, opened, onClose }: { b: Booking; opened: boolean; onClose: () => void }) {
  const refresh = useRefresh(b.booking_id);
  const quote = useQuery({
    queryKey: ['cancel-quote', b.booking_id],
    queryFn: () => api.get<RefundQuote>(`/bookings/${b.booking_id}/cancel-quote`),
    enabled: opened,
    gcTime: 0,
  });
  const cancel = useMutation({
    mutationFn: () => api.post(`/bookings/${b.booking_id}/cancel`),
    onSuccess: () => {
      toast('訂單已取消');
      refresh();
      onClose();
    },
  });
  return (
    <Modal opened={opened} onClose={onClose} title="取消訂單">
      <QueryState loading={quote.isLoading} error={quote.error}>
        {quote.data && (
          <Stack>
            <Text>
              {quote.data.refund_amount > 0
                ? `將退款 ${money(quote.data.refund_amount)}（${quote.data.note}）`
                : '此次取消不會退款'}
            </Text>
            <Text size="sm" c="dimmed">
              {quote.data.note}。取消後房間密碼將立即失效。
            </Text>
            <ErrorAlert error={cancel.error} />
            <Group justify="end">
              <Button variant="default" onClick={onClose}>
                返回
              </Button>
              <Button color="red" loading={cancel.isPending} onClick={() => cancel.mutate()}>
                確認取消
              </Button>
            </Group>
          </Stack>
        )}
      </QueryState>
    </Modal>
  );
}

/** 改期：選新時段 → 顯示價差 → 補付或退差額（FR-33）。 */
function RescheduleModal({
  b,
  opened,
  onClose,
}: {
  b: Booking;
  opened: boolean;
  onClose: () => void;
}) {
  const refresh = useRefresh(b.booking_id);
  const [range, setRange] = useState<PickedRange | null>(null);
  const [method, setMethod] = useState('CREDIT_CARD');
  const [card, setCard] = useState('');
  const key = useRef(newKey());
  const body = range && { start_at: range.start_at, end_at: range.end_at };
  const quote = useQuery({
    queryKey: ['reschedule-quote', b.booking_id, body],
    queryFn: () => api.post<RescheduleQuote>(`/bookings/${b.booking_id}/reschedule-quote`, body),
    enabled: opened && !!body,
    retry: false,
  });
  const submit = useMutation({
    mutationFn: () =>
      api.post(
        `/bookings/${b.booking_id}/reschedule`,
        {
          ...body,
          method: quote.data?.requires_payment ? method : null,
          card_no: method === 'CREDIT_CARD' ? card || null : null,
        },
        { 'Idempotency-Key': key.current },
      ),
    onSuccess: () => {
      toast('已完成改期');
      refresh();
      onClose();
    },
    onError: () => {
      key.current = newKey();
    },
  });
  const q = quote.data;
  return (
    <Modal opened={opened} onClose={onClose} title="改期" size="lg">
      <Stack>
        <Text size="sm" c="dimmed">
          原時段：{formatRange(b.start_at, b.end_at)}。每筆訂單限改期 1 次，須在原開始時間 24
          小時前。
        </Text>
        <SlotPicker spaceId={b.space_id} onPick={setRange} />
        <ErrorAlert error={quote.error} />
        {q && (
          <Alert color={q.diff > 0 ? 'yellow' : 'olive'} aria-live="polite">
            新金額 {money(q.new_amount)}（原 {money(q.old_amount)}）：
            {q.diff > 0
              ? `需補付 ${money(q.diff)}`
              : q.diff < 0
                ? `將退款 ${money(q.refund_amount)}`
                : '無價差'}
          </Alert>
        )}
        {q?.requires_payment && (
          <>
            <NativeSelect
              label="補付方式"
              value={method}
              onChange={(e) => setMethod(e.currentTarget.value)}
              data={[
                { value: 'CREDIT_CARD', label: '信用卡（模擬）' },
                { value: 'LINE_PAY', label: 'LINE Pay（模擬）' },
              ]}
            />
            {method === 'CREDIT_CARD' && (
              <TextInput
                label="卡號"
                value={card}
                onChange={(e) => setCard(e.currentTarget.value)}
                placeholder="4242 4242 4242 4242"
              />
            )}
          </>
        )}
        <ErrorAlert error={submit.error} />
        <Group justify="end">
          <Button variant="default" onClick={onClose}>
            返回
          </Button>
          <Button disabled={!q} loading={submit.isPending} onClick={() => submit.mutate()}>
            確認改期
          </Button>
        </Group>
      </Stack>
    </Modal>
  );
}

function ReviewForm({ b }: { b: Booking }) {
  const refresh = useRefresh(b.booking_id);
  const [rating, setRating] = useState(5);
  const [comment, setComment] = useState('');
  const submit = useMutation({
    mutationFn: () =>
      api.post(`/bookings/${b.booking_id}/review`, { rating, comment: comment || null }),
    onSuccess: () => {
      toast('感謝您的評論');
      refresh();
    },
  });
  return (
    <Card withBorder>
      <Stack>
        <Title order={4}>撰寫評論</Title>
        <Rating value={rating} onChange={setRating} aria-label="評分" />
        <Textarea
          label="評論內容（選填）"
          maxLength={500}
          value={comment}
          onChange={(e) => setComment(e.currentTarget.value)}
        />
        <ErrorAlert error={submit.error} />
        <Button w="fit-content" loading={submit.isPending} onClick={() => submit.mutate()}>
          送出評論
        </Button>
      </Stack>
    </Card>
  );
}

export function BookingDetailPage() {
  const id = Number(useParams().id);
  const booking = useBooking(id);
  const b = booking.data;
  const [cancelOpen, setCancelOpen] = useState(false);
  const [moveOpen, setMoveOpen] = useState(false);

  return (
    <QueryState loading={booking.isLoading} error={booking.error}>
      {b && (
        <Stack maw={680} mx="auto">
          <Group justify="space-between">
            <Title order={2}>訂單 {b.booking_no}</Title>
            <StatusBadge status={b.status} />
          </Group>
          <Card withBorder>
            <Stack gap={4}>
              <Text fw={700}>
                {b.branch_name} {b.space_name}
              </Text>
              <Text>
                {formatRange(b.start_at, b.end_at)}（{b.hours} 小時，{b.attendees} 人）
              </Text>
              <Text>
                金額：{money(b.total_amount)} 實收：{money(b.net_paid)}
              </Text>
              {b.note && <Text size="sm">備註：{b.note}</Text>}
              <Text size="sm">
                地址：{b.branch_address} 電話：{b.branch_phone}
              </Text>
              {b.cancel_reason && (
                <Text size="sm" c="red">
                  取消原因：{b.cancel_reason}
                </Text>
              )}
            </Stack>
          </Card>

          {b.status === 'PENDING_PAYMENT' && (
            <Alert color="yellow">
              此訂單尚未付款。
              <Anchor component={Link} to={`/bookings/${b.booking_id}/pay`}>
                前往付款
              </Anchor>
            </Alert>
          )}

          {b.access_code && (
            <Card withBorder aria-live="polite">
              <Title order={4}>房間密碼</Title>
              {b.access_code.state === 'VALID' ? (
                <Text fz={36} fw={700} ff="monospace" c="caramel.7">
                  {b.access_code.code}
                </Text>
              ) : (
                <Text>
                  {ACCESS_STATE[b.access_code.state]}
                  {b.access_code.state === 'NOT_YET_VALID' &&
                    `（將於 ${formatLocal(b.access_code.valid_from)} 生效）`}
                </Text>
              )}
              <Text size="sm" c="dimmed">
                有效時間：{formatLocal(b.access_code.valid_from)} ～{' '}
                {formatLocal(b.access_code.valid_until)}
              </Text>
              {b.entry_guide && (
                <Text size="sm" mt="xs" style={{ whiteSpace: 'pre-wrap' }}>
                  進入方式：{b.entry_guide}
                </Text>
              )}
            </Card>
          )}

          <Card withBorder>
            <Title order={4}>付款與退款紀錄</Title>
            {b.payments.length === 0 ? (
              <Text c="dimmed">無紀錄</Text>
            ) : (
              <Table>
                <Table.Tbody>
                  {b.payments.map((p) => (
                    <Table.Tr key={p.payment_id}>
                      <Table.Td>{formatLocal(p.created_at)}</Table.Td>
                      <Table.Td>{p.type === 'PAYMENT' ? '付款' : '退款'}</Table.Td>
                      <Table.Td>{money(p.amount)}</Table.Td>
                      <Table.Td>{p.status === 'SUCCESS' ? '成功' : '失敗（卡片遭拒）'}</Table.Td>
                    </Table.Tr>
                  ))}
                </Table.Tbody>
              </Table>
            )}
          </Card>

          <Group>
            {b.can_reschedule && (
              <Button variant="default" onClick={() => setMoveOpen(true)}>
                改期
              </Button>
            )}
            {b.can_cancel && (
              <Button color="red" variant="outline" onClick={() => setCancelOpen(true)}>
                取消訂單
              </Button>
            )}
          </Group>
          {b.status === 'CONFIRMED' && !b.can_reschedule && b.reschedule_count === 0 && (
            <Text size="sm" c="dimmed">
              距離開始不足 24 小時，無法改期；如需協助請聯絡客服。
            </Text>
          )}
          {b.reschedule_count > 0 && (
            <Text size="sm" c="dimmed">
              此訂單已改期 1 次，無法再改期。
            </Text>
          )}
          {b.can_review && <ReviewForm b={b} />}
          {b.reviewed && <Alert color="olive">您已評論過此訂單，謝謝！</Alert>}

          <CancelModal b={b} opened={cancelOpen} onClose={() => setCancelOpen(false)} />
          <RescheduleModal b={b} opened={moveOpen} onClose={() => setMoveOpen(false)} />
        </Stack>
      )}
    </QueryState>
  );
}
