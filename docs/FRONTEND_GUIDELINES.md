# FRONTEND_GUIDELINES.md — 前端规范

> 版本：V1
> 最后更新：2026-03-19
> 设计方向：轻游戏化，兼顾研究控制台。用户游玩页追求氛围感，管理后台追求清晰实用。

---

## 1. 设计理念

- **轻游戏化**：游玩界面带有奇幻/冒险氛围，但不过度花哨。通过色彩、字体、阴影营造"翻开一本故事书"的感觉。
- **管理端朴素**：管理后台走干净理性的 Dashboard 风格，表格表单为主，信息密度优先。
- **仅桌面端**：最小视口宽度 1024px，不做移动端适配。
- **暗色主题优先**：游玩页面使用暗色主题增强沉浸感，管理后台可保持浅色。

---

## 2. 配色方案

### 2.1 游玩界面（Dark Theme）

| 用途 | 色名 | 色值 | CSS 变量名 |
|------|------|------|-----------|
| 页面背景 | 深渊黑 | `#0F0F14` | `--bg-primary` |
| 卡片/面板背景 | 夜幕蓝 | `#1A1A2E` | `--bg-secondary` |
| 悬浮/高亮背景 | 暮光紫 | `#252540` | `--bg-hover` |
| 主文本 | 羊皮纸白 | `#E8E0D4` | `--text-primary` |
| 次文本 | 灰雾 | `#9A9AB0` | `--text-secondary` |
| 主强调色 | 琥珀金 | `#D4A853` | `--accent-primary` |
| 次强调色 | 翡翠绿 | `#4ADE80` | `--accent-secondary` |
| 危险色 | 血红 | `#EF4444` | `--danger` |
| 警告色 | 烛光橙 | `#F59E0B` | `--warning` |
| 成功色 | 翡翠绿 | `#4ADE80` | `--success` |
| 边框色 | 暗纹 | `#2A2A45` | `--border` |
| GM 文本 | 琥珀金 | `#D4A853` | `--gm-text` |
| 玩家文本 | 羊皮纸白 | `#E8E0D4` | `--player-text` |
| 系统提示文本 | 灰雾 | `#9A9AB0` | `--system-text` |

### 2.2 管理后台（Light Theme）

| 用途 | 色名 | 色值 | CSS 变量名 |
|------|------|------|-----------|
| 页面背景 | 白灰 | `#F8F9FA` | `--admin-bg-primary` |
| 卡片背景 | 纯白 | `#FFFFFF` | `--admin-bg-card` |
| 主文本 | 墨黑 | `#1A1A2E` | `--admin-text-primary` |
| 次文本 | 石灰 | `#6B7280` | `--admin-text-secondary` |
| 主强调色 | 靛蓝 | `#4F46E5` | `--admin-accent` |
| 表格斑马行 | 浅灰 | `#F3F4F6` | `--admin-table-stripe` |
| 边框色 | 浅线 | `#E5E7EB` | `--admin-border` |

### 2.3 模式徽章

| 模式 | 背景色 | 文字色 | 边框 |
|------|--------|--------|------|
| 严谨模式 | `#1E3A5F` | `#93C5FD` | `1px solid #3B82F6` |
| 创作模式 | `#3B2F1A` | `#FBBF24` | `1px solid #D4A853` |

---

## 3. 字体

### 3.1 字体栈

```css
/* 正文 / 叙事文本 */
--font-story: 'Noto Serif SC', 'Source Han Serif SC', 'STSong', serif;

/* UI 文本 / 按钮 / 标签 */
--font-ui: 'Inter', 'Noto Sans SC', 'Microsoft YaHei', sans-serif;

/* 代码 / 技术内容 */
--font-mono: 'JetBrains Mono', 'Fira Code', 'Consolas', monospace;
```

- 叙事对话区使用衬线字体（`--font-story`），增强文学感。
- 所有 UI 控件、导航、按钮使用无衬线字体（`--font-ui`）。
- 管理后台统一使用 `--font-ui`。

### 3.2 字号

