# Cloudflare Pages 部署指南 — ACG 游戏姬云端版

> 目标:把"单 HTML 版"部署到 Cloudflare Pages,搭配 GitHub Actions 每天自动抓 3 次(北京时间 8/13/20),**手机直接打开 URL 就能看最新数据**,电脑可以一直关着。

---

## 0. 整体架构

```
┌──────────────────────────────────────────────────────────┐
│  GitHub Repository(项目代码)                              │
│  ├─ .github/workflows/scrape.yml  ← 每天 3 次定时抓取    │
│  ├─ 单html版本/                                        │
│  │   ├─ index.html              ← 手机访问的页面          │
│  │   └─ data/acgyx_latest.json  ← 自动更新的最新数据     │
│  └─ 电脑版/                  ← 电脑本地用(可不上 Pages)  │
└────────┬─────────────────────────────────────────────────┘
         │ git push
         ▼
┌──────────────────────────────────────────────────────────┐
│  Cloudflare Pages(静态站点托管)                           │
│  https://<你的项目名>.pages.dev  ← 手机访问的地址         │
└──────────────────────────────────────────────────────────┘
         ▲
         │ 每 8/13/20 点(GitHub Actions 触发)
         │
┌────────┴─────────────────────────────────────────────────┐
│  acgyx.us  站点  ←  Actions 抓取,生成 JSON,git commit     │
└──────────────────────────────────────────────────────────┘
```

**关键点**:
- Cloudflare Pages 只托管**静态文件**(HTML + JSON)
- 抓取在 GitHub Actions 跑(免费 2000 分钟/月,够用)
- Actions 跑完会 commit + push JSON,Cloudflare 自动重新部署
- 用户手机上看到的永远是"今天抓的"数据

---

## 1. 准备工作(5 分钟)

### 1.1 注册 GitHub
- 打开 https://github.com/signup 注册账号
- 选 Free 计划(免费,够用)

### 1.2 注册 Cloudflare
- 打开 https://dash.cloudflare.com/sign-up 注册
- 不用绑卡,免费 Pages 不限流量

### 1.3 安装 Git(电脑端)
- 打开 https://git-scm.com/download/win 下载安装
- 装完右键桌面会有 "Git Bash Here"
- 打开 Git Bash,设用户名邮箱:
  ```bash
  git config --global user.name "你的名字"
  git config --global user.email "你的邮箱@example.com"
  ```

---

## 2. 创建 GitHub 仓库并 push 代码(10 分钟)

### 2.1 在 GitHub 网页上创建空仓库
1. 登录 GitHub,右上角 **+** → **New repository**
2. 填写:
   - Repository name: `acg-game-scraper`(可改名,后面 Pages URL 跟着改)
   - Description: 随便写
   - **Public**(必须 Public,免费 Pages 才能绑)
   - **不要**勾选 "Add a README"(本地已有文件)
3. 点 **Create repository**

### 2.2 推送本地代码到 GitHub
打开 PowerShell,执行:

```powershell
cd "D:\Tsinho文件夹\Trae\测试项目\ACG游戏姬工具"

# 1. 初始化 git(如果还没)
git init

# 2. 加 .gitignore(防止 .venv / __pycache__ / 测试截图被传上去)
#    如果已有这个文件,跳过这一步
@"
.venv/
__pycache__/
*.pyc
单html版本/_test_shot_*.png
单html版本/_shot_*.png
"@ | Out-File -Encoding utf8 .gitignore

# 3. 第一次提交
git add .
git commit -m "首次提交:ACG 游戏姬抓取 + 单 HTML 云端版"

# 4. 关联到 GitHub(替换成你刚建的仓库地址)
git remote add origin https://github.com/你的用户名/acg-game-scraper.git

# 5. 推上去
git branch -M main
git push -u origin main
```

