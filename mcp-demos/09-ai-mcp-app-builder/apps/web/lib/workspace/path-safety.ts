import { lstat, realpath } from "node:fs/promises";
import path from "node:path";

const WORKSPACE_ID_PATTERN = /^podman-[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;

export function assertSafeWorkspaceId(workspaceId: string): string {
  if (!WORKSPACE_ID_PATTERN.test(workspaceId)) {
    throw new Error("无效的 Podman 工作区 ID");
  }
  return workspaceId;
}

function isWithinRoot(root: string, candidate: string): boolean {
  return candidate === root || candidate.startsWith(`${root}${path.sep}`);
}

/**
 * 将 API 相对路径安全地解析到工作区内，并拒绝绝对路径、`..` 和符号链接。
 * 禁止符号链接会牺牲一部分灵活性，但可以避免宿主机文件通过挂载目录泄露。
 */
export async function resolveWorkspacePath(
  workspaceRoot: string,
  relativePath: string,
  options: { forWrite: boolean },
): Promise<string> {
  if (!relativePath || path.isAbsolute(relativePath)) {
    throw new Error("工作区文件必须使用非空相对路径");
  }

  const root = await realpath(workspaceRoot);
  const candidate = path.resolve(root, relativePath);
  if (!isWithinRoot(root, candidate)) {
    throw new Error("工作区路径越界");
  }

  const relative = path.relative(root, candidate);
  const segments = relative ? relative.split(path.sep) : [];
  let current = root;
  for (let index = 0; index < segments.length; index += 1) {
    current = path.join(current, segments[index]);
    try {
      const stat = await lstat(current);
      if (stat.isSymbolicLink()) {
        throw new Error("工作区路径不能经过符号链接");
      }
    } catch (error) {
      if (
        error instanceof Error &&
        "code" in error &&
        error.code === "ENOENT" &&
        options.forWrite
      ) {
        break;
      }
      throw error;
    }
  }

  return candidate;
}