| 用途 | 大小 | 行高 | CSS 类 |
|------|------|------|--------|
| 页面标题 H1 | 28px | 1.3 | `text-[28px] leading-[1.3]` |
| 区块标题 H2 | 22px | 1.4 | `text-[22px] leading-[1.4]` |
| 子标题 H3 | 18px | 1.4 | `text-[18px] leading-[1.4]` |
| 正文（叙事） | 16px | 1.8 | `text-base leading-[1.8]` |
| 正文（UI） | 14px | 1.5 | `text-sm leading-normal` |
| 辅助文本 | 12px | 1.5 | `text-xs` |
| 按钮文字 | 14px | 1.0 | `text-sm` |
| 选项卡文字 | 16px | 1.0 | `text-base` |

---

## 4. 间距系统

基于 **4px 倍数** 网格：

| Token | 值 | 用途 |
|-------|----|------|
| `space-1` | 4px | 图标与文字间距 |
| `space-2` | 8px | 紧凑元素内间距 |
| `space-3` | 12px | 表单字段间距 |
| `space-4` | 16px | 卡片内间距、列表项间距 |
| `space-5` | 20px | 小区块间距 |
| `space-6` | 24px | 区块间距 |
| `space-8` | 32px | 大区块间距 |
| `space-10` | 40px | 页面级间距 |
| `space-12` | 48px | 页面顶部/底部间距 |

Tailwind 中直接使用 `p-1`(4px) 到 `p-12`(48px) 对应。

---

## 5. 圆角与阴影

| 元素 | 圆角 | 阴影 |
|------|------|------|
| 按钮 | `rounded-lg` (8px) | 无 |
| 卡片 | `rounded-xl` (12px) | `shadow-md` (游玩) / `shadow-sm` (管理) |
| 对话气泡 | `rounded-2xl` (16px) | 无 |
| 输入框 | `rounded-lg` (8px) | `ring` 聚焦态 |
| 弹窗 | `rounded-xl` (12px) | `shadow-2xl` |
| 头像 | `rounded-full` | 无 |
| 模式徽章 | `rounded-full` | 无 |
| 选项按钮 | `rounded-xl` (12px) | `shadow-sm` + `hover:shadow-md` |

---

## 6. 组件规范

### 6.1 按钮

```
[主要按钮] 背景 accent-primary，文字 bg-primary，hover 亮度 +10%
[次要按钮] 背景透明，边框 border，文字 text-primary，hover 背景 bg-hover
[危险按钮] 背景 danger，文字白色，hover 亮度 -10%
[幽灵按钮] 无边框无背景，文字 text-secondary，hover 文字 text-primary
```

- 所有按钮高度 36px（sm）/ 40px（md）/ 48px（lg）。
- 左右内边距 16px / 20px / 24px。
- 禁用态：`opacity-50 cursor-not-allowed`。
- 加载态：文字替换为 spinner。

### 6.2 对话气泡

```
GM 气泡：
  - 左对齐
  - 背景 bg-secondary
  - 左侧 3px accent-primary 色条
  - 文字 gm-text，字体 font-story
  - 前缀标签「旁白」或角色名

玩家气泡：
  - 右对齐
  - 背景 bg-hover
  - 文字 player-text，字体 font-ui
  - 无前缀
```

### 6.3 选项按钮

```
  背景 bg-secondary
  边框 1px solid border
  hover: 边框变 accent-primary，背景变 bg-hover
  圆角 rounded-xl
  内间距 space-4
  文字 text-primary
  字号 16px
  最大宽度 100%，多行文本自动换行
```

- 2-4 个选项水平排列，空间不足时折行。
- 选项区域在叙事文本流式完成后淡入出现（200ms fade-in）。

### 6.4 输入区域

```
  背景 bg-secondary
  边框 1px solid border
  聚焦: 边框变 accent-primary + ring-2 ring-accent-primary/20
  圆角 rounded-lg
  高度自适应（最小 44px，最大 120px）
  右侧发送按钮内嵌
  Shift+Enter 换行，Enter 发送
```

### 6.5 导航栏（TopNav）

导航栏有两种状态，视觉样式不同：

