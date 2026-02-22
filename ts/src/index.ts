import express from 'express';
import { StdioClientTransport } from '@modelcontextprotocol/sdk/client/stdio.js';
import { Client } from '@modelcontextprotocol/sdk/client/index.js';
import { Redis } from 'ioredis';

const app = express();
app.use(express.json());

const redis = new Redis('redis://localhost');
const clients = new Map<string, Client>();

app.post('/chat', async (req, res) => {
  const { user_id, messages, mcp_config } = req.body;
  let client = clients.get(user_id);

  if (!client) {
    const transport = new StdioClientTransport({
      command: mcp_config.command,
      args: mcp_config.args,
    });
    client = new Client({ name: "bridgekit", version: "0.2" });
    await client.connect(transport);
    clients.set(user_id, client);
  }

  // TODO: add tool call + timeout → job logic
  const result = await client.callTool({ name: "analyze_data", arguments: { query: messages } });
  res.json(result);
});

app.listen(8001, () => console.log('TS BridgeKit running on 8001'));
