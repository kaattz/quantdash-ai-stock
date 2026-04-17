import { describe, it, expect } from 'vitest';
import * as fc from 'fast-check';
import { renderHook, act } from '@testing-library/react';
import { useStockDialog } from '../useStockDialog';
import type { Stock } from '@/types';

/**
 * Feature: 001-stock-card-click-trigger, Property 2: Dialog 单例性
 *
 * 对于任意股票序列 [S1, S2, ..., Sn]，依次调用 openDialog 后，
 * dialogState.stock 应始终等于最后一次调用的股票 Sn，
 * 且不会同时存在多个 Dialog。
 *
 * **Validates: Requirements 1.2, 3.2**
 */
describe('Feature: 001-stock-card-click-trigger, Property 2: Dialog 单例性', () => {
  /** 生成一个随机 Stock 对象 */
  const stockArb = fc.record({
    symbol: fc.string({ minLength: 1, maxLength: 10 }).filter((s) => s.trim().length > 0),
    name: fc.string({ minLength: 1, maxLength: 20 }),
    price: fc.float({ min: Math.fround(0.01), max: Math.fround(10000), noNaN: true }),
    pctChange: fc.float({ min: Math.fround(-100), max: Math.fround(100), noNaN: true }),
    volume: fc.string({ minLength: 1, maxLength: 10 }),
    turnover: fc.string({ minLength: 1, maxLength: 10 }),
    industry: fc.string({ minLength: 1, maxLength: 20 }),
    concepts: fc.array(fc.string({ minLength: 1, maxLength: 10 }), { maxLength: 5 }),
  }) as fc.Arbitrary<Stock>;

  /** 生成一个 mock MouseEvent，提供 clientX/clientY */
  function createMockMouseEvent(): React.MouseEvent {
    return {
      clientX: 400,
      clientY: 300,
      // 提供 MouseEvent 所需的最小接口
    } as unknown as React.MouseEvent;
  }

  it('依次调用 openDialog 后，dialogState.stock 始终等于最后一次调用的股票', () => {
    fc.assert(
      fc.property(
        // 生成一个非空的股票序列（至少 1 个，最多 20 个），且 symbol 唯一
        fc.array(stockArb, { minLength: 1, maxLength: 20 }).map((stocks) => {
          // 确保 symbol 唯一：给每个 stock 加上索引后缀
          return stocks.map((s, i) => ({ ...s, symbol: `${s.symbol}_${i}` }));
        }),
        (stockSequence) => {
          const { result } = renderHook(() => useStockDialog());

          // 依次对每个股票调用 openDialog
          for (const stock of stockSequence) {
            act(() => {
              result.current.openDialog(stock, createMockMouseEvent());
            });

            // 每次调用后，dialogState.stock 应等于当前股票
            expect(result.current.dialogState.stock).not.toBeNull();
            expect(result.current.dialogState.stock!.symbol).toBe(stock.symbol);
          }

          // 最终状态：dialogState.stock 等于序列中最后一个股票
          const lastStock = stockSequence[stockSequence.length - 1];
          expect(result.current.dialogState.stock!.symbol).toBe(lastStock.symbol);
        },
      ),
      { numRuns: 100 },
    );
  });
});
