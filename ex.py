from dotenv import load_dotenv
from elevenlabs.client import ElevenLabs
from elevenlabs.play import play
import os
print("CWD:", os.getcwd(), "KEY:", bool(os.getenv("ELEVEN_API_KEY")))

load_dotenv(dotenv_path="/Users/alex/Vibe_coding/.env")

client = ElevenLabs(api_key=os.getenv("ELEVEN_API_KEY"))

response = client.voices.search()
print(response.voices)