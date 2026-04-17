import { describe, it, expect, vi } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useStockDialog } from '../useStockDialog';
import type { Stock } from '@/types';

/**
 * useStockDialog 单元测试
 * 验证需求: 1.1, 1.2, 2.3, 3.5
 */

// ── Mock calculateDialogPosition ──
vi.mock('@/utils/calculateDialogPosition', () => ({
  calculateDialogPosition: vi.fn(({ clickX, clickY }: { clickX: number; clickY: number }) => ({
    x: clickX + 15,
    y: clickY - 50,
  })),
}));

// ── Mock 数据 ──
const mockStockA: Stock = {
  symbol: '600000',
  name: '浦发银行',
  price: 10.5,
  pctChange: 2.3,
  volume: '1000万',
  turnover: '1.05亿',
  industry: '银行',
  concepts: ['金融', '沪股通'],
};

const mockStockB: Stock = {
  symbol: '000001',
  name: '平安银行',
  price: 15.2,
  pctChange: -1.1,
  volume: '800万',
  turnover: '1.22亿',
  industry: '银行',
  concepts: ['金融', '深股通'],
};

/** 创建 mock MouseEvent */
function createMockMouseEvent(clientX = 400, clientY = 300): React.MouseEvent {
  return { clientX, clientY } as unknown as React.MouseEvent;
}

describe('useStockDialog 单元测试', () => {
  // ── openDialog 设置正确的股票和位置 ──
  describe('openDialog 设置正确的股票和位置', () => {
    it('调用 openDialog 后 dialogState 应包含正确的股票', () => {
      const { result } = renderHook(() => useStockDialog());

      act(() => {
        result.current.openDialog(mockStockA, createMockMouseEvent(400, 300));
      });

      expect(result.current.dialogState.stock).toEqual(mockStockA);
    });

    it('调用 openDialog 后 dialogState 应包含计算后的位置', () => {
      const { result } = renderHook(() => useStockDialog());

      act(() => {
        result.current.openDialog(mockStockA, createMockMouseEvent(400, 300));
      });

      // mock 返回 { x: clickX + 15, y: clickY - 50 }
      expect(result.current.dialogState.position).toEqual({ x: 415, y: 250 });
    });

    it('切换到不同股票时应更新 dialogState', () => {
      const { result } = renderHook(() => useStockDialog());

      act(() => {
        result.current.openDialog(mockStockA, createMockMouseEvent(400, 300));
      });
      expect(result.current.dialogState.stock?.symbol).toBe('600000');

      act(() => {
        result.current.openDialog(mockStockB, createMockMouseEvent(500, 400));
      });
      expect(result.current.dialogState.stock?.symbol).toBe('000001');
      expect(result.current.dialogState.position).toEqual({ x: 515, y: 350 });
    });
  });

  // ── closeDialog 清空状态 ──
  describe('closeDialog 清空状态', () => {
    it('调用 closeDialog 后 stock 应为 null', () => {
      const { result } = renderHook(() => useStockDialog());

      act(() => {
        result.current.openDialog(mockStockA, createMockMouseEvent());
      });
      expect(result.current.dialogState.stock).not.toBeNull();

      act(() => {
        result.current.closeDialog();
      });
      expect(result.current.dialogState.stock).toBeNull();
    });

    it('调用 closeDialog 后 position 应重置为 (0, 0)', () => {
      const { result } = renderHook(() => useStockDialog());

      act(() => {
        result.current.openDialog(mockStockA, createMockMouseEvent());
      });

      act(() => {
        result.current.closeDialog();
      });
      expect(result.current.dialogState.position).toEqual({ x: 0, y: 0 });
    });
  });

  // ── 点击同一股票 toggle 关闭 ──
  describe('点击同一股票 toggle 关闭', () => {
    it('连续两次点击同一股票应关闭 Dialog', () => {
      const { result } = renderHook(() => useStockDialog());

      act(() => {
        result.current.openDialog(mockStockA, createMockMouseEvent());
      });
      expect(result.current.dialogState.stock?.symbol).toBe('600000');

      act(() => {
        result.current.openDialog(mockStockA, createMockMouseEvent());
      });
      expect(result.current.dialogState.stock).toBeNull();
      expect(result.current.dialogState.position).toEqual({ x: 0, y: 0 });
    });

    it('关闭后再次点击同一股票应重新打开', () => {
      const { result } = renderHook(() => useStockDialog());

      // 第一次打开
      act(() => {
        result.current.openDialog(mockStockA, createMockMouseEvent());
      });
      expect(result.current.dialogState.stock).not.toBeNull();

      // toggle 关闭
      act(() => {
        result.current.openDialog(mockStockA, createMockMouseEvent());
      });
      expect(result.current.dialogState.stock).toBeNull();

      // 再次打开
      act(() => {
        result.current.openDialog(mockStockA, createMockMouseEvent());
      });
      expect(result.current.dialogState.stock?.symbol).toBe('600000');
    });
  });

  // ── 外部点击关闭 Dialog ──
  describe('外部点击关闭 Dialog', () => {
    it('Dialog 打开时，在 document 上触发 mousedown 应关闭 Dialog', () => {
      const { result } = renderHook(() => useStockDialog());

      // 创建 Dialog DOM 元素并挂载，模拟真实场景中 ref 已绑定
      const dialogDiv = document.createElement('div');
      document.body.appendChild(dialogDiv);

      act(() => {
        result.current.openDialog(mockStockA, createMockMouseEvent());
      });
      expect(result.current.dialogState.stock).not.toBeNull();

      // 将 dialogDiv 赋值给 dialogRef，模拟组件渲染后 ref 绑定
      (result.current.dialogRef as React.MutableRefObject<HTMLDivElement>).current = dialogDiv;

      // 在 Dialog 外部（document.body）触发 mousedown
      act(() => {
        document.dispatchEvent(new MouseEvent('mousedown', { bubbles: true }));
      });
      expect(result.current.dialogState.stock).toBeNull();

      // 清理
      document.body.removeChild(dialogDiv);
    });

    it('Dialog 关闭时，mousedown 不应产生副作用', () => {
      const { result } = renderHook(() => useStockDialog());

      // Dialog 未打开，触发 mousedown 不应报错
      act(() => {
        document.dispatchEvent(new MouseEvent('mousedown', { bubbles: true }));
      });
      expect(result.current.dialogState.stock).toBeNull();
    });

    it('点击 Dialog 内部（dialogRef 包含的元素）不应关闭 Dialog', () => {
      const { result } = renderHook(() => useStockDialog());

      // 创建一个 div 模拟 Dialog DOM 元素
      const dialogDiv = document.createElement('div');
      document.body.appendChild(dialogDiv);

      act(() => {
        result.current.openDialog(mockStockA, createMockMouseEvent());
      });

      // 将 dialogDiv 赋值给 dialogRef
      // dialogRef 是 useRef 创建的，可以直接赋值 current
      (result.current.dialogRef as React.MutableRefObject<HTMLDivElement>).current = dialogDiv;

      // 在 dialogDiv 内部触发 mousedown
      act(() => {
        dialogDiv.dispatchEvent(new MouseEvent('mousedown', { bubbles: true }));
      });

      // Dialog 不应关闭
      expect(result.current.dialogState.stock).not.toBeNull();
      expect(result.current.dialogState.stock?.symbol).toBe('600000');

      // 清理
      document.body.removeChild(dialogDiv);
    });
  });
});
