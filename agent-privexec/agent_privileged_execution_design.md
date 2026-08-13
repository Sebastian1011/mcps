# Codex / Claude Linux 特权命令执行方案设计

> 版本：v1.0  
> 日期：2026-08-12  
> 适用范围：Linux 图形桌面开发工作站；Codex CLI / IDE、Claude Code CLI / IDE

## 1. 摘要

目标是在不向 AI Coding Agent 暴露 sudo 密码、不配置 `NOPASSWD`、不允许 Agent 静默获得 root 的前提下，让 Codex 和 Claude Code 可以完成必要的系统级操作。

推荐方案不是“让 Skill 管理 sudo 密码”，而是四层组合：

1. **Agent Skill**：描述正确的特权操作工作流；
2. **Agent Permission / Rule**：强制禁止原始 `sudo` / `pkexec`，仅允许统一入口 `agent-privexec`；
3. **Polkit + pkexec**：使用 Linux 桌面环境原生 Authentication Agent 弹出 GUI 密码认证；
4. **Root-owned Privileged Helper**：执行经过策略校验的命令，并记录结构化审计日志。

核心原则：**Skill 是行为指导，不是安全边界；真正的安全边界必须由 Codex/Claude 的执行策略与 Linux OS 权限系统共同提供。**

---

## 2. 目标与非目标

### 2.1 目标

- Codex / Claude 可以执行必要的 root 操作；
- 用户在桌面 GUI 中完成管理员认证；
- 密码永远不进入 Agent 的 stdin、stdout、上下文、日志或环境变量；
- 每一次特权操作都必须显式经过 Agent approval 和 OS authentication；
- 禁止 `sudo -S`、`echo password | sudo`、`NOPASSWD` 等旁路；
- Codex 与 Claude 共用相同的 privileged execution 语义和 Linux 后端；
- 可审计：记录谁、何时、在哪个目录、请求执行了什么命令、结果如何；
- 即使模型不遵循 Skill，也无法直接绕过既定提权入口。

### 2.2 非目标

- 不给 Agent 一个长期 root shell；
- 不保存 sudo 密码；
- 不允许无人值守 root 自动化；
- 不支持 SSH / headless 环境下自动降级到文本密码输入；
- 不将 Agent 的“理解和判断”视为访问控制机制。

---

## 3. 威胁模型

假设 Agent 可能：

- 误执行危险命令；
- 因 prompt injection 运行非预期命令；
- 尝试使用 `/usr/bin/sudo`、`pkexec`、`bash -c` 等方式绕过 wrapper；
- 读取当前用户可以访问的文件、环境变量和进程信息；
- 修改用户目录中的脚本或 Skill；
- 将敏感信息输出到对话上下文。

因此不可信对象包括：

- LLM 本身；
- Skill 文本；
- 用户可写 wrapper；
- 项目仓库内的脚本；
- Agent 生成的 shell command。

可信边界应尽可能缩小到：

- root-owned executable；
- Polkit / `polkitd`；
- Desktop Authentication Agent；
- Codex / Claude Code 的本地 permission enforcement；
- root-owned policy / configuration。

---

## 4. 架构决策

### 4.1 最终选择

采用：

**Shared Skill + Agent Enforcement + `agent-privexec` + `pkexec --disable-internal-agent` + Polkit + root helper**

不将 `sudo -A` / askpass 作为主路径。

### 4.2 为什么主路径选择 Polkit

Polkit 的模型天然是：

```text
unprivileged process
        │
        ▼
      pkexec
        │
        ▼
     polkitd
        │
        ▼
Desktop Authentication Agent
        │
        ▼
   GUI Password Dialog
        │
        ▼
 privileged executable
```

密码由桌面 Authentication Agent 和系统认证栈处理，不需要经过 Agent 自己启动的 askpass helper。

使用：

```bash
pkexec --disable-internal-agent ...
```

