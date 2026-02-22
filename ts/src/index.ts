import express from 'express';
import { StdioClientTransport } from '@modelcontextprotocol/sdk/client/stdio.js';
import { Client } from '@modelcontextprotocol/sdk/client/index.js';
import Redis from 'ioredis';
import { v4 as uuidv4 } from 'crypto';

const app = express();
app.use(express.json());

const REDIS_URL = process.env.MCP_BRIDGEKIT_REDIS_URL || 'redis://localhost:6379';
const TIMEOUT_MS = Number(process.env.MCP_BRIDGEKIT_TIMEOUT_THRESHOLD_SECONDS || '25') * 1000;

const redis = new Redis(REDIS_URL);
const clients = new Map<string, { client: Client; createdAt: number }>();

// Session TTL in ms (1 hour)
const SESSION_TTL_MS = 3600 * 1000;

async function getClient(userId: string, config: { command: string; args: string[] }): Promise<Client> {
  const existing = clients.get(userId);
  if (existing && Date.now() - existing.createdAt < SESSION_TTL_MS) {
    return existing.client;
  }

  // Clean up expired session
  if (existing) {
    try { await existing.client.close(); } catch { /* ignore */ }
    clients.delete(userId);
  }

  const transport = new StdioClientTransport({
    command: config.command,
    args: config.args,
  });
  const client = new Client({ name: 'bridgekit-ts', version: '0.6.0' });
  await client.connect(transport);
  clients.set(userId, { client, createdAt: Date.now() });
  return client;
}

app.post('/chat', async (req, res) => {
  try {
    const { user_id, messages, mcp_config, tool_name, tool_args } = req.body;

    if (!user_id || !mcp_config) {
      return res.status(400).json({ status: 'error', message: 'user_id and mcp_config are required' });
    }

    const client = await getClient(user_id, mcp_config);
    const name = tool_name || 'analyze_data';
    const args = tool_args || { query: JSON.stringify(messages) };

    // Real timeout
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), TIMEOUT_MS);

    try {
      const result = await Promise.race([
        client.callTool({ name, arguments: args }),
        new Promise((_, reject) => {
          controller.signal.addEventListener('abort', () =>
            reject(new Error('TIMEOUT'))
          );
        }),
      ]);
      clearTimeout(timer);
      return res.json({ status: 'ok', result });
    } catch (err: any) {
      clearTimeout(timer);
      if (err.message === 'TIMEOUT') {
        // Queue as background job via Redis
        const jobId = crypto.randomUUID();
        await redis.setex(
          `bridgekit:job:${jobId}:status`, 600,
          JSON.stringify({ status: 'queued', tool_name: name, tool_args: args })
        );
        return res.status(202).json({ status: 'queued', job_id: jobId });
      }
      throw err;
    }
  } catch (err: any) {
    console.error('Error in /chat:', err);
    return res.status(500).json({ status: 'error', message: err.message || 'Internal error' });
  }
});

app.get('/health', (_req, res) => {
  res.json({ status: 'ok', active_sessions: clients.size });
});

app.delete('/session/:userId', async (req, res) => {
  const entry = clients.get(req.params.userId);
  if (entry) {
    try { await entry.client.close(); } catch { /* ignore */ }
    clients.delete(req.params.userId);
  }
  res.json({ status: 'ok', user_id: req.params.userId });
});

const PORT = Number(process.env.PORT || '8001');
app.listen(PORT, () => console.log(`TS BridgeKit running on ${PORT}`));
