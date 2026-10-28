import {
  Button,
  Checkbox,
  Collapse,
  Group,
  NativeSelect,
  NumberInput,
  Pagination,
  SimpleGrid,
  Stack,
  Text,
  TextInput,
  Title,
} from '@mantine/core';
import { useDisclosure } from '@mantine/hooks';
import { useSearchParams } from 'react-router-dom';
import { useFilterOptions, useSpaces } from '../api/queries';
import { Empty, QueryState } from '../components/common';
import { SpaceCard } from '../components/SpaceCard';
import { SPACE_TYPES, addDays, todayLocal } from '../lib/format';

const SORTS = [
  ['', '預設'],
  ['price_asc', '價格低到高'],
  ['price_desc', '價格高到低'],
  ['capacity_desc', '容量大到小'],
  ['capacity_asc', '容量小到大'],
  ['distance', '距離近到遠'],
] as const;

/** 搜尋條件存在網址參數，重新整理或分享連結都能還原。 */
export function SpacesPage() {
  const [params, setParams] = useSearchParams();
  const [open, { toggle }] = useDisclosure(true);
  const { data: options } = useFilterOptions();
  const get = (k: string) => params.get(k) ?? '';
  const set = (k: string, v: string) => {
    const next = new URLSearchParams(params);
    if (v) next.set(k, v);
    else next.delete(k);
    next.delete('page');
    setParams(next);
  };
  const equipment = get('equipment') ? get('equipment').split(',') : [];
  const query = Object.fromEntries(params.entries());
  const spaces = useSpaces(query);
  const hasGeo = !!get('lat') && !!get('lng');
  const districts = options?.cities[get('city')] ?? [];

  return (
    <Stack>
      <Group justify="space-between">
        <Title order={2}>找空間</Title>
        <Button variant="default" onClick={toggle} aria-expanded={open}>
          {open ? '收合篩選' : '展開篩選'}
        </Button>
      </Group>
      <Collapse in={open}>
        <SimpleGrid cols={{ base: 1, sm: 2, md: 4 }} spacing="sm">
          <NativeSelect
            label="縣市"
            value={get('city')}
            onChange={(e) => {
              set('district', '');
              set('city', e.currentTarget.value);
            }}
            data={['', ...Object.keys(options?.cities ?? {})]}
          />
          <NativeSelect
            label="行政區"
            value={get('district')}
            onChange={(e) => set('district', e.currentTarget.value)}
            data={['', ...districts]}
            disabled={!get('city')}
          />
          <NumberInput
            label="人數"
            min={1}
            value={get('people')}
            onChange={(v) => set('people', String(v ?? ''))}
          />
          <NativeSelect
            label="空間類型"
            value={get('type')}
            onChange={(e) => set('type', e.currentTarget.value)}
            data={[
              { value: '', label: '全部' },
              ...(options?.space_types ?? []).map((t) => ({ value: t, label: SPACE_TYPES[t] })),
            ]}
          />
          <NumberInput
            label="最低時租"
            min={0}
            value={get('min_price')}
            onChange={(v) => set('min_price', String(v ?? ''))}
          />
          <NumberInput
            label="最高時租"
            min={0}
            value={get('max_price')}
            onChange={(v) => set('max_price', String(v ?? ''))}
          />
          <TextInput
            label="日期"
            type="date"
            value={get('date')}
            min={todayLocal()}
            max={addDays(todayLocal(), 60)}
            onChange={(e) => set('date', e.currentTarget.value)}
          />
          <Group grow align="end">
            <NativeSelect
              label="開始"
              value={get('start')}
              onChange={(e) => set('start', e.currentTarget.value)}
              data={['', ...Array.from({ length: 24 }, (_, h) => String(h))]}
            />
            <NativeSelect
              label="結束"
              value={get('end')}
              onChange={(e) => set('end', e.currentTarget.value)}
              data={['', ...Array.from({ length: 24 }, (_, h) => String(h + 1))]}
            />
          </Group>
        </SimpleGrid>
        <Checkbox.Group
          label="設備（須全部具備）"
          mt="sm"
          value={equipment}
          onChange={(v) => set('equipment', v.join(','))}
        >
          <Group mt="xs">
            {options?.equipment.map((e) => (
              <Checkbox key={e.equipment_id} value={String(e.equipment_id)} label={e.name} />
            ))}
          </Group>
        </Checkbox.Group>
        <Group mt="sm">
          <NativeSelect
            label="排序"
            value={get('sort')}
            onChange={(e) => set('sort', e.currentTarget.value)}
            data={SORTS.filter(([v]) => v !== 'distance' || hasGeo).map(([value, label]) => ({
              value,
              label,
            }))}
          />
          <Button variant="subtle" onClick={() => setParams({})}>
            清除條件
          </Button>
        </Group>
        {hasGeo && (
          <Text size="sm" c="dimmed" mt="xs">
            顯示您 5 公里內的空間，依距離排序。
          </Text>
        )}
      </Collapse>
      <QueryState loading={spaces.isLoading} error={spaces.error}>
        {spaces.data && spaces.data.items.length === 0 ? (
          <Empty text="找不到符合條件的空間，請調整篩選條件" />
        ) : (
          <>
            <Text size="sm" c="dimmed">
              共 {spaces.data?.total} 個空間
            </Text>
            <SimpleGrid cols={{ base: 1, sm: 2, md: 3 }}>
              {spaces.data?.items.map((s) => (
                <SpaceCard key={s.space_id} space={s} soldOut={false} />
              ))}
            </SimpleGrid>
            <Pagination
              total={Math.ceil((spaces.data?.total ?? 0) / (spaces.data?.page_size ?? 12))}
              value={Number(get('page') || 1)}
              onChange={(p) => {
                const n = new URLSearchParams(params);
                n.set('page', String(p));
                setParams(n);
              }}
            />
          </>
        )}
      </QueryState>
    </Stack>
  );
}
