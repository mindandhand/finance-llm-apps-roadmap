import { execFile } from "node:child_process";
import { randomUUID } from "node:crypto";
import {
  cp,
  mkdir,
  mkdtemp,
  readFile,
  rm,
  writeFile,
} from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import { promisify } from "node:util";

import { assertSafeWorkspaceId, resolveWorkspacePath } from "./path-safety";
import type {
  ExecOpts,
  ExecResult,
  WorkspaceInfo,
  WorkspaceProvider,
} from "./types";

const execFileAsync = promisify(execFile);
const CONTAINER_WORKSPACE = "/workspace";
const MCP_PORT = 3109;
const WORKSPACE_LABEL = "io.finance-roadmap.workspace";

type PodmanCreateOptions = {
  containerName: string;
  workspacePath: string;
  image: string;
  memory: string;
  cpus: string;
  pidsLimit: number;
  httpProxy?: string;
};

export function buildPodmanCreateArgs(options: PodmanCreateOptions): string[] {
  const args = [
    "create",
    "--name",
    options.containerName,
    `--label=${WORKSPACE_LABEL}=true`,
    "--read-only",
    "--cap-drop=all",
    "--security-opt=no-new-privileges",
    "--http-proxy=false",
    `--memory=${options.memory}`,
    `--cpus=${options.cpus}`,
    `--pids-limit=${options.pidsLimit}`,
    "--tmpfs=/tmp:rw,noexec,nosuid,size=256m",
    "--env=HOME=/tmp",
    "--env=NPM_CONFIG_CACHE=/workspace/.npm-cache",
    `--volume=${options.workspacePath}:${CONTAINER_WORKSPACE}:rw`,
    `--publish=127.0.0.1::${MCP_PORT}`,
  ];
  if (options.httpProxy) {
    args.push(`--env=http_proxy=${options.httpProxy}`);
    args.push(`--env=https_proxy=${options.httpProxy}`);
    args.push(`--env=HTTP_PROXY=${options.httpProxy}`);
    args.push(`--env=HTTPS_PROXY=${options.httpProxy}`);
  }
  args.push(options.image);
  return args;
}

export function parsePublishedPort(output: string): number {
  const value = output.trim();
  const match = value.match(/^(?:127\.0\.0\.1|\[::1\]):(\d+)$/);
  if (!match) {
    throw new Error(`Podman 没有返回仅绑定本机的有效端口：${value}`);
  }
  const port = Number(match[1]);
  if (!Number.isInteger(port) || port < 1 || port > 65535) {
    throw new Error(`Podman 返回了无效端口：${value}`);
  }
  return port;
}

type CommandResult = { stdout: string; stderr: string };

async function runCommand(
  executable: string,
  args: string[],
  options: { timeoutMs?: number; cwd?: string } = {},
): Promise<CommandResult> {
  try {
    const result = await execFileAsync(executable, args, {
      cwd: options.cwd,
      timeout: options.timeoutMs ?? 60_000,
      maxBuffer: 10 * 1024 * 1024,
      encoding: "utf8",
    });
    return { stdout: result.stdout, stderr: result.stderr };
  } catch (error) {
    const detail = error as Error & {
      stdout?: string;
      stderr?: string;
      code?: string | number;
    };
    const message = detail.stderr?.trim() || detail.stdout?.trim() || detail.message;
    throw new Error(`${executable} 执行失败：${message}`, { cause: error });
  }
}

function resolveTemplatePath(): string {
  if (process.env.PODMAN_TEMPLATE_DIR) {
    return path.resolve(process.env.PODMAN_TEMPLATE_DIR);
  }
  const cwd = process.cwd();
  return cwd.endsWith(`${path.sep}apps${path.sep}web`)
    ? path.resolve(cwd, "../mcp-use-server")
    : path.resolve(cwd, "apps/mcp-use-server");
}

function resolveContainerCwd(cwd: string | undefined): string {
  if (!cwd) return CONTAINER_WORKSPACE;
  const candidate = cwd.startsWith("/")
    ? path.posix.normalize(cwd)
    : path.posix.resolve(CONTAINER_WORKSPACE, cwd);
  if (
    candidate !== CONTAINER_WORKSPACE &&
    !candidate.startsWith(`${CONTAINER_WORKSPACE}/`)
  ) {
    throw new Error("命令工作目录必须位于 /workspace 内");
  }
  return candidate;
}

