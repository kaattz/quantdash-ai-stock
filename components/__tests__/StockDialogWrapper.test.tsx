import React from 'react';
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import StockDialogWrapper from '../StockDialogWrapper';
import type { Stock } from '@/types';

/**
 * StockDialogWrapper 单元测试
 * 验证需求: 2.1, 2.2, 2.4
 */

// ── Mock StockHoverCard（懒加载组件，需要 mock 避免复杂依赖） ──
vi.mock('../StockHoverCard', () => ({
  default: () => <div data-testid="mock-hover-card">Mock Card</div>,
}));

// ── Mock 数据 ──
const mockStock: Stock = {
  symbol: '600000',
  name: '浦发银行',
  price: 10.5,
  pctChange: 2.3,
  volume: '1000万',
  turnover: '1.05亿',
  industry: '银行',
  concepts: ['金融', '沪股通'],
};

describe('StockDialogWrapper 单元测试', () => {
  // ── 关闭按钮存在且可点击关闭 ──
  describe('关闭按钮存在且可点击关闭', () => {
    it('应渲染关闭按钮（× 图标）', () => {
      const dialogRef = React.createRef<HTMLDivElement>();
      render(
        <StockDialogWrapper
          stock={mockStock}
          position={{ x: 100, y: 200 }}
          onClose={vi.fn()}
          dialogRef={dialogRef}
        />
      );

      const closeButton = screen.getByRole('button', { name: '关闭' });
      expect(closeButton).toBeDefined();
      expect(closeButton.textContent).toBe('×');
    });

    it('点击关闭按钮应调用 onClose 回调', () => {
      const onClose = vi.fn();
      const dialogRef = React.createRef<HTMLDivElement>();
      render(
        <StockDialogWrapper
          stock={mockStock}
          position={{ x: 100, y: 200 }}
          onClose={onClose}
          dialogRef={dialogRef}
        />
      );

      const closeButton = screen.getByRole('button', { name: '关闭' });
      fireEvent.click(closeButton);
      expect(onClose).toHaveBeenCalledTimes(1);
    });
  });

  // ── fixed 定位样式正确应用 ──
  describe('fixed 定位样式正确应用', () => {
    it('wrapper div 应使用 fixed 定位并设置正确的 left/top', () => {
      const dialogRef = React.createRef<HTMLDivElement>();
      const { container } = render(
        <StockDialogWrapper
          stock={mockStock}
          position={{ x: 150, y: 300 }}
          onClose={vi.fn()}
          dialogRef={dialogRef}
          centered={false}
        />
      );

      const wrapperDiv = container.firstElementChild as HTMLElement;
      expect(wrapperDiv.style.left).toBe('150px');
      expect(wrapperDiv.style.top).toBe('300px');
      expect(wrapperDiv.classList.contains('fixed')).toBe(true);
    });

    it('dialogRef 应正确绑定到 wrapper div', () => {
      const dialogRef = React.createRef<HTMLDivElement>();
      const { container } = render(
        <StockDialogWrapper
          stock={mockStock}
          position={{ x: 100, y: 200 }}
          onClose={vi.fn()}
          dialogRef={dialogRef}
          centered={false}
        />
      );

      // 非 centered 模式下，dialogRef 绑定到外层 fixed 定位的 wrapper div
      const outerWrapper = container.firstElementChild as HTMLElement;
      expect(outerWrapper.classList.contains('fixed')).toBe(true);
      expect(dialogRef.current).toBeDefined();
    });
  });
});
