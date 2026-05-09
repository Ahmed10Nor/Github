import asyncio
from dotenv import load_dotenv
load_dotenv()
from google import genai
from google.genai import types as genai_types
import os

GEMINI_KEY = os.getenv("GEMINI_API_KEY", "")
client = genai.Client(api_key=GEMINI_KEY)

msg = 'أنا أحمد، أريد تعلم Python، مستواي مبتدئ'
prompt = (
    f'استخلص من رسالة المستخدم:\n"{msg}"\n\n'
    'JSON فقط:\n'
    '{"name":"","goal":"","category":"academic","level":null,"hours_per_day":1.0,"days_per_week":5}'
)

async def test():
    config = genai_types.GenerateContentConfig(max_output_tokens=500)
    response = await client.aio.models.generate_content(
        model="gemini-flash-latest",
        contents=prompt,
        config=config,
    )
    print('finish_reason:', response.candidates[0].finish_reason)
    print('RAW:', repr(response.text))

asyncio.run(test())
