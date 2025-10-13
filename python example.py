from openai import OpenAI
from dotenv import load_dotenv
import os

# Load environment variables from a .env file in the current working directory
load_dotenv()

client = OpenAI()

model = os.getenv("OPENAI_MODEL", "gpt-5-nano-2025-08-07")
response = client.responses.create(
    model=model,
    input="Write a one-sentence bedtime story about a unicorn."
)

print(response.output_text)