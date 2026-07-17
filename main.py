import os

import anthropic
from dotenv import load_dotenv

load_dotenv()

client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

MODEL = "claude-opus-4-8"


def generate_message(prompt: str) -> str:
    """Ask Claude to generate a message and return the text."""
    response = client.messages.create(
        model=MODEL,
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )
    return "".join(block.text for block in response.content if block.type == "text")


if __name__ == "__main__":
    # TODO: wire up Supabase + Blooio to fetch recipients and send messages.
    text = generate_message("Write a short, friendly check-in message.")
    print(text)
