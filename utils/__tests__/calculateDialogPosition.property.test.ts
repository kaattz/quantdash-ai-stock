import { describe, it, expect } from 'vitest';
import * as fc from 'fast-check';
import { calculateDialogPosition } from '../calculateDialogPosition';

/**
 * Feature: 001-stock-card-click-trigger, Property 1: Dialog 视口包含性
 *
 * 对于任意有效的点击坐标和视口尺寸，calculateDialogPosition 计算出的
 * Dialog 位置应确保 Dialog 完全在视口内。
 *
 * 生成器约束：视口尺寸需 >= dialogSize + 2 * padding（默认 padding=10），
 * 以确保视口有足够空间容纳 Dialog 及其边距。
 *
 * **Validates: Requirements 4.2, 4.3, 4.4**
 */
describe('Feature: 001-stock-card-click-trigger, Property 1: Dialog 视口包含性', () => {
  const DEFAULT_PADDING = 10;

  it('Dialog 应始终完全在视口内（视口有足够空间容纳 Dialog 及边距时）', () => {
    fc.assert(
      fc.property(
        // 先生成 dialog 尺寸，再确保视口有足够空间（至少 2*padding 的余量）
        fc.integer({ min: 50, max: 2000 }),  // dialogWidth
        fc.integer({ min: 50, max: 2000 }),  // dialogHeight
        fc.nat({ max: 3000 }),               // extra viewport width (beyond minimum)
        fc.nat({ max: 3000 }),               // extra viewport height (beyond minimum)
        fc.integer({ min: 0, max: 5000 }),   // clickX
        fc.integer({ min: 0, max: 5000 }),   // clickY
        (dialogWidth, dialogHeight, extraW, extraH, clickX, clickY) => {
          // 视口需 >= dialogSize + 2*padding，确保有空间放置 Dialog 及边距
          const viewportWidth = dialogWidth + 2 * DEFAULT_PADDING + extraW;
          const viewportHeight = dialogHeight + 2 * DEFAULT_PADDING + extraH;

          const result = calculateDialogPosition({
            clickX,
            clickY,
            dialogWidth,
            dialogHeight,
            viewportWidth,
            viewportHeight,
          });

          // Dialog 完全在视口内
          expect(result.x).toBeGreaterThanOrEqual(0);
          expect(result.y).toBeGreaterThanOrEqual(0);
          expect(result.x + dialogWidth).toBeLessThanOrEqual(viewportWidth);
          expect(result.y + dialogHeight).toBeLessThanOrEqual(viewportHeight);
        },
      ),
      { numRuns: 200 },
    );
  });
});
