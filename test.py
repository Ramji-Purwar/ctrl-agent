from core.api_pool import call_gemini

ques = input("Ask: ")

messages = [
    {"role": "user", "parts": [{"text": ques}]}
]

response = call_gemini(messages)
print(response.text)