其中 `--disable-internal-agent` 很重要：如果当前没有图形 Authentication Agent，则操作直接失败，而不是退化成终端文本认证。这使“必须通过 GUI 完成认证”成为明确约束。

### 4.3 为什么不直接让 Agent 执行任意 `pkexec <command>`

不推荐：

```bash
pkexec bash
pkexec bash -c '...'
pkexec python -c '...'
```

原因：这会把一次认证等价为一个通用 root shell，降低命令级审计价值，也增加参数注入和复杂 shell 语义带来的风险。

所有 Agent 特权请求统一进入：

```bash
agent-privexec <operation> ...
```

随后固定调用 root-owned helper。

---

## 5. 总体架构

```mermaid
flowchart TD
    U[User] --> C[Codex]
    U --> A[Claude Code]

    S[Shared Privileged Execution Skill] --> C
    S --> A

    C --> CR[Codex ExecPolicy / Approval]
    A --> AR[Claude Permission Rules + PreToolUse Hook]

    CR --> P[agent-privexec]
    AR --> P

    P --> K[pkexec --disable-internal-agent]
    K --> PD[polkitd]
    PD --> GUI[Desktop Authentication Agent]
    GUI --> U

    PD --> H[/usr/local/libexec/agent-privexec-root]
    H --> V[Policy / argv validation]
    V --> E[execve privileged program]
    H --> L[journald / audit log]
```

---

## 6. 权限模型

### Layer 1：Skill

Skill 负责告诉 Agent：

- 遇到需要 root 的操作时使用 `agent-privexec`；
- 不尝试读取密码；
- 不调用 `sudo -S`；
- 不修改 sudoers；
- 不使用 root shell；
- 被用户拒绝后立即停止该操作。

**该层只改善行为，不承担强制安全。**

### Layer 2：Codex / Claude 执行策略

强制规则：

```text
sudo                -> FORBIDDEN
/usr/bin/sudo       -> FORBIDDEN
pkexec              -> FORBIDDEN
/usr/bin/pkexec     -> FORBIDDEN
agent-privexec ...  -> PROMPT / ASK
```

这样即使模型忽略 Skill，也不能通过正常 Bash tool 静默走原始提权路径。

### Layer 3：Polkit

Polkit action 使用：

```text
allow_any      = no
allow_inactive = no
allow_active   = auth_admin
```

明确不要使用：

```text
auth_admin_keep
```

因为 `auth_admin_keep` 会在短时间保留授权，而设计目标是每次特权请求都重新认证。

### Layer 4：Root helper

`/usr/local/libexec/agent-privexec-root`：

- owner：`root:root`；
- mode：`0755` 或更严格；
- 普通用户不可修改；
- 不通过 shell 拼接执行；
- 使用 argv / `execve()` 语义；
- 对 executable 使用 absolute path / realpath；
- 对允许的 program 与参数进行 policy 校验；
- 清理环境变量；
- 写入 journald / audit log。

---

## 7. 推荐命令接口

不要设计成：

```bash
agent-privexec "任意 shell string"
```

建议提供结构化 operation：

```bash
agent-privexec exec -- /usr/bin/apt install linux-tools-common
agent-privexec systemctl restart chronyd
agent-privexec chmod 0660 /dev/something
agent-privexec chown user:group /path
agent-privexec install-file ./config /etc/example/config
```

其中 `exec` 仍需要经过 executable allowlist。

建议初始 allowlist 只包含开发工作站常见操作，例如：

```text
/usr/bin/apt
/usr/bin/apt-get
/usr/bin/dnf
/usr/bin/pacman
/usr/bin/systemctl
/usr/bin/journalctl
/usr/bin/mount
/usr/bin/umount
/usr/sbin/ip
/usr/sbin/ethtool
/usr/sbin/sysctl
/usr/bin/chown
/usr/bin/chmod
/usr/bin/install
```

