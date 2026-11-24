from config import generate
from pydantic import BaseModel


class TestResponse(BaseModel):
    message: str


try:
    print("Testing Gemini connection...")

    result = generate(
        instruction="Reply with a short greeting.",
        payload={"task": "Say hello"},
        schema=TestResponse
    )

    print("SUCCESS!")
    print(result.message)

except Exception as e:
    print("FAILED!")
    print(e)