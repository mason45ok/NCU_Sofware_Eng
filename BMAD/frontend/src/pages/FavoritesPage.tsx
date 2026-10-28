import { SimpleGrid, Stack, Title } from '@mantine/core';
import { useFavorites } from '../api/queries';
import { Empty, QueryState } from '../components/common';
import { FavoriteButton, SpaceCard } from '../components/SpaceCard';

export function FavoritesPage() {
  const favorites = useFavorites(true);
  return (
    <Stack>
      <Title order={2}>我的收藏</Title>
      <QueryState loading={favorites.isLoading} error={favorites.error}>
        {favorites.data?.items.length === 0 && <Empty text="還沒有收藏的空間" />}
        <SimpleGrid cols={{ base: 1, sm: 2, md: 3 }}>
          {favorites.data?.items.map((s) => (
            <Stack key={s.space_id} gap={4}>
              <SpaceCard space={s} />
              <FavoriteButton spaceId={s.space_id} active />
            </Stack>
          ))}
        </SimpleGrid>
      </QueryState>
    </Stack>
  );
}
