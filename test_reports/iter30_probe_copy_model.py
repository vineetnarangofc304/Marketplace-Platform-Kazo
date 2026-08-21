import asyncio, os, uuid
from dotenv import load_dotenv
load_dotenv("/app/backend/.env")
from emergentintegrations.llm.chat import LlmChat, UserMessage

KEY = os.environ["EMERGENT_LLM_KEY"]
CANDIDATES = [
    ("gemini", "gemini-3.6-flash"),
    ("gemini", "gemini-3-flash-preview"),
    ("gemini", "gemini-2.5-flash"),
    ("gemini", "gemini-3.5-flash"),
]

async def main():
    for prov, model in CANDIDATES:
        chat = LlmChat(api_key=KEY, session_id=f"probe-{uuid.uuid4()}", system_message="You are terse.")
        chat.with_model(prov, model)
        try:
            r = await chat.send_message(UserMessage(text="Say OK"))
            print(f"OK   {prov}/{model} -> {str(r)[:60]}")
        except Exception as e:
            print(f"FAIL {prov}/{model} -> {str(e)[:140]}")

asyncio.run(main())
