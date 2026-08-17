import { Sandbox } from "e2b";
import type {
  WorkspaceProvider,
  WorkspaceInfo,
  ExecOpts,
  ExecResult,
} from "./types";

const WORKSPACE_PATH = "/home/user/workspace";
// 未配置模板时从仓库冷启动；可通过 E2B_REPO_URL 替换默认模板仓库。
const REPO_URL =
  process.env.E2B_REPO_URL ?? "https://github.com/CopilotKit/CopilotKit";
const TEMPLATE_ID = process.env.E2B_TEMPLATE;
// 沙箱默认保留 60 分钟，既给 Agent 留出构建时间，也避免忘记关闭造成持续计费。
const SANDBOX_TIMEOUT_MS = 60 * 60 * 1000;

export class E2BWorkspaceProvider implements WorkspaceProvider {
  async provision(_name: string): Promise<WorkspaceInfo> {
    if (!TEMPLATE_ID && !REPO_URL) {
      throw new Error(
        "Set E2B_TEMPLATE (recommended) or E2B_REPO_URL in your .env.local.",
      );
    }

    // 优先使用已安装依赖并完成预构建的 E2B Template，以缩短首次等待时间。
    // 没有 Template 时仍保留完整冷启动路径，保证功能不会依赖私有模板。
    const sandbox = TEMPLATE_ID
      ? await Sandbox.create(TEMPLATE_ID, { timeoutMs: SANDBOX_TIMEOUT_MS })
      : await Sandbox.create({ timeoutMs: SANDBOX_TIMEOUT_MS });

    if (TEMPLATE_ID) {
      // Template 已包含 node_modules 和 dist，并由 setStartCmd 在 3109 端口启动
      // Server，因此这里只需在后面取得公开 Endpoint。
    } else {
      // 无 Template 时执行完整冷启动：克隆、安装、启动，通常需要 60–90 秒。
      const clone = await sandbox.commands.run(
        `git clone --depth 1 ${REPO_URL} ${WORKSPACE_PATH}`,
        { timeoutMs: 2 * 60_000 },
      );
      if (clone.exitCode !== 0) {
        await sandbox.kill();
        throw new Error(
          `git clone failed (exit ${clone.exitCode}): ${clone.stderr}`,
        );
      }

      const install = await sandbox.commands.run(
        `cd ${WORKSPACE_PATH} && npm install --no-audit --no-fund --prefer-offline`,
        { timeoutMs: 15 * 60_000 },
      );
      if (install.exitCode !== 0) {
        await sandbox.kill();
        throw new Error(
          `npm install failed (exit ${install.exitCode}): ${install.stderr}`,
        );
      }

      // 后台启动开发 Server。等待完成后再返回 Endpoint，避免 UI 立即连接到
      // 尚未监听端口的 Server。
      await sandbox.commands.run(`cd ${WORKSPACE_PATH} && npm run dev`, {
        background: true,
      });
      await new Promise((r) => setTimeout(r, 10_000));
    }

    const endpoint = await this._getMcpEndpoint(sandbox);

    return {
      workspaceId: sandbox.sandboxId,
      endpoint,
      status: "running",
      path: WORKSPACE_PATH,
    };
  }

  async getInfo(workspaceId: string): Promise<WorkspaceInfo> {
    const sandbox = await Sandbox.connect(workspaceId);
    const endpoint = await this._getMcpEndpoint(sandbox);
    return { workspaceId, endpoint, status: "running", path: WORKSPACE_PATH };
  }

  async stop(workspaceId: string): Promise<void> {
    const sandbox = await Sandbox.connect(workspaceId);
    await sandbox.kill();
  }

  async readFile(workspaceId: string, path: string): Promise<string> {
    const sandbox = await Sandbox.connect(workspaceId);
    return sandbox.files.read(this._fullPath(path));
  }

