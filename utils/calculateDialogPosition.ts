/**
 * Dialog 定位计算纯函数
 * 根据点击位置和视口尺寸计算 Dialog 的最佳显示位置
 */

export interface PositionInput {
  clickX: number;          // 点击的 clientX
  clickY: number;          // 点击的 clientY
  dialogWidth: number;     // Dialog 宽度
  dialogHeight: number;    // Dialog 高度
  viewportWidth: number;   // 视口宽度
  viewportHeight: number;  // 视口高度
  gap?: number;            // 点击位置与 Dialog 的间距，默认 15
  padding?: number;        // 视口边缘安全间距，默认 10
}

export interface PositionOutput {
  x: number;  // Dialog left 值
  y: number;  // Dialog top 值
}

/**
 * 计算 Dialog 在视口中的最佳位置
 *
 * 定位算法：
 * 1. 默认将 Dialog 放在点击位置右侧，垂直居中偏上
 * 2. 若右侧放不下，则放到左侧
 * 3. 若底部超出，向上调整
 * 4. 若顶部超出，对齐到顶部
 *
 * 边界情况：
 * - 坐标 NaN/负数时 clamp 到 [padding, viewport - padding] 范围
 * - 视口尺寸小于 Dialog 尺寸时返回 (0, 0)
 */
export function calculateDialogPosition(input: PositionInput): PositionOutput {
  const gap = input.gap ?? 15;
  const padding = input.padding ?? 10;
  const { dialogWidth, dialogHeight, viewportWidth, viewportHeight } = input;

  // 视口尺寸小于 Dialog 尺寸时返回 (0, 0)
  if (viewportWidth < dialogWidth || viewportHeight < dialogHeight) {
    return { x: 0, y: 0 };
  }

  // 坐标 NaN/负数时 clamp 到安全范围
  const clickX = clamp(
    sanitize(input.clickX),
    padding,
    viewportWidth - padding
  );
  const clickY = clamp(
    sanitize(input.clickY),
    padding,
    viewportHeight - padding
  );

  // 1. 默认右侧，垂直居中偏上
  let x = clickX + gap;
  let y = clickY - dialogHeight / 4;

  // 2. 右侧放不下则左侧
  if (x + dialogWidth > viewportWidth - padding) {
    x = clickX - dialogWidth - gap;
  }

  // 3. 底部超出向上调整
  if (y + dialogHeight > viewportHeight - padding) {
    y = viewportHeight - dialogHeight - padding;
  }

  // 4. 顶部超出对齐顶部
  if (y < padding) {
    y = padding;
  }

  // 最终确保 x 不小于 padding
  if (x < padding) {
    x = padding;
  }

  return { x, y };
}

/** 将 NaN 转为 0 */
function sanitize(value: number): number {
  return Number.isNaN(value) ? 0 : value;
}

/** 将值限制在 [min, max] 范围内 */
function clamp(value: number, min: number, max: number): number {
  if (max < min) return min;
  return Math.min(Math.max(value, min), max);
}
