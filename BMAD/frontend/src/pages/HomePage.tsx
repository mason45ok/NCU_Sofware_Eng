import {
  Button,
  Group,
  NativeSelect,
  NumberInput,
  SimpleGrid,
  Stack,
  Text,
  TextInput,
  Title,
} from '@mantine/core';
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useFilterOptions, useSpaces } from '../api/queries';
import { QueryState, toast } from '../components/common';
import { SpaceCard } from '../components/SpaceCard';
import { addDays, todayLocal } from '../lib/format';

export function HomePage() {
  const navigate = useNavigate();
  const { data: options } = useFilterOptions();
  const featured = useSpaces({ page_size: 6 });
  const [city, setCity] = useState('');
  const [people, setPeople] = useState<number | string>('');
  const [date, setDate] = useState('');

  const search = () => {
    const sp = new URLSearchParams();
    if (city) sp.set('city', city);
    if (people) sp.set('people', String(people));
    if (date) sp.set('date', date);
    navigate(`/spaces?${sp.toString()}`);
  };

  const nearby = () => {
    if (!navigator.geolocation) return toast('此瀏覽器不支援定位，請改用手動搜尋', 'red');
    navigator.geolocation.getCurrentPosition(
      (pos) => navigate(`/spaces?lat=${pos.coords.latitude}&lng=${pos.coords.longitude}`),
      () => toast('無法取得定位，請允許定位權限或改用手動搜尋', 'red'),
    );
  };

  return (
    <Stack gap="xl">
      <Stack gap="xs" py="lg">
        <Title order={1}>找一個適合聚會的空間</Title>
        <Text c="dimmed">讀書會、小組討論、慶生、工作坊——線上預約，取得房間密碼自助入場。</Text>
      </Stack>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          search();
        }}
      >
        <SimpleGrid cols={{ base: 1, sm: 4 }} spacing="sm">
          <NativeSelect
            label="縣市"
            value={city}
            onChange={(e) => setCity(e.currentTarget.value)}
            data={['', ...Object.keys(options?.cities ?? {})]}
          />
          <NumberInput label="人數" min={1} value={people} onChange={setPeople} />
          <TextInput
            label="日期"
            type="date"
            value={date}
            min={todayLocal()}
            max={addDays(todayLocal(), 60)}
            onChange={(e) => setDate(e.currentTarget.value)}
          />
          <Group align="end" grow>
            <Button type="submit">搜尋</Button>
            <Button variant="default" onClick={nearby}>
              附近的空間
            </Button>
          </Group>
        </SimpleGrid>
      </form>
      <Stack>
        <Title order={3}>精選空間</Title>
        <QueryState loading={featured.isLoading} error={featured.error}>
          <SimpleGrid cols={{ base: 1, sm: 2, md: 3 }}>
            {featured.data?.items.map((s) => (
              <SpaceCard key={s.space_id} space={s} />
            ))}
          </SimpleGrid>
        </QueryState>
      </Stack>
    </Stack>
  );
}
