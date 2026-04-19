# 实现计划：股票卡片点击触发

## 概述

将 StockInfoSection 和 LimitUpLadderSection 中 StockHoverCard 的触发方式从 hover 改为 click，提取三个共享模块（纯函数、Hook、Wrapper 组件），然后逐步改造两个业务模块。

## 任务

- [x] 1. 创建 `calculateDialogPosition` 纯函数
  - [x] 1.1 创建 `utils/calculateDialogPosition.ts` 文件
    - 实现 `PositionInput` 和 `PositionOutput` 接口
    - 实现定位算法：默认右侧 → 右侧放不下则左侧 → 底部超出向上调整 → 顶部超出对齐顶部
    - 处理边界情况：坐标 NaN/负数时 clamp 到安全范围，视口小于 Dialog 时返回 (0, 0)
    - _需求: 4.1, 4.2, 4.3, 4.4_

  - [x] 1.2 编写 `calculateDialogPosition` 属性测试
    - **属性 1: Dialog 视口包含性**
    - 使用 `fast-check` 生成随机 clickX、clickY、viewportWidth、viewportHeight、dialogWidth、dialogHeight
    - 验证输出位置确保 Dialog 完全在视口内：`x >= 0 && x + dialogWidth <= viewportWidth && y >= 0 && y + dialogHeight <= viewportHeight`
    - **验证需求: 4.2, 4.3, 4.4**

  - [x] 1.3 编写 `calculateDialogPosition` 单元测试
    - 测试右侧放不下时切换到左侧
    - 测试底部超出时向上调整
    - 测试顶部超出时对齐顶部
    - 测试坐标异常值处理
    - _需求: 4.2, 4.3, 4.4_

- [x] 2. 创建 `useStockDialog` Hook
  - [x] 2.1 创建 `hooks/useStockDialog.ts` 文件
    - 实现 `DialogState` 接口（stock、position）
    - 实现 `openDialog`：调用 `calculateDialogPosition` 计算位置，设置当前股票；点击同一股票时 toggle 关闭
    - 实现 `closeDialog`：清空状态
    - 实现 `dialogRef` 和 `useEffect` 监听 `mousedown` 事件，检测外部点击关闭
    - _需求: 1.1, 1.2, 2.3, 3.1, 3.2, 3.5_

  - [x] 2.2 编写 `useStockDialog` 属性测试
    - **属性 2: Dialog 单例性**
    - 使用 `fast-check` 生成随机股票序列，依次调用 `openDialog`
    - 验证 `dialogState.stock` 始终等于最后一次调用的股票，不会同时存在多个 Dialog
    - **验证需求: 1.2, 3.2**

  - [x] 2.3 编写 `useStockDialog` 单元测试
    - 测试 openDialog 设置正确的股票和位置
    - 测试 closeDialog 清空状态
    - 测试点击同一股票 toggle 关闭
    - 测试外部点击关闭 Dialog
    - _需求: 1.1, 1.2, 2.3, 3.5_

- [x] 3. 创建 `StockDialogWrapper` 组件
  - [x] 3.1 创建 `components/StockDialogWrapper.tsx` 文件
    - 实现 `StockDialogWrapperProps` 接口（stock、position、onClose、dialogRef、onSizeChange）
    - 使用 `fixed` 定位渲染在指定坐标
    - 右上角渲染关闭按钮（× 图标），点击触发 `onClose`
    - 关闭按钮具有 hover 状态颜色变化
    - 内部渲染 `StockHoverCard` 组件，包裹 `Suspense` 和加载 fallback
    - 通过 `dialogRef` 支持外部点击检测
    - _需求: 2.1, 2.2, 2.4, 3.4_

  - [x] 3.2 编写 `StockDialogWrapper` 单元测试
    - 测试关闭按钮存在且可点击关闭
    - 测试 fixed 定位样式正确应用
    - _需求: 2.1, 2.2, 2.4_

- [x] 4. 检查点 - 确保共享模块完成
  - 确保所有测试通过，如有问题请向用户确认。

- [x] 5. 改造 StockInfoSection
  - [x] 5.1 移除 StockInfoSection 中的 hover 逻辑
    - 移除 `hoverTimeoutRef`、`closeTimeoutRef`、`mousePosRef` 相关 ref
    - 移除 `handleRowMouseEnter`、`handleRowMouseMove`、`handleRowMouseLeave` 函数
    - 移除 `handleCardMouseEnter`、`handleCardMouseLeave` 函数
    - 移除 `getCardStyle` 函数
    - 移除 `hoveredStock`、`cardPos` 状态
    - 移除表格行上的 `onMouseEnter`、`onMouseMove`、`onMouseLeave` 事件绑定
    - 移除底部 hover card portal 渲染块
    - _需求: 1.3, 1.4_

  - [x] 5.2 为 StockInfoSection 添加点击触发逻辑
    - 引入 `useStockDialog` Hook
    - 在表格行 `onClick` 中调用 `openDialog(stock, event)`，保留原有的 `setSelectedStock` 逻辑
    - 使用 `StockDialogWrapper` 渲染 Dialog（条件渲染：`dialogState.stock` 不为 null 时显示）
    - _需求: 1.1, 1.2, 2.1, 2.2, 2.3_

- [x] 6. 改造 LimitUpLadderSection
  - [x] 6.1 移除 LimitUpLadderSection 中的 hover 逻辑
    - 移除 `hoverTimeoutRef`、`closeTimeoutRef`、`mousePosRef` 相关 ref
    - 移除 `handleMouseEnter`、`handleMouseMove`、`handleMouseLeave` 函数
    - 移除 `openHoverCard`、`startCloseTimer`、`closeHoverInstant`、`updateHoverCardPosition` 函数
    - 移除 `hoveredStock`、`cardPos`、`hoverCardSizeRef` 状态/ref
    - 移除股票卡片上的 `onMouseEnter`、`onMouseMove`、`onMouseLeave` 事件绑定
    - 移除底部 hover card 渲染块
    - _需求: 3.3_

  - [x] 6.2 为 LimitUpLadderSection 添加点击触发逻辑
    - 引入 `useStockDialog` Hook
    - 在股票卡片 `onClick` 中调用 `openDialog(stock, event)`，保留原有的 `setSelectedStockSymbol` 逻辑
    - 使用 `StockDialogWrapper` 渲染 Dialog（条件渲染：`dialogState.stock` 不为 null 时显示）
    - _需求: 3.1, 3.2, 3.4, 3.5_

- [x] 7. 最终检查点 - 确保所有测试通过
  - 确保所有测试通过，如有问题请向用户确认。

## 说明

- 标记 `*` 的任务为可选任务，可跳过以加快 MVP 进度
- 每个任务引用了具体的需求编号，确保可追溯性
- 检查点用于增量验证，确保每个阶段的正确性
- 属性测试验证通用正确性属性，单元测试验证具体示例和边界情况