**共用规格**：
```
  高度 56px，固定顶部 (sticky top-0 z-50)
  背景 bg-secondary + backdrop-blur-sm (半透明毛玻璃)
  底边框 1px solid border
  左右内边距 space-6
  Logo: font-story, 20px, text-primary, font-bold
```

**未登录态**：
```
  左侧: Logo
  右侧: 登录/注册 两个文字链接按钮
    - 普通态: text-secondary, font-ui, 14px
    - 当前页高亮: text-primary + 底部 2px accent-primary 下划线
    - hover: text-primary 过渡 150ms
    - 间距: 两按钮间 space-4
```

**已登录态**：
```
  左侧: Logo（点击回 /stories）
  中部: 导航项（故事库 | 历史 | 画像）
    - 普通态: text-secondary, font-ui, 14px
    - 当前页: text-primary + 底部 2px accent-primary 下划线
    - hover: text-primary 过渡 150ms
    - 间距: 导航项间 space-6
    - 每项前缀一个 16px 图标（BookOpen / History / User）
  右侧: 头像下拉菜单
    - 头像: 32px rounded-full, 背景 bg-hover（无头像时显示首字母）
    - 使用 Radix DropdownMenu
    - 菜单项: 账号设置 / 管理后台(仅admin) / 退出登录
    - 菜单宽度 180px, 背景 bg-secondary, 圆角 rounded-lg, shadow-lg
    - 菜单项: 高度 36px, hover 背景 bg-hover, 左侧 20px 图标
    - 退出登录: text-danger
```

### 6.6 Auth 卡片（登录/注册共用）

```
  容器: 页面 flex 水平垂直居中
  卡片:
    宽度 400px
    背景 bg-secondary
    圆角 rounded-xl
    阴影 shadow-2xl
    内间距 40px
```

**卡片内部元素**：
```
  标题: font-story, 28px, text-primary, 居中, margin-bottom space-2
  副标题: font-ui, 14px, text-secondary, 居中, margin-bottom space-8

  输入框:
    宽度 100%
    高度 44px
    背景 bg-primary
    边框 1px solid border
    圆角 rounded-lg
    文字 text-primary, font-ui, 14px
    placeholder: text-secondary
    聚焦: 边框 accent-primary + ring-2 ring-accent-primary/20
    错误: 边框 danger + 下方 12px danger 文字 (slideDown 200ms)
    字段间距 space-3

  密码框额外:
    右侧内嵌眼睛图标 (Eye / EyeOff, 20px, text-secondary)
    hover: text-primary
    点击: 切换明文/密文, 图标 rotate 180° (200ms ease-in-out)

  主按钮:
    宽度 100%, 高度 44px
    背景 accent-primary, 文字 bg-primary, font-medium
    margin-top space-6
    hover: 亮度 +10%
    加载态: 文字替换为 16px spinner + "登录中..."/"注册中..."
    禁用态: opacity-50 cursor-not-allowed

  错误横幅 (登录失败时出现在标题下方):
    背景 danger/10, 边框 1px solid danger/30, 圆角 rounded-lg
    文字 danger, 12px, 居中
    内间距 space-2 space-3
    出现: slideDown + fadeIn 250ms
    消失: fadeOut 200ms (用户重新输入时)

  底部跳转链接:
    margin-top space-4, 居中
    文字 text-secondary, 14px
    链接部分 accent-primary + underline
    hover: 亮度 +10%
```

### 6.7 故事卡片（StoryCard）

```
  宽度: 响应式网格, min 280px, max 360px, gap space-6
  背景 bg-secondary
  圆角 rounded-xl
  阴影 shadow-md
  overflow hidden
  hover: shadow-lg + translateY(-2px) 过渡 200ms
  cursor pointer

  封面占位区:
    高度 160px, 背景 bg-hover
    居中显示 BookOpen 图标 (48px, text-secondary/30)

  内容区 (内间距 space-4):
    标题: font-story, 18px, text-primary, font-bold, 单行省略
    简介: font-ui, 14px, text-secondary, 3行截断 (line-clamp-3)
    底栏: flex justify-between, margin-top space-3
      左: 字数/章节 (12px, text-secondary)
      右: 入库状态标签 (12px, rounded-full, px-2 py-0.5)
        已就绪: 背景 accent-secondary/10, 文字 accent-secondary
        入库中: 背景 warning/10, 文字 warning
```

