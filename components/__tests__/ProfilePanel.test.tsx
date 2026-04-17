// Feature: 002-stock-news-and-profile, Task 3.4: ProfilePanel 单元测试
import React from 'react';
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import ProfilePanel from '../ProfilePanel';
import type { Stock } from '../../types';

// --- 基础测试数据 ---
const baseStock: Stock = {
  symbol: '600000',
  name: '浦发银行',
  price: 10.5,
  pctChange: 1.2,
  volume: '300万',
  turnover: '3000万',
  industry: '银行',
  concepts: [],
};

describe('ProfilePanel 单元测试', () => {
  // 需求 2.6：concepts 为空时显示提示
  it('concepts 为空时应显示"暂无概念板块数据"', () => {
    render(<ProfilePanel stock={{ ...baseStock, concepts: [] }} />);

    expect(screen.getByTestId('profile-no-concepts')).toBeDefined();
    expect(screen.getByText('暂无概念板块数据')).toBeDefined();
    expect(screen.queryAllByTestId('profile-concept-tag').length).toBe(0);
  });

  // 需求 2.7：财务指标为 undefined 时显示 "--"
  it('财务指标为 undefined 时应显示"--"', () => {
    const stock: Stock = {
      ...baseStock,
      pe: undefined,
      pb: undefined,
      marketCap: undefined,
    };

    render(<ProfilePanel stock={stock} />);

    expect(screen.getByTestId('profile-pe').textContent).toBe('--');
    expect(screen.getByTestId('profile-pb').textContent).toBe('--');
    expect(screen.getByTestId('profile-market-cap').textContent).toBe('--');
  });

  // 需求 2.3：财务指标有值时正确展示
  it('财务指标有值时应显示格式化数值', () => {
    const stock: Stock = {
      ...baseStock,
      pe: 15.5,
      pb: 1.2,
      marketCap: 500.8,
    };

    render(<ProfilePanel stock={stock} />);

    expect(screen.getByTestId('profile-pe').textContent).toBe('15.50');
    expect(screen.getByTestId('profile-pb').textContent).toBe('1.20');
    expect(screen.getByTestId('profile-market-cap').textContent).toBe('500.80 亿');
  });
});
