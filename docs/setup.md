# Setup and lab details

Everything needed to run all the labs. The first lab needs only the README's
[Setup](../README.md#setup); this page adds the commands for every lab, the extra environments,
deployments and resources the other labs need, the settings and the issues I hit. Back to the
[README](../README.md).

## Labs

Run all commands from the project root. The scripts delete the agents, threads, files and indexes they create at the
end of the run. Their indexes have fixed names (for example `myfitnessindex`, `fitness-sk-index`, `ai-safety-index`),
so a run replaces an index of the same name. GenAI Ops keeps its index with `--keep-index`. The two Basic RAG scripts
always keep theirs: like the notebook, they rebuild it at the start of each run (`SEARCH_INDEX_NAME`, or
`healthtips-index` when unset) and keep it afterwards, so it can be inspected in the portal (on the free Azure AI
Search tier it costs nothing).

| Lab | Script | Sample output | What it shows | Command |
|---|---|---|---|---|
| Setup check | [`check-setup.py`](../1-introduction/check-setup.py) | [output](../sample-output/check-setup.py-output-20261018-172359.txt) | read-only check of the three introduction notebooks' steps: settings, Entra ID sign-in, project deployments and connections, Azure AI Search; no model call | `uv run python 1-introduction/check-setup.py` |
| Chat completion | [`1-basic-chat-completion-azure-openai.py`](../2-notebooks/1-chat_completion/1-basic-chat-completion-azure-openai.py), [`-project-client.py`](../2-notebooks/1-chat_completion/1-basic-chat-completion-project-client.py) | [azure-openai](../sample-output/1-basic-chat-completion-azure-openai.py-output-20261016-070614.txt), [project-client](../sample-output/1-basic-chat-completion-project-client.py-output-20261014-094029.txt) | the same calls through `openai.AzureOpenAI` and through `AIProjectClient.get_openai_client()` | `uv run python 2-notebooks/1-chat_completion/1-basic-chat-completion-azure-openai.py` |
| Chat: REST vs SDK | [`1-basic-chat-completion-rest-vs-sdk.py`](../2-notebooks/1-chat_completion/1-basic-chat-completion-rest-vs-sdk.py) | [output](../sample-output/1-basic-chat-completion-rest-vs-sdk.py-output-20261021-131720.txt) | the same chat request sent by hand with `requests` (URL, headers, JSON body) and through the `openai` SDK; the [HTTP log](#http-log) shows both requests and responses in full, then a table compares status, latency and tokens | `uv run python 2-notebooks/1-chat_completion/1-basic-chat-completion-rest-vs-sdk.py` |
| Embeddings | [`2-embeddings-azure-openai.py`](../2-notebooks/1-chat_completion/2-embeddings-azure-openai.py), [`-project-client.py`](../2-notebooks/1-chat_completion/2-embeddings-project-client.py) | [azure-openai](../sample-output/2-embeddings-azure-openai.py-output-20261014-094054.txt), [project-client](../sample-output/2-embeddings-project-client.py-output-20261014-094058.txt) | text embeddings with `text-embedding-3-small` | `uv run python 2-notebooks/1-chat_completion/2-embeddings-azure-openai.py` |
| Image embeddings | [`2-embeddings-image-embeddings.py`](../2-notebooks/1-chat_completion/2-embeddings-image-embeddings.py) | [output](../sample-output/2-embeddings-image-embeddings.py-output-20261018-133654.txt) | Cohere `embed-v-4-0` puts an X-ray image and text captions in one vector space; the captions are ranked by cosine similarity to the image. Plain REST calls, because the `azure-ai-inference` SDK the notebook used was retired | `uv run python 2-notebooks/1-chat_completion/2-embeddings-image-embeddings.py` |
| Image generation | [`2-embeddings-image-generation.py`](../2-notebooks/1-chat_completion/2-embeddings-image-generation.py) | [output](../sample-output/2-embeddings-image-generation.py-output-20261018-133622.txt) | one image from the notebook's prompt on `gpt-image-2` (DALL-E 3 was retired on Azure), through the Azure OpenAI v1 endpoint with an Entra ID token; saved as PNG | `uv run python 2-notebooks/1-chat_completion/2-embeddings-image-generation.py` |
| Basic RAG | [`3-basic-rag-azure-openai.py`](../2-notebooks/1-chat_completion/3-basic-rag-azure-openai.py), [`-project-client.py`](../2-notebooks/1-chat_completion/3-basic-rag-project-client.py) | [azure-openai](../sample-output/3-basic-rag-azure-openai.py-output-20261014-094211.txt), [project-client](../sample-output/3-basic-rag-project-client.py-output-20261014-094224.txt) | vector index in Azure AI Search, answers grounded in the top matches | `uv run python 2-notebooks/1-chat_completion/3-basic-rag-azure-openai.py` |
| Phi-4 vs gpt-4o-mini | [`4-phi-4.py`](../2-notebooks/1-chat_completion/4-phi-4.py) | [output](../sample-output/4-phi-4.py-output-20261018-164134.txt) | Phi-4, Phi-4-reasoning and gpt-4o-mini on the same three prompts (a training plan, an answer from a context snippet, a pace calculation with one right answer), with tokens, time and cost per model; the Phi models are deployed on the Foundry resource and called through the Azure OpenAI v1 endpoint, since the serverless `azure-ai-inference` route the notebook used was retired | `uv run python 2-notebooks/1-chat_completion/4-phi-4.py` |
| DeepSeek thinking off vs on | [`5-deep-seek-v4-flash.py`](../2-notebooks/1-chat_completion/5-deep-seek-v4-flash.py) | [output](../sample-output/5-deep-seek-v4-flash.py-output-20261018-170548.txt) | the notebook's travel and PostgreSQL prompts plus the pace question on DeepSeek-V4-Flash (DeepSeek-R1 is retired on Azure), each with thinking off and on (`reasoning_effort="high"`); the thinking arrives in its own `reasoning_content` field, so the notebook's `<think>` regex isn't needed | `uv run python 2-notebooks/1-chat_completion/5-deep-seek-v4-flash.py` |
| Agent basics | [`1-basics.py`](../2-notebooks/2-agent_service/1-basics.py) | [output](../sample-output/1-basics.py-output-20261014-094247.txt) | Foundry Agent Service: agent, thread, messages, run | `uv run python 2-notebooks/2-agent_service/1-basics.py` |
| Code Interpreter | [`2-code_interpreter.py`](../2-notebooks/2-agent_service/2-code_interpreter.py) | [output](../sample-output/2-code_interpreter.py-output-20261018-142926.txt) | agent analyzes a CSV and returns a chart file | `uv run python 2-notebooks/2-agent_service/2-code_interpreter.py --output-dir charts` |
| File Search | [`3-file-search.py`](../2-notebooks/2-agent_service/3-file-search.py) | [output](../sample-output/3-file-search.py-output-20261014-101408.txt) | vector store over Markdown files, answers with file citations | `uv run python 2-notebooks/2-agent_service/3-file-search.py` |
| Grounding with Bing | [`4-bing_grounding.py`](../2-notebooks/2-agent_service/4-bing_grounding.py) | [output](../sample-output/4-bing_grounding.py-output-20261018-114459.txt) | new agents API (`azure-ai-projects` 2.x) agent with the Bing grounding tool through a project connection; answers with numbered web citations and the Bing search link; queries leave the Azure compliance boundary (Bing's terms apply) | `.venv-agents-v2/bin/python 2-notebooks/2-agent_service/4-bing_grounding.py` |
| Web Search (next to the Bing lab) | [`4-web_search.py`](../2-notebooks/2-agent_service/4-web_search.py) | [output](../sample-output/4-web_search.py-output-20261018-144147.txt) | the same three questions with the built-in `WebSearchTool`, which Microsoft now recommends first: no Grounding with Bing resource or project connection; it still runs on Grounding with Bing, so the same terms and compliance-boundary note apply | `.venv-agents-v2/bin/python 2-notebooks/2-agent_service/4-web_search.py` |
| Agent + Azure AI Search | [`5-agents-aisearch.py`](../2-notebooks/2-agent_service/5-agents-aisearch.py) | [output](../sample-output/5-agents-aisearch.py-output-20261018-204747.txt) | product search tool plus a local price function tool | `uv run python 2-notebooks/2-agent_service/5-agents-aisearch.py` |
| Agent + Azure Functions MCP server | [`6-agents-az-functions-mcp.py`](../2-notebooks/2-agent_service/6-agents-az-functions-mcp.py), [`function_app/`](../2-notebooks/2-agent_service/6-agents-az-functions-mcp/function_app/) | [output](../sample-output/6-agents-az-functions-mcp.py-output-20261017-114003.txt) | new agents API (`azure-ai-projects` 2.x) agent with an MCP tool to a Function app's two workout tools, key from a project connection, each call approved; see the [lab README](../2-notebooks/2-agent_service/6-agents-az-functions-mcp/README.md) for deploying | `.venv-agents-v2/bin/python 2-notebooks/2-agent_service/6-agents-az-functions-mcp.py` |
| Observability | [`1-observability.py`](../2-notebooks/3-quality_attributes/1-observability.py) | [output](../sample-output/1-observability.py-output-20261016-005619.txt) | OpenTelemetry traces of a chat call and a file-search agent (model, tokens, run status per step), to the console or to Application Insights and the Foundry portal's Tracing page | `uv run python 2-notebooks/3-quality_attributes/1-observability.py --destination azure-monitor` |
| Evaluation | [`2-evaluation.py`](../2-notebooks/3-quality_attributes/2-evaluation.py) | [output](../sample-output/2-evaluation.py-output-20261014-103533.txt) | `azure-ai-evaluation`: F1, plus relevance and groundedness judged by a model; results in the Foundry portal | `uv run python 2-notebooks/3-quality_attributes/2-evaluation.py --output-dir evaluation-results` |
| GenAI Ops | [`3-e2e-genai-ops.py`](../2-notebooks/3-quality_attributes/3-e2e-genai-ops.py) | [rerun after the fix](../sample-output/3-e2e-genai-ops.py-output-20261016-031924.txt) (sections 3 and 6), [full run before it](../sample-output/3-e2e-genai-ops.py-output-20261016-030225.txt) | safety evaluators (harm categories, copyrighted text), a direct attack simulator against a test agent, indirect attack (XPIA) generation against a fixed-reply target as in the notebook (no model sees those attacks), quality evaluation in the Foundry portal, RAG scored by a judge model, all traced to Application Insights | `uv run python 2-notebooks/3-quality_attributes/3-e2e-genai-ops.py --output-dir runs/genai-ops` |
| Semantic Kernel agent | [`1-rag-sk-agents-aisearch.py`](../2-notebooks/4-frameworks/1-rag-sk-agents-aisearch.py) | [output](../sample-output/1-rag-sk-agents-aisearch.py-output-20261015-121028.txt) | `AzureAIAgent` with a `@kernel_function` price plugin | `2-notebooks/4-frameworks/.venv/bin/python 2-notebooks/4-frameworks/1-rag-sk-agents-aisearch.py` |
| AutoGen multi-agent RAG | [`2-autogen-multi-agent-rag.py`](../2-notebooks/4-frameworks/2-autogen-multi-agent-rag.py) | [output](../sample-output/2-autogen-multi-agent-rag.py-output-20261015-165725.txt) | retriever and responder agents, embedding search over tips | `uv run python 2-notebooks/4-frameworks/2-autogen-multi-agent-rag.py` |
| AutoGen wellness agents | [`3-autogen-personalized-heart-rate.py`](../2-notebooks/4-frameworks/3-autogen-personalized-heart-rate.py) | [output](../sample-output/3-autogen-personalized-heart-rate.py-output-20261015-165744.txt) | hourly heart-rate summary from sample wearable data (pandas, matplotlib), then two agents plan workouts and breaks; a wellness demo with no health scoring, not medical advice | `uv run python 2-notebooks/4-frameworks/3-autogen-personalized-heart-rate.py --output-dir charts` |

The original notebooks are still next to the scripts. Each one starts with a note pointing to its working script.

The sample outputs are the full console output of a recorded run of each script (the run date is in the file name).
All are passing runs except the GenAI Ops full run, kept as evidence of the two failures it hid (see the
[findings](findings.md#red-teaming-an-agent-with-attack-simulators)) next to the rerun after the fix. My endpoints,
resource names and GUIDs (subscription, tenant and other IDs) are replaced with placeholders such as `<resource-name>`
and `<id>`; agent, thread and message IDs are left as they are, since the scripts delete those objects at the end of
each run. Model answers differ from run to run.

The image from the recorded image generation run: `gpt-image-2` at low quality, the notebook's prompt "A watercolor
painting of fresh fruits and vegetables arranged in a heart shape" (a 512 px copy of the 1024 px original):

<img src="../sample-output/2-embeddings-image-generation.py-image-20261018-133641.jpg" alt="Model-generated watercolor of fruits and vegetables arranged in a heart shape" width="256">

**Not included:** the workshop's end-to-end sample app, which this rebuild doesn't cover; it is in the
[original repository](https://github.com/Azure/ai-foundry-workshop/tree/main/3-ai-native-e2e-sample).

## What the other labs need

**Two more environments.** One environment holds only one version of each package, and some labs need versions
that conflict:

| Environment | Key packages | Labs | Why separate |
|---|---|---|---|
| `.venv` | `azure-ai-projects` 1.0.0, `azure-ai-agents` 1.1.0, AutoGen 0.7.5 | all others | the classic agents API (threads, messages, runs) the workshop notebooks use; `azure-ai-projects` 2.x removed it |
| `.venv-agents-v2` | `azure-ai-projects` 2.8.0, `mcp` | Bing, Web Search, Functions MCP | these tools need the new agents API, which exists only in 2.x |
| `2-notebooks/4-frameworks/.venv` | `semantic-kernel` 1.45.0, `azure-ai-agents` 1.2.0b6 | Semantic Kernel | Semantic Kernel needs a beta `azure-ai-agents` |

```bash
uv venv .venv-agents-v2 --python 3.13
uv pip install --python .venv-agents-v2/bin/python -r requirements-agents-v2.txt
uv venv 2-notebooks/4-frameworks/.venv --python 3.13
uv pip install --python 2-notebooks/4-frameworks/.venv/bin/python -r 2-notebooks/4-frameworks/requirements.txt
```

**More model deployments.** The two image scripts of the embeddings lab need an `embed-v-4-0` and a `gpt-image-2`
deployment, the Phi-4 lab a `Phi-4` and a `Phi-4-reasoning` deployment, and the DeepSeek lab a `DeepSeek-V4-Flash`
deployment (all GlobalStandard, no cost while idle):

```bash
az cognitiveservices account deployment create -g <resource-group> -n <resource-name> --deployment-name gpt-image-2 \
  --model-name gpt-image-2 --model-version 2026-04-21 --model-format OpenAI --sku-name GlobalStandard --sku-capacity 1
az cognitiveservices account deployment create -g <resource-group> -n <resource-name> --deployment-name embed-v-4-0 \
  --model-name embed-v-4-0 --model-version 1 --model-format Cohere --sku-name GlobalStandard --sku-capacity 10
az cognitiveservices account deployment create -g <resource-group> -n <resource-name> --deployment-name Phi-4 \
  --model-name Phi-4 --model-version 7 --model-format Microsoft --sku-name GlobalStandard --sku-capacity 20
az cognitiveservices account deployment create -g <resource-group> -n <resource-name> --deployment-name Phi-4-reasoning \
  --model-name Phi-4-reasoning --model-version 1 --model-format Microsoft --sku-name GlobalStandard --sku-capacity 20
az cognitiveservices account deployment create -g <resource-group> -n <resource-name> --deployment-name DeepSeek-V4-Flash \
  --model-name DeepSeek-V4-Flash --model-version 2026-04-23 --model-format DeepSeek --sku-name GlobalStandard \
  --sku-capacity 20
```

**Other resources.**
- Application Insights connected to the Foundry project (portal: project, Tracing, Connect): for the GenAI Ops lab
  and the observability lab's `--destination azure-monitor` mode.
- A Grounding with Bing resource and a project connection to it: for the Bing lab
  (`GROUNDING_WITH_BING_CONNECTION_NAME`).
- The Function app of the MCP lab: see its [lab README](../2-notebooks/2-agent_service/6-agents-az-functions-mcp/README.md).

`opentelemetry-util-genai` stays at 1.1b0 because version 1.2b0 renamed a module that
`opentelemetry-instrumentation-openai-v2` 2.4b0 still imports.

## Settings reference

All settings go in `2-notebooks/.env` (start from [`2-notebooks/.env.example`](../2-notebooks/.env.example)):

| Variable | Used for |
|---|---|
| `AZURE_AI_SERVICES_ENDPOINT`, `AZURE_AI_PROJECT_NAME` | Foundry project endpoint (or set `AZURE_AI_PROJECT_ENDPOINT` directly) |
| `OPENAI_ENDPOINT`, `OPENAI_API_VERSION` | Azure OpenAI endpoint of the Foundry resource |
| `MODEL_DEPLOYMENT_NAME` | chat model for the agent, framework, observability and GenAI Ops labs and the model comparisons (gpt-4o-mini) |
| `EMBEDDING_MODEL_DEPLOYMENT_NAME` | embedding model (text-embedding-3-small) |
| `IMAGE_EMBEDDING_MODEL_DEPLOYMENT_NAME`, `IMAGE_MODEL_DEPLOYMENT_NAME` | image embeddings (embed-v-4-0) and image generation (gpt-image-2) in the embeddings lab |
| `OPENAI_DEPLOYMENT_NAME` | chat model for the basic chat and Basic RAG labs, and judge model for the evaluation and GenAI Ops labs (gpt-4o) |
| `AZURE_AI_SEARCH_ENDPOINT`, `AZURE_AI_SEARCH_API_KEY`, `SEARCH_INDEX_NAME` | Azure AI Search |
| `AZURE_FUNCTIONS_MCP_URL`, `AZURE_FUNCTIONS_MCP_KEY` | Azure Functions MCP lab |
| `GROUNDING_WITH_BING_CONNECTION_NAME` | Bing lab: name of the project connection to the Grounding with Bing resource |
| `PHI_MODEL_DEPLOYMENT_NAME`, `PHI_REASONING_MODEL_DEPLOYMENT_NAME` | Phi-4 lab (Phi-4 and Phi-4-reasoning) |
| `DEEPSEEK_MODEL_DEPLOYMENT_NAME` | DeepSeek lab (DeepSeek-V4-Flash) |

Microsoft's notebooks connect with a hub-style `PROJECT_CONNECTION_STRING`; current Foundry projects use the project
endpoint instead, which is why these scripts read `AZURE_AI_SERVICES_ENDPOINT` and `AZURE_AI_PROJECT_NAME` (or
`AZURE_AI_PROJECT_ENDPOINT`):

```text
Hub-style connection string (Microsoft's notebooks):
  <region>.api.azureml.ms;<subscription-id>;<resource-group>;<project-name>
  e.g. eastus2.api.azureml.ms;<subscription-id>;<resource-group>;<project-name>

Foundry project endpoint (these scripts):
  https://<resource-name>.services.ai.azure.com/api/projects/<project-name>
  = AZURE_AI_SERVICES_ENDPOINT + /api/projects/ + AZURE_AI_PROJECT_NAME
    (or set AZURE_AI_PROJECT_ENDPOINT directly)
```

### HTTP log

Every script calls `http_log.enable()` from [`workshop_utils/http_log.py`](../workshop_utils/http_log.py), which
prints each HTTP request and response the script sends: method, URL, headers and body, then status, headers and
body. It hooks the transport of `requests`, `httpx2` and `httpx`, so it also shows the calls the SDKs make (openai,
the azure-* SDKs, Semantic Kernel, AutoGen, the MCP client). Authorization and key headers, key query parameters and
token fields are replaced with `<redacted>`; long and binary bodies are shortened. A request and its response share a
call number:

```text
--- OUTBOUND REQUEST #1 ---
> POST https://<resource-name>.openai.azure.com/openai/deployments/gpt-4o-mini/chat/completions?api-version=...
> Authorization: Bearer <redacted>
> Content-Type: application/json
>
{
  "messages": [ ... ]
}

--- OUTBOUND RESPONSE #1 ---
< 200 OK
< Content-Type: application/json
<
{
  "choices": [ ... ]
}
```

It is set with environment variables on the command line (not in `.env`, which the scripts read after the log
starts), for example `HTTP_LOG=summary uv run python 1-introduction/check-setup.py`:

| Variable | Values |
|---|---|
| `HTTP_LOG` | `full` (default), `summary` (one line per call), `off` |
| `HTTP_LOG_METRICS` | `false` (default), `true`: time, bytes and token usage per call, and totals at the end |
| `HTTP_LOG_MAX_BODY` | characters shown of each body, default 8192; the rest is cut with `...more...` |
| `HTTP_LOG_POLLS` | `short` (default): a repeated GET of the same URL, such as an agent run checked until it ends, is one line with the reply's `status` (`HTTP #7 GET <url> -> 200 OK, status: in_progress`); the first GET of a URL stays in full. `full`: every one in full |

Unit tests against a local server (no Azure): `uv run python -m unittest discover -s tests -v`.

## Troubleshooting

Issues I hit while building the labs:

| Symptom | Cause | Fix |
|---|---|---|
| `DefaultAzureCredential failed to retrieve a token` | not signed in with the Azure CLI | `az login`, then `uv run python 1-introduction/check-setup.py` |
| `Required environment variable is not set: AZURE_AI_PROJECT_NAME` (or another setting) | `2-notebooks/.env` is missing or incomplete | `cp 2-notebooks/.env.example 2-notebooks/.env`, fill it in, run the setup check |
| 429 (rate limit) errors from a new deployment, often on the first or second call | the deployment's rate limit is too low: for the Phi-4, DeepSeek and embed-v-4-0 deployments here, capacity 1 meant 1 request and 1,000 tokens per minute (the ratio differs by model) | check the limits with `az cognitiveservices account deployment show -g <resource-group> -n <resource-name> --deployment-name <deployment> --query properties.rateLimits`, then raise the capacity (for example `--sku-capacity 20` in the deployment commands above); pay-as-you-go billing is per token, so capacity costs nothing |
| agent scripts fail on `agents.threads`, `messages` or `runs` | `azure-ai-projects` 2.x removed the classic agents operations | keep `azure-ai-projects==1.0.0` in the main environment; the 2.x labs use their own `.venv-agents-v2` |
| the MCP agent's tool calls get `503 Site Unavailable` | Python on Flex Consumption handles one request at a time per instance, and the MCP client's open stream holds that slot | raise the per-instance concurrency; see the [lab README](../2-notebooks/2-agent_service/6-agents-az-functions-mcp/README.md) |
| Phi-4-reasoning's thinking can't be split from its answer | the Azure endpoint strips the `<think>` tags and rejects `skip_special_tokens` | nothing to fix: the reply is printed as one text (see [Phi-4 in the findings](findings.md#phi-4-and-phi-4-reasoning-vs-gpt-4o-mini)) |