### 6.8 状态面板（StatePanel）

```
  位置: 游玩页对话区右侧, 固定宽度 280px
  背景 bg-secondary
  左边框 1px solid border
  默认折叠
```

**标题栏**：
```
  高度 48px, 内间距 space-4 水平
  flex justify-between align-center
  文字 "状态面板", font-ui, 14px, font-medium, text-primary
  右侧切换箭头: ChevronLeft, 20px, text-secondary（展开态朝左，折叠态 rotate-180 朝右）
    hover: text-primary
    点击: 折叠面板 (与顶栏箭头联动)
  底边框 1px solid border
```

**各字段规格**：

| 字段 | 图标 | 标签样式 | 值样式 | 空状态文案 |
|------|------|----------|--------|-----------|
| 当前位置 | 📍 | 12px text-secondary | 14px text-primary, 单行或折行 | 「未知」text-secondary italic |
| 当前目标 | 🎯 | 12px text-secondary | 14px text-primary, 最多 2 行, 超出省略 | 「无特定目标」text-secondary italic |
| 关键物品 | 🎒 | 12px text-secondary | 圆角 Tag（见下方） | 「暂无物品」text-secondary italic |
| NPC 关系 | 👥 | 12px text-secondary | 列表（见下方） | 「尚未遇见 NPC」text-secondary italic |

**物品 Tag 样式**：
```
  背景 bg-hover
  文字 text-primary, 12px
  圆角 rounded-md
  内间距 px-2 py-1
  间距 4px (gap-1)
  flex-wrap, 超过 4 个自动换行
```

**NPC 关系列表**：
```
  每条 NPC:
    名字行: 14px, text-primary, font-medium
    关系行: 12px, text-secondary
      前缀彩色圆点 (8px):
        🟢 友善: accent-secondary (#4ADE80)
        🟡 中立: warning (#F59E0B)
        🔴 敌对: danger (#EF4444)
        ⚪ 未知: text-secondary (#9A9AB0)
    条目间距 space-3
```

**字段间分割线**: `1px solid border`, margin space-3 垂直。

**数据刷新高亮**：
```
  当 SSE 收到 state_update 事件时:
    变化字段背景色: accent-primary/20 → transparent
    过渡时长 300ms, ease-out
    无变化字段不做动画
    面板折叠时静默更新，展开时显示最新值
```

### 6.9 表格（管理后台）

```
  thead: 背景 admin-bg-card，文字 admin-text-secondary，字号 12px 大写
  tbody: 斑马行 admin-table-stripe
  td: 内间距 space-3 垂直，space-4 水平
  hover: 行背景 admin-accent/5
  操作列: 图标按钮群（编辑/删除）
```

### 6.10 表单（管理后台）

```
  标签: admin-text-primary，14px，font-medium，margin-bottom space-1
  输入框: 高度 40px，圆角 rounded-lg，边框 admin-border
  聚焦: 边框 admin-accent + ring
  错误: 边框 danger + 下方红色提示文字 12px
  间距: 字段间 space-4
```

### 6.11 模式徽章

```
  圆角 rounded-full
  内间距 px-3 py-1
  字号 12px，font-medium
  前缀圆点 ● (8px)
  不可点击
```

---

## 7. 布局规范

### 7.1 前台布局

```
┌─────────────────────────────────────────────┐
│ TopNav (高度 56px, 固定顶部)                 │
├─────────────────────────────────────────────┤
│                                             │
│  Main Content (max-width: 1200px, 居中)      │
│  padding: space-8 水平, space-6 垂直         │
│                                             │
└─────────────────────────────────────────────┘
```

### 7.2 游玩页布局

