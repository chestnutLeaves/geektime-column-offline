# 部署与资源管理

本项目运行时只需要静态文件服务器。已有生成好的 HTML、CSS、JavaScript、图片和 PDF 时，部署无需执行 Python，也不需要安装数据库或 Node.js。Python 是开发电脑上的页面生成、校验、资源管理和预览工具。

| 部署方式 | 首次部署 | 网站更新 |
| --- | --- | --- |
| 直接静态部署 | 将公开文件放到静态网站根目录 | 替换变更的公开文件，不需要 Docker |
| 当前 Docker 方式 | 构建镜像，或者导入已有镜像，再创建容器 | 重新构建镜像，用新镜像重建容器；远端先导出、传输、导入 |

只有修改作者 JSON、页面模板或共用外壳等生成输入时，才需要先在开发电脑上重新生成相应 HTML。修改 CSS、JavaScript 无需运行生成脚本。Docker 镜像也可因 Nginx 配置或基础镜像更新而重新构建，不限于内容变化。

## Git 仓库和独立资源

根目录的 HTML、`static/`、模板、脚本、JSON 清单和必要证据均可进入 Git。`assets/` 和 `downloads/` 中的 PDF 体积较大，由 `.gitignore` 排除；下载页 `downloads/index.html` 仍保留在 Git。

本机这份项目已经复制了完整资源。以后从 Git 克隆时，图片和 PDF 需要通过与当前 `data/manifests/resources.jsonl` 匹配的资源包补齐。不要把“只克隆仓库”与“已获得完整离线阅读包”混为一谈。

在拥有完整资源的项目中按需导出：

```powershell
python scripts/resources.py export exports/resources.zip
```

在另一个克隆项目中导入：

```powershell
python scripts/resources.py import resources.zip
python scripts/resources.py check
```

工具使用 ZIP64，支持大于 4 GiB 的资源包；导出时不再压缩已压缩图片。导入先校验全部文件名、大小和 SHA-256，再安装文件。清单不一致、资源损坏或包含额外文件的包会被拒绝。导入需要临时磁盘空间，约等于资源包解压后的大小。

本次目录整理没有导出资源包或 Docker 镜像。`exports/` 只在执行导出命令后创建，导出结果不进入 Git。

## 普通静态服务器

推荐将以下公开文件复制到独立网站根目录，再由面板静态网站或 Nginx 提供访问，默认首页设置为 `index.html`：

```text
index.html  about.html  course-sources.html
courses/  articles/  geektime/  relationships/
downloads/  assets/  static/
```

如果直接以完整项目根目录作为网站根目录，请使用或参照 `docker/nginx.conf` 的白名单，不要把 `.git/`、`data/`、`scripts/`、`ui/`、`docs/`、`reports/`、`tests/` 等维护目录开放给访问者。

Nginx 的 `http` 块应加载标准 `mime.types`，使 `.html` 返回 `text/html`。不需要给 `.md` 配置特殊类型。本项目保留 `/courses/...` 等根路径链接，默认使用独立域名根路径；子路径托管需要另行适配。

后续更新直接替换发布目录中的相应文件，无需打包镜像；浏览器有旧缓存时刷新缓存后核对效果。只有修改 Nginx 配置才需要按服务器管理方式重新加载配置。

## Docker

### 构建和本机运行

Windows 使用 Docker Desktop 的 Linux 容器模式。确认图片和 PDF 已补齐后，在根目录运行；Docker 构建不调用 Python：

```powershell
docker compose up -d --build
```

访问 <http://127.0.0.1:18891/>。容器名为 `lianglianglee-library`，默认只绑定本机。`Dockerfile` 逐项复制公开内容，不复制维护工具或原始 Git 仓库。

```powershell
docker compose ps
docker compose logs --tail 100
docker compose stop
```

首次从源码部署需要构建镜像。当前配置将文件复制进镜像，更新网站文件后需要重新构建并更新容器，本机仍执行 `docker compose up -d --build`。重启或迁移内容未变的已有镜像，无需重新构建。

### 导出镜像

镜像已经构建成功时，可直接使用 Docker 导出，不需要 Python。在项目根目录执行：

```powershell
New-Item -ItemType Directory -Force exports | Out-Null
docker image save -o exports/lianglianglee-library.tar lianglianglee-library:local
```

