'use client';

import React, { useEffect, useState } from 'react';
import { Stock, NewsItem } from '../types';
import { getInfoGatheringNews, filterNewsByStock } from '../services/newsService';
import { Loader2 } from 'lucide-react';

export interface NewsPanelProps {
  stock: Stock;
}

const NewsPanel: React.FC<NewsPanelProps> = ({ stock }) => {
  const [loading, setLoading] = useState(true);
  const [allNews, setAllNews] = useState<NewsItem[]>([]);
  const [fetchFailed, setFetchFailed] = useState(false);

  useEffect(() => {
    let mounted = true;

    const load = async () => {
      setLoading(true);
      setFetchFailed(false);
      try {
        const news = await getInfoGatheringNews();
        if (!mounted) return;
        setAllNews(news);
      } catch {
        if (!mounted) return;
        setFetchFailed(true);
        setAllNews([]);
      } finally {
        if (mounted) setLoading(false);
      }
    };

    load();
    return () => { mounted = false; };
  }, []);

  // 加载中
  if (loading) {
    return (
      <div className="flex items-center justify-center h-full" data-testid="news-loading">
        <Loader2 className="animate-spin text-[#848e9c]" size={24} />
      </div>
    );
  }

  // 加载失败或无数据
  if (fetchFailed || allNews.length === 0) {
    return (
      <div className="flex items-center justify-center h-full text-sm text-[#848e9c]" data-testid="news-empty">
        暂无相关资讯
      </div>
    );
  }

  const filtered = filterNewsByStock(allNews, stock.name, stock.symbol);

  // 过滤后无匹配
  if (filtered.length === 0) {
    return (
      <div className="flex items-center justify-center h-full text-sm text-[#848e9c]" data-testid="news-no-match">
        暂无该股相关资讯
      </div>
    );
  }

  return (
    <div className="overflow-y-auto h-full px-3 py-2" data-testid="news-list">
      {filtered.map((item) => (
        <div
          key={item.id}
          className="py-2 border-b border-slate-200 dark:border-slate-700/50 last:border-b-0"
          data-testid="news-item"
        >
          <div className="text-sm text-slate-900 dark:text-[#e1e4ea] leading-snug">
            {item.url ? (
              <a
                href={item.url}
                target="_blank"
                rel="noopener noreferrer"
                className="hover:text-[#f0b90b] transition-colors"
                data-testid="news-link"
              >
                {item.title}
              </a>
            ) : (
              <span data-testid="news-title-text">{item.title}</span>
            )}
          </div>
          <div className="flex items-center gap-2 mt-1 text-xs text-[#848e9c]">
            <span data-testid="news-source">{item.source}</span>
            <span>·</span>
            <span data-testid="news-time">{item.time}</span>
          </div>
        </div>
      ))}
    </div>
  );
};

export default NewsPanel;
