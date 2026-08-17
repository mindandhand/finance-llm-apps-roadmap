import { E2BWorkspaceProvider } from "./e2b";
import { PodmanWorkspaceProvider } from "./podman";
import { selectWorkspaceProvider } from "./provider-selection";
import type { WorkspaceProvider } from "./types";

let _provider: WorkspaceProvider | null = null;

/** Returns a singleton WorkspaceProvider for the current process. */
export function getProvider(): WorkspaceProvider {
  if (!_provider) {
    const providerName = selectWorkspaceProvider(
      process.env.WORKSPACE_PROVIDER,
      process.env.E2B_API_KEY,
    );
    _provider =
      providerName === "podman"
        ? new PodmanWorkspaceProvider()
        : new E2BWorkspaceProvider();
  }
  return _provider;
}

export type {
  WorkspaceProvider,
  WorkspaceInfo,
  ExecOpts,
  ExecResult,
} from "./types";
