# 海垦日报 · 历史归档（最小 SPA 骨架）

![GitHub Pages](https://img.shields.io/badge/GitHub%20Pages-已上线-brightgreen) ![自动归档](https://img.shields.io/badge/每日%2009:40-自动同步-blue)

> 🌐 **公网版**：https://pandhow.github.io/haiken-archive/ ｜ 由「海垦日报·归档+公网同步」自动化每日 09:40 自动发布（日报生成 09:10 → 本地归档 → 推公网）

一个**纯前端 SPA**，归档「海垦日报」每日自动生成的 HTML 报告。零后端、零数据库、零构建工具——双击或起个静态服务就能跑。

## 目录结构

```
haiken-archive/
├── index.html              # 外壳：顶栏 + 期次列表 + 内容查看区
├── app.js                  # SPA 运行时：拉 manifest → 渲染列表 → 哈希路由 → iframe 载入
├── styles.css              # 归档站自身样式（深色科技风）
├── data/
│   └── manifest.json       # 期次清单（日期/期号/标题/标签/文件路径）
├── issues/
│   └── 2026-07-23.html     # 每期日报独立 HTML（自动化产物原样放入）
└── README.md               # 本文件
```

## 本地运行

需要 http 协议（fetch manifest 才能工作），起个本地静态服务即可：

```bash
cd haiken-archive
python -m http.server 8080
# 浏览器打开 http://localhost:8080
```

或用 Node：`npx serve .` / `npx http-server -p 8080`

> 直接双击 `index.html` 也能看外壳，但 `fetch('data/manifest.json')` 在 `file://` 下会被 CORS 拦截，列表会加载失败——所以建议用上面的本地服务器。

## 新增一期（日常流程）

海垦日报自动化每天 09:10 生成 `D:\Harry的文件\海垦日报_YYYY-MM-DD.html`，**且 HTML 头里自带 `<meta name="archive-title">` 与 `<meta name="archive-tags">`**。

### ✅ 推荐：一键自动归档（免手动）

```bash
cd haiken-archive
python archive_sync.py
```

脚本会：
- 扫描 `D:\Harry的文件\海垦日报_*.html`
- 把新一期复制进 `issues/YYYY-MM-DD.html`
- 从 HTML 的 `<meta>` 自动读取标题/标签，生成/追加 `data/manifest.json`
- 幂等：内容一致的已归档期次自动跳过；**绝不覆盖人工精修过的标题**
- 支持 `--dry-run` 预览、`--source` / `--archive` 自定义目录

建议把这一步接在自动化生成之后（或在本地随时手动跑一次），归档即完全免手动。

### 手动归档（备用）

若需手工操作，两步即可：

1. 把当天的 HTML 复制进 `issues/`，命名 `YYYY-MM-DD.html`
2. 在 `data/manifest.json` 的 `issues` 数组**顶部**加一条：
   ```json
   {
     "date": "2026-07-24",
     "issue_no": "002",
     "title": "一句话概括当天核心看点",
     "tags": ["标签1", "标签2"],
     "file": "issues/2026-07-24.html"
   }
   ```
3. 刷新页面，新期次出现在列表顶部

## 功能

- **期次列表**：左侧按日期降序，每条显示日期/期号/标题/标签
- **搜索过滤**：顶栏搜索框，按标题/标签/日期/期号实时过滤
- **哈希路由**：URL `#/2026-07-23` 直接定位某期，可分享/收藏
- **iframe 载入**：每期 HTML 独立渲染，样式互不污染，原报告外观 100% 保留
- **关于页**：`#/about`

## 架构说明（这是 SPA，不是静态站）

| 层 | 文件 | 作用 |
|---|---|---|
| 静态外壳 | `index.html` | 页面骨架（顶栏/侧栏/查看区） |
| JS 运行时 | `app.js` | 路由 + 状态 + 渲染（页面不刷新切换内容） |
| 数据接口 | `data/manifest.json` | 唯一数据源，等同后端 API |
| 动态 DOM | `#issueList` / `#issueFrame` | JS 运行时填入/切换 |

导航不刷新整页 → 这就是 SPA。数据来自 JSON（而非写死在 HTML 里）→ 加期不用改代码。

## 后续可扩展（非必需）

- ~~自动生成 manifest~~ ✅ 已完成：`archive_sync.py` 扫描源目录自动拼 manifest
- 全文搜索：把每期正文文本抽成 `data/index.json`，搜索能命中正文
- 部署上云：整个目录传 CloudStudio / GitHub Pages / Vercel，即得公网可访问归档站
- 双端同步：归档站更新后，可触发同步到飞书/ima（沿用既有「双端文档同步」技能）
- 定时归档：把 `python archive_sync.py` 也挂成每日自动化（紧接 09:10 日报生成之后跑），归档零人工
