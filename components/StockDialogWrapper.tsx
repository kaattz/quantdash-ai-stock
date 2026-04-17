import React, { Suspense } from 'react';
import { Loader2 } from 'lucide-react';
import type { Stock } from '@/types';

// 懒加载 StockHoverCard 组件
const StockHoverCard = React.lazy(() => import('./StockHoverCard'));

interface StockDialogWrapperProps {
  stock: Stock;
  position?: { x: number; y: number };
  onClose: () => void;
  dialogRef: React.RefObject<HTMLDivElement>;
  onSizeChange?: (size: { width: number; height: number }) => void;
  /** 是否居中显示（全屏遮罩 + 居中），默认 true */
  centered?: boolean;
}

/**
 * 股票 Dialog 包装组件
 * - centered 模式：全屏半透明遮罩 + 居中显示，点击遮罩关闭
 * - 非 centered 模式：fixed 定位渲染在指定坐标
 * - 右上角关闭按钮（× 图标）
 * - 内部渲染 StockHoverCard，包裹 Suspense 和加载 fallback
 * - 通过 dialogRef 支持外部点击检测
 */
const StockDialogWrapper: React.FC<StockDialogWrapperProps> = ({
  stock,
  position,
  onClose,
  dialogRef,
  onSizeChange,
  centered = true,
}) => {
  const cardContent = (
    <div ref={dialogRef} className="relative">
      {/* 关闭按钮 */}
      <button
        onClick={onClose}
        className="absolute -top-3 -right-3 z-10 w-6 h-6 rounded-full bg-slate-900 text-white flex items-center justify-center text-xs cursor-pointer hover:bg-red-500 transition-colors"
        aria-label="关闭"
      >
        ×
      </button>

      {/* StockHoverCard 内容 */}
      <Suspense
        fallback={
          <div className="w-[320px] h-[180px] rounded-lg border border-slate-200 dark:border-slate-700 bg-white/95 dark:bg-slate-900/95 shadow-2xl flex items-center justify-center text-slate-500 dark:text-gray-400">
            <Loader2 className="animate-spin" />
          </div>
        }
      >
        <StockHoverCard stock={stock} onSizeChange={onSizeChange} />
      </Suspense>
    </div>
  );

  if (centered) {
    return (
      <div
        className="fixed inset-0 flex items-center justify-center"
        style={{ zIndex: 99 }}
        onClick={(e) => {
          // 点击遮罩（非 card 区域）关闭
          if (e.target === e.currentTarget) onClose();
        }}
      >
        {cardContent}
      </div>
    );
  }

  return (
    <div
      ref={dialogRef}
      className="fixed"
      style={{ left: position?.x ?? 0, top: position?.y ?? 0, zIndex: 99 }}
    >
      {cardContent}
    </div>
  );
};

export default StockDialogWrapper;
