# 本地沙箱设计与学习指南

本文说明如何在保留 E2B 功能的前提下，为 09 使用本地沙箱。当前代码已实现 Podman Provider；未显式配置 Provider 且没有 `E2B_API_KEY` 时默认使用 Podman。

## 1. 为什么需要本地沙箱

本地沙箱主要解决以下问题：

- 没有 `E2B_API_KEY` 时仍能学习完整构建流程；
- 开发期间减少云端调用和等待；
- 在内网中运行 MCP Server；
- 理解沙箱生命周期、文件系统、命令执行与端口暴露的实现细节。

本地沙箱不能自动获得与托管沙箱相同的安全性。普通容器与宿主机共享内核，适合学习、开发和受信任代码；面向恶意客户代码还需要更强的运行时隔离。

## 2. 推荐方案

当前项目优先选择 rootless Podman：

```text
Next.js / Mastra
  ↓ WorkspaceProvider
PodmanWorkspaceProvider
  ├─ 创建独立工作目录
  ├─ 创建 rootless 容器
  ├─ 挂载 /workspace
  ├─ 执行文件和命令操作
  ├─ 映射 MCP 端口
  └─ 停止并清理资源
```

macOS 上 Podman 容器运行在 Podman Machine 的 Linux 虚拟机中，并非直接运行在 macOS 内核。端口映射后，Next.js 仍通过 `127.0.0.1` 访问 MCP Server。

## 3. Provider 抽象

不要用大量 `if (WORKSPACE_PROVIDER === ...)` 分散在 API Route 中。统一通过工厂创建 Provider：

```ts
interface WorkspaceProvider {
  provision(name: string): Promise<WorkspaceInfo>;
  getInfo(workspaceId: string): Promise<WorkspaceInfo>;
  stop(workspaceId: string): Promise<void>;
  readFile(workspaceId: string, path: string): Promise<string>;
  writeFile(
    workspaceId: string,
    path: string,
    content: string,
  ): Promise<void>;
  editFile(
    workspaceId: string,
    path: string,
    search: string,
    replace: string,
  ): Promise<void>;
  exec(
    workspaceId: string,
    command: string,
    options?: ExecOpts,
  ): Promise<ExecResult>;
  prepareDownload(workspaceId: string): Promise<{ downloadUrl: string }>;
}
```

工厂只负责选择实现：

```ts
export function createWorkspaceProvider(): WorkspaceProvider {
  switch (process.env.WORKSPACE_PROVIDER) {
    case "podman":
      return new PodmanWorkspaceProvider();
    case "e2b":
    case undefined:
      return new E2BWorkspaceProvider();
    default:
      throw new Error("不支持的 WORKSPACE_PROVIDER");
  }
}
```

这样可以保证创建、读取、执行和停止操作始终落在同一个 Provider。

## 4. 本地工作区生命周期

### 创建

```text
生成 workspaceId
  ↓
创建独立临时目录
  ↓
复制 mcp-use-server 模板
  ↓
创建受限容器并挂载目录
  ↓
启动 MCP Server
  ↓
等待健康检查
  ↓
取得随机映射端口
  ↓
返回 http://127.0.0.1:<port>/mcp
```

只有健康检查通过后才能返回 Endpoint。固定等待若干秒容易在慢机器上失败，也会在快机器上浪费时间。

### 使用

工作区操作需要先通过 `workspaceId` 找到容器和工作目录。建议维护服务端注册表：

```ts
type LocalWorkspaceRecord = {
  workspaceId: string;
  containerId: string;
  hostPath: string;
  endpoint: string;
  createdAt: number;
};
```

不要接受客户直接传入容器 ID 或宿主机路径。

### 停止

停止顺序：

1. 标记工作区正在关闭，拒绝新命令；
2. 停止并删除容器；
3. 删除临时工作目录；
4. 从注册表移除记录；
5. 记录退出原因和资源使用情况。

还要通过后台回收任务清理超时或服务崩溃后遗留的工作区。

## 5. 容器镜像

建议为本地 Provider 建立固定镜像，而不是每次临时安装所有依赖：

```dockerfile
FROM node:22-bookworm-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       python3 python3-pip git curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace
```

学习阶段可在启动后安装 Node 依赖。稳定后应将通用依赖构建进镜像，以减少冷启动时间和供应链变化。

镜像中不要写入模型、GitHub、数据库或客户系统的密钥。

## 6. 容器限制

用于学习的启动参数至少应包含：

```bash
podman run --detach \
  --read-only \
  --cap-drop=all \
  --security-opt=no-new-privileges \
  --memory=1g \
  --cpus=1 \
  --pids-limit=256 \
  --tmpfs=/tmp:rw,size=128m \
  --volume <workspace>:/workspace:rw \
  --publish 127.0.0.1::3109 \
  <image>
```

参数含义：

| 参数 | 目的 |
|---|---|
| `--read-only` | 阻止修改容器根文件系统 |
| `--cap-drop=all` | 删除默认 Linux capabilities |
| `no-new-privileges` | 阻止进程通过 setuid 等方式提升权限 |
| `--memory`、`--cpus` | 限制资源消耗 |
| `--pids-limit` | 限制 fork bomb |
| `--tmpfs` | 提供大小受限的临时写入空间 |
| `127.0.0.1::3109` | 只向本机随机端口暴露 MCP Server |

