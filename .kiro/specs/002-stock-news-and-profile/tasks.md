# 实现计划：个股资讯与个股资料

## 概述

基于设计文档，为 StockHoverCard 组件实现"个股资讯"和"个股资料"两个按钮的交互功能。实现顺序为：先完成数据层（过滤函数），再构建两个面板组件，最后修改 StockHoverCard 集成面板切换逻辑。

## 任务

- [x] 1. 实现新闻过滤函数 filterNewsByStock
  - [x] 1.1 在 `services/newsService.ts` 中新增 `filterNewsByStock` 纯函数
    - 接收 `NewsItem[]`、`stockName`、`stockSymbol` 三个参数
    - 按标题和内容匹配股票名称或代码进行过滤
    - 实现标题匹配优先排序逻辑（标题匹配的条目排在仅内容匹配的条目之前）
    - _需求：4.1, 4.2_

  - [x] 1.2 编写属性测试：新闻过滤正确性
    - **属性 1：新闻过滤正确性**
    - 使用 fast-check 生成随机 NewsItem 数组和随机股票名称/代码
    - 验证 filterNewsByStock 返回的每条新闻，其标题或内容中必须包含该股票名称或股票代码
    - **验证需求：1.2, 4.1**

  - [x] 1.3 编写属性测试：标题匹配优先排序
    - **属性 2：标题匹配优先排序**
    - 生成包含标题匹配和内容匹配的混合新闻列表
    - 验证排序后所有标题匹配条目排在仅内容匹配条目之前
    - **验证需求：4.2**

- [x] 2. 实现 NewsPanel 组件
  - [x] 2.1 创建 `components/NewsPanel.tsx` 组件
    - 定义 `NewsPanelProps` 接口，接收 `stock: Stock` 属性
    - 调用 `getInfoGatheringNews()` 获取全部新闻数据
    - 使用 `filterNewsByStock()` 按股票名称/代码过滤新闻
    - 渲染新闻列表，每条新闻展示标题、来源、时间
    - 当 `url` 字段存在时，标题渲染为可点击链接（`target="_blank"`）
    - 加载中显示 loading 指示器
    - 加载失败或无数据时显示"暂无相关资讯"空状态提示
    - 过滤后无匹配新闻时显示"暂无该股相关资讯"提示
    - _需求：1.1, 1.2, 1.3, 1.5, 1.6, 1.7, 4.1, 4.3_

  - [x] 2.2 编写属性测试：新闻条目渲染完整性
    - **属性 3：新闻条目渲染完整性**
    - 使用 fast-check 生成随机 NewsItem（有/无 url）
    - 渲染后验证输出包含标题、来源、时间信息
    - 验证有 url 时标题为链接（target="_blank"），无 url 时为普通文本
    - **验证需求：1.3, 1.7**

  - [x] 2.3 编写 NewsPanel 单元测试
    - 测试加载中显示 loading 指示器
    - 测试空数据显示空状态提示
    - 测试新闻列表正确渲染
    - _需求：1.3, 1.5, 1.6_

- [x] 3. 实现 ProfilePanel 组件
  - [x] 3.1 创建 `components/ProfilePanel.tsx` 组件
    - 定义 `ProfilePanelProps` 接口，接收 `stock: Stock` 属性
    - 展示股票代码、名称、所属行业
    - 展示财务指标：PE、PB、总市值（字段为 undefined 时显示 `--`）
    - 以标签形式展示 `concepts` 数组中的概念板块
    - concepts 为空时显示"暂无概念板块数据"提示
    - _需求：2.1, 2.2, 2.3, 2.4, 2.6, 2.7_

  - [x] 3.2 编写属性测试：股票资料展示完整性
    - **属性 4：股票资料展示完整性**
    - 使用 fast-check 生成随机 Stock 对象（有/无财务指标）
    - 渲染后验证包含股票代码、名称、行业信息
    - 验证有值时显示数值，undefined 时显示 `--`
    - **验证需求：2.2, 2.3, 2.7**

  - [x] 3.3 编写属性测试：概念板块标签完整性
    - **属性 5：概念板块标签完整性**
    - 使用 fast-check 生成随机 concepts 数组
    - 渲染后验证标签数量等于 concepts.length
    - **验证需求：2.4**

  - [x] 3.4 编写 ProfilePanel 单元测试
    - 测试 concepts 为空时显示提示
    - 测试财务指标为 undefined 时显示 `--`
    - _需求：2.6, 2.7_

- [x] 4. 检查点 - 确保所有测试通过
  - 确保所有测试通过，如有问题请询问用户。

- [ ] 5. 修改 StockHoverCard 集成面板切换
  - [x] 5.1 在 StockHoverCard 中新增面板状态管理
    - 新增 `PanelType` 类型定义（`'chart' | 'news' | 'profile'`）
    - 新增 `activePanel` 状态，默认值为 `'chart'`
    - 实现 `togglePanel` 切换函数（toggle 行为：点击已激活面板切回 chart）
    - _需求：3.3_

  - [x] 5.2 修改 K 线图区域实现条件渲染
    - 根据 `activePanel` 状态条件渲染：chart 显示 K 线图、news 显示 NewsPanel、profile 显示 ProfilePanel
    - 向 NewsPanel 和 ProfilePanel 传递当前 `stock` 对象
    - _需求：1.1, 2.1, 3.1, 3.2, 3.3_

  - [x] 5.3 绑定底部按钮事件和激活态样式
    - "个股资讯"按钮绑定 `onClick={() => togglePanel('news')}`
    - "个股资料"按钮绑定 `onClick={() => togglePanel('profile')}`
    - 按钮激活态样式：当对应面板展示时高亮显示
    - _需求：1.1, 1.4, 2.1, 2.5_

  - [x] 5.4 编写属性测试：面板互斥不变量
    - **属性 6：面板互斥不变量**
    - 使用 fast-check 生成随机操作序列（点击"个股资讯"或"个股资料"按钮）
    - 验证执行后 activePanel 始终为 'chart'、'news'、'profile' 三者之一
    - **验证需求：3.3**

  - [x] 5.5 编写 StockHoverCard 面板切换单元测试
    - 测试点击"个股资讯"展示 NewsPanel
    - 测试再次点击关闭 NewsPanel 恢复图表
    - 测试点击"个股资料"展示 ProfilePanel
    - 测试再次点击关闭 ProfilePanel
    - 测试面板互斥切换：news → profile、profile → news
    - _需求：1.1, 1.4, 2.1, 2.5, 3.1, 3.2_

- [x] 6. 最终检查点 - 确保所有测试通过
  - 确保所有测试通过，如有问题请询问用户。

## 备注

- 标记 `*` 的任务为可选任务，可跳过以加速 MVP 开发
- 每个任务引用了具体的需求编号以确保可追溯性
- 检查点确保增量验证
- 属性测试使用 fast-check + vitest，验证设计文档中定义的正确性属性
- 单元测试使用 vitest + @testing-library/react，验证具体示例和边界情况
