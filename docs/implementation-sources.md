# Implementation sources

Chest's framework-specific integration choices are grounded in these official
references. Versions are pinned in `requirements.txt` so CI and deployment use
the same APIs that were verified locally.

- Strands single-agent sessions use a unique session id and a fresh agent per
  request with `SnapshotSessionManager` and `LocalFileStorage`:
  https://strandsagents.com/docs/user-guide/concepts/agents/session-management/
- Strands graph spend and time bounds use `set_max_node_executions`,
  `set_execution_timeout`, and `set_node_timeout`:
  https://strandsagents.com/docs/api/python/strands.multiagent.graph/
- AgentCore's supported Strands entrypoint uses `BedrockAgentCoreApp` and
  `@app.entrypoint`:
  https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/using-any-agent-framework.html
- AgentCore Runtime containers listen on port 8080 and expose `/invocations`
  plus `/ping`:
  https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-http-protocol-contract.html
- Twilio webhook authentication validates the complete public URL, all form
  values, and the request signature with Twilio's SDK:
  https://www.twilio.com/docs/usage/security#validating-requests-are-coming-from-twilio
- Telegram webhook authentication uses the `secret_token` value returned in
  the `X-Telegram-Bot-Api-Secret-Token` header:
  https://core.telegram.org/bots/api#setwebhook

The Blooio webhook signature shape remains provider-specific and should be
confirmed against the team's Blooio dashboard documentation before enabling
that optional channel publicly.
