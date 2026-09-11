FROM public.ecr.aws/docker/library/python:3.12-slim-trixie

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN useradd --create-home --uid 1000 bedrock_agentcore

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY --chown=bedrock_agentcore:bedrock_agentcore . .

USER bedrock_agentcore

# AgentCore Runtime's HTTP service contract uses port 8080. The Python SDK
# supplies both POST /invocations and GET /ping.
EXPOSE 8080

CMD ["opentelemetry-instrument", "python", "-m", "chest.agentcore_app"]
