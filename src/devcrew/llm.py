import os

from dotenv import load_dotenv
from groq import Groq

load_dotenv()
_client: Groq | None = None

def get_client() -> Groq:
    """Return a process-wide Groq client, creating it on first use."""
    global _client
    if _client is None:
        _client = Groq(api_key=os.environ["GROQ_API_KEY"])
    return _client


def get_model() -> str:
    """Return the model name every node should use, from env with a fallback."""
    return os.environ.get("DEVCREW_MODEL", "openai/gpt-oss-120b")


def complete(system: str, user: str, max_tokens: int = 2000) -> str:
    """Send a single-turn request and return the response text.
    Every node uses this same call shape so token usage and model choice
    stay consistent across Planner, Coder, Tester, and Reviewer. Groq's
    API follows OpenAI's chat completions shape, so system/user go in
    the messages list rather than as a separate top-level field.
    """
    response = get_client().chat.completions.create(
        model=get_model(),
        max_tokens=max_tokens,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    )
    return response.choices[0].message.content