按实际发行版裁剪。

默认禁止作为 privileged target：

```text
/bin/bash
/bin/sh
/usr/bin/zsh
/usr/bin/env
/usr/bin/sudo
/usr/bin/pkexec
python -c
perl -e
ruby -e
```

原因是这些入口很容易退化为通用 root code execution，破坏命令级 policy。

---

## 8. Polkit Action

建议固定绑定 root helper：

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE policyconfig PUBLIC
  "-//freedesktop//DTD polkit Policy Configuration 1.0//EN"
  "http://www.freedesktop.org/software/polkit/policyconfig-1.dtd">

<policyconfig>
  <vendor>Local Workstation</vendor>

  <action id="com.local.agent-privexec.execute">
    <description>Execute an approved privileged development operation</description>
    <message>Authentication is required to run this privileged command: $(command_line)</message>

    <defaults>
      <allow_any>no</allow_any>
      <allow_inactive>no</allow_inactive>
      <allow_active>auth_admin</allow_active>
    </defaults>

    <annotate key="org.freedesktop.policykit.exec.path">
      /usr/local/libexec/agent-privexec-root
    </annotate>
  </action>
</policyconfig>
```

`pkexec` 只对固定 root helper 使用该 action。`$(command_line)` 由 `pkexec`
展开，使桌面认证弹窗同时显示本次请求的完整 broker 命令和结构化操作参数。

---

## 9. `agent-privexec` Client

用户侧入口可以位于：

```text
/usr/local/bin/agent-privexec
```

建议本身也由 root 安装，普通用户不可修改。

核心调用：

```bash
exec /usr/bin/pkexec \
  --disable-internal-agent \
  /usr/local/libexec/agent-privexec-root \
  -- "$@"
```

实际实现中需要：

- 生成 request ID；
- 记录调用 Agent 类型；
- 保留原始 cwd 作为显式字段，而不是信任 root 进程的 cwd；
- 可选显示 command preview；
- 对超过一定长度的 command 拒绝；
- 禁止 NUL / 非法编码等异常输入。

---

## 10. Codex 接入

Codex 支持 Skills，并且 ExecPolicy Rules 可以对命令前缀设置 `allow`、`prompt`、`forbidden`；规则由执行层而不是模型执行。

推荐 `~/.codex/rules/privileged.rules`：

```python
prefix_rule(
    pattern=["sudo"],
    decision="forbidden",
    justification="Direct sudo is forbidden. Use agent-privexec instead.",
)

prefix_rule(
    pattern=["/usr/bin/sudo"],
    decision="forbidden",
    justification="Direct sudo is forbidden. Use agent-privexec instead.",
)

prefix_rule(
    pattern=["pkexec"],
    decision="forbidden",
    justification="Direct pkexec is forbidden. Use agent-privexec instead.",
)

prefix_rule(
    pattern=["/usr/bin/pkexec"],
    decision="forbidden",
    justification="Direct pkexec is forbidden. Use agent-privexec instead.",
)

prefix_rule(
    pattern=["agent-privexec"],
    decision="prompt",
    justification="Privileged operation requires explicit user approval.",
)
```

上线前使用：

```bash
codex execpolicy check --pretty \
  --rules ~/.codex/rules/privileged.rules \
  -- agent-privexec systemctl restart chronyd
