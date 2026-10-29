import { Button, SimpleGrid, Text } from '@mantine/core';
import type { Slot } from '../api/types';

export interface Selection {
  start: number;
  end: number; // 不含
}

/** 純邏輯：點第一格為開始、再點一格為結束，中間自動連續選取；遇到不可選的格子則改為重新選取。 */
export function nextSelection(
  slots: Slot[],
  current: Selection | null,
  hour: number,
): Selection | null {
  const target = slots.find((s) => s.start === hour);
  if (!target || target.status !== 'AVAILABLE') return current;
  if (!current || current.end - current.start > 1) return { start: hour, end: hour + 1 };
  if (hour === current.start) return null;
  if (hour < current.start) return { start: hour, end: hour + 1 };
  const between = slots.filter((s) => s.start >= current.start && s.start <= hour);
  if (between.some((s) => s.status !== 'AVAILABLE')) return { start: hour, end: hour + 1 };
  return { start: current.start, end: hour + 1 };
}

const LABEL: Record<Slot['status'], string> = {
  AVAILABLE: '可預約',
  BOOKED: '已被預約',
  PAST: '已過去',
};

/** SlotGrid 只負責顯示與選取，不計算金額（BR-07）。 */
export function SlotGrid({
  slots,
  selection,
  onChange,
}: {
  slots: Slot[];
  selection: Selection | null;
  onChange: (s: Selection | null) => void;
}) {
  return (
    <SimpleGrid cols={{ base: 3, sm: 4, md: 6 }} spacing="xs" role="group" aria-label="可預約時段">
      {slots.map((s) => {
        const selected = !!selection && s.start >= selection.start && s.start < selection.end;
        const disabled = s.status !== 'AVAILABLE';
        return (
          <Button
            key={s.start}
            size="sm"
            variant={selected ? 'filled' : disabled ? 'default' : 'light'}
            color={selected ? 'caramel' : disabled ? 'gray' : 'olive'}
            disabled={disabled}
            aria-pressed={selected}
            aria-label={`${String(s.start).padStart(2, '0')}:00，${LABEL[s.status]}`}
            onClick={() => onChange(nextSelection(slots, selection, s.start))}
            styles={{ label: { flexDirection: 'column', lineHeight: 1.2 } }}
          >
            <span>{String(s.start).padStart(2, '0')}:00</span>
            <Text span size="xs">
              {selected ? '已選' : LABEL[s.status]}
            </Text>
          </Button>
        );
      })}
    </SimpleGrid>
  );
}
