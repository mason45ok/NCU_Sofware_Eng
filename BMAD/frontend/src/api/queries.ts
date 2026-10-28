import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useEffect, useState } from 'react';
import { api, resetCsrf } from './client';
import type {
  Availability,
  Booking,
  FilterOptions,
  Page,
  Quote,
  Review,
  SpaceDetail,
  SpaceSummary,
  User,
} from './types';

// ---------- 帳號 ----------
export function useMe() {
  return useQuery({
    queryKey: ['me'],
    queryFn: async () => (await api.get<{ user: User | null }>('/auth/me')).user,
    staleTime: 60_000,
  });
}

export function useLogout() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => api.post('/auth/logout'),
    onSuccess: () => {
      resetCsrf();
      qc.clear();
      qc.setQueryData(['me'], null);
    },
  });
}

/** 登入、註冊、驗證完成後：session 已更新，重取 CSRF 與使用者。 */
export function useRefreshSession() {
  const qc = useQueryClient();
  return async () => {
    resetCsrf();
    await qc.invalidateQueries({ queryKey: ['me'] });
  };
}

// ---------- 目錄 ----------
export const useFilterOptions = () =>
  useQuery({
    queryKey: ['filters'],
    queryFn: () => api.get<FilterOptions>('/catalog/filters'),
    staleTime: 300_000,
  });

export const useSpaces = (params: Record<string, unknown>) =>
  useQuery({
    queryKey: ['spaces', params],
    queryFn: () => api.get<Page<SpaceSummary>>('/spaces', params),
    placeholderData: keepPreviousData,
  });

export const useSpace = (id: number) =>
  useQuery({ queryKey: ['space', id], queryFn: () => api.get<SpaceDetail>(`/spaces/${id}`) });

export const useAvailability = (id: number, date: string) =>
  useQuery({
    queryKey: ['availability', id, date],
    queryFn: () => api.get<Availability>(`/spaces/${id}/availability`, { date }),
    enabled: !!date,
  });

export const useReviews = (id: number, page = 1) =>
  useQuery({
    queryKey: ['reviews', id, page],
    queryFn: () => api.get<Page<Review>>(`/spaces/${id}/reviews`, { page }),
  });

/** 停止選取 300ms 後才向後端試算（PRD 第 8 節）；前端不自行計算金額。 */
export function useQuote(
  body: { space_id: number; start_at: string; end_at: string; attendees: number } | null,
  enabled: boolean,
) {
  const [debounced, setDebounced] = useState(body);
  useEffect(() => {
    const t = setTimeout(() => setDebounced(body), 300);
    return () => clearTimeout(t);
  }, [body?.space_id, body?.start_at, body?.end_at, body?.attendees]); // eslint-disable-line react-hooks/exhaustive-deps
  return useQuery({
    queryKey: ['quote', debounced],
    queryFn: () => api.post<Quote>('/bookings/quote', debounced),
    enabled: enabled && !!debounced,
    retry: false,
  });
}

// ---------- 會員 ----------
export const useBooking = (id: number) =>
  useQuery({ queryKey: ['booking', id], queryFn: () => api.get<Booking>(`/bookings/${id}`) });

export const useMyBookings = (tab: string, page: number) =>
  useQuery({
    queryKey: ['my-bookings', tab, page],
    queryFn: () => api.get<Page<Booking>>('/me/bookings', { tab, page }),
  });

export const useFavorites = (enabled: boolean) =>
  useQuery({
    queryKey: ['favorites'],
    queryFn: () => api.get<{ items: SpaceSummary[] }>('/me/favorites'),
    enabled,
  });

export function useToggleFavorite() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, on }: { id: number; on: boolean }) =>
      on ? api.put(`/me/favorites/${id}`) : api.del(`/me/favorites/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['favorites'] }),
  });
}