```

并专门测试 compound shell command，确认不能通过 `bash -lc` 等形式绕过规则。

---

## 11. Claude Code 接入

Claude Code 的 permission rules 由客户端执行，而不是由模型执行；`deny` 优先于 `ask`，`ask` 优先于 `allow`。另外可以通过 `PreToolUse` hook 检查 Bash tool 的完整 `tool_input.command`。

推荐同时使用：

1. Permission rules：
   - `Bash(sudo *)` -> deny
   - `Bash(/usr/bin/sudo *)` -> deny
   - `Bash(pkexec *)` -> deny
   - `Bash(/usr/bin/pkexec *)` -> deny
   - `Bash(agent-privexec *)` -> ask

2. `PreToolUse` Hook：
   - 检查完整 Bash command；
   - 捕获 shell wrapper、变量拼接等 permission pattern 不容易覆盖的场景；
   - 发现直接 sudo / pkexec 时返回 `permissionDecision: deny`；
   - 告诉 Claude 改用 `agent-privexec`。

Hook 的重点不是“自动批准 wrapper”，而是**阻止旁路**。

---

## 12. Shared Skill

建议维护唯一源：

```text
~/.agent-skills/privileged-exec/
├── SKILL.md
└── references/
    └── policy.md
```

然后分别暴露给 Codex / Claude 的 Skill 搜索路径。

Skill 核心内容：

```markdown
---
name: privileged-exec
description: Safely perform Linux operations requiring administrative privileges.
---

# Privileged execution

When an operation requires root privileges:

1. Never use sudo or pkexec directly.
2. Never request or inspect the user's password.
3. Never use sudo -S, NOPASSWD, or password piping.
4. Use `agent-privexec` only.
5. Pass commands as structured argv; do not wrap them in `bash -c`.
6. Explain the privileged operation before requesting execution.
7. If authentication or approval is denied, stop the privileged operation.
8. Never attempt to weaken the privilege policy or modify sudoers/polkit policy.
```

---

## 13. 用户交互流程

标准流程：

```text
Agent determines root is required
            │
            ▼
Agent proposes exact privileged command
            │
            ▼
Codex / Claude permission prompt
            │
       User approves
            │
            ▼
agent-privexec
            │
            ▼
pkexec --disable-internal-agent
            │
            ▼
Native desktop authentication dialog
            │
      User enters password
            │
            ▼
root helper validates policy
            │
      allowed / denied
            │
            ▼
execve target program
            │
            ▼
