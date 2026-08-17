import assert from "node:assert/strict";
import { mkdtemp, mkdir, realpath, symlink, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import test from "node:test";

import {
  assertSafeWorkspaceId,
  resolveWorkspacePath,
} from "./path-safety.ts";
import {
  buildPodmanCreateArgs,
  parsePublishedPort,
} from "./podman.ts";
import { selectWorkspaceProvider } from "./provider-selection.ts";

test("显式选择 podman 时不要求 E2B API Key", () => {
  assert.equal(selectWorkspaceProvider("podman", undefined), "podman");
});

test("显式选择 e2b 时要求 E2B API Key", () => {
  assert.throws(
    () => selectWorkspaceProvider("e2b", undefined),
    /E2B_API_KEY/,
  );
  assert.equal(selectWorkspaceProvider("e2b", "e2b-test"), "e2b");
});

test("未设置 Provider 时，有 E2B Key 沿用 E2B，否则默认 Podman", () => {
  assert.equal(selectWorkspaceProvider(undefined, "e2b-test"), "e2b");
  assert.equal(selectWorkspaceProvider(undefined, undefined), "podman");
});

test("工作区 ID 只接受服务端生成的安全格式", () => {
  assert.equal(
    assertSafeWorkspaceId("podman-01234567-89ab-cdef-0123-456789abcdef"),
    "podman-01234567-89ab-cdef-0123-456789abcdef",
  );
  assert.throws(() => assertSafeWorkspaceId("../../host"), /工作区 ID/);
  assert.throws(() => assertSafeWorkspaceId("podman-$(id)"), /工作区 ID/);
});

test("路径解析拒绝绝对路径和父目录越界", async () => {
  const root = await mkdtemp(path.join(tmpdir(), "workspace-path-test-"));
  await mkdir(path.join(root, "tools"));

  assert.equal(
    await resolveWorkspacePath(root, "tools/demo.ts", { forWrite: true }),
    path.join(await realpath(root), "tools", "demo.ts"),
  );
  await assert.rejects(
    resolveWorkspacePath(root, "../secret", { forWrite: true }),
    /工作区路径越界/,
  );
  await assert.rejects(
    resolveWorkspacePath(root, "/etc/passwd", { forWrite: false }),
    /相对路径/,
  );
});

test("路径解析拒绝通过符号链接逃离工作区", async () => {
  const root = await mkdtemp(path.join(tmpdir(), "workspace-link-test-"));
  const outside = await mkdtemp(path.join(tmpdir(), "workspace-outside-"));
  await writeFile(path.join(outside, "secret.txt"), "secret");
  await symlink(outside, path.join(root, "linked"));

  await assert.rejects(
    resolveWorkspacePath(root, "linked/secret.txt", { forWrite: false }),
    /符号链接/,
  );
});

test("Podman 端口输出只接受本机 IPv4 或 IPv6 映射", () => {
  assert.equal(parsePublishedPort("127.0.0.1:49152\n"), 49152);
  assert.equal(parsePublishedPort("[::1]:49153\n"), 49153);
  assert.throws(() => parsePublishedPort("0.0.0.0:49154\n"), /本机/);
  assert.throws(() => parsePublishedPort("unexpected"), /端口/);
});

test("Podman 容器参数包含隔离、配额和本机端口绑定", () => {
  const args = buildPodmanCreateArgs({
    containerName: "mcp-app-podman-01234567",
    workspacePath: "/tmp/workspaces/podman-01234567",
    image: "mcp-app-builder-sandbox:local",
    memory: "1g",
    cpus: "1",
    pidsLimit: 256,
  });

  assert.deepEqual(args.slice(0, 2), ["create", "--name"]);
  assert.ok(args.includes("--read-only"));
  assert.ok(args.includes("--cap-drop=all"));
  assert.ok(args.includes("--security-opt=no-new-privileges"));
  assert.ok(args.includes("--http-proxy=false"));
  assert.ok(args.includes("--memory=1g"));
  assert.ok(args.includes("--cpus=1"));
  assert.ok(args.includes("--pids-limit=256"));
  assert.ok(args.includes("--publish=127.0.0.1::3109"));
  assert.ok(
    args.includes("--volume=/tmp/workspaces/podman-01234567:/workspace:rw"),
  );
  assert.equal(args.at(-1), "mcp-app-builder-sandbox:local");
});
