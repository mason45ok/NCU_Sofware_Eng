import { Alert, Badge, Center, Loader, Stack, Text } from '@mantine/core';
import { notifications } from '@mantine/notifications';
import { useEffect, useState } from 'react';
import { ApiError } from '../api/client';
import { BOOKING_STATUS } from '../lib/format';

/** 載入中、錯誤、空狀態的統一呈現。 */
export function QueryState({
  loading,
  error,
  children,
}: {
  loading: boolean;
  error: unknown;
  children: React.ReactNode;
}) {
  if (loading)
    return (
      <Center py="xl" aria-busy="true">
        <Loader />
      </Center>
    );
  if (error) return <ErrorAlert error={error} />;
  return <>{children}</>;
}

export function ErrorAlert({ error }: { error: unknown }) {
  if (!error) return null;
  const message = error instanceof ApiError ? error.message : '發生未知錯誤，請稍後再試';
  return (
    <Alert color="red" title="操作失敗" role="alert">
      {message}
    </Alert>
  );
}

export function Empty({ text }: { text: string }) {
  return (
    <Stack align="center" py="xl">
      <Text c="dimmed">{text}</Text>
    </Stack>
  );
}

export function StatusBadge({ status }: { status: string }) {
  const s = BOOKING_STATUS[status] ?? { label: status, color: 'gray' };
  return <Badge color={s.color}>{s.label}</Badge>;
}

export function toast(message: string, color: 'green' | 'red' = 'green') {
  notifications.show({ message, color });
}

export function toastError(error: unknown) {
  toast(error instanceof ApiError ? error.message : '發生未知錯誤，請稍後再試', 'red');
}

/** 倒數計時，回傳剩餘秒數（到 0 為止）。 */
export function useCountdown(targetIso: string | undefined): number {
  const calc = () =>
    targetIso ? Math.max(0, Math.floor((new Date(targetIso).getTime() - Date.now()) / 1000)) : 0;
  const [left, setLeft] = useState(calc);
  useEffect(() => {
    setLeft(calc());
    const t = setInterval(() => setLeft(calc()), 1000);
    return () => clearInterval(t);
  }, [targetIso]); // eslint-disable-line react-hooks/exhaustive-deps
  return left;
}
