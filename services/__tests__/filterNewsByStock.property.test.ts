// Feature: 002-stock-news-and-profile, Property 1: 新闻过滤正确性
import fc from 'fast-check';
import { filterNewsByStock } from '../newsService';
import type { NewsItem } from '../../types';

/**
 * Validates: Requirements 1.2, 4.1
 *
 * 属性 1：新闻过滤正确性
 * 对于任意新闻列表和任意股票名称/代码组合，filterNewsByStock 返回的每条新闻，
 * 其标题或内容中必须包含该股票名称或股票代码。
 */

// --- Arbitraries ---

const newsTypeArb = fc.constantFrom('notice' as const, 'news' as const, 'report' as const);

const sentimentArb = fc.constantFrom('bullish' as const, 'bearish' as const, 'neutral' as const, null);

const newsItemArb: fc.Arbitrary<NewsItem> = fc.record({
  id: fc.uuid(),
  title: fc.string({ minLength: 0, maxLength: 100 }),
  source: fc.string({ minLength: 1, maxLength: 30 }),
  time: fc.string({ minLength: 1, maxLength: 20 }),
  content: fc.string({ minLength: 0, maxLength: 200 }),
  url: fc.option(fc.webUrl(), { nil: undefined }),
  sentiment: fc.option(sentimentArb, { nil: undefined }),
  type: newsTypeArb,
});

// 生成非空且不含特殊正则字符的股票名称/代码，避免 trivial 空字符串匹配
const stockIdentifierArb = fc.string({ minLength: 1, maxLength: 20 }).filter(
  (s) => s.trim().length > 0,
);

describe('filterNewsByStock - 属性 1：新闻过滤正确性', () => {
  it('返回的每条新闻，其标题或内容中必须包含股票名称或股票代码', () => {
    fc.assert(
      fc.property(
        fc.array(newsItemArb, { minLength: 0, maxLength: 30 }),
        stockIdentifierArb,
        stockIdentifierArb,
        (items, stockName, stockSymbol) => {
          const result = filterNewsByStock(items, stockName, stockSymbol);

          // 每条返回的新闻必须在标题或内容中包含 stockName 或 stockSymbol
          for (const item of result) {
            const titleMatch =
              item.title.includes(stockName) || item.title.includes(stockSymbol);
            const contentMatch =
              item.content?.includes(stockName) || item.content?.includes(stockSymbol);
            expect(titleMatch || contentMatch).toBe(true);
          }
        },
      ),
      { numRuns: 100 },
    );
  });

  it('返回结果是输入数组的子集（不会凭空创造新闻）', () => {
    fc.assert(
      fc.property(
        fc.array(newsItemArb, { minLength: 0, maxLength: 30 }),
        stockIdentifierArb,
        stockIdentifierArb,
        (items, stockName, stockSymbol) => {
          const result = filterNewsByStock(items, stockName, stockSymbol);

          // 返回的每条新闻都必须存在于原始输入中
          for (const item of result) {
            expect(items).toContainEqual(item);
          }
        },
      ),
      { numRuns: 100 },
    );
  });

  it('不会遗漏任何匹配的新闻条目', () => {
    fc.assert(
      fc.property(
        fc.array(newsItemArb, { minLength: 0, maxLength: 30 }),
        stockIdentifierArb,
        stockIdentifierArb,
        (items, stockName, stockSymbol) => {
          const result = filterNewsByStock(items, stockName, stockSymbol);

          // 手动计算应匹配的条目
          const expectedMatches = items.filter((item) => {
            const titleMatch =
              item.title.includes(stockName) || item.title.includes(stockSymbol);
            const contentMatch =
              item.content?.includes(stockName) || item.content?.includes(stockSymbol);
            return titleMatch || contentMatch;
          });

          // 返回数量应与手动过滤一致
          expect(result.length).toBe(expectedMatches.length);
        },
      ),
      { numRuns: 100 },
    );
  });
});
