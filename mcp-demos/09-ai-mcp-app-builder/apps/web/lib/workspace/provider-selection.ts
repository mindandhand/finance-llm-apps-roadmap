export type WorkspaceProviderName = "e2b" | "podman";

/**
 * 解析工作区后端。显式选择 Podman 时完全不依赖 E2B 凭证；未显式配置时，
 * 只为已有 E2B 用户保留兼容回退，避免悄悄选择错误的执行环境。
 */
export function selectWorkspaceProvider(
  configuredProvider: string | undefined,
  e2bApiKey: string | undefined,
): WorkspaceProviderName {
  const normalized = configuredProvider?.trim().toLowerCase();

  if (normalized === "podman") return "podman";
  if (normalized === "e2b") {
    if (!e2bApiKey?.trim()) {
      throw new Error("WORKSPACE_PROVIDER=e2b 时必须配置 E2B_API_KEY");
    }
    return "e2b";
  }
  if (normalized) {
    throw new Error(
      `不支持的 WORKSPACE_PROVIDER=${configuredProvider}，只能使用 e2b 或 podman`,
    );
  }
  if (e2bApiKey?.trim()) return "e2b";
  return "podman";
}
