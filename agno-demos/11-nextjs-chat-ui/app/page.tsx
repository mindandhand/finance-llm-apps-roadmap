"use client";

import { Send, Wrench } from "lucide-react";
import { useState } from "react";

type ToolEvent = {
  type: string;
  tool_name?: string;
  detail: string;
};

const apiBase = process.env.NEXT_PUBLIC_AGUI_URL ?? "http://127.0.0.1:7777";

function parseAgUiBlock(block: string): { type: string; data: Record<string, unknown> } | null {
  const dataLine = block.split("\n").find((line) => line.startsWith("data: "));
  if (!dataLine) return null;
  const data = JSON.parse(dataLine.slice(6)) as Record<string, unknown>;
  if (typeof data.type !== "string") return null;
  return {
    type: data.type,
    data
  };
}

export default function Page() {
  const [message, setMessage] = useState("比较 SH510300 和 SH588000 的波动率");
  const [answer, setAnswer] = useState("");
  const [events, setEvents] = useState<ToolEvent[]>([]);
  const [running, setRunning] = useState(false);

  async function run() {
    setRunning(true);
    setAnswer("");
    setEvents([]);
    try {
      const response = await fetch(`${apiBase}/agui`, {
        method: "POST",
        headers: {"content-type": "application/json", accept: "text/event-stream"},
        body: JSON.stringify({
          threadId: "finance-thread-ui",
          runId: `run-${crypto.randomUUID()}`,
          state: {},
          messages: [{id: `message-${crypto.randomUUID()}`, role: "user", content: message}],
          tools: [],
          context: [],
          forwardedProps: {}
        })
      });
      if (!response.ok) throw new Error(`AG-UI request failed: ${response.status}`);
      const reader = response.body?.getReader();
      if (!reader) throw new Error("AG-UI response has no stream");
      const decoder = new TextDecoder();
      let buffer = "";
      while (true) {
        const {value, done} = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, {stream: true});
        const blocks = buffer.split("\n\n");
        buffer = blocks.pop() ?? "";
        for (const block of blocks) {
          const parsed = parseAgUiBlock(block);
          if (!parsed) continue;
          if (parsed.type === "TEXT_MESSAGE_CONTENT") {
            setAnswer((current) => current + String(parsed.data.delta ?? ""));
          }
          if (parsed.type.startsWith("TOOL_CALL_") || parsed.type.startsWith("RUN_")) {
            setEvents((current) => [
              ...current,
              {
                type: parsed.type,
                tool_name: String(parsed.data.toolCallName ?? ""),
                detail: JSON.stringify(parsed.data, null, 2)
              }
            ]);
          }
        }
      }
    } catch (error) {
      setAnswer(`请求失败：${error instanceof Error ? error.message : String(error)}`);
    } finally {
      setRunning(false);
    }
  }

  return (
    <main className="shell">
      <section className="chat">
        <div className="messages">
          <div className="assistant">{answer || " "}</div>
        </div>
        <div className="composer">
          <input value={message} onChange={(event) => setMessage(event.target.value)} />
          <button onClick={run} disabled={running} aria-label="Send">
            <Send size={18} />
          </button>
        </div>
      </section>
      <aside className="tools">
        <h2><Wrench size={18} /> Tools</h2>
        {events.map((event, index) => (
          <pre key={`${event.event}-${index}`}>{event.detail}</pre>
        ))}
      </aside>
    </main>
  );
}
