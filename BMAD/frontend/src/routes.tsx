import { Suspense, lazy, type ComponentType } from 'react';
import { Navigate, Outlet, Route, Routes, useLocation } from 'react-router-dom';
import { useMe } from './api/queries';
import { QueryState } from './components/common';
import { AdminLayout, PublicLayout } from './components/layouts';
import {
  ForgotPasswordPage,
  GoogleLinkPage,
  LoginPage,
  RegisterPage,
  ResetPasswordPage,
  SetPasswordPage,
  VerifyEmailPage,
} from './pages/auth';
import { BookPage } from './pages/BookPage';
import { BookingDetailPage } from './pages/BookingDetailPage';
import { ContactPage } from './pages/ContactPage';
import { FavoritesPage } from './pages/FavoritesPage';
import { HomePage } from './pages/HomePage';
import { MyBookingsPage } from './pages/MyBookingsPage';
import { PayPage } from './pages/PayPage';
import { ProfilePage } from './pages/ProfilePage';
import { SpaceDetailPage } from './pages/SpaceDetailPage';
import { SpacesPage } from './pages/SpacesPage';

// 管理後台只有管理員使用，延後載入以縮小前台的初始下載量
const lazyNamed = <T extends Record<string, ComponentType>>(
  load: () => Promise<T>,
  name: keyof T,
) => lazy(() => load().then((m) => ({ default: m[name] })));

const AdminBookingDetailPage = lazyNamed(
  () => import('./pages/admin/AdminBookings'),
  'AdminBookingDetailPage',
);
const AdminBookingsPage = lazyNamed(
  () => import('./pages/admin/AdminBookings'),
  'AdminBookingsPage',
);
const AdminBranchesPage = lazyNamed(
  () => import('./pages/admin/AdminBranches'),
  'AdminBranchesPage',
);
const AdminDashboardPage = lazyNamed(
  () => import('./pages/admin/AdminDashboard'),
  'AdminDashboardPage',
);
const AdminEquipmentPage = lazyNamed(
  () => import('./pages/admin/AdminEquipment'),
  'AdminEquipmentPage',
);
const AdminNotificationsPage = lazyNamed(
  () => import('./pages/admin/AdminNotifications'),
  'AdminNotificationsPage',
);
const AdminReviewsPage = lazyNamed(() => import('./pages/admin/AdminReviews'), 'AdminReviewsPage');
const AdminSpaceEditPage = lazyNamed(
  () => import('./pages/admin/AdminSpaces'),
  'AdminSpaceEditPage',
);
const AdminSpacesPage = lazyNamed(() => import('./pages/admin/AdminSpaces'), 'AdminSpacesPage');
const AdminUsersPage = lazyNamed(() => import('./pages/admin/AdminUsers'), 'AdminUsersPage');

/** 受保護路由：未登入導向登入頁，登入後返回原頁。前端隱藏不算權限控制，後端另行檢查。 */
function RequireAuth({ admin = false }: { admin?: boolean }) {
  const { data: me, isLoading, error } = useMe();
  const location = useLocation();
  return (
    <QueryState loading={isLoading} error={error}>
      {!me ? (
        <Navigate
          to={`/login?next=${encodeURIComponent(location.pathname + location.search)}`}
          replace
        />
      ) : admin && me.role !== 'ADMIN' ? (
        <Navigate to="/" replace />
      ) : (
        <Suspense fallback={null}>
          <Outlet />
        </Suspense>
      )}
    </QueryState>
  );
}

export function AppRoutes() {
  return (
    <Routes>
      <Route element={<PublicLayout />}>
        <Route path="/" element={<HomePage />} />
        <Route path="/spaces" element={<SpacesPage />} />
        <Route path="/spaces/:id" element={<SpaceDetailPage />} />
        <Route path="/login" element={<LoginPage />} />
        <Route path="/register" element={<RegisterPage />} />
        <Route path="/verify-email" element={<VerifyEmailPage />} />
        <Route path="/forgot-password" element={<ForgotPasswordPage />} />
        <Route path="/reset-password" element={<ResetPasswordPage />} />
        <Route path="/set-password" element={<SetPasswordPage />} />
        <Route path="/auth/google/link" element={<GoogleLinkPage />} />
        <Route path="/contact" element={<ContactPage />} />
        <Route element={<RequireAuth />}>
          <Route path="/book/:spaceId" element={<BookPage />} />
          <Route path="/bookings/:id/pay" element={<PayPage />} />
          <Route path="/me/bookings" element={<MyBookingsPage />} />
          <Route path="/me/bookings/:id" element={<BookingDetailPage />} />
          <Route path="/me/favorites" element={<FavoritesPage />} />
          <Route path="/me/profile" element={<ProfilePage />} />
        </Route>
      </Route>
      <Route element={<RequireAuth admin />}>
        <Route path="/admin" element={<AdminLayout />}>
          <Route index element={<AdminDashboardPage />} />
          <Route path="bookings" element={<AdminBookingsPage />} />
          <Route path="bookings/:id" element={<AdminBookingDetailPage />} />
          <Route path="branches" element={<AdminBranchesPage />} />
          <Route path="spaces" element={<AdminSpacesPage />} />
          <Route path="spaces/:id" element={<AdminSpaceEditPage />} />
          <Route path="equipment" element={<AdminEquipmentPage />} />
          <Route path="users" element={<AdminUsersPage />} />
          <Route path="reviews" element={<AdminReviewsPage />} />
          <Route path="notifications" element={<AdminNotificationsPage />} />
        </Route>
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
