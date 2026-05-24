import express from "express";
import cors from "cors";
import { query } from "gitclaw";

const app = express();
const PORT = process.env.AGENT_RUNNER_PORT || 4000;

app.use(cors());
app.use(express.json({ limit: "10mb" }));

app.get("/health", (_req, res) => {
  res.json({ status: "ok", service: "repomind-gitagent-runner" });
});

interface RunRequest {
  dir: string;
  prompt: string;
  systemPromptSuffix?: string;
  model?: string;
  maxTurns?: number;
  repoPath?: string;
}

async function collectAgentOutput(options: RunRequest): Promise<string> {
  const stream = query({
    dir: options.dir,
    prompt: options.prompt,
    systemPromptSuffix: options.systemPromptSuffix,
    model: options.model,
    maxTurns: options.maxTurns ?? 25,
  });

  let content = "";
  for await (const msg of stream) {
    if (msg.type === "delta" && msg.content) {
      content += msg.content;
    }
    if (msg.type === "assistant" && msg.content) {
      content = msg.content;
    }
  }
  return content;
}

app.post("/run", async (req, res) => {
  try {
    const body = req.body as RunRequest;
    if (!body.dir || !body.prompt) {
      res.status(400).json({ error: "dir and prompt are required" });
      return;
    }

    const content = await collectAgentOutput(body);
    res.json({
      content,
      costs: undefined,
    });
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err);
    res.status(500).json({ error: message });
  }
});

app.post("/run/stream", async (req, res) => {
  try {
    const body = req.body as RunRequest;
    if (!body.dir || !body.prompt) {
      res.status(400).json({ error: "dir and prompt are required" });
      return;
    }

    res.setHeader("Content-Type", "text/event-stream");
    res.setHeader("Cache-Control", "no-cache");
    res.setHeader("Connection", "keep-alive");

    const stream = query({
      dir: body.dir,
      prompt: body.prompt,
      systemPromptSuffix: body.systemPromptSuffix,
      model: body.model,
      maxTurns: body.maxTurns ?? 25,
    });

    for await (const msg of stream) {
      res.write(`data: ${JSON.stringify(msg)}\n\n`);
    }
    res.write(`data: ${JSON.stringify({ type: "done" })}\n\n`);
    res.end();
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err);
    res.write(`data: ${JSON.stringify({ type: "error", message })}\n\n`);
    res.end();
  }
});

app.listen(PORT, () => {
  console.log(`RepoMind GitAgent runner listening on :${PORT}`);
});
