# mcps

自用的 MCP servers 与 Claude Code / Codex skills 集合。

## 获取仓库

```bash
git clone https://github.com/Sebastian1011/mcps.git
cd mcps
```

下文命令均在仓库根目录执行。Skill 通过软链接安装，因此移动或删除仓库后链接会失效；安装完成后请重启 Claude Code / Codex 会话。

## Skills

### [`privileged-exec`](agent-privexec/)

通过 Polkit 为 AI coding agent 提供受策略约束、需用户确认的 Linux 提权执行能力。需要 Linux 桌面环境、Polkit、`pkexec` 和 Python 3.11+。

先安装系统边界，再以普通用户安装 agent 规则与 skill：

```bash
cd agent-privexec
sudo ./install.sh
./install-agents.sh
```

只安装指定的 agent 配置或 skill 时，可使用 `./install-agents.sh --codex`、`--claude` 或 `--skill`。完整说明与卸载方法见 [`agent-privexec/README.md`](agent-privexec/README.md)。

### [`minio`](minio/)

使用 `mc` CLI 操作 MinIO 及 S3 兼容对象存储。使用前需先[安装 MinIO Client](https://min.io/docs/minio/linux/reference/minio-mc.html)。

```bash
cd minio
./install.sh              # 同时安装到 Claude Code 和 Codex
./install.sh --claude     # 仅 Claude Code
./install.sh --codex      # 仅 Codex
```

卸载运行 `./uninstall.sh`。更多信息见 [`minio/README.md`](minio/README.md)。

### [`delegate-worker`](ai-worker/skills/delegate-worker/)

将低风险、高上下文量的仓库检索、内容压缩和视觉任务委托给本地 `ai-worker` CLI。仓库仅包含 skill，不包含 `ai-worker` CLI 的安装程序；安装前请确认 `ai-worker` 已在 `PATH` 中。

```bash
mkdir -p ~/.claude/skills ~/.codex/skills
ln -sfnT "$PWD/ai-worker/skills/delegate-worker" ~/.claude/skills/delegate-worker
ln -sfnT "$PWD/ai-worker/skills/delegate-worker" ~/.codex/skills/delegate-worker
```

如只使用其中一个 agent，只需执行对应的软链接命令。

### [`markdown-preview`](markdown-preview/)

在本地浏览器实时预览 Markdown，支持 Mermaid、KaTeX、代码高亮、表格和本地图片。需要 Python 3，无需安装额外 Python 包；增强渲染资源从 `cdn.jsdelivr.net` 加载。

```bash
mkdir -p ~/.claude/skills ~/.codex/skills
ln -sfnT "$PWD/markdown-preview" ~/.claude/skills/markdown-preview
ln -sfnT "$PWD/markdown-preview" ~/.codex/skills/markdown-preview
```

如只使用其中一个 agent，只需执行对应的软链接命令。

## MCP servers

### [`akshare`](akshare/)

基于 [akshare](https://akshare.akfamily.xyz/index.html) 的金融行情 MCP，提供 16 类市场的标的检索、实时行情和多周期历史 K 线。推荐使用 Docker Compose 安装：

```bash
cd akshare
cp .env.example .env
docker compose up -d --build
curl -fsS http://localhost:8890/healthz
```

服务启动后，按使用的客户端注册 MCP：

```bash
# Claude Code
claude mcp add --transport http akshare http://localhost:8890/mcp

# Codex
codex mcp add akshare --url http://localhost:8890/mcp
```

查看日志使用 `docker compose logs -f akshare-mcp`，停止服务使用 `docker compose down`。开发环境、本地 `uv` 运行方式及配置项见 [`akshare/README.md`](akshare/README.md)。
