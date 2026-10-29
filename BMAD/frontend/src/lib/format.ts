import dayjs from 'dayjs';
import timezone from 'dayjs/plugin/timezone';
import utc from 'dayjs/plugin/utc';

dayjs.extend(utc);
dayjs.extend(timezone);

export const TZ = 'Asia/Taipei';
const WEEKDAYS = '日一二三四五六';

/** 畫面一律以 Asia/Taipei 顯示，格式 2026/11/20（五）14:00 */
export function formatLocal(iso: string): string {
  const d = dayjs(iso).tz(TZ);
  return `${d.format('YYYY/MM/DD')}（${WEEKDAYS[d.day()]}）${d.format('HH:mm')}`;
}

export function formatRange(startIso: string, endIso: string): string {
  return `${formatLocal(startIso)} ～ ${dayjs(endIso).tz(TZ).format('HH:mm')}`;
}

export function todayLocal(): string {
  return dayjs().tz(TZ).format('YYYY-MM-DD');
}

export function addDays(date: string, days: number): string {
  return dayjs(date).add(days, 'day').format('YYYY-MM-DD');
}

export const money = (n: number) => `NT$ ${n.toLocaleString('zh-TW')}`;

export const BOOKING_STATUS: Record<string, { label: string; color: string }> = {
  PENDING_PAYMENT: { label: '待付款', color: 'yellow' },
  CONFIRMED: { label: '已確認', color: 'olive' },
  COMPLETED: { label: '已完成', color: 'gray' },
  CANCELLED: { label: '已取消', color: 'red' },
  EXPIRED: { label: '已失效', color: 'gray' },
};

export const SPACE_TYPES: Record<string, string> = {
  MEETING: '會議',
  CLASSROOM: '教室',
  PARTY: '聚會',
  STUDIO: '攝影',
  MULTI: '多功能',
};

export const SPACE_STATUS: Record<string, string> = {
  AVAILABLE: '可預約',
  MAINTENANCE: '維修中',
  DISABLED: '停用',
};

export const USER_STATUS: Record<string, string> = {
  ACTIVE: '正常',
  FROZEN: '凍結',
  BLACKLISTED: '黑名單',
};

export const EQUIPMENT_CATEGORY: Record<string, string> = {
  AV: '影音',
  FURNITURE: '家具',
  KITCHEN: '廚房',
  NETWORK: '網路',
  OTHER: '其他',
};

export const ACCESS_STATE: Record<string, string> = {
  NOT_YET_VALID: '尚未生效',
  VALID: '有效',
  EXPIRED: '已失效',
  REVOKED: '已撤銷',
};

export const NOTIFY_TYPE: Record<string, string> = {
  VERIFY_EMAIL: 'Email 驗證',
  RESET_PASSWORD: '重設密碼',
  SET_PASSWORD: '設定密碼',
  BOOKING_CONFIRMED: '預約確認',
  BOOKING_CANCELLED: '訂單取消',
  BOOKING_RESCHEDULED: '訂單改期',
};

export const ACTION_LABEL: Record<string, string> = {
  CREATE: '建立',
  PAY: '付款',
  CANCEL: '取消',
  EXPIRE: '逾時失效',
  COMPLETE: '完成',
  RESCHEDULE: '改期',
  REFUND: '退款',
};

/** 台北當地日期（YYYY-MM-DD）＋整點 → 含時區的 ISO 8601（供後台代為改期使用）。 */
export function localIso(date: string, hour: number): string {
  return dayjs.tz(`${date} ${String(hour).padStart(2, '0')}:00`, TZ).format();
}
