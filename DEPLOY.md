# 部署到手机（GitHub Pages + 一键更新）

目标：手机上打开一个网址就能看到当日谷底分，点一下就能拉最新数据。

---

## 一、一次性设置（在电脑上做，约 10 分钟）

### 1. 注册 GitHub（已有可跳过）

https://github.com 注册，记下用户名。

### 2. 建仓库

网页右上角 **+ → New repository**
- Repository name：`515450`（随便起）
- 选 **Private**（私有，别人看不到）还是 Public 都行
- **不要**勾选 "Add a README"
- 点 **Create repository**

### 3. 把项目传上去

在项目文件夹 `D:\User\xvhai\515450-temp` 里，右键 → 「在终端中打开」（或 Win+R 输 `cmd` 再 `cd /d D:\User\xvhai\515450-temp`），依次执行：

```bat
git init
git add -A
git commit -m "first"
git branch -M main
git remote add origin https://github.com/你的用户名/515450.git
git push -u origin main
```

第一次推送会弹窗让你登录 GitHub（浏览器授权即可）。

### 4. 打开 Pages

仓库页面 → **Settings → Pages**
- Source 选 **Deploy from a branch**
- Branch 选 **main**，目录选 **/docs**
- 点 **Save**

等 1–2 分钟，网址就是：

```
https://你的用户名.github.io/515450/
```

手机浏览器打开这个网址，加到主屏幕即可。

### 5. 允许 Action 提交

仓库 → **Settings → Actions → General → Workflow permissions**
选 **Read and write permissions** → Save

（否则自动更新完推不上去）

---

## 二、手机上更新数据

### 方式 A：手动触发（推荐）

1. 手机装 **GitHub** App，登录
2. 打开仓库 → 下方 **Actions** 标签 → 选 **更新谷底分数据**
3. 点 **Run workflow → Run workflow**
4. 等 1–2 分钟，刷新网页就是最新数据

### 方式 B：自动

已经配好定时任务：**工作日北京时间 15:24** 自动跑一次，你什么都不用点。

---

## 三、每天会生成什么

| 文件 | 内容 |
|---|---|
| `docs/index.html` | 手机主页：今日谷底分、定投金额、可切换区间曲线 |
| `docs/review-2026.html` | 今年回放（按区间染色） |
| `docs/review-all.html` | 全区间回放 |
| `docs/review-month.html` | 近月回放 |

---

## 四、可能遇到的问题

### 1. Action 里取数失败

GitHub 的服务器在国外，访问腾讯 / 蛋卷 / 东财的接口**偶尔会超时或被拦**。

如果 Actions 日志里出现「取数失败」，说明那天的网络不通，解决办法：

- 再点一次 Run workflow（通常第二次能成功）
- 或者把定时任务改到另一个时间点（改 `update.yml` 里的 cron）

### 2. 手机上网页打不开

- 确认 Pages 已经显示 "Your site is live at ..."
- 国内访问 `github.io` 有时慢，多点几次或换个网络

### 3. 想改成自己的规则

改 `config.json` 里的 `dca` 段，然后手机上 Run workflow 一次即可生效。

---

## 五、如果 Actions 取数一直失败

备选方案：**电脑跑，手机看**。

1. 电脑每天双击 `每日打分.cmd`
2. 再跑一下 `python build_mobile.py`
3. `git add -A && git commit -m update && git push`

手机端不用任何操作，刷新就是最新的。

---

## 附：目录结构

```
515450-temp/
├─ .github/workflows/update.yml   # 自动更新任务
├─ docs/                          # 手机网站（自动生成）
│  ├─ index.html
│  ├─ review-2026.html
│  ├─ review-all.html
│  └─ review-month.html
├─ daily_score.py                 # 取数 + 打分
├─ trough.py                      # 谷底分
├─ build_mobile.py                # 生成手机版
├─ config.json                    # 规则配置
└─ 每日打分.cmd                   # 电脑端一键运行
```
