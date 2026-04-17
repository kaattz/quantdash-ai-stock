'use client';

import React, { useEffect, useState } from 'react';
import { Stock } from '../types';
import { loadLocalJsonFile } from '../services/localDataService';
import { Loader2 } from 'lucide-react';

export interface ProfilePanelProps {
  stock: Stock;
}

// 公司概况数据结构（对应 stock_company.json 中的单条记录）
interface CompanyInfo {
  chairman?: string;
  main_business?: string;
  introduction?: string;
  reg_capital?: number;
  setup_date?: string;
  province?: string;
  city?: string;
  website?: string;
  employees?: number;
}

// stock_company.json 文件结构
interface StockCompanyFile {
  updated?: string;
  data?: Record<string, CompanyInfo>;
}

// 格式化市值显示（亿元）
const formatMarketCap = (value: number | undefined): string => {
  if (value === undefined) return '--';
  return `${value.toFixed(2)} 亿`;
};

const formatMetric = (value: number | undefined): string => {
  if (value === undefined) return '--';
  return value.toFixed(2);
};

const ProfilePanel: React.FC<ProfilePanelProps> = ({ stock }) => {
  const [companyInfo, setCompanyInfo] = useState<CompanyInfo | null>(null);
  const [companyLoading, setCompanyLoading] = useState(true);

  useEffect(() => {
    let mounted = true;
    const load = async () => {
      setCompanyLoading(true);
      try {
        const file = await loadLocalJsonFile<StockCompanyFile>('stock_company.json');
        if (!mounted) return;
        const info = file?.data?.[stock.symbol] ?? null;
        setCompanyInfo(info);
      } catch {
        if (mounted) setCompanyInfo(null);
      } finally {
        if (mounted) setCompanyLoading(false);
      }
    };
    load();
    return () => { mounted = false; };
  }, [stock.symbol]);

  return (
    <div
      className="overflow-y-auto h-full px-4 py-3 text-sm"
      data-testid="profile-panel"
    >
      {/* 基本信息 */}
      <div className="mb-4">
        <div className="flex items-baseline gap-2 mb-1">
          <span
            className="text-lg font-bold text-slate-900 dark:text-[#e1e4ea]"
            data-testid="profile-name"
          >
            {stock.name}
          </span>
          <span
            className="text-xs text-[#848e9c]"
            data-testid="profile-symbol"
          >
            {stock.symbol}
          </span>
        </div>
        <div
          className="text-xs text-[#848e9c]"
          data-testid="profile-industry"
        >
          {stock.industry}
        </div>
      </div>

      {/* 财务指标 */}
      <div className="grid grid-cols-3 gap-3 mb-4">
        <div className="bg-slate-100 dark:bg-[#2b313f] rounded px-3 py-2">
          <div className="text-xs text-[#848e9c] mb-1">市盈率(PE)</div>
          <div
            className="text-sm font-mono text-slate-900 dark:text-[#e1e4ea]"
            data-testid="profile-pe"
          >
            {formatMetric(stock.pe)}
          </div>
        </div>
        <div className="bg-slate-100 dark:bg-[#2b313f] rounded px-3 py-2">
          <div className="text-xs text-[#848e9c] mb-1">市净率(PB)</div>
          <div
            className="text-sm font-mono text-slate-900 dark:text-[#e1e4ea]"
            data-testid="profile-pb"
          >
            {formatMetric(stock.pb)}
          </div>
        </div>
        <div className="bg-slate-100 dark:bg-[#2b313f] rounded px-3 py-2">
          <div className="text-xs text-[#848e9c] mb-1">总市值</div>
          <div
            className="text-sm font-mono text-slate-900 dark:text-[#e1e4ea]"
            data-testid="profile-market-cap"
          >
            {formatMarketCap(stock.marketCap)}
          </div>
        </div>
      </div>

      {/* 概念板块 */}
      <div className="mb-4">
        <div className="text-xs text-[#848e9c] mb-2">概念板块</div>
        {stock.concepts.length > 0 ? (
          <div className="flex flex-wrap gap-1.5">
            {stock.concepts.map((concept) => (
              <span
                key={concept}
                className="inline-block px-2 py-0.5 text-xs rounded bg-slate-100 dark:bg-[#2b313f] text-slate-700 dark:text-[#cfd3dc] border border-slate-200 dark:border-slate-600/50"
                data-testid="profile-concept-tag"
              >
                {concept}
              </span>
            ))}
          </div>
        ) : (
          <div
            className="text-xs text-[#848e9c]"
            data-testid="profile-no-concepts"
          >
            暂无概念板块数据
          </div>
        )}
      </div>

      {/* 公司概况 */}
      <div>
        <div className="text-xs text-[#848e9c] mb-2">公司概况</div>
        {companyLoading ? (
          <div className="flex items-center gap-2 text-xs text-[#848e9c]">
            <Loader2 className="animate-spin" size={14} /> 加载中...
          </div>
        ) : companyInfo ? (
          <div className="space-y-2" data-testid="profile-company-info">
            {/* 主营业务 */}
            {companyInfo.main_business && (
              <div className="bg-slate-100 dark:bg-[#2b313f] rounded px-3 py-2">
                <div className="text-xs text-[#848e9c] mb-1">主营业务</div>
                <div className="text-xs text-slate-700 dark:text-[#cfd3dc] leading-relaxed">
                  {companyInfo.main_business}
                </div>
              </div>
            )}
            {/* 公司简介 */}
            {companyInfo.introduction && (
              <div className="bg-slate-100 dark:bg-[#2b313f] rounded px-3 py-2">
                <div className="text-xs text-[#848e9c] mb-1">公司简介</div>
                <div className="text-xs text-slate-700 dark:text-[#cfd3dc] leading-relaxed">
                  {companyInfo.introduction}
                </div>
              </div>
            )}
            {/* 基本信息网格 */}
            <div className="grid grid-cols-2 gap-2 text-xs">
              {companyInfo.chairman && (
                <div className="bg-slate-100 dark:bg-[#2b313f] rounded px-3 py-1.5">
                  <span className="text-[#848e9c]">董事长：</span>
                  <span className="text-slate-700 dark:text-[#cfd3dc]">{companyInfo.chairman}</span>
                </div>
              )}
              {companyInfo.province && (
                <div className="bg-slate-100 dark:bg-[#2b313f] rounded px-3 py-1.5">
                  <span className="text-[#848e9c]">所在地：</span>
                  <span className="text-slate-700 dark:text-[#cfd3dc]">
                    {companyInfo.province}{companyInfo.city ? ` ${companyInfo.city}` : ''}
                  </span>
                </div>
              )}
              {companyInfo.setup_date && (
                <div className="bg-slate-100 dark:bg-[#2b313f] rounded px-3 py-1.5">
                  <span className="text-[#848e9c]">成立日期：</span>
                  <span className="text-slate-700 dark:text-[#cfd3dc]">{companyInfo.setup_date}</span>
                </div>
              )}
              {companyInfo.reg_capital != null && (
                <div className="bg-slate-100 dark:bg-[#2b313f] rounded px-3 py-1.5">
                  <span className="text-[#848e9c]">注册资本：</span>
                  <span className="text-slate-700 dark:text-[#cfd3dc]">{companyInfo.reg_capital} 万元</span>
                </div>
              )}
              {companyInfo.employees != null && (
                <div className="bg-slate-100 dark:bg-[#2b313f] rounded px-3 py-1.5">
                  <span className="text-[#848e9c]">员工人数：</span>
                  <span className="text-slate-700 dark:text-[#cfd3dc]">{companyInfo.employees.toLocaleString()}</span>
                </div>
              )}
              {companyInfo.website && (
                <div className="bg-slate-100 dark:bg-[#2b313f] rounded px-3 py-1.5">
                  <span className="text-[#848e9c]">官网：</span>
                  <span className="text-slate-700 dark:text-[#cfd3dc]">{companyInfo.website}</span>
                </div>
              )}
            </div>
          </div>
        ) : (
          <div
            className="text-xs text-[#848e9c]"
            data-testid="profile-no-description"
          >
            暂无公司概况数据，请运行 npm run sync:company 同步
          </div>
        )}
      </div>
    </div>
  );
};

export default ProfilePanel;
