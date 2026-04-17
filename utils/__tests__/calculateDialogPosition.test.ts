import { describe, it, expect } from 'vitest';
import { calculateDialogPosition } from '../calculateDialogPosition';

/**
 * calculateDialogPosition 单元测试
 * 验证需求: 4.2, 4.3, 4.4
 */

// 通用默认值
const DIALOG_W = 300;
const DIALOG_H = 200;
const VP_W = 1024;
const VP_H = 768;
const GAP = 15;
const PADDING = 10;

/** 构造输入的辅助函数 */
function makeInput(overrides: Record<string, number> = {}) {
  return {
    clickX: 400,
    clickY: 400,
    dialogWidth: DIALOG_W,
    dialogHeight: DIALOG_H,
    viewportWidth: VP_W,
    viewportHeight: VP_H,
    ...overrides,
  };
}

describe('calculateDialogPosition 单元测试', () => {
  // ── 右侧放不下时切换到左侧 ──
  describe('右侧放不下时切换到左侧', () => {
    it('点击位置靠近右边缘时，Dialog 应出现在点击位置左侧', () => {
      // 点击位置在 x=900，右侧剩余 1024-900=124，不够放 300+15+10
      const result = calculateDialogPosition(makeInput({ clickX: 900 }));
      // 左侧定位: clickX - dialogWidth - gap = 900 - 300 - 15 = 585
      expect(result.x).toBe(585);
    });

    it('点击位置刚好让右侧放不下时切换到左侧', () => {
      // 右侧需要: clickX + gap + dialogWidth + padding <= viewportWidth
      // 临界: clickX + 15 + 300 + 10 = 1024 → clickX = 699
      // clickX = 700 时右侧放不下
      const result = calculateDialogPosition(makeInput({ clickX: 700 }));
      expect(result.x).toBe(700 - DIALOG_W - GAP); // 385
    });

    it('点击位置刚好让右侧放得下时不切换', () => {
      // clickX + gap + dialogWidth = clickX + 315, 需要 <= viewportWidth - padding = 1014
      // clickX = 699 → 699 + 315 = 1014, 刚好放得下
      const result = calculateDialogPosition(makeInput({ clickX: 699 }));
      expect(result.x).toBe(699 + GAP); // 714
    });
  });

  // ── 底部超出时向上调整 ──
  describe('底部超出时向上调整', () => {
    it('点击位置靠近底部时，Dialog 应向上调整', () => {
      // clickY=700, y = 700 - 200/4 = 650, 650+200=850 > 768-10=758
      const result = calculateDialogPosition(makeInput({ clickY: 700 }));
      // 向上调整: viewportHeight - dialogHeight - padding = 768 - 200 - 10 = 558
      expect(result.y).toBe(558);
    });

    it('点击位置在最底部时也能正确调整', () => {
      const result = calculateDialogPosition(makeInput({ clickY: VP_H }));
      expect(result.y).toBe(VP_H - DIALOG_H - PADDING); // 558
    });
  });

  // ── 顶部超出时对齐顶部 ──
  describe('顶部超出时对齐顶部', () => {
    it('点击位置靠近顶部时，Dialog 应对齐到顶部 padding', () => {
      // clickY=20, y = 20 - 200/4 = -30, 小于 padding=10
      const result = calculateDialogPosition(makeInput({ clickY: 20 }));
      expect(result.y).toBe(PADDING); // 10
    });

    it('点击位置在最顶部时对齐到 padding', () => {
      const result = calculateDialogPosition(makeInput({ clickY: 0 }));
      // clickY clamp 到 padding=10, y = 10 - 50 = -40, 小于 padding → y = 10
      expect(result.y).toBe(PADDING);
    });
  });

  // ── 坐标异常值处理 ──
  describe('坐标异常值处理 (NaN, 负数)', () => {
    it('clickX 为 NaN 时应 clamp 到安全范围', () => {
      const result = calculateDialogPosition(makeInput({ clickX: NaN }));
      // NaN → sanitize → 0 → clamp(0, 10, 1014) → 10
      // x = 10 + 15 = 25
      expect(result.x).toBeGreaterThanOrEqual(0);
      expect(result.x + DIALOG_W).toBeLessThanOrEqual(VP_W);
    });

    it('clickY 为 NaN 时应 clamp 到安全范围', () => {
      const result = calculateDialogPosition(makeInput({ clickY: NaN }));
      // NaN → sanitize → 0 → clamp(0, 10, 758) → 10
      expect(result.y).toBeGreaterThanOrEqual(0);
      expect(result.y + DIALOG_H).toBeLessThanOrEqual(VP_H);
    });

    it('clickX 为负数时应 clamp 到 padding', () => {
      const result = calculateDialogPosition(makeInput({ clickX: -100 }));
      // clamp(-100, 10, 1014) → 10, x = 10 + 15 = 25
      expect(result.x).toBe(PADDING + GAP); // 25
    });

    it('clickY 为负数时应 clamp 到 padding', () => {
      const result = calculateDialogPosition(makeInput({ clickY: -50 }));
      // clamp(-50, 10, 758) → 10, y = 10 - 50 = -40 → 顶部对齐 → 10
      expect(result.y).toBe(PADDING);
    });

    it('两个坐标都为 NaN 时仍返回有效位置', () => {
      const result = calculateDialogPosition(makeInput({ clickX: NaN, clickY: NaN }));
      expect(result.x).toBeGreaterThanOrEqual(0);
      expect(result.y).toBeGreaterThanOrEqual(0);
      expect(result.x + DIALOG_W).toBeLessThanOrEqual(VP_W);
      expect(result.y + DIALOG_H).toBeLessThanOrEqual(VP_H);
    });
  });

  // ── 视口小于 Dialog 时返回 (0, 0) ──
  describe('视口小于 Dialog 时返回 (0, 0)', () => {
    it('视口宽度小于 Dialog 宽度时返回 (0, 0)', () => {
      const result = calculateDialogPosition(makeInput({ viewportWidth: 200 }));
      expect(result).toEqual({ x: 0, y: 0 });
    });

    it('视口高度小于 Dialog 高度时返回 (0, 0)', () => {
      const result = calculateDialogPosition(makeInput({ viewportHeight: 100 }));
      expect(result).toEqual({ x: 0, y: 0 });
    });

    it('视口宽高都小于 Dialog 时返回 (0, 0)', () => {
      const result = calculateDialogPosition(
        makeInput({ viewportWidth: 100, viewportHeight: 50 }),
      );
      expect(result).toEqual({ x: 0, y: 0 });
    });

    it('视口尺寸刚好等于 Dialog 尺寸时不返回 (0, 0)', () => {
      const result = calculateDialogPosition(
        makeInput({ viewportWidth: DIALOG_W, viewportHeight: DIALOG_H }),
      );
      // 视口 == Dialog 尺寸，不触发 (0,0) 分支
      expect(result).not.toEqual({ x: 0, y: 0 });
    });
  });
});
