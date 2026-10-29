import { MantineProvider } from '@mantine/core';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { useState } from 'react';
import type { Slot } from '../api/types';
import { SlotGrid, nextSelection, type Selection } from './SlotGrid';

const make = (statuses: Slot['status'][]): Slot[] =>
  statuses.map((status, i) => ({
    start: 9 + i,
    end: 10 + i,
    start_at: `2026-11-04T${String(9 + i).padStart(2, '0')}:00:00+08:00`,
    end_at: `2026-11-04T${String(10 + i).padStart(2, '0')}:00:00+08:00`,
    status,
  }));

describe('nextSelection（FR-14、PRD 第 8 節）', () => {
  const slots = make(['AVAILABLE', 'AVAILABLE', 'AVAILABLE', 'BOOKED', 'AVAILABLE']);

  it('第一次點選為單一小時', () => {
    expect(nextSelection(slots, null, 10)).toEqual({ start: 10, end: 11 });
  });

  it('第二次點選較晚的格子，中間自動連續選取', () => {
    expect(nextSelection(slots, { start: 9, end: 10 }, 11)).toEqual({ start: 9, end: 12 });
  });

  it('中間含有已被預約的格子時，改為重新選取', () => {
    expect(nextSelection(slots, { start: 10, end: 11 }, 13)).toEqual({ start: 13, end: 14 });
  });

  it('不可選的格子不會改變選取', () => {
    const current: Selection = { start: 9, end: 10 };
    expect(nextSelection(slots, current, 12)).toBe(current);
  });

  it('點同一格取消選取；已有區間時重新開始', () => {
    expect(nextSelection(slots, { start: 9, end: 10 }, 9)).toBeNull();
    expect(nextSelection(slots, { start: 9, end: 12 }, 10)).toEqual({ start: 10, end: 11 });
  });
});

describe('SlotGrid', () => {
  function Harness() {
    const [sel, setSel] = useState<Selection | null>(null);
    return (
      <MantineProvider>
        <SlotGrid
          slots={make(['AVAILABLE', 'AVAILABLE', 'BOOKED', 'PAST'])}
          selection={sel}
          onChange={setSel}
        />
      </MantineProvider>
    );
  }

  it('已被預約與已過去的格子無法點選，點選後標示已選', async () => {
    render(<Harness />);
    expect(screen.getByRole('button', { name: '11:00，已被預約' })).toBeDisabled();
    expect(screen.getByRole('button', { name: '12:00，已過去' })).toBeDisabled();
    const first = screen.getByRole('button', { name: '09:00，可預約' });
    await userEvent.click(first);
    expect(screen.getByRole('button', { name: '09:00，可預約' })).toHaveAttribute(
      'aria-pressed',
      'true',
    );
    await userEvent.click(screen.getByRole('button', { name: '10:00，可預約' }));
    expect(screen.getByRole('button', { name: '10:00，可預約' })).toHaveAttribute(
      'aria-pressed',
      'true',
    );
  });
});
