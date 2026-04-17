// Feature: 002-stock-news-and-profile, Property 2: 标题匹配优先排序
import fc from 'fast-check';
import { filterNewsByStock } from '../newsService';
import type { NewsItem } from '../../types';

/**
 * Validates: Requirements 4.2
 *
 * 属性 2：标题匹配优先排序
 * 对于任意经过 filterNewsByStock 过滤并排序后的新闻列表，
 * 所有标题中包含股票名称的条目应排在仅内容匹配的条目之前。
 */

// --- Arbitraries ---

const newsTypeArb = fc.constantFrom('notice' as const, 'news' as const, 'report' as const);

const sentimentArb = fc.constantFrom('bullish' as const, 'bearish' as const, 'neutral' as const, null);

const stockName = 'TestStock';
const stockSymbol = 'TS001';

/**
 * 生成标题中包含 stockName 的新闻条目（标题匹配）
 */
const titleMatchedItemArb: fc.Arbitrary<NewsItem> = fc.record({
  id: fc.uuid(),
  title: fc.string({ minLength: 0, maxLength: 40 }).map((s) => `${s}${stockName}${s.slice(0, 5)}`),
  source: fc.string({ minLength: 1, maxLength: 20 }),
  time: fc.string({ minLength: 1, maxLength: 20 }),
  content: fc.string({ minLength: 0, maxLength: 100 }),
  url: fc.option(fc.webUrl(), { nil: undefined }),
  sentiment: fc.option(sentimentArb, { nil: undefined }),
  type: newsTypeArb,
});

/**
 * 生成仅内容中包含 stockName 的新闻条目（内容匹配，标题不含）
 */
const contentOnlyMatchedItemArb: fc.Arbitrary<NewsItem> = fc.record({
  id: fc.uuid(),
  title: fc.string({ minLength: 1, maxLength: 40 }).filter(
    (t) => !t.includes(stockName) && !t.includes(stockSymbol),
  ),
  source: fc.string({ minLength: 1, maxLength: 20 }),
  time: fc.string({ minLength: 1, maxLength: 20 }),
  content: fc.string({ minLength: 0, maxLength: 40 }).map((s) => `${s}${stockName}${s.slice(0, 5)}`),
  url: fc.option(fc.webUrl(), { nil: undefined }),
  sentiment: fc.option(sentimentArb, { nil: undefined }),
  type: newsTypeArb,
});

/**
 * 生成不匹配的新闻条目（标题和内容都不含 stockName/stockSymbol）
 */
const unmatchedItemArb: fc.Arbitrary<NewsItem> = fc.record({
  id: fc.uuid(),
  title: fc.string({ minLength: 1, maxLength: 40 }).filter(
    (t) => !t.includes(stockName) && !t.includes(stockSymbol),
  ),
  source: fc.string({ minLength: 1, maxLength: 20 }),
  time: fc.string({ minLength: 1, maxLength: 20 }),
  content: fc.string({ minLength: 0, maxLength: 100 }).filter(
    (c) => !c.includes(stockName) && !c.includes(stockSymbol),
  ),
  url: fc.option(fc.webUrl(), { nil: undefined }),
  sentiment: fc.option(sentimentArb, { nil: undefined }),
  type: newsTypeArb,
});

describe('filterNewsByStock - 属性 2：标题匹配优先排序', () => {
  it('排序后所有标题匹配条目排在仅内容匹配条目之前', () => {
    fc.assert(
      fc.property(
        fc.array(titleMatchedItemArb, { minLength: 1, maxLength: 10 }),
        fc.array(contentOnlyMatchedItemArb, { minLength: 1, maxLength: 10 }),
        fc.array(unmatchedItemArb, { minLength: 0, maxLength: 5 }),
        (titleItems, contentItems, unmatchedItems) => {
          // 混合所有类型的新闻条目
          const mixed = [...contentItems, ...unmatchedItems, ...titleItems];

          const result = filterNewsByStock(mixed, stockName, stockSymbol);

          // 不匹配的条目应被过滤掉
          expect(result.length).toBe(titleItems.length + contentItems.length);

          // 找到第一个仅内容匹配条目的索引
          const firstContentOnlyIndex = result.findIndex((item) => {
            const inTitle = item.title.includes(stockName) || item.title.includes(stockSymbol);
            return !inTitle;
          });

          // 如果存在仅内容匹配条目，则其之前的所有条目都应是标题匹配
          if (firstContentOnlyIndex > 0) {
            for (let i = 0; i < firstContentOnlyIndex; i++) {
              const inTitle =
                result[i].title.includes(stockName) || result[i].title.includes(stockSymbol);
              expect(inTitle).toBe(true);
            }
          }

          // 从第一个仅内容匹配条目开始，后续不应再出现标题匹配条目
          if (firstContentOnlyIndex >= 0) {
            for (let i = firstContentOnlyIndex; i < result.length; i++) {
              const inTitle =
                result[i].title.includes(stockName) || result[i].title.includes(stockSymbol);
              expect(inTitle).toBe(false);
            }
          }
        },
      ),
      { numRuns: 100 },
    );
  });
});
