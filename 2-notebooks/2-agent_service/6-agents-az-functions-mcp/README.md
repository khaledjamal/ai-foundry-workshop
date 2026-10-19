# Azure Functions remote MCP server, used by a Foundry agent

The original lab gave the agent an Azure Functions tool through storage queues, which needs a standard agent setup
(the project's own storage), not the basic setup used here. This version turns the Function app into a **remote MCP
server** instead: any MCP client can use its tools, and a Foundry agent on the new agents API (`azure-ai-projects` 2.x) calls
them through its MCP tool.

```
Foundry agent (gpt-4o-mini) ──MCP tool──> https://<function-app>.azurewebsites.net/runtime/webhooks/mcp
   key from a project connection             Function app (Flex Consumption, Python 3.13)
   every call approved by the script           list_workout_goals, suggest_workout
```

## Files

| File | What it is |
|---|---|
| [`function_app/`](function_app/) | the Function app: two `@app.mcp_tool()` functions with fixed logic (no model), `host.json` with the MCP server name and instructions |
| [`../6-agents-az-functions-mcp-client.py`](../6-agents-az-functions-mcp-client.py) | MCP client test with no model: lists the tools, calls them and checks the answers (local or Azure) |
| [`../6-agents-az-functions-mcp.py`](../6-agents-az-functions-mcp.py) | the agent: a prompt agent with an MCP tool pointing to the Function app |
| [`../../../scripts/probe-mcp-http.py`](../../../scripts/probe-mcp-http.py) | the same MCP calls as raw JSON-RPC over HTTP, for debugging an endpoint below the SDK |

## How it works

- **Tools.** `list_workout_goals()` returns the goals (cardio, strength, mobility); `suggest_workout(goal, minutes)`
  returns a plan with warm-up, main block and cool-down, or a clear error for an unknown goal or a length outside
  10-90 minutes. The MCP extension takes each tool's name from the function, its description from the docstring and
  its input schema from the typed parameters.
- **No key in the agent.** In Azure every MCP call needs the Function's `mcp_extension` system key in the
  `x-functions-key` header. The key is stored once in a Foundry project connection (type Custom keys, key name
  `x-functions-key`); the agent's `MCPTool` only gets the connection's ID.
- **Approval before each tool call.** The tool uses `require_approval="always"`: each call comes back as an
  `mcp_approval_request`, and the script approves only the two workout tools on this server and denies anything else.
- **Honest result.** The agent gets two questions in one conversation ("Which workout goals can you plan for?", then
  "Plan a 30-minute strength workout for me."). The script exits with 1 unless the first turn called
  `list_workout_goals`, the second called `suggest_workout` with `strength` and `30`, and both turns got an answer.
- **App check first.** Before creating the agent, one request without a key tells a stopped app (HTTP 403, the script
  prints the start command) from a running one (HTTP 401) and wakes it, so the agent's first call doesn't wait for a
  cold start.

## Run it

Run the commands from the project root. The agent needs `azure-ai-projects` 2.x, which the other labs' venv must not
get, so it uses its own venv:

```bash
uv venv .venv-agents-v2 --python 3.13
uv pip install --python .venv-agents-v2/bin/python -r requirements-agents-v2.txt
```

**1. Locally**, with [Azure Functions Core Tools](https://learn.microsoft.com/azure/azure-functions/functions-run-local)
(`func`) and the free client test (no Azure resources, no model):

```bash
cd 2-notebooks/2-agent_service/6-agents-az-functions-mcp/function_app
uv venv .venv && uv pip install -r requirements.txt && source .venv/bin/activate
func start
# in a second terminal, from the project root:
.venv-agents-v2/bin/python 2-notebooks/2-agent_service/6-agents-az-functions-mcp-client.py
```

`local.settings.json` (not in git) needs `FUNCTIONS_WORKER_RUNTIME=python`; with `AzureWebJobsStorage=""` and
`AzureWebJobsSecretStorageType=files`, the host starts without a storage emulator.

**2. In Azure** (Flex Consumption: no fixed monthly fee, scales to zero):

```bash
az provider register --namespace Microsoft.Web --wait
az storage account create -n <storage-account> -g <resource-group> -l <region> --sku Standard_LRS --min-tls-version TLS1_2 --allow-blob-public-access false
az functionapp create -g <resource-group> -n <function-app> --storage-account <storage-account> \
  --flexconsumption-location <region> --runtime python --runtime-version 3.13 --instance-memory 512 \
  --maximum-instance-count 1 --https-only true --deployment-storage-auth-type SystemAssignedIdentity
az functionapp scale config set -g <resource-group> -n <function-app> --trigger-type http --trigger-settings perInstanceConcurrency=16
cd 2-notebooks/2-agent_service/6-agents-az-functions-mcp/function_app && func azure functionapp publish <function-app>
```

Then put `AZURE_FUNCTIONS_MCP_URL` (`https://<function-app>.azurewebsites.net/runtime/webhooks/mcp`) and
`AZURE_FUNCTIONS_MCP_KEY` (from `az functionapp keys list -g <resource-group> -n <function-app> --query systemKeys.mcp_extension -o tsv`)
in `2-notebooks/.env`, rerun the client test against Azure, and create the project connection `workout-mcp-key`:
type Custom keys, key `x-functions-key` with that value, target the MCP URL (in the Foundry portal, or with
`az rest --method put` on the project's `connections/workout-mcp-key`).

**3. The agent** (a few small gpt-4o-mini calls, well under $0.01 per run):

```bash
.venv-agents-v2/bin/python 2-notebooks/2-agent_service/6-agents-az-functions-mcp.py
```

## Findings

- **One instance, one request at a time.** On Flex Consumption a Python app handles one HTTP request at a time per
  instance by default. With the instance count capped at 1 (a cost cap), the MCP client's open stream took that one
  slot, and its tool calls got `503 Site Unavailable`; the raw probe, which opens no stream, worked. Raising the
  per-instance concurrency (`perInstanceConcurrency=16` above) fixed it and kept the cap.
- **The agent filled in numbers of its own.** The tool returned a 4-minute warm-up of "arm swings, hip circles, 10
  easy squats"; the agent showed "Arm swings: 1 minute, Hip circles: 1 minute". One line in its instructions ("show
  times, counts and exercises only as the tool gives them") fixed it.

The workout plans are general fitness ideas, not medical advice.
