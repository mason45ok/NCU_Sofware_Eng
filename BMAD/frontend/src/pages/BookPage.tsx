import { zodResolver } from '@hookform/resolvers/zod';
import {
  Alert,
  Anchor,
  Button,
  Card,
  List,
  NumberInput,
  Stack,
  Text,
  Textarea,
  Title,
} from '@mantine/core';
import { useMutation } from '@tanstack/react-query';
import { Controller, useForm } from 'react-hook-form';
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { z } from 'zod';
import { api } from '../api/client';
import { useMe, useQuote, useSpace } from '../api/queries';
import type { Booking } from '../api/types';
import { ErrorAlert, QueryState } from '../components/common';
import { formatRange, money } from '../lib/format';

const schema = z.object({
  attendees: z.number({ invalid_type_error: '請輸入使用人數' }).int().min(1, '至少 1 人'),
  note: z.string().max(500, '備註最多 500 字').optional(),
});
type Values = z.infer<typeof schema>;

/** 預約確認頁（FR-20、21）：金額由後端試算 API 回傳。 */
export function BookPage() {
  const spaceId = Number(useParams().spaceId);
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const start = params.get('start') ?? '';
  const end = params.get('end') ?? '';
  const space = useSpace(spaceId);
  const { data: me } = useMe();
  const form = useForm<Values>({
    resolver: zodResolver(schema),
    defaultValues: { attendees: 1, note: '' },
  });
  const attendees = form.watch('attendees');
  const valid = !!start && !!end;
  const quote = useQuote(
    valid
      ? { space_id: spaceId, start_at: start, end_at: end, attendees: Number(attendees) || 1 }
      : null,
    valid,
  );

  const create = useMutation({
    mutationFn: (v: Values) =>
      api.post<Booking>('/bookings', {
        space_id: spaceId,
        start_at: start,
        end_at: end,
        attendees: v.attendees,
        note: v.note || null,
      }),
    onSuccess: (b) => navigate(`/bookings/${b.booking_id}/pay`),
  });

  return (
    <QueryState loading={space.isLoading} error={space.error}>
      <Stack maw={560} mx="auto">
        <Title order={2}>確認預約</Title>
        {!valid && (
          <Alert color="red">
            請先回到空間頁選擇時段。
            <Anchor component={Link} to={`/spaces/${spaceId}`}>
              回到空間頁
            </Anchor>
          </Alert>
        )}
        {me && !me.email_verified && (
          <Alert color="yellow" title="尚未驗證 email" role="alert">
            請先到信箱點擊驗證連結後再預約。
          </Alert>
        )}
        {space.data && valid && (
          <Card withBorder>
            <Text fw={700}>
              {space.data.branch.name} {space.data.name}
            </Text>
            <Text>{formatRange(start, end)}</Text>
          </Card>
        )}
        <form onSubmit={form.handleSubmit((v) => create.mutate(v))}>
          <Stack>
            <Controller
              control={form.control}
              name="attendees"
              render={({ field, fieldState }) => (
                <NumberInput
                  label="使用人數"
                  min={1}
                  max={space.data?.capacity}
                  description={`此空間最多容納 ${space.data?.capacity} 人`}
                  {...field}
                  error={fieldState.error?.message}
                />
              )}
            />
            <Textarea
              label="使用目的與備註（選填）"
              maxLength={500}
              {...form.register('note')}
              error={form.formState.errors.note?.message}
            />
            <Card withBorder aria-live="polite">
              <ErrorAlert error={quote.error} />
              {quote.data && (
                <Stack gap={4}>
                  <Text>時數：{quote.data.hours} 小時</Text>
                  <Text>時租：{money(quote.data.hourly_price)}</Text>
                  <Text fw={700} fz="lg" c="caramel.7">
                    總金額：{money(quote.data.total_amount)}
                  </Text>
                  <Text size="sm" c="dimmed">
                    建立訂單後須於 {quote.data.payment_deadline_minutes}{' '}
                    分鐘內付款，逾時將自動失效。
                  </Text>
                  <Text size="sm" fw={500} mt="xs">
                    取消規則
                  </Text>
                  <List size="sm">
                    {quote.data.cancel_policy.map((t) => (
                      <List.Item key={t}>{t}</List.Item>
                    ))}
                  </List>
                </Stack>
              )}
            </Card>
            <ErrorAlert error={create.error} />
            {create.error && (create.error as { code?: string }).code === 'SLOT_TAKEN' && (
              <Anchor component={Link} to={`/spaces/${spaceId}`}>
                重新選擇時段
              </Anchor>
            )}
            <Button type="submit" loading={create.isPending} disabled={!valid || !quote.data}>
              送出預約並前往付款
            </Button>
          </Stack>
        </form>
      </Stack>
    </QueryState>
  );
}
