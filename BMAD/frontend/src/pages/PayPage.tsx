import { Alert, Anchor, Button, Card, Radio, Stack, Text, TextInput, Title } from '@mantine/core';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useRef, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { ApiError, api, newKey } from '../api/client';
import { useBooking } from '../api/queries';
import type { PayResult } from '../api/types';
import { ErrorAlert, QueryState, StatusBadge, useCountdown } from '../components/common';
import { formatRange, money } from '../lib/format';

/** 模擬付款頁（FR-22）：每次操作一個 Idempotency-Key，收到結果後才換新的鍵。 */
export function PayPage() {
  const id = Number(useParams().id);
  const navigate = useNavigate();
  const qc = useQueryClient();
  const booking = useBooking(id);
  const b = booking.data;
  const left = useCountdown(b?.expires_at);
  const [method, setMethod] = useState('CREDIT_CARD');
  const [card, setCard] = useState('');
  const [declined, setDeclined] = useState(false);
  const key = useRef(newKey());

  const pay = useMutation({
    mutationFn: () =>
      api.post<PayResult>(
        `/bookings/${id}/pay`,
        { method, card_no: method === 'CREDIT_CARD' ? card || null : null },
        { 'Idempotency-Key': key.current },
      ),
    onSuccess: (r) => {
      key.current = newKey();
      qc.invalidateQueries({ queryKey: ['booking', id] });
      if (r.status === 'SUCCESS') navigate(`/me/bookings/${id}`, { replace: true });
      else setDeclined(true);
    },
    onError: (e) => {
      if (e instanceof ApiError && e.code !== 'IDEMPOTENCY_KEY_REUSED') key.current = newKey();
      qc.invalidateQueries({ queryKey: ['booking', id] });
    },
  });

  const expired = b?.status === 'EXPIRED' || (b?.status === 'PENDING_PAYMENT' && left === 0);

  return (
    <QueryState loading={booking.isLoading} error={booking.error}>
      {b && (
        <Stack maw={520} mx="auto">
          <Title order={2}>付款</Title>
          <Card withBorder>
            <Text fw={700}>
              {b.branch_name} {b.space_name} <StatusBadge status={b.status} />
            </Text>
            <Text>{formatRange(b.start_at, b.end_at)}</Text>
            <Text fw={700} fz="lg" c="caramel.7">
              {money(b.total_amount)}
            </Text>
            <Text size="sm" c="dimmed">
              訂單編號 {b.booking_no}
            </Text>
          </Card>
          {b.status === 'CONFIRMED' ? (
            <Alert color="olive">
              此訂單已付款完成。
              <Anchor component={Link} to={`/me/bookings/${id}`}>
                查看訂單
              </Anchor>
            </Alert>
          ) : expired ? (
            <Alert color="red" title="訂單已失效" role="alert">
              超過付款期限，請重新預約。
              <Anchor component={Link} to={`/spaces/${b.space_id}`}>
                回到空間頁
              </Anchor>
            </Alert>
          ) : b.status !== 'PENDING_PAYMENT' ? (
            <Alert color="gray">此訂單目前無法付款。</Alert>
          ) : (
            <>
              <Alert color={left < 120 ? 'red' : 'yellow'} role="timer" aria-live="off">
                請在 {String(Math.floor(left / 60)).padStart(2, '0')}:
                {String(left % 60).padStart(2, '0')} 內完成付款
              </Alert>
              <Radio.Group label="付款方式" value={method} onChange={setMethod}>
                <Stack mt="xs" gap="xs">
                  <Radio value="CREDIT_CARD" label="信用卡（模擬）" />
                  <Radio value="LINE_PAY" label="LINE Pay（模擬）" />
                </Stack>
              </Radio.Group>
              {method === 'CREDIT_CARD' && (
                <TextInput
                  label="卡號"
                  placeholder="4242 4242 4242 4242"
                  value={card}
                  onChange={(e) => setCard(e.currentTarget.value)}
                  inputMode="numeric"
                  autoComplete="off"
                  description="示範用：4000 0000 0000 0002 一律遭拒，可測試付款失敗與重付"
                />
              )}
              {declined && (
                <Alert color="red" title="卡片遭拒" role="alert">
                  付款未成功，訂單仍保留，請更換卡號或付款方式後重試。
                </Alert>
              )}
              <ErrorAlert error={pay.error} />
              <Button
                loading={pay.isPending}
                onClick={() => {
                  setDeclined(false);
                  pay.mutate();
                }}
              >
                確認付款 {money(b.total_amount)}
              </Button>
            </>
          )}
        </Stack>
      )}
    </QueryState>
  );
}