如果容器需要下载安装依赖，就不能简单使用 `--network=none`。应根据场景选择：

- 构建阶段允许受控联网，运行阶段关闭外网；
- 使用内部包代理和域名白名单；
- 预构建全部依赖，运行阶段完全断网。

## 7. 文件路径安全

字符串拼接不能阻止路径穿越。必须解析并检查最终路径：

```ts
function resolveWorkspacePath(root: string, relativePath: string): string {
  const resolvedRoot = path.resolve(root);
  const resolvedPath = path.resolve(resolvedRoot, relativePath);

  if (
    resolvedPath !== resolvedRoot &&
    !resolvedPath.startsWith(`${resolvedRoot}${path.sep}`)
  ) {
    throw new Error("工作区路径越界");
  }

  return resolvedPath;
}
```

还需考虑符号链接：某个工作区内文件可能链接到挂载范围外。面向不可信用户时，不能仅依赖字符串前缀检查。

当前 E2B Provider 的 `_fullPath()` 只移除了前导斜杠，还没有拒绝 `..`。本地 Provider 实施时应同时补充公共路径校验及测试。

## 8. 命令执行边界

09 的 Agent 编程场景需要通用 `exec`，但不应把它直接作为客户 API：

```text
可信开发 Agent → 内部通用 exec
客户提交 Python → 受控 run_python
```

`run_python` 应明确限制：

- 固定解释器和启动参数；
- 执行超时；
- stdout/stderr 最大字节数；
- 输入文件数量与总大小；
- 输出文件白名单；
- 环境变量白名单；
- 网络策略；
- 同时运行任务数量。

即使 Shell 命令只由 Agent 生成，也应将模型视为不可信输入，因为用户可能通过提示注入诱导 Agent 执行危险命令。

## 9. Endpoint 与网络

E2B 返回公网 HTTPS Endpoint，本地 Provider 返回本机地址：

```text
E2B:   https://<sandbox>.e2b.app/mcp
本地:  http://127.0.0.1:<random-port>/mcp
```

当前 Next.js 后端和浏览器通常位于同一台开发机器，因此本机 Endpoint 可以工作。如果 Next.js 部署在容器、虚拟机或远程服务器中，`127.0.0.1` 指向的对象会改变，需要改用共享容器网络、反向代理或可达的宿主机地址。

不要直接监听 `0.0.0.0` 并把未经鉴权的本地 MCP Server 暴露到局域网或公网。

## 10. 下载设计

本地工作区下载不应暴露任意宿主机文件。服务端只能根据已登记的 `workspaceId` 打包对应工作目录。

打包前建议排除：

```text
node_modules
dist
.git
.env
密钥文件
缓存和日志
```

压缩包文件名应使用安全的服务端标识，不应直接拼接用户输入。下载完成后是否销毁工作区，需要由产品策略明确决定。

## 11. 测试清单

### 正常能力

- 创建工作区并取得 Endpoint；
- 读、写、编辑嵌套文件；
- 前台和后台执行命令；
- MCP Server 启动后能完成 `tools/list`；
- 下载包包含源码且不包含依赖和密钥；
- 停止后容器、目录和注册表记录均被清理。

### 异常情况

- Podman 未安装或 Machine 未启动；
- 镜像不存在；
- 宿主机端口不可用；
- MCP Server 启动失败；
- 命令超时或容器被 OOM Kill；
- 服务重启后注册表与实际容器不一致；
- 同一个工作区被并发停止和执行命令。

### 安全情况

- `../` 和绝对路径；
- 符号链接逃逸；
- 无限循环；
- 无限输出；
- 内存耗尽；
- fork bomb；
- 读取宿主机目录；
- 访问 Podman Socket；
- 访问宿主机服务和云元数据地址；
- 任务完成后继续访问旧 Endpoint。

## 12. 分阶段实施

建议按以下顺序实现，每一步都保持 E2B 可用：

1. 提取 Provider 工厂，但仍只返回 E2B；
2. 为公共路径校验和 Provider 选择编写测试；
3. 实现 Podman 创建、查询和停止；
4. 实现文件读写与命令执行；
5. 实现端口发现和 MCP 健康检查；
6. 实现下载与超时回收；
7. 增加本地模式 UI 状态和错误提示；
8. 完成资源限制及安全测试；
9. 最后再考虑客户级 `run_python` API。

第一阶段不要同时引入 Kubernetes、队列、数据库和多租户计费。先让单机 Provider 在完整回归测试下稳定运行，再逐步增强。

## 13. 模式选择建议

| 使用场景 | 建议模式 |
|---|---|
| 本地学习 09 | rootless Podman |
| 团队内部可信 Agent | Podman 或独立开发虚拟机 |
| 快速使用托管环境 | E2B、Daytona 或 Modal |
| 面向客户的不可信 Python | 托管强隔离沙箱，或 Kubernetes + gVisor/Kata |
| 高安全多租户平台 | microVM/Kata，并配合完整控制平面 |

本地 Podman 是学习 Provider 抽象和沙箱生命周期的合适起点，但不是所有威胁模型的最终答案。