export class PodmanWorkspaceProvider implements WorkspaceProvider {
  private readonly podman = process.env.PODMAN_BIN?.trim() || "podman";
  private readonly image =
    process.env.PODMAN_SANDBOX_IMAGE?.trim() ||
    "mcp-app-builder-sandbox:local";
  private readonly baseDir = path.resolve(
    process.env.PODMAN_WORKSPACE_ROOT?.trim() ||
      path.join(tmpdir(), "mcp-app-builder-workspaces"),
  );

  async provision(_name: string): Promise<WorkspaceInfo> {
    await runCommand(this.podman, ["info", "--format", "{{.Host.Security.Rootless}}"]);

    const workspaceId = `podman-${randomUUID()}`;
    const workspacePath = await this.createWorkspaceDirectory(workspaceId);
    const containerName = this.containerName(workspaceId);

    try {
      await runCommand(
        this.podman,
        buildPodmanCreateArgs({
          containerName,
          workspacePath,
          image: this.image,
          memory: process.env.PODMAN_MEMORY?.trim() || "1g",
          cpus: process.env.PODMAN_CPUS?.trim() || "1",
          pidsLimit: Number(process.env.PODMAN_PIDS_LIMIT || 256),
          httpProxy: process.env.PODMAN_HTTP_PROXY?.trim() || undefined,
        }),
        { timeoutMs: 60_000 },
      );
      await runCommand(this.podman, ["start", containerName]);
      // 依赖在镜像构建时已经安装。复制镜像内的独立依赖目录，避免每个工作区
      // 再次联网解析数千个包，也不会把共享可写缓存暴露给不同工作区。
      await this.runExec(
        workspaceId,
        "cp -a /opt/mcp-template/node_modules /workspace/node_modules",
        { timeoutMs: 5 * 60_000 },
      );
      await this.runExec(
        workspaceId,
        "npm run dev > /tmp/mcp-server.log 2>&1",
        { background: true },
      );
      const endpoint = await this.waitForEndpoint(workspaceId);
      return {
        workspaceId,
        endpoint,
        status: "running",
        path: CONTAINER_WORKSPACE,
      };
    } catch (error) {
      await runCommand(this.podman, ["rm", "--force", containerName]).catch(
        () => undefined,
      );
      await rm(workspacePath, { recursive: true, force: true });
      throw error;
    }
  }

  async getInfo(workspaceId: string): Promise<WorkspaceInfo> {
    await this.assertOwnedWorkspace(workspaceId);
    const containerName = this.containerName(workspaceId);
    const { stdout } = await runCommand(this.podman, [
      "inspect",
      "--format",
      "{{.State.Running}}",
      containerName,
    ]);
    const running = stdout.trim() === "true";
    return {
      workspaceId,
      endpoint: running ? await this.getEndpoint(workspaceId) : "",
      status: running ? "running" : "stopped",
      path: CONTAINER_WORKSPACE,
    };
  }

  async stop(workspaceId: string): Promise<void> {
    await this.assertOwnedWorkspace(workspaceId);
    await runCommand(this.podman, [
      "rm",
      "--force",
      this.containerName(workspaceId),
    ]);
    await rm(this.workspacePath(workspaceId), { recursive: true, force: true });
  }

  async readFile(workspaceId: string, relativePath: string): Promise<string> {
    await this.assertOwnedWorkspace(workspaceId);
    const target = await resolveWorkspacePath(
      this.workspacePath(workspaceId),
      relativePath,
      { forWrite: false },
    );
    return readFile(target, "utf8");
  }

  async writeFile(
    workspaceId: string,
    relativePath: string,
    content: string,
  ): Promise<void> {
    await this.assertOwnedWorkspace(workspaceId);
    const target = await resolveWorkspacePath(
      this.workspacePath(workspaceId),
      relativePath,
      { forWrite: true },
    );
    await mkdir(path.dirname(target), { recursive: true });
    await writeFile(target, content, "utf8");
  }

  async editFile(
    workspaceId: string,
    relativePath: string,
    search: string,
    replace: string,
  ): Promise<void> {
    const content = await this.readFile(workspaceId, relativePath);
    if (!content.includes(search)) {
      throw new Error(`文件“${relativePath}”中没有找到待替换内容`);
    }
    await this.writeFile(workspaceId, relativePath, content.replace(search, replace));
  }

  async exec(
    workspaceId: string,
    cmd: string,
    options?: ExecOpts,
  ): Promise<ExecResult> {
    await this.assertOwnedWorkspace(workspaceId);
    if (!cmd.trim()) throw new Error("执行命令不能为空");
    return this.runExec(workspaceId, cmd, options);
  }