也可以选择项目提供的 Python 工具，流式压缩为 `.tar.gz` 并生成 SHA-256 校验文件：

```powershell
python scripts/maintenance/export_image.py --output exports/lianglianglee-library.tar.gz
```

导出脚本仅保存已有镜像，不会执行镜像构建。两种方式得到的镜像包都可用 `docker load -i` 导入，Docker 支持直接加载 gzip 压缩镜像包；面板若只接受 `.tar`，使用第一种导出方式。

### Linux 主机或面板部署

支持 Docker 的 Linux 主机或面板可以运行该镜像，不需要另装 Python、Node.js 或网站数据库，也不需要再次上传网站源码。镜像包含构建时的 Nginx 和全部公开网站文件。

**先确认目标主机架构与镜像平台匹配。** 在 Linux 上使用 `uname -m`：`x86_64` 对应 `linux/amd64`，`aarch64` 对应 `linux/arm64`。项目当前未固定构建平台；已构建镜像可这样检查：

```bash
docker image inspect lianglianglee-library:local --format '{{.Os}}/{{.Architecture}}'
```

例如，目标是 x86-64 Linux 主机时，可在开发电脑的项目根目录明确构建 `linux/amd64` 镜像：

```powershell
docker buildx build --platform linux/amd64 --load -t lianglianglee-library:local .
```

ARM64 主机需要对应的 `linux/arm64` 镜像，且 `Dockerfile` 固定的基础镜像必须支持该平台；跨架构构建前应核实其支持情况。不要默认单一架构镜像可在另一架构主机原生运行。

将镜像包传到服务器后，在面板的 Docker 镜像管理中导入。如果面板没有对应入口，可在服务器终端执行：

```bash
docker load -i lianglianglee-library.tar
```

这是 `docker image save` / `docker load` 格式，不能用容器文件系统的 `export` / `import` 流程代替。导入只恢复镜像和标签，仍需要创建并启动容器。

| 面板配置 | 设置 |
| --- | --- |
| 镜像 | `lianglianglee-library:local` |
| 容器端口 | `80`，HTTP |
| 主机端口 | 例如 `8080`，选择未被占用的端口 |
| 重启策略 | `unless-stopped` |
| 启动命令 | 保留镜像默认值 |
| 网站文件挂载 | 无需配置，镜像已经包含文件 |

使用终端创建容器的等价示例：

```bash
docker run -d --name lianglianglee-library --restart unless-stopped -p 8080:80 lianglianglee-library:local
```

然后访问 `http://服务器地址:8080/`，并确认该端口允许访问。需要域名或 HTTPS 时，在面板中配置反向代理到这个 HTTP 服务。

项目 `compose.yaml` 默认映射 `127.0.0.1:18891:80`，仅宿主机本地可访问。面板反向代理若在同一宿主机，可接入该地址；若代理本身在另一个容器中，应按面板的容器网络方式配置上游。不要将 `127.0.0.1` 当成远端用户的访问地址。

镜像导出不会携带 Compose 中的端口、重启策略和临时目录设置。这些应在创建容器时配置。若面板启用只读根文件系统，应同时为 `/var/cache/nginx` 和 `/var/run` 提供可写 tmpfs，与项目 Compose 配置一致。仅导入镜像的服务器也不需要照搬包含 `build: .` 的本地 Compose 文件。

更新远端网站时：本地重新生成必要页面 → 构建镜像 → 导出并传输 → 远端导入 → 用新镜像重建容器并保留所需端口配置。只重启原容器不会切换到新镜像。

上述内容是部署方法说明，不代表已经在目标 Linux 主机或具体面板上完成验证。

参考：[Docker 镜像导出](https://docs.docker.com/reference/cli/docker/image/save/)、[镜像导入及压缩包支持](https://docs.docker.com/reference/cli/docker/image/load/)、[镜像平台与 CPU 架构](https://docs.docker.com/build/building/multi-platform/)。

## GitHub 使用边界

上传仓库前检查 `.gitignore` 是否生效，尤其是 `assets/`、PDF、`.cache/`、`.dev/` 和 `exports/`。当前配置保留根目录入口及文章 HTML，不把大资源放入普通 Git 历史。

完整站点约 4.24 GiB。当前不提供 GitHub Pages 自动部署配置；其容量和项目子路径与本项目默认部署方式不匹配。GitHub 托管源码与服务器托管完整阅读站是两个独立步骤。
