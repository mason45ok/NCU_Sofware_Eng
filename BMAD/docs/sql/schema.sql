-- 聚點 空間租借系統：參考 DDL（PostgreSQL 16）
-- 正式結構以 Alembic migration 產生；本檔用於驗證約束與作為 migration 的對照。
-- 時間一律 timestamptz（存 UTC），營業時間 TIME 為 Asia/Taipei 當地時間。

CREATE EXTENSION IF NOT EXISTS btree_gist;

-- ===== 帳號 =====
CREATE TABLE users (
  user_id            BIGSERIAL PRIMARY KEY,
  email              VARCHAR(254) NOT NULL,
  name               VARCHAR(50)  NOT NULL,
  phone              VARCHAR(20),
  role               VARCHAR(10)  NOT NULL DEFAULT 'USER'
                       CHECK (role IN ('USER','ADMIN')),
  status             VARCHAR(12)  NOT NULL DEFAULT 'ACTIVE'
                       CHECK (status IN ('ACTIVE','FROZEN','BLACKLISTED')),
  status_reason      VARCHAR(200),
  email_verified_at  TIMESTAMPTZ,
  last_login_at      TIMESTAMPTZ,
  created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
  CHECK (status = 'ACTIVE' OR status_reason IS NOT NULL)
);
-- email 不分大小寫唯一
CREATE UNIQUE INDEX uq_users_email ON users (lower(email));

