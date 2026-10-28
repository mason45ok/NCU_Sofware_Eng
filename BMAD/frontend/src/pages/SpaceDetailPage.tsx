import {
  Alert,
  Anchor,
  Badge,
  Button,
  Card,
  Divider,
  Grid,
  Group,
  Image,
  List,
  Pagination,
  Stack,
  Text,
  Title,
} from '@mantine/core';
import { useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { useFavorites, useMe, useQuote, useReviews, useSpace } from '../api/queries';
import { ErrorAlert, QueryState } from '../components/common';
import { SlotPicker, type PickedRange } from '../components/SlotPicker';
import { FavoriteButton } from '../components/SpaceCard';
import { EQUIPMENT_CATEGORY, SPACE_TYPES, formatLocal, money } from '../lib/format';

function Reviews({ spaceId }: { spaceId: number }) {
  const [page, setPage] = useState(1);
  const reviews = useReviews(spaceId, page);
  return (
    <Stack>
      <Title order={4}>評論</Title>
      <QueryState loading={reviews.isLoading} error={reviews.error}>
        {reviews.data?.items.length === 0 && <Text c="dimmed">尚無評論</Text>}
        {reviews.data?.items.map((r) => (
          <Card key={r.review_id} withBorder padding="sm">
            <Group justify="space-between">
              <Text fw={500}>{r.reviewer}</Text>
              <Text size="sm" c="dimmed">
                {formatLocal(r.created_at)}
              </Text>
            </Group>
            <Text c="caramel.7" aria-label={`${r.rating} 顆星`}>
              {'★'.repeat(r.rating)}
              {'☆'.repeat(5 - r.rating)}
            </Text>
            {r.comment && <Text>{r.comment}</Text>}
          </Card>
        ))}
        <Pagination
          total={Math.ceil((reviews.data?.total ?? 0) / (reviews.data?.page_size ?? 10))}
          value={page}
          onChange={setPage}
        />
      </QueryState>
    </Stack>
  );
}

/** 預約面板（BookingPanel）：價格只顯示後端試算結果，前端不自行計算（BR-07）。 */
function BookingPanel({ spaceId, bookable }: { spaceId: number; bookable: boolean }) {
  const { data: me } = useMe();
  const navigate = useNavigate();
  const [picked, setPicked] = useState<PickedRange | null>(null);
  const quote = useQuote(
    picked
      ? { space_id: spaceId, start_at: picked.start_at, end_at: picked.end_at, attendees: 1 }
      : null,
    !!me && !!picked,
  );

  const go = () => {
    if (!picked) return;
    const dest = `/book/${spaceId}?start=${encodeURIComponent(picked.start_at)}&end=${encodeURIComponent(picked.end_at)}`;
    navigate(me ? dest : `/login?next=${encodeURIComponent(dest)}`);
  };

  return (
    <Card withBorder padding="md">
      <Stack>
        <Title order={4}>選擇日期與時段</Title>
        {!bookable ? (
          <Alert color="yellow">此空間目前暫停開放預約</Alert>
        ) : (
          <>
            <SlotPicker spaceId={spaceId} onPick={setPicked} />
            {picked && (
              <Stack gap={4} aria-live="polite">
                <Text>
                  已選 {formatLocal(picked.start_at)} 起，共 {picked.hours} 小時
                </Text>
                {me ? (
                  <>
                    <ErrorAlert error={quote.error} />
                    {quote.data && (
                      <Text fw={700} fz="lg" c="caramel.7">
                        {money(quote.data.total_amount)}
                      </Text>
                    )}
                  </>
                ) : (
                  <Text size="sm" c="dimmed">
                    登入後可查看金額並預約
                  </Text>
                )}
              </Stack>
            )}
            <Button disabled={!picked || (!!me && !quote.data)} onClick={go}>
              {me ? '預約' : '登入後預約'}
            </Button>
          </>
        )}
      </Stack>
    </Card>
  );
}

export function SpaceDetailPage() {
  const id = Number(useParams().id);
  const space = useSpace(id);
  const { data: me } = useMe();
  const favorites = useFavorites(!!me);
  const d = space.data;
  const isFavorite = !!favorites.data?.items.some((s) => s.space_id === id);

  return (
    <QueryState loading={space.isLoading} error={space.error}>
      {d && (
        <Grid gutter="lg">
          <Grid.Col span={{ base: 12, md: 7 }}>
            <Stack>
              <Group justify="space-between" wrap="nowrap">
                <Title order={2}>
                  {d.branch.name} {d.name}
                </Title>
                <FavoriteButton spaceId={id} active={isFavorite} />
              </Group>
              {d.status !== 'AVAILABLE' && (
                <Badge color="gray" w="fit-content">
                  已下架／暫停開放
                </Badge>
              )}
              <Group gap="xs" style={{ overflowX: 'auto' }} wrap="nowrap">
                {d.photos.length === 0 && (
                  <Image
                    h={240}
                    src={null}
                    alt="尚無照片"
                    fallbackSrc="https://placehold.co/600x320?text=%E5%B0%9A%E7%84%A1%E7%85%A7%E7%89%87"
                  />
                )}
                {d.photos.map((p) => (
                  <Image
                    key={p.photo_id}
                    src={p.image_url}
                    h={240}
                    w="auto"
                    radius="md"
                    alt={p.caption ?? d.name}
                  />
                ))}
              </Group>
              <Group>
                <Badge variant="light">{SPACE_TYPES[d.space_type]}</Badge>
                <Text>容納 {d.capacity} 人</Text>
                {d.area && <Text>{d.area} 坪</Text>}
                <Text fw={700} c="caramel.7">
                  {money(d.hourly_price)} / 小時
                </Text>
                <Text c="dimmed">
                  {d.avg_rating ? `★ ${d.avg_rating}（${d.review_count} 則）` : '尚無評價'}
                </Text>
              </Group>
              {d.description && <Text>{d.description}</Text>}
              <Divider />
              <Title order={4}>設備</Title>
              {d.equipment.length === 0 ? (
                <Text c="dimmed">未提供設備資訊</Text>
              ) : (
                <List>
                  {d.equipment.map((e) => (
                    <List.Item key={e.equipment_id}>
                      {e.name} × {e.quantity}
                      {e.note ? `（${e.note}）` : ''}{' '}
                      <Text span size="xs" c="dimmed">
                        {EQUIPMENT_CATEGORY[e.category]}
                      </Text>
                    </List.Item>
                  ))}
                </List>
              )}
              <Title order={4}>使用規定</Title>
              <Text style={{ whiteSpace: 'pre-wrap' }}>{d.rules || '無'}</Text>
              <Title order={4}>取消規則</Title>
              <List>
                {d.cancel_policy.map((t) => (
                  <List.Item key={t}>{t}</List.Item>
                ))}
              </List>
              <Title order={4}>場館資訊</Title>
              <Text>
                {d.branch.city}
                {d.branch.district}
                {d.branch.address}（營業 {d.branch.open_hour}:00–{d.branch.close_hour}:00）
              </Text>
              <Text>
                電話：{d.branch.phone}{' '}
                <Anchor href={d.branch.maps_url} target="_blank" rel="noreferrer">
                  在 Google Maps 開啟
                </Anchor>
              </Text>
              <Divider />
              <Reviews spaceId={id} />
            </Stack>
          </Grid.Col>
          <Grid.Col span={{ base: 12, md: 5 }}>
            <BookingPanel spaceId={id} bookable={d.bookable} />
            {!me && (
              <Text size="sm" mt="sm">
                <Anchor component={Link} to="/login">
                  登入
                </Anchor>
                後可收藏與預約
              </Text>
            )}
          </Grid.Col>
        </Grid>
      )}
    </QueryState>
  );
}