result + audit log
```

这里有两个不同意义上的确认：

- **Agent Approval**：确认“我要执行的具体命令是什么”；
- **OS Authentication**：确认“当前操作者确实有管理员身份”。

两者不应该合并。

---

## 14. 密码与认证要求

硬性要求：

- 密码只能进入桌面 Authentication Agent / PAM（Pluggable Authentication Modules）认证路径；
- Agent 不得获得密码字符串；
- 不写入文件；
- 不进入 environment；
- 不进入 stdin pipe；
- 不进入 shell history；
- 不进入 Agent transcript；
- 不使用 `auth_admin_keep`；
- 不使用 `sudo` credential cache 作为工作流依赖。

---

## 15. 审计

每次请求建议记录：

```json
{
  "request_id": "uuid",
  "timestamp": "...",
  "uid": 1000,
  "user": "...",
  "agent": "codex|claude",
  "cwd": "/home/user/project",
  "operation": "systemctl",
  "argv": ["restart", "chronyd"],
  "decision": "allowed|denied",
  "exit_code": 0,
  "duration_ms": 123
}
```

记录到：

```text
journald
```

例如使用固定 identifier：

```text
agent-privexec
```

严禁日志记录：

- password；
- token；
- secret environment；
- stdin payload 中可能存在的 credential。

---

## 16. 失败策略

### 没有桌面 Authentication Agent

因为使用：

```bash
pkexec --disable-internal-agent
```

所以直接失败。

Agent 应提示：

```text
Privileged operation requires an active graphical Polkit authentication agent.
```

不要自动切换到：

```text
sudo
sudo -S
pkttyagent
```

### 用户取消 GUI

视为显式拒绝；不重试，不寻找绕过方式。

### Policy 不允许命令

返回明确错误，例如：

```text
agent-privexec: executable /bin/bash is not permitted by privileged policy
```

由用户决定是否扩展 root-owned policy。

---

## 17. 为什么不把 `sudoplz` 作为主方案

`sudoplz` 是当前非常接近需求的现成工具，适合快速落地：它基于 `SUDO_ASKPASS`，可以给 Claude Code、Cursor 等 Agent 提供 GUI approval，并使用加密方式保存 sudo credential。

但本设计不将其作为长期主路径，原因是：

1. 仍然围绕 sudo credential / askpass 架构；
2. 需要保存一个可恢复的 sudo credential；
3. 我们的目标是让密码只存在于 OS Authentication Agent / PAM 认证路径；
4. Polkit 更适合作为 Linux GUI 授权机制的系统级边界。

因此：

```text
Polkit + root helper   = 推荐生产方案
sudoplz                = 快速 PoC / fallback
简单 zenity askpass    = 不推荐
NOPASSWD                = 禁止
```

---

## 18. 部署顺序

建议分四阶段：

### Phase 1：OS Backend

安装：

```text
/usr/local/bin/agent-privexec
/usr/local/libexec/agent-privexec-root
/usr/share/polkit-1/actions/com.local.agent-privexec.policy
/etc/agent-privexec/policy.toml
```

确保以上安全相关文件由 root 拥有并不可被普通用户修改。

### Phase 2：Codex Enforcement

增加：

```text
~/.codex/rules/privileged.rules
```

测试：

```text
sudo -> forbidden
pkexec -> forbidden
agent-privexec -> prompt
```

### Phase 3：Claude Enforcement

增加：

```text
permission deny / ask rules
PreToolUse hook
```

重点测试 shell wrapper 绕过。

### Phase 4：Shared Skill

最后再安装 Skill。

顺序必须是：

```text
先建立安全边界
再给模型行为指导
```

而不是反过来。

---

## 19. 验收标准

上线前至少通过以下测试：

| Test | Expected |
|---|---|
| `sudo id` | Agent execution layer 拒绝 |
| `/usr/bin/sudo id` | 拒绝 |
| `pkexec id` | 拒绝 |
| `bash -lc 'sudo id'` | 拒绝 |
| `agent-privexec exec -- /usr/bin/id` | 用户 approval + GUI authentication |
| GUI 中 Cancel | 操作失败，不重试 |
| 无图形 Polkit Agent | 操作失败，不 fallback TTY |
| `agent-privexec exec -- /bin/bash` | root helper policy 拒绝 |
| 修改用户目录 Skill | 不影响 OS policy |
| 修改项目 hook | 不应影响 root helper / Polkit policy |
| 密码搜索 Agent transcript | 不存在 |
| journald | 能查到 request / argv / result |

---

## 20. 最终结论

最优方案不是给 Codex / Claude 一个“会输入 sudo 密码的 Skill”，而是建立一个专门的 **Privileged Execution Boundary**：

```text
                 Human
                   │
          ┌────────┴────────┐
          │                 │
       Codex             Claude
          │                 │
     ExecPolicy       Permission Hook
          └────────┬────────┘
                   │
             agent-privexec
                   │
                pkexec
                   │
                polkitd
                   │
          GUI Authentication
                   │
          root-owned helper
                   │
           policy validation
                   │
               execve()
```

安全边界从弱到强依次为：

```text
Skill instruction
      <
Agent permission enforcement
      <
root-owned privileged helper
      <
Polkit / OS authentication
```

因此推荐长期维护的组件只有一个真正具有系统安全意义的核心：

**`agent-privexec` privileged broker。**

Codex 和 Claude 只是它的两个不可信客户端。

---

## 参考资料

- OpenAI Codex — Agent Skills
- OpenAI Codex — Rules / ExecPolicy
- OpenAI Codex — Agent approvals & security
- Anthropic Claude Code — Skills
- Anthropic Claude Code — Permissions
- Anthropic Claude Code — Hooks / PreToolUse
- polkit Reference Manual — polkit(8)
- polkit Reference Manual — pkexec(1)
- crypdick/sudoplz — GitHub project
