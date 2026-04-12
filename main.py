from fastapi import FastAPI
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
import requests
import os
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("OPENROUTER_API_KEY")

app = FastAPI()

# ✅ ROOT ROUTE (IMPORTANT)
@app.get("/")
def home():
    return {"message": "Backend running ✅"}

# ✅ CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -----------------------------

class QuestionRequest(BaseModel):
    role: str
    level: str


class EvaluateRequest(BaseModel):
    questions: list[str]
    answers: list[str]


# 🔥 GENERATE QUESTIONS
@app.post("/generate-questions")
async def generate_questions(data: QuestionRequest):
    try:
        if not API_KEY:
            return {"error": "API KEY NOT FOUND ❌"}

        prompt = f"""
Generate 10 interview questions for a {data.role} candidate.

Difficulty level: {data.level}

Return only a numbered list.
"""

        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": "openrouter/auto",  # ✅ FIXED
                "messages": [
                    {"role": "user", "content": prompt}
                ],
            },
            timeout=15,  # ✅ FIXED
        )

        result = response.json()

        print("API RESPONSE:", result)

        if "choices" not in result:
            return {
                "questions": "1. Tell me about yourself\n2. Why do you want this job?\n3. What are your strengths?\n4. Describe a project\n5. How do you solve problems?"
            }

        return {
            "questions": result["choices"][0]["message"]["content"]
        }

    except Exception as e:
        print("ERROR:", e)
        return {"error": str(e)}


# 🔥 EVALUATE ANSWERS
@app.post("/evaluate")
async def