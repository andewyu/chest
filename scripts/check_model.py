"""One command that answers "does the model actually work?".

    python scripts/check_model.py

Makes a real Bedrock call with the configured BEDROCK_MODEL_ID and prints a
diagnosis. No agent, no tools, no ledger — if this fails, nothing else in Chest
can work, and the failure modes are distinctive enough to name.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import boto3  # noqa: E402
from botocore.exceptions import ClientError, NoCredentialsError  # noqa: E402

from chest.config import AWS_REGION, BEDROCK_MODEL_ID  # noqa: E402

# Bedrock's error text is accurate but buried. These are the ones worth
# translating into the thing you actually have to go do.
HINTS = {
    "use case details": (
        "The account has not submitted Anthropic's use case details form.\n"
        "  Bedrock console -> Model access -> Anthropic -> fill the form.\n"
        "  It's a one-time, per-account step and it clears within ~15 minutes."
    ),
    "on-demand throughput isn": (
        f"{BEDROCK_MODEL_ID} needs the cross-region inference profile prefix.\n"
        "  Use us.anthropic.<model>, not the bare anthropic.<model> id."
    ),
    "end of its life": (
        "That model version is retired. Pick a current one from:\n"
        "  aws bedrock list-foundation-models --by-provider anthropic"
    ),
    "AccessDenied": (
        "Credentials are valid but not authorized for bedrock:InvokeModel\n"
        "  on this model. Check the API key's scope or the IAM policy."
    ),
}


def main() -> int:
    print(f"region: {AWS_REGION}")
    print(f"model:  {BEDROCK_MODEL_ID}")

    client = boto3.client("bedrock-runtime", region_name=AWS_REGION)
    try:
        response = client.converse(
            modelId=BEDROCK_MODEL_ID,
            messages=[{"role": "user", "content": [{"text": "reply with: ok"}]}],
            inferenceConfig={"maxTokens": 16},
        )
    except NoCredentialsError:
        print("\nFAIL  no credentials.")
        print("  Set AWS_BEARER_TOKEN_BEDROCK in .env (Bedrock console -> API keys),")
        print("  or configure a normal AWS profile.")
        return 1
    except ClientError as exc:
        message = exc.response.get("Error", {}).get("Message", str(exc))
        print(f"\nFAIL  {exc.response['Error']['Code']}: {message}")
        for needle, hint in HINTS.items():
            if needle in message or needle in str(exc):
                print(f"\n  {hint}")
                break
        return 1

    usage = response["usage"]
    print(f"\nOK    replied {response['output']['message']['content'][0]['text']!r}")
    print(f"      {usage['inputTokens']} in / {usage['outputTokens']} out")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
