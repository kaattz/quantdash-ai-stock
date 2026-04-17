import React from 'react';
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import type { Stock } from '@/types';

/**
 * StockHoverCard 面板切换单元测试
 * 验证需求: 1.1, 1.4, 2.1, 2.5, 3.1, 3.2
 */

// ── Mock recharts ──
vi.mock('recharts', () => ({
  ResponsiveContainer: ({ children }: any) => <div>{children}</div>,
  ComposedChart: ({ children }: any) => <div>{children}</div>,
  Bar: () => null,
  Line: () => null,
  XAxis: () => null,
  YAxis: () => null,
  Tooltip: () => null,
  Cell: () => null,
  ReferenceLine: () => null,
}));

// ── Mock quotesService ──
vi.mock('../../services/quotesService', () => ({
  getStockKline: vi.fn().mockResolvedValue([]),
}));

// ── Mock chanService ──
vi.mock('../../services/chanService', () => ({
  analyzeChanStructure: vi.fn().mockReturnValue({
    mergedKlines: [], fractals: [], bis: [], segments: [], pivotZones: [],
    summary: { mergedCount: 0, fractalCount: 0, biCount: 0, segmentCount: 0, pivotZoneCount: 0, latestDirection: null },
  }),
}));

// ── Mock aiNavigationService ──
vi.mock('../../services/aiNavigationService', () => ({
  emitAIStockObservationRequest: vi.fn(),
}));

// ── Mock NewsPanel / ProfilePanel ──
vi.mock('../NewsPanel', () => ({
  default: () => <div data-testid="news-panel">NewsPanel</div>,
}));
vi.mock('../ProfilePanel', () => ({
  default: () => <div data-testid="profile-panel">ProfilePanel</div>,
}));

// ── Mock lucide-react ──
vi.mock('lucide-react', () => ({
  Loader2: (props: any) => <span {...props} data-testid="loader" />,
  Plus: () => <span />,
  LayoutGrid: () => <span />,
  FileText: () => <span />,
  Info: () => <span />,
  Lock: () => <span />,
  Maximize2: () => <span />,
  Minimize2: () => <span />,
  Sparkles: () => <span />,
}));

// ── Mock newsService ──
vi.mock('../../services/newsService', () => ({
  getInfoGatheringNews: vi.fn().mockResolvedValue([]),
  filterNewsByStock: vi.fn().mockReturnValue([]),
}));

import StockHoverCard from '../StockHoverCard';

// ── 测试数据 ──
const mockStock: Stock = {
  symbol: '600000',
  name: '浦发银行',
  price: 10.5,
  pctChange: 1.2,
  volume: '300万',
  turnover: '3000万',
  industry: '银行',
  concepts: ['金融科技'],
};

describe('StockHoverCard 面板切换单元测试', () => {
  // ── 需求 1.1: 点击"个股资讯"展示 NewsPanel ──
  it('点击"个股资讯"按钮应展示 NewsPanel', () => {
    render(<StockHoverCard stock={mockStock} />);

    expect(screen.queryByTestId('news-panel')).toBeNull();

    fireEvent.click(screen.getByText('个股资讯'));

    expect(screen.getByTestId('news-panel')).toBeDefined();
  });

  // ── 需求 1.4: 再次点击关闭 NewsPanel 恢复图表 ──
  it('再次点击"个股资讯"应关闭 NewsPanel', () => {
    render(<StockHoverCard stock={mockStock} />);

    const btn = screen.getByText('个股资讯');
    fireEvent.click(btn);
    expect(screen.getByTestId('news-panel')).toBeDefined();

    fireEvent.click(btn);
    expect(screen.queryByTestId('news-panel')).toBeNull();
  });

  // ── 需求 2.1: 点击"个股资料"展示 ProfilePanel ──
  it('点击"个股资料"按钮应展示 ProfilePanel', () => {
    render(<StockHoverCard stock={mockStock} />);

    expect(screen.queryByTestId('profile-panel')).toBeNull();

    fireEvent.click(screen.getByText('个股资料'));

    expect(screen.getByTestId('profile-panel')).toBeDefined();
  });

  // ── 需求 2.5: 再次点击关闭 ProfilePanel ──
  it('再次点击"个股资料"应关闭 ProfilePanel', () => {
    render(<StockHoverCard stock={mockStock} />);

    const btn = screen.getByText('个股资料');
    fireEvent.click(btn);
    expect(screen.getByTestId('profile-panel')).toBeDefined();

    fireEvent.click(btn);
    expect(screen.queryByTestId('profile-panel')).toBeNull();
  });

  // ── 需求 3.1: 面板互斥 news → profile ──
  it('从 NewsPanel 切换到 ProfilePanel 时应互斥', () => {
    render(<StockHoverCard stock={mockStock} />);

    fireEvent.click(screen.getByText('个股资讯'));
    expect(screen.getByTestId('news-panel')).toBeDefined();
    expect(screen.queryByTestId('profile-panel')).toBeNull();

    fireEvent.click(screen.getByText('个股资料'));
    expect(screen.getByTestId('profile-panel')).toBeDefined();
    expect(screen.queryByTestId('news-panel')).toBeNull();
  });

  // ── 需求 3.2: 面板互斥 profile → news ──
  it('从 ProfilePanel 切换到 NewsPanel 时应互斥', () => {
    render(<StockHoverCard stock={mockStock} />);

    fireEvent.click(screen.getByText('个股资料'));
    expect(screen.getByTestId('profile-panel')).toBeDefined();
    expect(screen.queryByTestId('news-panel')).toBeNull();

    fireEvent.click(screen.getByText('个股资讯'));
    expect(screen.getByTestId('news-panel')).toBeDefined();
    expect(screen.queryByTestId('profile-panel')).toBeNull();
  });
});
