// Feature: 002-stock-news-and-profile, Property 4: 股票资料展示完整性
import React from 'react';
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import fc from 'fast-check';
import ProfilePanel from '../ProfilePanel';
import type { Stock } from '../../types';

/**
 * Validates: Requirements 2.2, 2.3, 2.7
 *
 * 属性 4：股票资料展示完整性
 * 对于任意 Stock 对象，ProfilePanel 的渲染输出应包含股票代码、名称和所属行业；
 * 对于 PE、PB、marketCap 等财务指标，当字段有值时应显示该数值，
 * 当字段为 undefined 时应显示 `--` 占位符。
 */

// --- Arbitraries ---

// 生成随机 Stock 对象，pe/pb/marketCap 可能为 undefined
const stockArb: fc.Arbitrary<Stock> = fc.record({
  symbol: fc.stringMatching(/^[0-9]{6}$/),
  name: fc.string({ minLength: 1, maxLength: 10 }).filter((s) => s.trim().length > 0),
  price: fc.float({ min: Math.fround(0.01), max: Math.fround(9999), noNaN: true }),
  pctChange: fc.float({ min: Math.fround(-10), max: Math.fround(10), noNaN: true }),
  volume: fc.string({ minLength: 1, maxLength: 10 }),
  turnover: fc.string({ minLength: 1, maxLength: 10 }),
  industry: fc.string({ minLength: 1, maxLength: 10 }).filter((s) => s.trim().length > 0),
  concepts: fc.array(fc.string({ minLength: 1, maxLength: 8 }), { minLength: 0, maxLength: 5 }),
  pe: fc.option(fc.float({ min: Math.fround(0.01), max: Math.fround(9999), noNaN: true }), { nil: undefined }),
  pb: fc.option(fc.float({ min: Math.fround(0.01), max: Math.fround(9999), noNaN: true }), { nil: undefined }),
  marketCap: fc.option(fc.float({ min: Math.fround(0.01), max: Math.fround(99999), noNaN: true }), { nil: undefined }),
});

// --- Tests ---

describe('ProfilePanel - 属性 4：股票资料展示完整性', () => {
  it('应始终展示股票代码、名称、行业信息', () => {
    fc.assert(
      fc.property(stockArb, (stock) => {
        const { unmount } = render(<ProfilePanel stock={stock} />);

        expect(screen.getByTestId('profile-symbol').textContent).toBe(stock.symbol);
        expect(screen.getByTestId('profile-name').textContent).toBe(stock.name);
        expect(screen.getByTestId('profile-industry').textContent).toBe(stock.industry);

        unmount();
      }),
      { numRuns: 100 },
    );
  });

  it('当 pe/pb/marketCap 有值时应显示格式化数值', () => {
    // 生成所有财务指标都有值的 Stock
    const stockWithMetricsArb = stockArb.map((s) => ({
      ...s,
      pe: s.pe ?? 12.34,
      pb: s.pb ?? 1.56,
      marketCap: s.marketCap ?? 100.5,
    }));

    fc.assert(
      fc.property(stockWithMetricsArb, (stock) => {
        const { unmount } = render(<ProfilePanel stock={stock} />);

        expect(screen.getByTestId('profile-pe').textContent).toBe(stock.pe!.toFixed(2));
        expect(screen.getByTestId('profile-pb').textContent).toBe(stock.pb!.toFixed(2));
        expect(screen.getByTestId('profile-market-cap').textContent).toBe(
          `${stock.marketCap!.toFixed(2)} 亿`,
        );

        unmount();
      }),
      { numRuns: 100 },
    );
  });

  it('当 pe/pb/marketCap 为 undefined 时应显示 "--"', () => {
    // 生成所有财务指标都为 undefined 的 Stock
    const stockWithoutMetricsArb = stockArb.map((s) => ({
      ...s,
      pe: undefined,
      pb: undefined,
      marketCap: undefined,
    }));

    fc.assert(
      fc.property(stockWithoutMetricsArb, (stock) => {
        const { unmount } = render(<ProfilePanel stock={stock} />);

        expect(screen.getByTestId('profile-pe').textContent).toBe('--');
        expect(screen.getByTestId('profile-pb').textContent).toBe('--');
        expect(screen.getByTestId('profile-market-cap').textContent).toBe('--');

        unmount();
      }),
      { numRuns: 100 },
    );
  });

  it('财务指标有值显示数值、undefined 显示 "--"（混合情况）', () => {
    fc.assert(
      fc.property(stockArb, (stock) => {
        const { unmount } = render(<ProfilePanel stock={stock} />);

        const peText = screen.getByTestId('profile-pe').textContent;
        const pbText = screen.getByTestId('profile-pb').textContent;
        const mcText = screen.getByTestId('profile-market-cap').textContent;

        if (stock.pe !== undefined) {
          expect(peText).toBe(stock.pe.toFixed(2));
        } else {
          expect(peText).toBe('--');
        }

        if (stock.pb !== undefined) {
          expect(pbText).toBe(stock.pb.toFixed(2));
        } else {
          expect(pbText).toBe('--');
        }

        if (stock.marketCap !== undefined) {
          expect(mcText).toBe(`${stock.marketCap.toFixed(2)} 亿`);
        } else {
          expect(mcText).toBe('--');
        }

        unmount();
      }),
      { numRuns: 100 },
    );
  });
});