> **如果 push 失败要登录**:
> - 弹窗让你登录 GitHub,正常输入账号密码
> - 装了 2FA 要输入验证码
> - 不行就装 [GitHub CLI](https://cli.github.com/):`winget install GitHub.cli`,然后 `gh auth login`

### 2.3 验证
浏览器打开 `https://github.com/你的用户名/acg-game-scraper`,能看到所有文件就 OK。

---

## 3. 绑定 Cloudflare Pages(5 分钟)

### 3.1 创建 Pages 项目
1. 登录 https://dash.cloudflare.com
2. 左边栏点 **Workers & Pages** → **Pages** → **Create application**
3. 选 **Connect to Git**
4. 点 **GitHub** → 授权 Cloudflare 访问你的 GitHub
5. 选 **Only select repositories**,搜索 `acg-game-scraper`,点 **Install & Authorize**
6. 回到 Cloudflare,选你的仓库 → **Begin setup**

### 3.2 配置构建设置
- **Project name**:`acg-game-scraper`(可改,会变成 `xxx.pages.dev`)
- **Production branch**:`main`
- **Framework preset**:选 **None**
- **Build command**:**留空**(我们是纯静态,不需要 build)
- **Build output directory**:`单html版本`
  > ⚠️ **关键**:这里填 `单html版本`,Cloudflare 才会把这个目录当站点根目录
- **Environment variables**:不用设

### 3.3 部署
点 **Save and Deploy**,等 1-2 分钟,看到绿色的 ✅ 就成功了。

### 3.4 拿到你的 URL
部署完成后会显示:
```
🌍 https://acg-game-scraper.pages.dev
```

**手机浏览器打开这个 URL 就能用了!**

---

## 4. 测试自动抓取(2 分钟)

### 4.1 手动触发一次
1. 打开 GitHub 仓库 → **Actions** 标签
2. 左边选 **抓取 ACG 游戏姬**
3. 右边 **Run workflow** → 点绿色按钮 **Run workflow**
4. 等 1-2 分钟,看是否有 ✅

### 4.2 验证数据更新
- Actions 跑完,仓库里 `单html版本/data/acgyx_latest.json` 会被自动 commit 更新
- Cloudflare 检测到 push,会自动重新部署
- 等 1-2 分钟,手机刷新 Pages URL 就能看到新数据

### 4.3 定时任务
`scrape.yml` 里写的是:
```yaml
schedule:
  - cron: "0 0,5,12 * * *"
```
- UTC 时间 0:00 / 5:00 / 12:00
- = 北京时间 **8:00 / 13:00 / 20:00**(每天 3 次)
- 你不用动,GitHub 会自动跑

---

## 5. 故障排查

### 5.1 Pages 部署成功但页面 404
- **原因**:Build output directory 填错
- **解决**:回到 Pages 设置,把 `Build output directory` 改成 `单html版本`,点 **Retry deployment**

### 5.2 页面打开了但显示"加载失败"
- **原因**:JSON 路径不对,或者 `acgyx_latest.json` 没生成
- **解决**:
  1. 直接打开 `https://你的项目.pages.dev/data/acgyx_latest.json`,看能不能看到 JSON
  2. 如果 404:去 GitHub Actions 手动跑一次 scrape.yml
  3. 如果 JSON 看到了但 HTML 不读:打开浏览器 F12 控制台看 fetch 错误

### 5.3 Actions 跑失败
打开 GitHub → Actions → 失败的那次 → 看红色步骤,常见原因:
- **依赖装不上**:网络问题,点 **Re-run jobs** 重试
- **scraper 报错**:可能是 acgyx.us 改了页面结构,看 `电脑版/scraper.py` 是否需要调整

### 5.4 想换手机访问的域名
- 在 Cloudflare Pages → **Custom domains** → **Set up a custom domain**
- 填你已有的域名(如 `acg.你的域名.com`),按提示去域名注册商加 CNAME 记录

### 5.5 想改抓取时间
- 编辑 `.github/workflows/scrape.yml` 的 `cron`
- cron 格式是 UTC,北京 = UTC + 8
- 例:想改成北京时间 6/12/18 → UTC 22/4/10 → `cron: "0 22,4,10 * * *"`

---

## 6. 进阶(可选)

### 6.1 加访问密码
- Cloudflare Pages → **Settings** → **Access policies** → **Add**
- 选 "Service Auth" 登录方式,设用户名密码
- 免费额度 50 个用户,够用

### 6.2 多设备同步访问历史
- 在 Cloudflare Pages → **Analytics** 看访问量
- 或加 Google Analytics(在 index.html 的 `<head>` 加 GA 脚本)

### 6.3 自动归档历史数据
- 改 `.github/workflows/scrape.yml`,在 commit 前加:
  ```yaml
  - name: 备份历史
    run: |
      mkdir -p archive/$(date +%Y%m%d)
      cp 单html版本/data/acgyx_latest.json archive/$(date +%Y%m%d)/
  ```

---

## 7. 一图流(完整操作顺序)

```
1. 注册 GitHub + Cloudflare 账号
         ↓
2. 本地 git init + add + commit + push
         ↓
3. Cloudflare Pages 连 GitHub,选单html版本 为输出目录
         ↓
4. 部署成功 → 拿到 https://xxx.pages.dev
         ↓
5. 浏览器打开验证
         ↓
6. GitHub Actions 手动跑一次,看 JSON 是否更新
         ↓
7. 手机收藏 https://xxx.pages.dev,完事 🎉
```

---

## 8. 关键文件对应

| 文件 | 作用 | 部署时是否需要 |
|------|------|----------------|
| `单html版本/index.html` | 手机访问的页面 | ✅ 必须 |
| `单html版本/data/acgyx_latest.json` | 数据 | ✅ 必须(Actions 自动更新) |
| `.github/workflows/scrape.yml` | 定时抓取 | ✅ 必须 |
| `电脑版/` | 电脑本地用 | ⚠️ 可选(带了能让 Actions 直接调 scraper.py) |
| `单html版本/_t_html_v2.py` | 测试脚本 | ❌ 不需要(.gitignore 已排除测试截图) |
| `.venv/` | 虚拟环境 | ❌ 不会传(.gitignore) |

---

## 9. 下次更新

以后要改页面:
1. 电脑改 `单html版本/index.html`
2. 测一下:`cd 单html版本; python -m http.server 8000`,手机扫码访问 `http://你电脑IP:8000/index.html`
3. 测试 OK 后 `git add . && git commit -m "xxx" && git push`
4. Cloudflare 1-2 分钟自动部署完成,手机刷新就是新版本

---

## 10. 联系

遇到问题先看:
1. GitHub Actions 日志(看抓取是否成功)
2. Cloudflare Pages → **Deployments** → 看 build 日志
3. 手机浏览器 F12(用 USB 调试)看 console 错误

其他问题直接问。
