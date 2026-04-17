// Feature: 002-stock-news-and-profile, Task 2.3: NewsPanel 单元测试
import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import NewsPanel from '../NewsPanel';
import type { Stock, NewsItem } from '../../types';

// --- Mock newsService ---
vi.mock('../../services/newsService', () => ({
  getInfoGatheringNews: vi.fn(),
  filterNewsByStock: vi.fn(),
}));

import { getInfoGatheringNews, filterNewsByStock } from '../../services/newsService';

const mockedGetNews = vi.mocked(getInfoGatheringNews);
const mockedFilter = vi.mocked(filterNewsByStock);

// --- Mock lucide-react ---
vi.mock('lucide-react', () => ({
  Loader2: (props: Record<string, unknown>) =>
    React.createElement('span', { 'data-testid': 'loader-icon', ...props }),
}));

// --- 测试数据 ---
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

const mockNewsItems: NewsItem[] = [
  {
    id: '1',
    title: '浦发银行发布年报',
    source: '财联社',
    time: '10:30',
    content: '浦发银行2024年年报显示营收增长',
    url: 'https://example.com/news/1',
    type: 'news',
  },
  {
    id: '2',
    title: '银行板块集体走强',
    source: '东方财富',
    time: '11:00',
    content: '浦发银行涨幅居前',
    type: 'news',
  },
];

describe('NewsPanel 单元测试', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  // 需求 1.5：加载中显示 loading 指示器
  it('加载中应显示 loading 指示器', () => {
    mockedGetNews.mockReturnValue(new Promise(() => {})); // 永不 resolve

    render(<NewsPanel stock={mockStock} />);

    expect(screen.getByTestId('news-loading')).toBeDefined();
    expect(screen.getByTestId('loader-icon')).toBeDefined();
  });

  // 需求 1.6：空数据显示空状态提示
  it('数据为空时应显示"暂无相关资讯"', async () => {
    mockedGetNews.mockResolvedValue([]);

    render(<NewsPanel stock={mockStock} />);

    await waitFor(() => {
      expect(screen.getByTestId('news-empty')).toBeDefined();
    });
    expect(screen.getByText('暂无相关资讯')).toBeDefined();
  });

  // 需求 1.6：加载失败显示空状态提示
  it('加载失败时应显示"暂无相关资讯"', async () => {
    mockedGetNews.mockRejectedValue(new Error('网络错误'));

    render(<NewsPanel stock={mockStock} />);

    await waitFor(() => {
      expect(screen.getByTestId('news-empty')).toBeDefined();
    });
    expect(screen.getByText('暂无相关资讯')).toBeDefined();
  });

  // 需求 1.3：新闻列表正确渲染
  it('应正确渲染新闻列表，展示标题、来源、时间', async () => {
    mockedGetNews.mockResolvedValue(mockNewsItems);
    mockedFilter.mockReturnValue(mockNewsItems);

    render(<NewsPanel stock={mockStock} />);

    await waitFor(() => {
      expect(screen.getByTestId('news-list')).toBeDefined();
    });

    // 验证新闻条目数量
    const items = screen.getAllByTestId('news-item');
    expect(items.length).toBe(2);

    // 验证来源和时间
    const sources = screen.getAllByTestId('news-source');
    expect(sources[0].textContent).toBe('财联社');
    expect(sources[1].textContent).toBe('东方财富');

    const times = screen.getAllByTestId('news-time');
    expect(times[0].textContent).toBe('10:30');
    expect(times[1].textContent).toBe('11:00');

    // 有 url 的新闻标题应为链接
    const link = screen.getByTestId('news-link') as HTMLAnchorElement;
    expect(link.textContent).toBe('浦发银行发布年报');
    expect(link.getAttribute('href')).toBe('https://example.com/news/1');
    expect(link.getAttribute('target')).toBe('_blank');

    // 无 url 的新闻标题应为普通文本
    const titleText = screen.getByTestId('news-title-text');
    expect(titleText.textContent).toBe('银行板块集体走强');
    expect(titleText.tagName).toBe('SPAN');
  });
});
