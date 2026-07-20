import os
import requests

LLM_PROVIDER = os.getenv("LLM_PROVIDER", "ollama")  # Default to ollama

def generate_summary(prompt: str) -> str:
    if LLM_PROVIDER == "ollama":
        # Local Ollama endpoint
        response = requests.post(
            "http://localhost:11434/api/generate",
            json={"model": os.getenv("OLLAMA_MODEL", "llama3.2"), "prompt": prompt, "stream": False}
        )
        return response.json()["response"]

    elif LLM_PROVIDER == "anthropic":
        # Anthropic API
        import anthropic
        client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
        msg = client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=1000,
            messages=[{"role": "user", "content": prompt}]
        )
        return msg.content[0].text

    # Add future providers here (e.g., groq, openai, deepseek)
    else:
        raise ValueError(f"Unsupported provider: {LLM_PROVIDER}")