CREATE TABLE user_passwords (
  password_id      BIGSERIAL PRIMARY KEY,
  user_id          BIGINT NOT NULL UNIQUE REFERENCES users(user_id) ON DELETE CASCADE,
  password_hash    CHAR(64) NOT NULL,           -- PBKDF2-SHA256 結果（hex）
  password_salt    CHAR(32) NOT NULL,           -- 16 bytes 隨機鹽值（hex）
  failed_attempts  INT NOT NULL DEFAULT 0 CHECK (failed_attempts >= 0),
  locked_until     TIMESTAMPTZ,
  created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE external_accounts (
  ext_id            BIGSERIAL PRIMARY KEY,
  user_id           BIGINT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
  provider          VARCHAR(10) NOT NULL CHECK (provider IN ('GOOGLE')),
  provider_user_id  VARCHAR(255) NOT NULL,      -- Google 的 sub
  provider_email    VARCHAR(254),
  linked_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (provider, provider_user_id),
  UNIQUE (user_id, provider)
);

CREATE TABLE account_tokens (
  token_id    BIGSERIAL PRIMARY KEY,
  user_id     BIGINT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
  purpose     VARCHAR(20) NOT NULL
                CHECK (purpose IN ('VERIFY_EMAIL','RESET_PASSWORD','SET_PASSWORD')),
  token_hash  CHAR(64) NOT NULL UNIQUE,         -- SHA-256(token)，明文只出現在信件連結
  expires_at  TIMESTAMPTZ NOT NULL,
  used_at     TIMESTAMPTZ,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  CHECK (expires_at > created_at)
);
CREATE INDEX ix_account_tokens_user ON account_tokens (user_id, purpose);

-- ===== 場地 =====
CREATE TABLE branches (
  branch_id   BIGSERIAL PRIMARY KEY,
  name        VARCHAR(50)  NOT NULL,
  city        VARCHAR(20)  NOT NULL,
  district    VARCHAR(20)  NOT NULL,
  address     VARCHAR(200) NOT NULL,
  phone       VARCHAR(20)  NOT NULL,
  latitude    NUMERIC(9,6) NOT NULL CHECK (latitude BETWEEN -90 AND 90),
  longitude   NUMERIC(9,6) NOT NULL CHECK (longitude BETWEEN -180 AND 180),
  open_time   TIME NOT NULL,
  close_time  TIME NOT NULL,
  status      VARCHAR(10) NOT NULL DEFAULT 'OPEN' CHECK (status IN ('OPEN','DISABLED')),
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  CHECK (close_time > open_time),
  CHECK (extract(minute FROM open_time) = 0 AND extract(second FROM open_time) = 0),
  CHECK (extract(minute FROM close_time) = 0 AND extract(second FROM close_time) = 0)
);
CREATE INDEX ix_branches_area ON branches (city, district);

CREATE TABLE spaces (
  space_id      BIGSERIAL PRIMARY KEY,
  branch_id     BIGINT NOT NULL REFERENCES branches(branch_id),
  name          VARCHAR(50) NOT NULL,
  space_type    VARCHAR(10) NOT NULL
                  CHECK (space_type IN ('MEETING','CLASSROOM','PARTY','STUDIO','MULTI')),
  capacity      INT NOT NULL CHECK (capacity > 0),
  area          NUMERIC(5,1) CHECK (area > 0),
  hourly_price  INT NOT NULL CHECK (hourly_price > 0),
  description   TEXT,
  rules         TEXT,
  entry_guide   TEXT,
  status        VARCHAR(12) NOT NULL DEFAULT 'AVAILABLE'
                  CHECK (status IN ('AVAILABLE','MAINTENANCE','DISABLED')),
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (branch_id, name)
);

CREATE TABLE space_photos (
  photo_id     BIGSERIAL PRIMARY KEY,
  space_id     BIGINT NOT NULL REFERENCES spaces(space_id) ON DELETE CASCADE,
  image_url    VARCHAR(255) NOT NULL,
  caption      VARCHAR(100),
  sort_order   INT NOT NULL DEFAULT 0 CHECK (sort_order >= 0),
  uploaded_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ix_space_photos_space ON space_photos (space_id, sort_order);

-- ===== 設備 =====
CREATE TABLE equipment (
  equipment_id  BIGSERIAL PRIMARY KEY,
  name          VARCHAR(50) NOT NULL UNIQUE,
  category      VARCHAR(10) NOT NULL
                  CHECK (category IN ('AV','FURNITURE','KITCHEN','NETWORK','OTHER')),
  is_active     BOOLEAN NOT NULL DEFAULT TRUE,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE space_equipment (
  space_id      BIGINT NOT NULL REFERENCES spaces(space_id) ON DELETE CASCADE,
  equipment_id  BIGINT NOT NULL REFERENCES equipment(equipment_id),
  quantity      INT NOT NULL DEFAULT 1 CHECK (quantity > 0),
  note          VARCHAR(100),
  PRIMARY KEY (space_id, equipment_id)
);

-- ===== 交易 =====
CREATE TABLE bookings (
  booking_id             BIGSERIAL PRIMARY KEY,
  booking_no             VARCHAR(20) NOT NULL UNIQUE,   -- 例：B20261108-0001
  user_id                BIGINT NOT NULL REFERENCES users(user_id),
  space_id               BIGINT NOT NULL REFERENCES spaces(space_id),
  start_at               TIMESTAMPTZ NOT NULL,
  end_at                 TIMESTAMPTZ NOT NULL,
  attendees              INT NOT NULL CHECK (attendees > 0),
  note                   VARCHAR(500),
  hourly_price_snapshot  INT NOT NULL CHECK (hourly_price_snapshot > 0),
  total_amount           INT NOT NULL CHECK (total_amount > 0),
  status                 VARCHAR(16) NOT NULL DEFAULT 'PENDING_PAYMENT'
                           CHECK (status IN ('PENDING_PAYMENT','CONFIRMED','CANCELLED','EXPIRED','COMPLETED')),
  expires_at             TIMESTAMPTZ NOT NULL,          -- 付款期限
  reschedule_count       INT NOT NULL DEFAULT 0 CHECK (reschedule_count BETWEEN 0 AND 1),
  cancelled_by           BIGINT REFERENCES users(user_id),
  cancel_reason          VARCHAR(200),
  cancelled_at           TIMESTAMPTZ,
  created_at             TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at             TIMESTAMPTZ NOT NULL DEFAULT now(),
  CHECK (end_at > start_at),
  CHECK (extract(epoch FROM start_at)::bigint % 3600 = 0),   -- 整點
  CHECK (extract(epoch FROM end_at)::bigint   % 3600 = 0),
  CHECK (total_amount = hourly_price_snapshot * (extract(epoch FROM (end_at - start_at))::int / 3600)),
  CHECK ((status = 'CANCELLED') = (cancelled_at IS NOT NULL))
);
-- 核心：同一空間的有效訂單（待付款、已確認）時段不可重疊。[) 半開區間，相鄰時段不衝突。
ALTER TABLE bookings ADD CONSTRAINT ex_bookings_no_overlap
  EXCLUDE USING gist (space_id WITH =, tstzrange(start_at, end_at, '[)') WITH &&)
  WHERE (status IN ('PENDING_PAYMENT','CONFIRMED'));
CREATE INDEX ix_bookings_user ON bookings (user_id, status);
CREATE INDEX ix_bookings_pending_expiry ON bookings (expires_at) WHERE status = 'PENDING_PAYMENT';
CREATE INDEX ix_bookings_confirmed_end ON bookings (end_at) WHERE status = 'CONFIRMED';

CREATE TABLE booking_status_logs (
  log_id       BIGSERIAL PRIMARY KEY,
  booking_id   BIGINT NOT NULL REFERENCES bookings(booking_id),
  from_status  VARCHAR(16),                 -- 建立時為 NULL
  to_status    VARCHAR(16) NOT NULL,
  action       VARCHAR(12) NOT NULL
                 CHECK (action IN ('CREATE','PAY','CANCEL','EXPIRE','COMPLETE','RESCHEDULE','REFUND')),
  changed_by   BIGINT REFERENCES users(user_id),   -- NULL 代表系統排程
  reason       VARCHAR(200),
  created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ix_booking_status_logs_booking ON booking_status_logs (booking_id, created_at);

CREATE TABLE payments (
  payment_id       BIGSERIAL PRIMARY KEY,
  booking_id       BIGINT NOT NULL REFERENCES bookings(booking_id),
  type             VARCHAR(8)  NOT NULL CHECK (type IN ('PAYMENT','REFUND')),
  amount           INT NOT NULL CHECK (amount > 0),
  method           VARCHAR(12) NOT NULL CHECK (method IN ('CREDIT_CARD','LINE_PAY')),
  status           VARCHAR(8)  NOT NULL CHECK (status IN ('SUCCESS','FAILED')),
  idempotency_key  VARCHAR(64) NOT NULL UNIQUE,
  transaction_no   VARCHAR(40),             -- 模擬交易序號，成功時才有
  created_by       BIGINT REFERENCES users(user_id),
  created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  CHECK ((status = 'SUCCESS') = (transaction_no IS NOT NULL))
);
CREATE INDEX ix_payments_booking ON payments (booking_id);

CREATE TABLE access_codes (
  code_id      BIGSERIAL PRIMARY KEY,
  booking_id   BIGINT NOT NULL UNIQUE REFERENCES bookings(booking_id),
  code         CHAR(6) NOT NULL CHECK (code ~ '^[0-9]{6}$'),
  valid_from   TIMESTAMPTZ NOT NULL,
  valid_until  TIMESTAMPTZ NOT NULL,
  revoked_at   TIMESTAMPTZ,
  created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
  CHECK (valid_until > valid_from)
);

-- ===== 互動 =====
CREATE TABLE reviews (
  review_id   BIGSERIAL PRIMARY KEY,
  booking_id  BIGINT NOT NULL UNIQUE REFERENCES bookings(booking_id),
  rating      SMALLINT NOT NULL CHECK (rating BETWEEN 1 AND 5),
  comment     VARCHAR(500),
  is_hidden   BOOLEAN NOT NULL DEFAULT FALSE,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE user_favorites (
  user_id     BIGINT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
  space_id    BIGINT NOT NULL REFERENCES spaces(space_id) ON DELETE CASCADE,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (user_id, space_id)
);

CREATE TABLE notification_logs (
  notification_id  BIGSERIAL PRIMARY KEY,
  user_id          BIGINT NOT NULL REFERENCES users(user_id),
  booking_id       BIGINT REFERENCES bookings(booking_id),
  type             VARCHAR(20) NOT NULL
                     CHECK (type IN ('VERIFY_EMAIL','RESET_PASSWORD','SET_PASSWORD',
                                     'BOOKING_CONFIRMED','BOOKING_CANCELLED','BOOKING_RESCHEDULED')),
  recipient        VARCHAR(254) NOT NULL,
  subject          VARCHAR(200) NOT NULL,
  status           VARCHAR(8) NOT NULL DEFAULT 'PENDING' CHECK (status IN ('PENDING','SENT','FAILED')),
  attempts         INT NOT NULL DEFAULT 0 CHECK (attempts >= 0),
  error_message    VARCHAR(500),
  sent_at          TIMESTAMPTZ,
  created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ix_notification_logs_status ON notification_logs (status, created_at);
