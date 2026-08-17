import assert from "node:assert/strict";
import test from "node:test";

import { PodmanWorkspaceProvider } from "./podman";

test(
  "Podman Provider 完成创建、文件、命令、端口和销毁生命周期",
  { skip: process.env.RUN_PODMAN_INTEGRATION !== "1", timeout: 20 * 60_000 },
  async (context) => {
    const provider = new PodmanWorkspaceProvider();
    const workspace = await provider.provision("integration-test");
    context.after(async () => {
      await provider.stop(workspace.workspaceId).catch(() => undefined);
    });

    assert.equal(workspace.status, "running");
    assert.match(workspace.workspaceId, /^podman-/);
    assert.match(workspace.endpoint, /^http:\/\/127\.0\.0\.1:\d+\/mcp$/);

    await provider.writeFile(workspace.workspaceId, "tmp/hello.txt", "hello");
    assert.equal(
      await provider.readFile(workspace.workspaceId, "tmp/hello.txt"),
      "hello",
    );
    await provider.editFile(
      workspace.workspaceId,
      "tmp/hello.txt",
      "hello",
      "你好",
    );
    assert.equal(
      await provider.readFile(workspace.workspaceId, "tmp/hello.txt"),
      "你好",
    );

    const result = await provider.exec(
      workspace.workspaceId,
      "node -e 'process.stdout.write(\"sandbox-ok\")'",
    );
    assert.equal(result.stdout, "sandbox-ok");
    assert.equal(result.exitCode, 0);

    const info = await provider.getInfo(workspace.workspaceId);
    assert.equal(info.status, "running");
    assert.equal(info.endpoint, workspace.endpoint);

    await provider.stop(workspace.workspaceId);
    await assert.rejects(provider.getInfo(workspace.workspaceId));
  },
);
