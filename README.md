# 技术阅读库

一个 HTML 静态阅读站，包含技术专栏、技术文章、生活文章、PDF，以及作者与发布时间筛选、搜索和最近阅读功能。

**部署只需要 HTML、CSS、JavaScript、图片和 PDF 等静态文件，以及 Nginx 等静态文件服务器。服务器不需要安装 Python、Node.js 或数据库。** Docker 是可选的部署方式；Python 只用于重新生成页面、维护检查和本地预览。

项目根目录就是网站根目录，`index.html` 在根目录，没有 `site/` 这一层。当前整理版本包含 159 个专栏、6,300 篇文章和 5 份 PDF。

## 一、静态文件部署

已有完整网站文件时，可以直接部署，不需要先执行任何 Python 脚本，也不需要构建 Docker 镜像。

**仓库包含全部已整理的图片和 5 份 PDF，使用 Git LFS 随版本一起保存，不需要另找资源包。** 首次下载代码的电脑需安装 Git 和 Git LFS，然后执行：

```bash
git lfs install
git clone git@codeup.aliyun.com:yuping/personal/project/geektime-column-offline.git
cd geektime-column-offline
git lfs pull
git lfs fsck
```

如果已经克隆过旧版本，在仓库中执行 `git pull --ff-only` 和 `git lfs pull` 即可补齐资源。Git LFS 只用于代码获取和维护，静态服务器运行网站不依赖它。没有安装 Git LFS 的客户端可能只取得资源指针；不要直接部署这些指针文件。完整获取方法见 [仓库与资源获取](docs/deployment.md#仓库与资源获取)。

文件下载完成后部署：

1. 在服务器或面板中创建静态网站，使用 Nginx 等静态文件服务器。
2. 将下面这些文件和目录复制到网站根目录，保持相对位置不变。
3. 设置默认首页为 `index.html`，通过网站地址访问。

```text
网站根目录/
├─ index.html
├─ about.html
├─ course-sources.html
├─ courses/
├─ articles/
├─ geektime/
├─ relationships/
├─ downloads/
├─ assets/
└─ static/
```

- 只发布上面的内容；`scripts/`、`data/`、`.git/` 等维护目录不需要上传。
- Nginx 应加载标准 `mime.types`，使 HTML 返回 `text/html`。配置可参考 [docker/nginx.conf](docker/nginx.conf)。
- 站内链接使用 `/courses/...` 等根路径，应部署在域名根路径；部署到 `/项目名/` 等子路径前需要适配链接。
- `assets/` 和 `downloads/` 中的资源必须与 HTML 一起发布，不能只上传页面；上面的完整克隆步骤会获取这些文件。

**以后更新网站：直接替换发布目录中的相应静态文件，不需要打包镜像。** 如果改的是作者 JSON 或页面模板，先按第三部分在开发电脑上生成 HTML，再上传生成结果。

## 二、Docker 打包部署

此方式将 Nginx 和网站静态文件装在同一个镜像里。构建镜像和运行容器都不需要 Python；Windows 上使用 Docker Desktop 的 Linux 容器模式。

### 1. 构建并在本机运行

确认图片和 PDF 已补齐，在项目根目录执行：

```powershell
docker compose up -d --build
```

访问 <http://127.0.0.1:18891/>。`Dockerfile` 只复制公开网站内容，不包含维护脚本、原始仓库或元数据文件。

首次使用这份源码进行 Docker 部署需要构建镜像。**以后网站文件或镜像配置发生变化，再重新构建并更新容器；日常访问、重启或迁移已有镜像无需重新构建。** 本地更新仍执行上面的命令即可。

### 2. 导出镜像文件

构建成功后，在项目根目录执行以下 PowerShell 命令：

```powershell
New-Item -ItemType Directory -Force exports | Out-Null
docker image save -o exports/lianglianglee-library.tar lianglianglee-library:local
```

得到 `exports/lianglianglee-library.tar`。这是 Docker 镜像包，包含 Nginx 和构建时的网站文件，不是网站源码压缩包。导出过程也不需要 Python；可选的压缩导出工具见 [部署文档](docs/deployment.md#导出镜像)。

### 3. 导入 Linux 主机或面板运行

**可以在支持 Docker 的 Linux 主机或面板中运行，前提是镜像平台与目标主机匹配。** 例如 x86-64 主机使用 `linux/amd64`，ARM64 主机使用 `linux/arm64`。构建时应按目标平台准备镜像，不能把单一架构镜像当成通用镜像；检查与构建方法见 [Linux 部署说明](docs/deployment.md#linux-主机或面板部署)。

在面板中导入镜像包，然后使用 `lianglianglee-library:local` 创建容器，设置：

| 配置 | 值或说明 |
| --- | --- |
| 容器端口 | `80`，网站使用 HTTP |
| 主机端口 | 例如 `8080`，映射为 `8080:80`；选择未占用端口 |
| 重启策略 | `unless-stopped` |
| 启动命令 | 使用镜像默认值 |
| 网站目录挂载 | 不需要，文件已经包含在镜像中 |

也可以上传镜像包后，在 Linux 终端执行：

```bash
docker load -i lianglianglee-library.tar
docker run -d --name lianglianglee-library --restart unless-stopped -p 8080:80 lianglianglee-library:local
```

访问 `http://服务器地址:8080/`，或在面板中为该服务配置域名反向代理。需要允许访问所选端口。镜像导入只恢复镜像，不会自动创建容器或携带本机的端口映射；应使用对应 `docker load` 的镜像导入功能。

项目自带的 `compose.yaml` 默认绑定 `127.0.0.1:18891`，仅宿主机本地可访问；用于服务器时可接入同机面板的反向代理，或按需修改端口绑定。更新远端网站时，重新构建、导出、导入新镜像，并用新镜像重建容器；只重启旧容器不会更新内容。

## 三、Python 重新生成页面

**这一部分只在维护网站时使用，不是服务器部署步骤。** 浏览器不直接读取作者 JSON：JSON 和模板先由 Python 生成 HTML，再将 HTML 发布到服务器。

需要重新生成页面时，在开发电脑上准备 Python 3.11 或更新版本，并在项目根目录安装依赖：

```powershell
python -m pip install -r requirements.txt
```

| 修改内容 | 修改位置 | 后续操作 |
| --- | --- | --- |
| 作者、发布日期、资料来源 | `data/course-metadata.json` | 运行 `python scripts/build_home.py` |
| 首页、专栏列表与最近阅读模板 | `ui/home.html`、`ui/courses.html`、`ui/recent-reading.html` | 运行 `python scripts/build_home.py` |
| 共用页头、导航、阅读页外壳 | `scripts/ui_common.py` | 运行 `python scripts/refresh_layout.py` |
| 字体、颜色、间距等样式 | `static/` 中相应 CSS | 不需要 Python，刷新预览或发布修改后的 CSS |
| 搜索、排序、最近阅读交互 | `static/` 中相应 JavaScript | 不需要 Python，刷新预览或发布修改后的 JavaScript |

`build_home.py` 更新首页、技术专栏目录、文章目录、PDF 目录和资料来源页，不重新转换文章正文。不要只修改生成后的卡片 HTML，否则下次生成时会被 JSON 和模板覆盖。

首页是整个书库的概览，技术专栏列表位于 `/courses/index.html`。所有内容目录共用固定位置的导航；旧的首页专栏筛选链接会自动转到新专栏目录。

`refresh_layout.py` 批量更新阅读页外壳，逐篇校验正文区域字节不变，并更新页面清单中的校验值。

批量修改后，可按需检查链接和文件完整性：

```powershell
python scripts/verify_site.py --project .
python scripts/verify_integrity.py --project .
```

生成完成后，静态部署只上传更新后的公开文件；使用当前 Docker 部署方式则重新构建镜像。原仓库对比、缺图修复和完整重建工具位于 `scripts/maintenance/`，日常部署不需要运行，详见 [开发与维护](docs/development.md)。

## 四、本地预览

预览用于在开发电脑上查看和调整页面，不代表线上服务器也需要 Python。可以选择以下任一种方式。

### 使用 Python 预览

准备 Python 3.11 或更新版本，在项目根目录执行：

```powershell
python scripts/dev_server.py
```

Windows 也可双击 `启动本地预览.cmd`。预览工具只使用 Python 标准库，不需要先安装页面生成依赖。

访问 <http://127.0.0.1:18890/>。修改 HTML、CSS、JS 后刷新即可；修改 JSON 或模板后先执行第三部分的生成步骤。关闭预览时按 `Ctrl+C`，修改端口可使用 `--port 18892`。

预览服务仅绑定本机，并限制只访问公开网站文件，`data/`、`scripts/`、`.git/` 等目录不会开放。

### 使用 Docker 预览

不使用 Python 时，也可以按第二部分运行 Docker，通过 <http://127.0.0.1:18891/> 访问。当前 Docker 配置将文件复制进镜像，修改文件后需要重新构建并更新容器才能看到变化。

最近阅读保存在浏览器的 `localStorage`，最多 50 篇，不上传服务器。不同域名、协议、端口的记录相互独立，所以 18890 与 18891 的记录不会自动共享。

## 五、目录结构与作用

```text
lianglianglee-library/
├─ index.html                 网站首页，已经生成，可直接部署
├─ about.html                 关于书库、来源与完整性说明
├─ course-sources.html        专栏作者、发布日期与查证依据页面
├─ courses/                   技术专栏目录和各章节 HTML
├─ articles/                  独立技术文章 HTML 与技术文章目录
├─ geektime/                  单文件专栏合集 HTML 和兼容入口
├─ relationships/             生活文章 HTML 与目录
├─ downloads/                 PDF 文件和下载页；PDF 通过 Git LFS 随仓库保存
├─ assets/                    文章图片与附件；通过 Git LFS 随仓库保存
├─ static/                    CSS、JavaScript，包括搜索、排序、最近阅读
├─ ui/                        首页、专栏列表与最近阅读模板；不是部署必需文件
├─ data/                      页面生成、核验、资源恢复所需的维护资料
│  ├─ course-metadata.json    专栏作者、发布时间、来源等元数据
│  ├─ manifests/             页面、资源、处理问题清单及校验值
│  ├─ provenance/            来源查证记录、修复依据
│  │  └─ snapshots/          核验和恢复所用的必要证据快照
│  ├─ reviews/               人工核对表原件副本
│  └─ upstream.json          原始仓库地址与固定提交版本
├─ scripts/                   页面生成、预览、校验和资源包管理工具
│  └─ maintenance/           原仓库对比、完整重建、图片修复、镜像导出
├─ docker/
│  └─ nginx.conf             镜像中的 Nginx 配置，限制可访问的目录
├─ docs/                      开发维护、部署、内容来源的详细文档
├─ tests/                     维护工具的测试，不参与网站运行
├─ reports/                   检查结果，不参与网站运行
│  └─ archive/               原整理过程的历史检查报告
├─ .cache/                    按需产生的源仓库下载和资源处理缓存
├─ .dev/                      本地预览进程编号与日志
├─ exports/                   按需导出的资源包、Docker 镜像文件
├─ .git/                      本地 Git 版本管理数据，不部署
├─ .gitignore                 排除镜像归档、缓存、日志和可再生成的导出包
├─ .gitattributes             文件类型、换行策略和图片/PDF 的 Git LFS 规则
├─ .dockerignore              限定 Docker 构建时可读取的项目文件
├─ Dockerfile                 镜像构建配置：Nginx 加公开静态文件
├─ compose.yaml               本机容器启动配置：端口、重启、临时目录等
├─ requirements.txt           Python 页面生成与维护工具依赖
├─ 启动本地预览.cmd           Windows 本地预览入口，调用 Python
├─ 打开本地预览.url           打开默认本地预览地址，不负责启动服务
├─ NOTICE.md                  第三方内容来源与许可说明
└─ README.md                  本说明
```

`.cache/`、`.dev/`、`exports/` 等目录按需产生，不必预先创建，也不进入 Git。`data/manifests/` 和 `data/provenance/snapshots/` 属于维护输入，不是临时缓存。普通静态部署仅需要第一部分列出的公开文件。

图片与 PDF 均纳入仓库，Git LFS 管理的资源约 4.00 GiB；生成的 Docker 镜像、重复资源导出包和本地运行缓存不提交。完整站点约 4.24 GiB，部署前应确认资源下载完成。当前没有提供 GitHub Pages 自动部署配置。

仍有 11 个原始图片 URL 未恢复，尚未完成与源站的全部正文、资源在线逐项核验，见 [内容来源与校验](docs/provenance.md)。第三方文章和图片的权利归原作者或权利人；本项目不重新授予这些内容的使用权，见 [NOTICE](NOTICE.md)。

详细资料：[开发与维护](docs/development.md) · [部署与资源管理](docs/deployment.md) · [Docker 镜像导入说明](https://docs.docker.com/reference/cli/docker/image/load/) · [Docker 平台与架构说明](https://docs.docker.com/build/building/multi-platform/)。
