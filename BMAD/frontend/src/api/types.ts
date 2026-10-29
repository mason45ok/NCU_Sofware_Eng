export interface User {
  user_id: number;
  email: string;
  name: string;
  phone: string | null;
  role: 'USER' | 'ADMIN';
  status: 'ACTIVE' | 'FROZEN' | 'BLACKLISTED';
  status_reason: string | null;
  email_verified: boolean;
  has_password: boolean;
  last_login_at: string | null;
  created_at: string | null;
}

export interface Page<T> {
  items: T[];
  page: number;
  page_size: number;
  total: number;
}

export interface SpaceSummary {
  space_id: number;
  name: string;
  branch_name: string;
  city: string;
  district: string;
  space_type: string;
  capacity: number;
  hourly_price: number;
  status: string;
  cover_url: string | null;
  avg_rating: number | null;
  review_count: number;
  distance_km: number | null;
}

export interface SpaceDetail {
  space_id: number;
  name: string;
  space_type: string;
  capacity: number;
  area: number | null;
  hourly_price: number;
  description: string | null;
  rules: string | null;
  entry_guide: string | null;
  status: string;
  bookable: boolean;
  cancel_policy: string[];
  branch: {
    branch_id: number;
    name: string;
    city: string;
    district: string;
    address: string;
    phone: string;
    latitude: number;
    longitude: number;
    open_hour: number;
    close_hour: number;
    maps_url: string;
  };
  photos: { photo_id: number; image_url: string; caption: string | null; sort_order: number }[];
  equipment: {
    equipment_id: number;
    name: string;
    category: string;
    quantity: number;
    note: string | null;
  }[];
  avg_rating: number | null;
  review_count: number;
}

export interface FilterOptions {
  cities: Record<string, string[]>;
  space_types: string[];
  equipment: { equipment_id: number; name: string; category: string }[];
}

export interface Slot {
  start: number;
  end: number;
  start_at: string;
  end_at: string;
  status: 'AVAILABLE' | 'BOOKED' | 'PAST';
}

export interface Availability {
  space_id: number;
  date: string;
  bookable: boolean;
  reason: string | null;
  slots: Slot[];
}

export interface Review {
  review_id: number;
  booking_id: number | null;
  space_id: number | null;
  space_name: string | null;
  reviewer: string;
  rating: number;
  comment: string | null;
  is_hidden: boolean;
  created_at: string;
}

export interface Payment {
  payment_id: number;
  type: 'PAYMENT' | 'REFUND';
  amount: number;
  method: string;
  status: string;
  transaction_no: string | null;
  created_at: string;
}

export interface Booking {
  booking_id: number;
  booking_no: string;
  status: string;
  space_id: number;
  space_name: string;
  branch_name: string;
  branch_address: string;
  branch_phone: string;
  entry_guide: string | null;
  user_id: number;
  user_email: string | null;
  start_at: string;
  end_at: string;
  hours: number;
  attendees: number;
  note: string | null;
  hourly_price_snapshot: number;
  total_amount: number;
  expires_at: string;
  reschedule_count: number;
  cancelled_by: number | null;
  cancel_reason: string | null;
  cancelled_at: string | null;
  net_paid: number;
  payments: Payment[];
  access_code: {
    state: string;
    code: string | null;
    valid_from: string;
    valid_until: string;
  } | null;
  can_cancel: boolean;
  can_reschedule: boolean;
  can_review: boolean;
  reviewed: boolean;
  created_at: string;
}

export interface Quote {
  space_id: number;
  hours: number;
  hourly_price: number;
  total_amount: number;
  payment_deadline_minutes: number;
  cancel_policy: string[];
}

export interface PayResult {
  status: 'SUCCESS' | 'FAILED';
  reason: string | null;
  booking: Booking;
}

export interface RefundQuote {
  status: string;
  net_paid: number;
  ratio: number;
  refund_amount: number;
  note: string;
}

export interface RescheduleQuote {
  old_amount: number;
  new_amount: number;
  diff: number;
  new_hours: number;
  requires_payment: boolean;
  refund_amount: number;
}

export interface Branch {
  branch_id: number;
  name: string;
  city: string;
  district: string;
  address: string;
  phone: string;
  latitude: number;
  longitude: number;
  open_hour: number;
  close_hour: number;
  status: string;
  space_count: number;
}

export interface AdminSpace {
  space_id: number;
  branch_id: number;
  branch_name: string;
  name: string;
  space_type: string;
  capacity: number;
  area: number | null;
  hourly_price: number;
  description: string | null;
  rules: string | null;
  entry_guide: string | null;
  status: string;
}

export interface Equipment {
  equipment_id: number;
  name: string;
  category: string;
  is_active: boolean;
}

export interface StatusLog {
  log_id: number;
  from_status: string | null;
  to_status: string;
  action: string;
  changed_by: number | null;
  reason: string | null;
  created_at: string;
}

export interface NotificationLog {
  notification_id: number;
  user_id: number;
  booking_id: number | null;
  type: string;
  recipient: string;
  subject: string;
  status: string;
  attempts: number;
  error_message: string | null;
  sent_at: string | null;
  created_at: string;
}