```
┌─────────────────────────────────────────────┐
│ TopBar (作品名 + 模式徽章 + 操作按钮)         │
├───────────────────────────┬─────────────────┤
│                           │                 │
│  对话区域                  │  状态面板        │
│  (flex-1, 可滚动)         │  (280px, 可折叠) │
│                           │                 │
├───────────────────────────┴─────────────────┤
│ 选项区域 + 输入区域 (固定底部, 高度自适应)     │
└─────────────────────────────────────────────┘
```

- 对话区域占满剩余高度，溢出时滚动，新消息自动滚到底部。
- 状态面板折叠时对话区域占满宽度。
- **整页定高**：`PlaySessionPage` 主壳使用 `h-[calc(100vh-3.5rem)]` + `overflow-hidden`，中间主卡片 `flex-1 min-h-0`；仅**对话列表列** `overflow-y-auto`，选项区/输入区 `shrink-0`。避免浏览器整页滚动导致右侧状态面板被滚出视口。
- **滚动条语义色**：对话列表容器加类名 `play-session-messages-scroll`，在 `globals.css` 内用 `--scrollbar-track` / `--scrollbar-thumb` / `--scrollbar-thumb-hover`（继承 `:root` 暗色或 `body.admin-route` 浅色下的 `--bg-primary`、`--border`、`--bg-hover` 等），避免系统默认亮白滚动条破坏沉浸感。
- **GM 气泡与选项去重**：`stripMetaSuffixForDisplay` 支持 `stripNumberedTail`；`ChatBubble` 仅在「非流式 + `messageId>0` + `coerceChoicesFromMetadata(metadata).length >= 2`」时去掉文末编号块。GM 旁白正文不再整段套用 `formatPlainChoiceLabel`（仅玩家气泡与 `ChoicePanel` 按钮文案做加粗剥离）。细节与产品语义见 `APP_FLOW.md` §3.5.2。

### 7.3 Auth 页面布局（登录/注册）

```
┌─────────────────────────────────────────────┐
│ TopNav 未登录态 (高度 56px, 固定顶部)         │
├─────────────────────────────────────────────┤
│                                             │
│            ┌───────────────┐                │
│            │               │                │
│            │  Auth Card    │                │  全屏暗色背景 bg-primary
│            │  (400px 宽)   │                │  卡片水平垂直居中
│            │               │                │  (flex items-center justify-center)
│            └───────────────┘                │
│                                             │
└─────────────────────────────────────────────┘
```

- 背景覆盖整个视口，纯色 `bg-primary`（不加背景图/纹理，保持简洁）。
- 卡片垂直居中偏上（`padding-bottom: 10vh`，视觉重心略高于几何中心）。

### 7.4 管理后台布局

```
┌────────┬────────────────────────────────────┐
│        │ TopBar (面包屑 + 管理员头像)         │
│ 侧边栏  ├────────────────────────────────────┤
│ (220px) │                                    │
│ 固定    │  Content Area                      │
│        │  (flex-1, padding space-6)          │
│        │                                    │
└────────┴────────────────────────────────────┘
```

---

## 8. 动画与过渡

**全局通用**：

| 场景 | 动画 | 时长 | 缓动 |
|------|------|------|------|
| 页面切换 | 无（SPA 即时切换） | — | — |
| 按钮 hover | 背景色/亮度过渡 | 150ms | ease |
| 按钮点击反馈 | scale(1→0.97→1) | 100ms | ease |
| 按钮加载态 | 文字 fadeOut → spinner fadeIn | 150ms | ease |
| 输入框聚焦 | 边框色过渡 + ring 出现 | 150ms | ease |
| 表单行内错误出现 | slideDown + fadeIn | 200ms | ease-out |
| 表单错误横幅出现 | slideDown + fadeIn | 250ms | ease-out |
| 表单错误横幅消失 | fadeOut | 200ms | ease-in |
| 弹窗打开 | fadeIn + scale(0.95→1) | 150ms | ease-out |
| 弹窗关闭 | fadeOut + scale(1→0.95) | 100ms | ease-in |
| 通知 toast | slideIn 从顶部 | 300ms | spring |
| 导航高亮下划线切换 | width + opacity 过渡 | 200ms | ease |

