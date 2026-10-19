"""Basic chat completion lab (1-basic-chat-completion.ipynb) as a script.

Connection method: the openai package's AzureOpenAI client, created directly with the
Azure OpenAI endpoint (OPENAI_ENDPOINT) and an Entra ID token from the Azure CLI login.

Run from the project root:
    uv run python 2-notebooks/1-chat_completion/1-basic-chat-completion-azure-openai.py
"""

import os
from pathlib import Path

from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from dotenv import load_dotenv
from openai import AzureOpenAI

COGNITIVE_SERVICES_SCOPE = "https://cognitiveservices.azure.com/.default"

FITNESS_SYSTEM_PROMPT = (
    "You are FitChat GPT, a friendly fitness assistant.\n"
    "Always remind users: I'm not a medical professional.\n"
    "Answer with empathy and disclaimers."
)

TRAINER_SYSTEM_TEMPLATE = (
    "You are FitChat GPT, an AI personal trainer for {name}.\n"
    "Your user wants to achieve: {goal}.\n"
    "Remind them you're not a medical professional. Offer friendly advice."
)


def print_section(title):
    print()
    print("=" * 80)
    print(title)
    print("=" * 80)


def load_environment():
    env_path = Path(__file__).resolve().parent.parent / ".env"
    if not env_path.exists():
        raise FileNotFoundError(f".env file not found: {env_path}")
    load_dotenv(env_path)
    print(f"Loaded .env from: {env_path}")


def require_env(name):
    value = os.getenv(name)
    if not value:
        raise ValueError(f"Required environment variable is not set: {name}")
    return value


def create_client():
    endpoint = require_env("OPENAI_ENDPOINT")
    api_version = require_env("OPENAI_API_VERSION")

    token_provider = get_bearer_token_provider(DefaultAzureCredential(), COGNITIVE_SERVICES_SCOPE)
    client = AzureOpenAI(
        azure_endpoint=endpoint,
        azure_ad_token_provider=token_provider,
        api_version=api_version,
    )

    print("Connection method: AzureOpenAI (direct)")
    print(f"Endpoint:          {endpoint}")
    print(f"API version:       {api_version}")
    return client


def chat(client, model, system_prompt, user_input):
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_input},
        ],
        max_tokens=400,
        temperature=0.7,
    )
    usage = response.usage
    print(f"(tokens: prompt {usage.prompt_tokens}, completion {usage.completion_tokens})")
    return response.choices[0].message.content


def main():
    print_section("BASIC CHAT COMPLETION - AzureOpenAI")
    load_environment()
    model = require_env("OPENAI_DEPLOYMENT_NAME")
    print(f"Model deployment:  {model}")
    client = create_client()

    print_section("1. Chat with a system prompt")
    question = "How can I start a beginner workout routine at home?"
    print(f"User: {question}")
    print(f"Assistant: {chat(client, model, FITNESS_SYSTEM_PROMPT, question)}")

    print_section("2. Prompt template with fill-ins")
    system_prompt = TRAINER_SYSTEM_TEMPLATE.format(
        name="Jordan",
        goal="increase muscle tone and endurance",
    )
    question = "What kind of home exercise do you recommend for a busy schedule?"
    print(f"User: {question}")
    print(f"Assistant: {chat(client, model, system_prompt, question)}")

    print_section("DONE")


if __name__ == "__main__":
    main()