  async writeFile(
    workspaceId: string,
    path: string,
    content: string,
  ): Promise<void> {
    const sandbox = await Sandbox.connect(workspaceId);
    const full = this._fullPath(path);
    // Agent 可以创建嵌套文件，因此写入前先确保父目录存在。
    const dir = full.substring(0, full.lastIndexOf("/"));
    await sandbox.commands.run(`mkdir -p "${dir}"`);
    await sandbox.files.write(full, content);
  }

  async editFile(
    workspaceId: string,
    path: string,
    search: string,
    replace: string,
  ): Promise<void> {
    const sandbox = await Sandbox.connect(workspaceId);
    const full = this._fullPath(path);
    const content = await sandbox.files.read(full);
    if (!content.includes(search)) {
      throw new Error(
        `Search string not found in "${path}". Make sure the search string matches exactly.`,
      );
    }
    await sandbox.files.write(full, content.replace(search, replace));
  }

  async exec(
    workspaceId: string,
    cmd: string,
    opts?: ExecOpts,
  ): Promise<ExecResult> {
    const sandbox = await Sandbox.connect(workspaceId);

    if (opts?.background) {
      await sandbox.commands.run(cmd, {
        cwd: opts.cwd ?? WORKSPACE_PATH,
        background: true,
      });
      return { stdout: "", stderr: "", exitCode: 0, background: true };
    }

    const result = await sandbox.commands.run(cmd, {
      cwd: opts?.cwd ?? WORKSPACE_PATH,
      timeoutMs: opts?.timeoutMs ?? 60_000,
    });

    return {
      stdout: result.stdout ?? "",
      stderr: result.stderr ?? "",
      exitCode: result.exitCode ?? 0,
    };
  }

  async prepareDownload(workspaceId: string): Promise<{ downloadUrl: string }> {
    const sandbox = await Sandbox.connect(workspaceId);
    // 下载包只保留可复现的源码；node_modules、dist 和沙箱 Agent 元数据体积大且
    // 可由安装/构建命令恢复。E2B 镜像通常没有 GNU zip，因此统一使用 tar。
    const clean = await sandbox.commands.run(
      `cd ${WORKSPACE_PATH} && rm -rf node_modules dist .agent`,
      { timeoutMs: 120_000 },
    );
    if (clean.exitCode !== 0) {
      throw new Error(
        `Failed to prepare workspace for download: ${clean.stderr || clean.stdout || "unknown error"}`,
      );
    }
    const archive = await sandbox.commands.run(
      `cd /home/user && rm -f workspace.tar.gz workspace.zip && tar -czf workspace.tar.gz workspace`,
      { timeoutMs: 5 * 60_000 },
    );
    if (archive.exitCode !== 0) {
      throw new Error(
        `Archive failed (exit ${archive.exitCode}): ${archive.stderr || archive.stdout || "is tar available?"}`,
      );
    }
    const url = await sandbox.downloadUrl("/home/user/workspace.tar.gz");
    return { downloadUrl: url };
  }

  // ── helpers ────────────────────────────────────────────────────────────────

  private async _getMcpEndpoint(sandbox: Sandbox): Promise<string> {
    // 优先使用 E2B 管理的 MCP URL，不需要自行映射端口。betaGetMcpUrl 尚未进入
    // SDK 的公开类型定义，所以这里局部放宽类型并保留 getHost 回退路径。
    try {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const url = (sandbox as any).betaGetMcpUrl?.();
      if (url) return url as string;
    } catch {
      // 当前 SDK 不支持 betaGetMcpUrl 时继续使用下方兼容路径。
    }
    // mcp-use 模板默认监听 3109，回退时把该端口映射为公开 HTTPS Endpoint。
    return `https://${sandbox.getHost(3109)}/mcp`;
  }

  private _fullPath(relativePath: string): string {
    // API 约定接收相对路径，这里只统一前导斜杠后再拼接工作区根目录。
    // 注意：这不是安全校验；若接口将来向不可信调用方开放，还需拒绝 `..`。
    const clean = relativePath.replace(/^\//, "");
    return `${WORKSPACE_PATH}/${clean}`;
  }
}
