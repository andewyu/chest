# AgentCore deployment

Chest now has a runnable AgentCore Runtime entry point and container definition.
Everything through local validation works without an AWS account; deployment and
model calls require AWS access.

## Prepared in the repository

- `chest/agentcore_app.py` exposes the AgentCore HTTP runtime contract.
- `agentcore/agentcore.json` describes the `chest` container runtime.
- `Dockerfile` builds a non-root Python container on port 8080.
- OpenTelemetry auto-instrumentation is enabled in the container command.
- Runtime requests require a non-empty prompt and use AgentCore's runtime
  session identifier unless an explicit `session_id` is supplied.

## Local, credential-free checks

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pytest -q
python -m chest.agentcore_app
```

The last command listens on port 8080. `GET /ping` can be checked without AWS
credentials. An invocation reaches Bedrock and therefore needs model access.

The current AWS CLI for AgentCore is distributed through npm. You can avoid a
global install:

```bash
npx @aws/agentcore validate
npx @aws/agentcore dev
```

## Steps that require the AWS account

1. Install AWS CLI v2 and authenticate to the hackathon AWS account.
2. Confirm Claude Haiku 4.5 access in `us-west-2` (or change both environment
   values to the enabled region/model).
3. Run `npx @aws/agentcore deploy` from the repository root.
4. Run `npx @aws/agentcore invoke "What is our balance?"` for chat, then
   `npx @aws/agentcore invoke /sweep` for the full five-agent graph. Inspect its
   trace with `npx @aws/agentcore traces`.
5. Set secrets as runtime environment/config values; never commit `.env`.

AgentCore's deploy path creates the AWS resources through CDK. The checked-in
`aws-targets.json` is intentionally empty until an authenticated deployment
selects the real account and region.

Official references:

- [AgentCore CLI workflow](https://aws.github.io/bedrock-agentcore-starter-toolkit/examples/runtime-framework-agents.html)
- [Use any agent framework with the AgentCore Python SDK](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/using-any-agent-framework.html)
- [AgentCore Runtime HTTP protocol contract](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-http-protocol-contract.html)
