import { Alert, Stack, Text, TextInput } from '@mantine/core';
import { useEffect, useState } from 'react';
import { useAvailability } from '../api/queries';
import { addDays, todayLocal } from '../lib/format';
import { QueryState } from './common';
import { SlotGrid, type Selection } from './SlotGrid';

export interface PickedRange {
  start_at: string;
  end_at: string;
  hours: number;
}

const REASON: Record<string, string> = {
  UNAVAILABLE: '此空間目前暫停開放',
  OUT_OF_RANGE: '超出可預約範圍（今天起 60 天內）',
};

/** 日期選擇器＋時段格（D13）。只負責顯示與選取，金額由後端試算。 */
export function SlotPicker({
  spaceId,
  initialDate,
  onPick,
}: {
  spaceId: number;
  initialDate?: string;
  onPick: (range: PickedRange | null) => void;
}) {
  const [date, setDate] = useState(initialDate || todayLocal());
  const [selection, setSelection] = useState<Selection | null>(null);
  const availability = useAvailability(spaceId, date);
  const slots = availability.data?.slots ?? [];

  useEffect(() => setSelection(null), [date, spaceId]);
  useEffect(() => {
    if (!selection) return onPick(null);
    const first = slots.find((s) => s.start === selection.start);
    const last = slots.find((s) => s.start === selection.end - 1);
    onPick(
      first && last
        ? { start_at: first.start_at, end_at: last.end_at, hours: selection.end - selection.start }
        : null,
    );
  }, [selection, availability.data]); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <Stack gap="sm">
      <TextInput
        label="日期"
        type="date"
        value={date}
        min={todayLocal()}
        max={addDays(todayLocal(), 60)}
        onChange={(e) => e.currentTarget.value && setDate(e.currentTarget.value)}
      />
      <QueryState loading={availability.isLoading} error={availability.error}>
        {availability.data && !availability.data.bookable ? (
          <Alert color="yellow">{REASON[availability.data.reason ?? ''] ?? '目前無法預約'}</Alert>
        ) : (
          <>
            <SlotGrid slots={slots} selection={selection} onChange={setSelection} />
            <Text size="xs" c="dimmed">
              點一格選擇開始，再點另一格選擇結束，中間會自動連續選取。
            </Text>
          </>
        )}
      </QueryState>
    </Stack>
  );
}
