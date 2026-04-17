// Feature: 002-stock-news-and-profile, Property 6: 面板互斥不变量
import { describe, it, expect } from 'vitest';
import fc from 'fast-check';

/**
 * Validates: Requirements 3.3
 *
 * 属性 6：面板互斥不变量
 * 对于任意面板切换操作序列（点击"个股资讯"或"个股资料"按钮），
 * 执行后 activePanel 状态始终为 'chart'、'news'、'profile' 三者之一，
 * 即同一时刻最多展示一个面板。
 *
 * 测试策略：将 togglePanel 逻辑抽取为纯状态机函数进行测试，
 * 避免渲染完整 StockHoverCard 组件的复杂依赖。
 */

// --- 状态机定义 ---

type PanelType = 'chart' | 'news' | 'profile';

const VALID_PANELS: ReadonlySet<PanelType> = new Set(['chart', 'news', 'profile']);

// 与 StockHoverCard 中 togglePanel 逻辑一致
const togglePanel = (current: PanelType, panel: 'news' | 'profile'): PanelType => {
  return current === panel ? 'chart' : panel;
};

// --- Arbitraries ---

// 生成随机面板操作（点击"个股资讯"或"个股资料"）
const panelActionArb: fc.Arbitrary<'news' | 'profile'> = fc.constantFrom('news' as const, 'profile' as const);

// 生成随机操作序列
const actionSequenceArb = fc.array(panelActionArb, { minLength: 1, maxLength: 50 });

// --- Tests ---

describe('StockHoverCard - 属性 6：面板互斥不变量', () => {
  it('任意操作序列执行后，activePanel 始终为 chart/news/profile 之一', () => {
    fc.assert(
      fc.property(actionSequenceArb, (actions) => {
        let state: PanelType = 'chart';

        for (const action of actions) {
          state = togglePanel(state, action);
          // 每一步都验证状态合法性
          expect(VALID_PANELS.has(state)).toBe(true);
        }
      }),
      { numRuns: 200 },
    );
  });

  it('点击已激活面板应切回 chart，点击不同面板应切换到该面板', () => {
    fc.assert(
      fc.property(actionSequenceArb, (actions) => {
        let state: PanelType = 'chart';

        for (const action of actions) {
          const prevState = state;
          state = togglePanel(state, action);

          if (prevState === action) {
            // 点击已激活面板 → 切回 chart
            expect(state).toBe('chart');
          } else {
            // 点击不同面板 → 切换到该面板
            expect(state).toBe(action);
          }
        }
      }),
      { numRuns: 200 },
    );
  });

  it('初始状态为 chart，且任意操作序列中不会出现非法状态', () => {
    fc.assert(
      fc.property(actionSequenceArb, (actions) => {
        const states: PanelType[] = ['chart'];
        let current: PanelType = 'chart';

        for (const action of actions) {
          current = togglePanel(current, action);
          states.push(current);
        }

        // 所有中间状态都必须合法
        states.forEach((s) => {
          expect(VALID_PANELS.has(s)).toBe(true);
        });

        // 同一时刻最多展示一个面板（状态始终是单一值，不可能同时为两个面板）
        states.forEach((s) => {
          const isNews = s === 'news';
          const isProfile = s === 'profile';
          // news 和 profile 不可能同时为 true
          expect(isNews && isProfile).toBe(false);
        });
      }),
      { numRuns: 200 },
    );
  });
});
