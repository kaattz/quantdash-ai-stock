# 需求文档

## 简介

在 A 股分析看板项目（quantdash-ai-stock）中，StockHoverCard 组件底部有"个股资讯"和"个股资料"两个按钮，目前仅为占位状态，没有实际功能。本需求旨在实现这两个按钮的点击交互，使用户能够快速查看某只股票的相关新闻资讯和基本资料信息（含概念板块）。

## 术语表

- **StockHoverCard**：股票悬浮卡片组件，展示个股 K 线图、技术指标及操作按钮
- **Stock**：股票数据对象，包含 symbol、name、price、pctChange、industry、concepts 等字段
- **NewsItem**：新闻条目数据对象，包含 id、title、source、time、content、url、sentiment、type 等字段
- **NewsPanel**：个股资讯面板，展示与特定股票相关的新闻列表
- **ProfilePanel**：个股资料面板，展示股票的基本资料信息
- **ConceptTag**：概念板块标签，以标签形式展示股票所属的概念板块

## 需求

### 需求 1：个股资讯按钮交互

**用户故事：** 作为一名 A 股投资者，我希望在 StockHoverCard 中点击"个股资讯"按钮后能看到该股票相关的新闻资讯，以便快速了解个股动态。

#### 验收标准

1. WHEN 用户点击"个股资讯"按钮，THE StockHoverCard SHALL 在卡片内展示 NewsPanel
2. WHEN NewsPanel 展示时，THE NewsPanel SHALL 显示与当前股票相关的新闻列表
3. THE NewsPanel SHALL 对每条新闻展示标题、来源、时间信息
4. WHEN 用户再次点击"个股资讯"按钮，THE StockHoverCard SHALL 关闭 NewsPanel 并恢复 K 线图视图
5. WHEN 新闻数据正在加载时，THE NewsPanel SHALL 显示加载状态指示器
6. IF 新闻数据加载失败或无相关新闻，THEN THE NewsPanel SHALL 显示"暂无相关资讯"的空状态提示
7. WHEN 新闻条目包含 url 字段，THE NewsPanel SHALL 将标题渲染为可点击链接，点击后在新标签页打开原文

### 需求 2：个股资料按钮交互

**用户故事：** 作为一名 A 股投资者，我希望在 StockHoverCard 中点击"个股资料"按钮后能看到该股票的基本资料和所属概念板块，以便快速了解个股基本面。

#### 验收标准

1. WHEN 用户点击"个股资料"按钮，THE StockHoverCard SHALL 在卡片内展示 ProfilePanel
2. WHEN ProfilePanel 展示时，THE ProfilePanel SHALL 显示股票代码、股票名称、所属行业信息
3. WHEN ProfilePanel 展示时，THE ProfilePanel SHALL 显示市盈率（PE）、市净率（PB）、总市值（marketCap）等财务指标（如数据可用）
4. THE ProfilePanel SHALL 以 ConceptTag 标签形式展示股票所属的全部概念板块
5. WHEN 用户再次点击"个股资料"按钮，THE StockHoverCard SHALL 关闭 ProfilePanel 并恢复 K 线图视图
6. IF 股票的 concepts 数组为空，THEN THE ProfilePanel SHALL 显示"暂无概念板块数据"的提示
7. IF 财务指标数据不可用（字段为 undefined），THEN THE ProfilePanel SHALL 对该指标显示"--"占位符

### 需求 3：面板互斥切换

**用户故事：** 作为一名用户，我希望资讯面板和资料面板之间是互斥的，以保持界面整洁。

#### 验收标准

1. WHILE NewsPanel 处于展示状态，WHEN 用户点击"个股资料"按钮，THE StockHoverCard SHALL 关闭 NewsPanel 并展示 ProfilePanel
2. WHILE ProfilePanel 处于展示状态，WHEN 用户点击"个股资讯"按钮，THE StockHoverCard SHALL 关闭 ProfilePanel 并展示 NewsPanel
3. THE StockHoverCard SHALL 同一时刻最多展示 NewsPanel 和 ProfilePanel 中的一个

### 需求 4：新闻数据按股票过滤

**用户故事：** 作为一名投资者，我希望看到的新闻是与当前查看的股票相关的，而不是全市场新闻。

#### 验收标准

1. WHEN NewsPanel 加载新闻数据时，THE NewsPanel SHALL 根据股票名称或股票代码对新闻标题和内容进行匹配过滤
2. THE NewsPanel SHALL 优先展示标题中包含股票名称的新闻条目
3. WHEN 过滤后无匹配新闻，THE NewsPanel SHALL 显示"暂无该股相关资讯"的提示
