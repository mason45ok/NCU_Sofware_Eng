import { ActionIcon, Badge, Card, Group, Image, Text } from '@mantine/core';
import { Link } from 'react-router-dom';
import { useMe, useToggleFavorite } from '../api/queries';
import type { SpaceSummary } from '../api/types';
import { SPACE_TYPES, money } from '../lib/format';

export function FavoriteButton({ spaceId, active }: { spaceId: number; active: boolean }) {
  const { data: me } = useMe();
  const toggle = useToggleFavorite();
  if (!me) return null;
  return (
    <ActionIcon
      variant={active ? 'filled' : 'default'}
      color="caramel"
      aria-label={active ? '取消收藏' : '加入收藏'}
      aria-pressed={active}
      onClick={() => toggle.mutate({ id: spaceId, on: !active })}
      loading={toggle.isPending}
    >
      {active ? '♥' : '♡'}
    </ActionIcon>
  );
}

export function SpaceCard({ space, soldOut }: { space: SpaceSummary; soldOut?: boolean }) {
  const offline = soldOut ?? space.status !== 'AVAILABLE';
  return (
    <Card withBorder padding="sm" component={Link} to={`/spaces/${space.space_id}`}>
      <Card.Section>
        <Image
          src={space.cover_url}
          h={160}
          alt={`${space.name} 封面`}
          fallbackSrc="https://placehold.co/600x320?text=%E8%81%9A%E9%BB%9E"
        />
      </Card.Section>
      <Group justify="space-between" mt="sm" wrap="nowrap">
        <Text fw={700} lineClamp={1}>
          {space.branch_name} {space.name}
        </Text>
        {offline && <Badge color="gray">已下架</Badge>}
      </Group>
      <Group gap="xs" mt={4}>
        <Badge variant="light">{SPACE_TYPES[space.space_type]}</Badge>
        <Text size="sm" c="dimmed">
          {space.city}
          {space.district} · 容納 {space.capacity} 人
        </Text>
      </Group>
      <Group justify="space-between" mt="xs">
        <Text fw={700} c="caramel.7">
          {money(space.hourly_price)} / 小時
        </Text>
        <Text size="sm" c="dimmed">
          {space.avg_rating ? `★ ${space.avg_rating}（${space.review_count}）` : '尚無評價'}
          {space.distance_km != null && ` · ${space.distance_km} 公里`}
        </Text>
      </Group>
    </Card>
  );
}