**Auth 页面（登录/注册）**：

| 场景 | 动画 | 时长 | 缓动 |
|------|------|------|------|
| 卡片入场 | fadeIn + translateY(20px→0) | 400ms | ease-out |
| 成功退场 | fadeOut + translateY(0→-10px) | 200ms | ease-in |
| 密码可见切换图标 | rotate(180deg) | 200ms | ease-in-out |
| 登录⇄注册路由切换 | 旧卡片 fadeOut → 新卡片 fadeIn | 各 150ms | ease |

**游玩页**：

| 场景 | 动画 | 时长 | 缓动 |
|------|------|------|------|
| 对话气泡出现 | slideUp + fadeIn | 200ms | ease-out |
| 选项面板出现 | fadeIn（叙事文本流式完成后） | 200ms | ease-out |
| 流式文字 | 逐字出现（无额外动画） | — | — |
| 状态面板展开 | slideIn from right + fadeIn | 250ms | ease-in-out |
| 状态面板折叠 | slideOut to right + fadeOut | 250ms | ease-in-out |
| 状态面板箭头旋转 | rotate(0→180deg)，与面板动画同步 | 250ms | ease-in-out |
| 状态字段刷新高亮 | 背景色 accent-primary/20 → transparent | 300ms | ease-out |

**故事库**：

| 场景 | 动画 | 时长 | 缓动 |
|------|------|------|------|
| 故事卡片 hover | translateY(-2px) + shadow 升级 | 200ms | ease |

不使用的动画：无 3D 翻转、无粒子效果、无页面滚动视差、无弹跳效果、无光效。保持轻量克制。

---

## 9. 图标

- 使用 **Lucide React** 图标库。
- 图标大小统一：16px（内联）/ 20px（按钮内）/ 24px（导航）。
- 图标颜色跟随当前文字颜色（`currentColor`）。
- 关键图标对照表：

| 用途 | 图标名 |
|------|--------|
| 故事库 | `BookOpen` |
| 历史 | `History` |
| 画像 | `User` |
| 设置 | `Settings` |
| 管理后台 | `Shield` |
| 退出 | `LogOut` |
| 密码可见 | `Eye` |
| 密码隐藏 | `EyeOff` |
| 发送 | `Send` |
| 标记错误 | `Flag` |
| 状态面板切换 | `ChevronLeft`（折叠态朝左，展开态旋转 180° 朝右） |
| 严谨模式 | `ShieldCheck` |
| 创作模式 | `Sparkles` |
| 删除 | `Trash2` |
| 编辑 | `Pencil` |
| 新增 | `Plus` |
| 上传 | `Upload` |
| 评测 | `BarChart3` |
| 展开 | `ChevronDown` |
| 折叠 | `ChevronUp` |

---

## 10. 命名规范

### 10.1 文件命名

- 页面组件：`PascalCasePage.tsx`（如 `StoryLibraryPage.tsx`、`PlaySessionPage.tsx`），页面统一加 `Page` 后缀以区别于功能组件
- UI 基础组件：`PascalCase.tsx`（如 `Button.tsx`、`Dialog.tsx`）
- Hooks：`camelCase.ts`（如 `useAuth.ts`、`useSession.ts`）
- Store：`camelCase.ts`（如 `authStore.ts`、`sessionStore.ts`）
- 工具函数：`camelCase.ts`（如 `formatDate.ts`）
- API 封装：`camelCase.ts`（如 `storyApi.ts`、`sessionApi.ts`）
- 类型定义：`camelCase.ts`（如 `story.ts`、`session.ts`）

### 10.2 CSS 命名

- 全部使用 Tailwind 原子类，不写自定义 CSS 类名。
- CSS 变量用于设计令牌（颜色、字体），定义在 `styles/globals.css`。
- 组件变体用 `clsx` + `tailwind-merge` 动态拼接。

### 10.3 组件 Props

- 使用 TypeScript interface，以 `Props` 后缀命名。
- 示例：`ButtonProps`、`ChatBubbleProps`。
