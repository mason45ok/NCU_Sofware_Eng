"""Service 層：在 create_app() 中以建構子注入相依並組裝（D3）。"""

from __future__ import annotations

from dataclasses import dataclass

from ..mail.sender import Mailer
from ..utils.clock import Clock
from .access_code import AccessCodeService
from .admin_booking import AdminBookingService
from .admin_catalog import AdminCatalogService
from .admin_user import AdminUserService
from .auth import AuthService
from .availability import AvailabilityService
from .booking import BookingService
from .catalog import CatalogService
from .favorite import FavoriteService
from .google_auth import GoogleAuthService
from .notification import NotificationService
from .password import PasswordService
from .payment import PaymentService
from .review import ReviewService


@dataclass
class Services:
    clock: Clock
    notifications: NotificationService
    passwords: PasswordService
    auth: AuthService
    google: GoogleAuthService
    availability: AvailabilityService
    catalog: CatalogService
    favorites: FavoriteService
    payments: PaymentService
    access_codes: AccessCodeService
    bookings: BookingService
    reviews: ReviewService
    admin_catalog: AdminCatalogService
    admin_bookings: AdminBookingService
    admin_users: AdminUserService


def build_services(clock: Clock, mailer: Mailer) -> Services:
    notifications = NotificationService(clock, mailer)
    passwords = PasswordService(clock, notifications)
    auth = AuthService(clock, passwords, notifications)
    google = GoogleAuthService(auth, passwords)
    availability = AvailabilityService(clock)
    catalog = CatalogService(clock, availability)
    payments = PaymentService()
    access_codes = AccessCodeService(clock)
    bookings = BookingService(clock, availability, payments, access_codes, notifications)
    return Services(
        clock=clock,
        notifications=notifications,
        passwords=passwords,
        auth=auth,
        google=google,
        availability=availability,
        catalog=catalog,
        favorites=FavoriteService(catalog),
        payments=payments,
        access_codes=access_codes,
        bookings=bookings,
        reviews=ReviewService(clock, bookings),
        admin_catalog=AdminCatalogService(bookings),
        admin_bookings=AdminBookingService(clock, bookings),
        admin_users=AdminUserService(clock),
    )
