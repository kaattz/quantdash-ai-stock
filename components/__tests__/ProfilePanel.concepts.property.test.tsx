// Feature: 002-stock-news-and-profile, Property 5: 概念板块标签完整性
import React from 'react';
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import fc from 'fast-check';
import ProfilePanel from '../ProfilePanel';
import type { Stock } from '../../types';

/**
 * Validates: Requirements 2.4
 *
 * 属性 5：概念板块标签完整性
 * 对于任意 Stock 对象，当其 concepts 数组非空时，ProfilePanel 应为数组中的每个概念
 * 渲染一个标签，且标签数量等于 concepts.length。
 */

// --- Arbitraries ---

// 生成非空概念字符串（避免空白字符串）
const conceptArb = fc.string({ minLength: 1, maxLength: 10 }).filter((s) => s.trim().length > 0);

// 生成随机 Stock 对象，concepts 数组长度可变（包括空数组）
const stockArb = (concepts: fc.Arbitrary<string[]>): fc.Arbitrary<Stock> =>
  fc.record({
    symbol: fc.stringMatching(/^[0-9]{6}$/),
    name: fc.string({ minLength: 1, maxLength: 10 }).filter((s) => s.trim().length > 0),
    price: fc.float({ min: Math.fround(0.01), max: Math.fround(9999), noNaN: true }),
    pctChange: fc.float({ min: Math.fround(-10), max: Math.fround(10), noNaN: true }),
    volume: fc.string({ minLength: 1, maxLength: 10 }),
    turnover: fc.string({ minLength: 1, maxLength: 10 }),
    industry: fc.string({ minLength: 1, maxLength: 10 }).filter((s) => s.trim().length > 0),
    concepts,
    pe: fc.option(fc.float({ min: Math.fround(0.01), max: Math.fround(9999), noNaN: true }), { nil: undefined }),
    pb: fc.option(fc.float({ min: Math.fround(0.01), max: Math.fround(9999), noNaN: true }), { nil: undefined }),
    marketCap: fc.option(fc.float({ min: Math.fround(0.01), max: Math.fround(99999), noNaN: true }), { nil: undefined }),
  });

// --- Tests ---

describe('ProfilePanel - 属性 5：概念板块标签完整性', () => {
  it('当 concepts 非空时，渲染的标签数量应等于 concepts.length', () => {
    const nonEmptyConceptsArb = fc.uniqueArray(conceptArb, { minLength: 1, maxLength: 10 });

    fc.assert(
      fc.property(stockArb(nonEmptyConceptsArb), (stock) => {
        const { unmount } = render(<ProfilePanel stock={stock} />);

        const tags = screen.getAllByTestId('profile-concept-tag');
        expect(tags).toHaveLength(stock.concepts.length);

        unmount();
      }),
      { numRuns: 100 },
    );
  });

  it('每个标签的文本内容应与对应的 concept 字符串匹配', () => {
    const nonEmptyConceptsArb = fc.uniqueArray(conceptArb, { minLength: 1, maxLength: 10 });

    fc.assert(
      fc.property(stockArb(nonEmptyConceptsArb), (stock) => {
        const { unmount } = render(<ProfilePanel stock={stock} />);

        const tags = screen.getAllByTestId('profile-concept-tag');
        const tagTexts = tags.map((tag) => tag.textContent);

        stock.concepts.forEach((concept) => {
          expect(tagTexts).toContain(concept);
        });

        unmount();
      }),
      { numRuns: 100 },
    );
  });

  it('当 concepts 为空数组时，应显示"暂无概念板块数据"', () => {
    const emptyConceptsArb = fc.constant([] as string[]);

    fc.assert(
      fc.property(stockArb(emptyConceptsArb), (stock) => {
        const { unmount } = render(<ProfilePanel stock={stock} />);

        const noConceptsEl = screen.getByTestId('profile-no-concepts');
        expect(noConceptsEl.textContent).toBe('暂无概念板块数据');

        // 确保没有渲染任何概念标签
        expect(screen.queryAllByTestId('profile-concept-tag')).toHaveLength(0);

        unmount();
      }),
      { numRuns: 100 },
    );
  });
});
