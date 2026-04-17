import { useState, useRef, useEffect, useCallback } from 'react';
import type { Stock } from '@/types';
import { calculateDialogPosition } from '@/utils/calculateDialogPosition';

/** Dialog 状态：当前显示的股票和定位坐标 */
export interface DialogState {
  stock: Stock | null;
  position: { x: number; y: number };
}

export interface UseStockDialogReturn {
  dialogState: DialogState;
  openDialog: (stock: Stock, clickEvent: React.MouseEvent) => void;
  closeDialog: () => void;
  dialogRef: React.RefObject<HTMLDivElement>;
}

/** Dialog 默认尺寸 */
const DEFAULT_DIALOG_WIDTH = 900;
const DEFAULT_DIALOG_HEIGHT = 760;

/**
 * 管理股票 Dialog 的打开/关闭、定位计算和外部点击检测
 */
export function useStockDialog(): UseStockDialogReturn {
  const [dialogState, setDialogState] = useState<DialogState>({
    stock: null,
    position: { x: 0, y: 0 },
  });

  const dialogRef = useRef<HTMLDivElement>(null!);

  const closeDialog = useCallback(() => {
    setDialogState({ stock: null, position: { x: 0, y: 0 } });
  }, []);

  const openDialog = useCallback(
    (stock: Stock, clickEvent: React.MouseEvent) => {
      // 点击同一股票时 toggle 关闭
      setDialogState((prev) => {
        if (prev.stock?.symbol === stock.symbol) {
          return { stock: null, position: { x: 0, y: 0 } };
        }

        const position = calculateDialogPosition({
          clickX: clickEvent.clientX,
          clickY: clickEvent.clientY,
          dialogWidth: DEFAULT_DIALOG_WIDTH,
          dialogHeight: DEFAULT_DIALOG_HEIGHT,
          viewportWidth: window.innerWidth,
          viewportHeight: window.innerHeight,
        });

        return { stock, position };
      });
    },
    [],
  );

  // 外部点击检测：mousedown 在 Dialog 外部时关闭
  useEffect(() => {
    if (!dialogState.stock) return;

    const handleMouseDown = (e: MouseEvent) => {
      if (
        dialogRef.current &&
        !dialogRef.current.contains(e.target as Node)
      ) {
        closeDialog();
      }
    };

    document.addEventListener('mousedown', handleMouseDown);
    return () => {
      document.removeEventListener('mousedown', handleMouseDown);
    };
  }, [dialogState.stock, closeDialog]);

  return { dialogState, openDialog, closeDialog, dialogRef };
}
