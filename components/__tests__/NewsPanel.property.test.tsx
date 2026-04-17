// Feature: 002-stock-news-and-profile, Property 3: 新闻条目渲染完整性
import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import fc from 'fast-check';
import NewsPanel from '../NewsPanel';
import type { Stock, NewsItem } from '../../types';

/**
 * Validates: Requirements 1.3, 1.7
 *
 * 属性 3：新闻条目渲染完整性
 * 对于任意 NewsItem，渲染后的输出应包含该条目的标题、来源和时间信息；
 * 且当 url 字段存在时，标题应渲染为指向该 url 的链接（target="_blank"），
 * 当 url 不存在时，标题应渲染为普通文本。
 */

// --- Mock newsService ---
vi.mock('../../services/newsService', () => ({
  getInfoGatheringNews: vi.fn(),
  filterNewsByStock: vi.fn(),
}));

import { getInfoGatheringNews, filterNewsByStock } from '../../services/newsService';

const mockedGetInfoGatheringNews = vi.mocked(getInfoGatheringNews);
const mockedFilterNewsByStock = vi.mocked(filterNewsByStock);

// --- Mock lucide-react to avoid SVG rendering issues in jsdom ---
vi.mock('lucide-react', () => ({
  Loader2: (props: Record<string, unknown>) =>
    React.createElement('span', { 'data-testid': 'loader-icon', ...props }),
}));

// --- Arbitraries ---

const STOCK_NAME = '测试股票';
const STOCK_SYMBOL = '600999';

const mockStock: Stock = {
  symbol: STOCK_SYMBOL,
  name: STOCK_NAME,
  price: 10.0,
  pctChange: 1.5,
  volume: '500万',
  turnover: '5000万',
  industry: '测试行业',
  concepts: ['概念A'],
};

const newsTypeArb = fc.constantFrom('notice' as const, 'news' as const, 'report' as const);

// 生成标题中包含股票名称的 NewsItem（确保通过过滤）
const newsItemWithUrlArb: fc.Arbitrary<NewsItem> = fc.record({
  id: fc.uuid(),
  title: fc.string({ minLength: 1, maxLength: 40 }).map((s) => `${s}${STOCK_NAME}`),
  source: fc.string({ minLength: 1, maxLength: 20 }),
  time: fc.string({ minLength: 1, maxLength: 20 }),
  content: fc.string({ minLength: 0, maxLength: 100 }),
  url: fc.webUrl(),
  sentiment: fc.constantFrom('bullish' as const, 'bearish' as const, 'neutral' as const, null),
  type: newsTypeArb,
});

const newsItemWithoutUrlArb: fc.Arbitrary<NewsItem> = fc.record({
  id: fc.uuid(),
  title: fc.string({ minLength: 1, maxLength: 40 }).map((s) => `${s}${STOCK_NAME}`),
  source: fc.string({ minLength: 1, maxLength: 20 }),
  time: fc.string({ minLength: 1, maxLength: 20 }),
  content: fc.string({ minLength: 0, maxLength: 100 }),
  sentiment: fc.constantFrom('bullish' as const, 'bearish' as const, 'neutral' as const, null),
  type: newsTypeArb,
});

// 混合生成有 url 和无 url 的 NewsItem
const newsItemArb: fc.Arbitrary<NewsItem> = fc.oneof(newsItemWithUrlArb, newsItemWithoutUrlArb);

// --- Tests ---

describe('NewsPanel - 属性 3：新闻条目渲染完整性', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('每条新闻应展示标题、来源、时间信息', async () => {
    await fc.assert(
      fc.asyncProperty(
        fc.array(newsItemArb, { minLength: 1, maxLength: 5 }),
        async (items) => {
          mockedGetInfoGatheringNews.mockResolvedValue(items);
          mockedFilterNewsByStock.mockReturnValue(items);

          const { unmount } = render(<NewsPanel stock={mockStock} />);

          // 等待加载完成
          await waitFor(() => {
            expect(screen.getByTestId('news-list')).toBeDefined();
          });

          const newsItems = screen.getAllByTestId('news-item');
          expect(newsItems.length).toBe(items.length);

          // 验证每条新闻的来源和时间
          const sources = screen.getAllByTestId('news-source');
          const times = screen.getAllByTestId('news-time');

          for (let i = 0; i < items.length; i++) {
            expect(sources[i].textContent).toBe(items[i].source);
            expect(times[i].textContent).toBe(items[i].time);
          }

          // 验证标题文本存在
          for (const item of items) {
            if (item.url) {
              const link = screen
                .getAllByTestId('news-link')
                .find((el) => el.textContent === item.title);
              expect(link).toBeDefined();
            } else {
              const text = screen
                .getAllByTestId('news-title-text')
                .find((el) => el.textContent === item.title);
              expect(text).toBeDefined();
            }
          }

          unmount();
        },
      ),
      { numRuns: 100 },
    );
  });

  it('有 url 的新闻标题应渲染为 target="_blank" 的链接', async () => {
    await fc.assert(
      fc.asyncProperty(
        fc.array(newsItemWithUrlArb, { minLength: 1, maxLength: 5 }),
        async (items) => {
          mockedGetInfoGatheringNews.mockResolvedValue(items);
          mockedFilterNewsByStock.mockReturnValue(items);

          const { unmount } = render(<NewsPanel stock={mockStock} />);

          await waitFor(() => {
            expect(screen.getByTestId('news-list')).toBeDefined();
          });

          const links = screen.getAllByTestId('news-link');
          expect(links.length).toBe(items.length);

          for (let i = 0; i < items.length; i++) {
            const link = links[i] as HTMLAnchorElement;
            expect(link.tagName).toBe('A');
            expect(link.getAttribute('target')).toBe('_blank');
            expect(link.getAttribute('href')).toBe(items[i].url);
            expect(link.textContent).toBe(items[i].title);
          }

          unmount();
        },
      ),
      { numRuns: 100 },
    );
  });

  it('无 url 的新闻标题应渲染为普通文本（非链接）', async () => {
    await fc.assert(
      fc.asyncProperty(
        fc.array(newsItemWithoutUrlArb, { minLength: 1, maxLength: 5 }),
        async (items) => {
          mockedGetInfoGatheringNews.mockResolvedValue(items);
          mockedFilterNewsByStock.mockReturnValue(items);

          const { unmount } = render(<NewsPanel stock={mockStock} />);

          await waitFor(() => {
            expect(screen.getByTestId('news-list')).toBeDefined();
          });

          const textElements = screen.getAllByTestId('news-title-text');
          expect(textElements.length).toBe(items.length);

          for (let i = 0; i < items.length; i++) {
            expect(textElements[i].tagName).toBe('SPAN');
            expect(textElements[i].textContent).toBe(items[i].title);
          }

          // 不应有任何链接
          expect(screen.queryAllByTestId('news-link').length).toBe(0);

          unmount();
        },
      ),
      { numRuns: 100 },
    );
  });
});
