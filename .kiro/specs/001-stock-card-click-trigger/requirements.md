# 需求文档

## 简介

将股票信息模块（StockInfoSection）和连板天梯模块（LimitUpLadderSection）中的股票 K 线卡片（StockHoverCard）触发方式从鼠标悬停（hover）改为点击（click）触发，并统一增加关闭按钮，提升用户交互的可控性和一致性。

## 术语表

- **StockInfoSection**: 股票信息模块，包含实时行情表格，展示股票列表及详情
- **LimitUpLadderSection**: 连板天梯模块，展示连板股票的天梯数据和对比视图
- **StockHoverCard**: 股票 K 线卡片组件，展示单只股票的日 K/周 K/月 K 线图及技术指标
- **Dialog**: 弹出对话框，指 StockHoverCard 以浮层形式展示在页面上
- **关闭按钮**: Dialog 右上角的可点击关闭图标

## 需求

### 需求 1：StockInfoSection 点击触发 Dialog

**用户故事：** 作为用户，我希望在实时行情表格中点击某一行时才弹出该股票的 K 线卡片 Dialog，以便我能主动控制卡片的显示，避免鼠标移动时频繁弹出干扰浏览。

#### 验收标准

1. WHEN 用户点击实时行情表格中的某一行, THE StockInfoSection SHALL 弹出该行对应股票的 StockHoverCard Dialog
2. WHEN Dialog 已打开且用户点击表格中另一行, THE StockInfoSection SHALL 关闭当前 Dialog 并弹出新点击行对应股票的 Dialog
3. THE StockInfoSection SHALL 移除所有基于鼠标悬停（hover）触发 StockHoverCard 的逻辑，包括 handleRowMouseEnter 中的延迟显示定时器和 handleRowMouseLeave 中的延迟关闭定时器
4. THE StockInfoSection SHALL 移除 handleCardMouseEnter 和 handleCardMouseLeave 事件处理，因为 Dialog 不再需要 hover 保持逻辑

### 需求 2：StockInfoSection Dialog 增加关闭按钮

**用户故事：** 作为用户，我希望 StockInfoSection 弹出的 K 线卡片 Dialog 上有一个明显的关闭按钮，以便我能方便地关闭卡片。

#### 验收标准

1. THE StockInfoSection SHALL 在 StockHoverCard Dialog 的右上角显示一个关闭按钮（× 图标）
2. WHEN 用户点击关闭按钮, THE StockInfoSection SHALL 关闭当前显示的 StockHoverCard Dialog
3. WHEN 用户点击 Dialog 外部区域, THE StockInfoSection SHALL 关闭当前显示的 StockHoverCard Dialog
4. THE 关闭按钮 SHALL 具有明确的视觉样式，包括 hover 状态的颜色变化，确保用户能清晰识别其为可交互元素

### 需求 3：LimitUpLadderSection 点击触发 Dialog

**用户故事：** 作为用户，我希望在连板天梯模块中点击股票卡片时才弹出 K 线 Dialog，以便与 StockInfoSection 保持一致的交互体验。

#### 验收标准

1. WHEN 用户点击连板天梯中的股票卡片, THE LimitUpLadderSection SHALL 弹出该股票的 StockHoverCard Dialog
2. WHEN Dialog 已打开且用户点击另一个股票卡片, THE LimitUpLadderSection SHALL 关闭当前 Dialog 并弹出新点击股票的 Dialog
3. THE LimitUpLadderSection SHALL 移除所有基于鼠标悬停（hover）触发 StockHoverCard 的逻辑，包括 handleMouseEnter 中的延迟显示定时器和 handleMouseLeave 中的延迟关闭定时器
4. THE LimitUpLadderSection SHALL 保留已有的关闭按钮（× 按钮）功能
5. WHEN 用户点击关闭按钮或 Dialog 外部区域, THE LimitUpLadderSection SHALL 关闭当前显示的 StockHoverCard Dialog

### 需求 4：Dialog 定位与显示

**用户故事：** 作为用户，我希望弹出的 K 线卡片 Dialog 能合理定位在可视区域内，不会被页面边界截断。

#### 验收标准

1. WHEN Dialog 弹出时, THE StockInfoSection 和 LimitUpLadderSection SHALL 将 Dialog 定位在点击位置附近，使用 fixed 定位
2. IF Dialog 的默认位置会超出视口右侧边界, THEN THE 定位逻辑 SHALL 将 Dialog 移至点击位置的左侧显示
3. IF Dialog 的默认位置会超出视口底部边界, THEN THE 定位逻辑 SHALL 向上调整 Dialog 位置，确保完整显示在视口内
4. IF Dialog 的默认位置会超出视口顶部边界, THEN THE 定位逻辑 SHALL 将 Dialog 顶部对齐到视口顶部附近（保留适当间距）
