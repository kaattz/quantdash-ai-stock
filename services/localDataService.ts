import { getJsonCandidatePaths } from './dataPathService';

type LoadLocalJsonOptions = {
  timeout?: number;
  cacheBustToken?: number | string;
};

const getPublicBase = () => (import.meta.env.BASE_URL ?? '/').replace(/\/?$/, '/');

export const loadLocalJsonFile = async <T>(
  fileName: string,
  options: LoadLocalJsonOptions = {},
): Promise<T | null> => {
  if (typeof window === 'undefined') return null;

  const controller = new AbortController();
  const timeoutId = window.setTimeout(() => controller.abort(), options.timeout ?? 1500);
  const cacheBustToken = options.cacheBustToken ?? Date.now();
  const candidates = getJsonCandidatePaths(fileName);

  try {
    for (const candidate of candidates) {
      const response = await fetch(`${getPublicBase()}${candidate}?v=${cacheBustToken}`, {
        cache: 'no-store',
        signal: controller.signal,
      });
      if (!response.ok) continue;

      const contentType = response.headers.get('content-type') || '';
      const raw = await response.text();
      if (!raw.trim() || contentType.includes('text/html') || raw.trim().startsWith('<!DOCTYPE')) {
        continue;
      }

      return JSON.parse(raw) as T;
    }

    return null;
  } catch (error) {
    if ((error as Error).name !== 'AbortError') {
      console.warn(`Failed to load local data file ${fileName}`, error);
    }
    return null;
  } finally {
    clearTimeout(timeoutId);
  }
};

/**
 * 检测本地数据是否过期。
 * 从数据数组中提取最新日期，与当前日期比较，超过 maxStaleDays 个自然日视为过期。
 * 支持 "YYYY-MM-DD"、"MM-DD"（自动补当前年份）以及对象中的 fullDate 字段。
 */
export const isLocalDataStale = <T extends Record<string, any>>(
  data: T[] | null | undefined,
  maxStaleDays = 2,
): boolean => {
  if (!Array.isArray(data) || data.length === 0) return true;

  const extractDate = (item: T): string | null => {
    const fullDate = item.fullDate ?? item.date;
    if (typeof fullDate !== 'string' || !fullDate) return null;
    // "YYYY-MM-DD" 格式
    if (/^\d{4}-\d{2}-\d{2}$/.test(fullDate)) return fullDate;
    // "MM-DD" 格式，补当前年份
    if (/^\d{2}-\d{2}$/.test(fullDate)) return `${new Date().getFullYear()}-${fullDate}`;
    return null;
  };

  const last = data[data.length - 1];
  const dateStr = extractDate(last);
  if (!dateStr) return true;

  const latestDate = new Date(dateStr + 'T00:00:00');
  if (Number.isNaN(latestDate.getTime())) return true;

  const now = new Date();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const diffMs = today.getTime() - latestDate.getTime();
  const diffDays = diffMs / (1000 * 60 * 60 * 24);
  return diffDays > maxStaleDays;
};

/**
 * 检测非数组结构的本地数据是否过期（如 sector_rotation 的 dates 数组）。
 * 从 dates 数组中取最新日期进行判断。
 */
export const isLocalDatesStale = (
  dates: string[] | null | undefined,
  maxStaleDays = 2,
): boolean => {
  if (!Array.isArray(dates) || dates.length === 0) return true;
  const latest = dates[0]; // dates 通常按降序排列，第一个是最新的
  if (typeof latest !== 'string') return true;
  const fullDate = /^\d{4}-\d{2}-\d{2}$/.test(latest)
    ? latest
    : /^\d{2}-\d{2}$/.test(latest)
      ? `${new Date().getFullYear()}-${latest}`
      : null;
  if (!fullDate) return true;
  const latestDate = new Date(fullDate + 'T00:00:00');
  if (Number.isNaN(latestDate.getTime())) return true;
  const now = new Date();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const diffMs = today.getTime() - latestDate.getTime();
  return diffMs / (1000 * 60 * 60 * 24) > maxStaleDays;
};

export const checkLocalPublicFileExists = async (
  fileName: string,
  timeout = 1000,
): Promise<boolean> => {
  if (typeof window === 'undefined') return false;

  const controller = new AbortController();
  const timeoutId = window.setTimeout(() => controller.abort(), timeout);
  const candidates = getJsonCandidatePaths(fileName);
  try {
    for (const candidate of candidates) {
      const response = await fetch(`${getPublicBase()}${candidate}?v=${Date.now()}`, {
        method: 'HEAD',
        signal: controller.signal,
        cache: 'no-store',
      });
      if (response.ok) return true;
    }
    return false;
  } catch {
    return false;
  } finally {
    clearTimeout(timeoutId);
  }
};