  async prepareDownload(workspaceId: string): Promise<{ downloadUrl: string }> {
    await this.assertOwnedWorkspace(workspaceId);
    const staging = await mkdtemp(path.join(tmpdir(), "mcp-app-download-"));
    const archivePath = path.join(staging, "workspace.tar.gz");
    const downloadRoot = path.join(staging, "workspace");
    try {
      await cp(this.workspacePath(workspaceId), downloadRoot, {
        recursive: true,
        filter: (source) =>
          !["node_modules", "dist", ".git", ".env", ".agent", ".npm-cache"].includes(
            path.basename(source),
          ),
      });
      await runCommand("tar", ["-czf", archivePath, "-C", staging, "workspace"], {
        timeoutMs: 5 * 60_000,
      });
      const archive = await readFile(archivePath);
      return {
        downloadUrl: `data:application/gzip;base64,${archive.toString("base64")}`,
      };
    } finally {
      await rm(staging, { recursive: true, force: true });
    }
  }

  private async createWorkspaceDirectory(workspaceId: string): Promise<string> {
    await mkdir(this.baseDir, { recursive: true, mode: 0o700 });
    const target = this.workspacePath(workspaceId);
    await mkdir(target, { mode: 0o700 });
    await cp(resolveTemplatePath(), target, {
      recursive: true,
      filter: (source) =>
        !["node_modules", "dist", ".git", ".agent"].includes(
          path.basename(source),
        ),
    });
    return target;
  }

  private async assertOwnedWorkspace(workspaceId: string): Promise<void> {
    assertSafeWorkspaceId(workspaceId);
    const { stdout } = await runCommand(this.podman, [
      "inspect",
      "--format",
      `{{ index .Config.Labels "${WORKSPACE_LABEL}" }}`,
      this.containerName(workspaceId),
    ]);
    if (stdout.trim() !== "true") {
      throw new Error("该容器不是由本地工作区 Provider 创建的");
    }
  }

  private async runExec(
    workspaceId: string,
    cmd: string,
    options?: ExecOpts,
  ): Promise<ExecResult> {
    const args = ["exec"];
    if (options?.background) args.push("--detach");
    args.push("--workdir", resolveContainerCwd(options?.cwd));
    args.push(this.containerName(workspaceId), "/bin/sh", "-lc", cmd);
    const result = await runCommand(this.podman, args, {
      timeoutMs: options?.timeoutMs,
    });
    return {
      stdout: result.stdout,
      stderr: result.stderr,
      exitCode: 0,
      ...(options?.background ? { background: true } : {}),
    };
  }

  private async getEndpoint(workspaceId: string): Promise<string> {
    const { stdout } = await runCommand(this.podman, [
      "port",
      this.containerName(workspaceId),
      `${MCP_PORT}/tcp`,
    ]);
    return `http://127.0.0.1:${parsePublishedPort(stdout)}/mcp`;
  }

  private async waitForEndpoint(workspaceId: string): Promise<string> {
    const endpoint = await this.getEndpoint(workspaceId);
    const deadline = Date.now() + 90_000;
    while (Date.now() < deadline) {
      try {
        // macOS 的端口转发由 Podman Machine 管理，构建进程所在的受限环境未必
        // 能回连宿主随机端口。mcp-use 在 listen 回调后输出该固定日志，因此用
        // 容器内就绪标志检查；getEndpoint() 仍验证端口只绑定在本机地址。
        await this.runExec(
          workspaceId,
          `grep -Fq '[SERVER] Listening on http://localhost:${MCP_PORT}' /tmp/mcp-server.log`,
          { timeoutMs: 3_000 },
        );
        return endpoint;
      } catch {
        await new Promise((resolve) => setTimeout(resolve, 1_000));
      }
    }
    const log = await this.runExec(
      workspaceId,
      "tail -n 80 /tmp/mcp-server.log 2>/dev/null || true",
    ).catch(() => ({ stdout: "", stderr: "", exitCode: 0 }));
    throw new Error(
      `本地 MCP Server 未在 90 秒内就绪：${endpoint}` +
        (log.stdout.trim() ? `\n${log.stdout.trim()}` : ""),
    );
  }

  private workspacePath(workspaceId: string): string {
    return path.join(this.baseDir, assertSafeWorkspaceId(workspaceId));
  }

  private containerName(workspaceId: string): string {
    return `mcp-app-${assertSafeWorkspaceId(workspaceId)}`;
  }
}
