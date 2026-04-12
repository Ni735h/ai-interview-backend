from fastapi import FastAPI
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
import requests
import os
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("OPENROUTER_API_KEY")

app = FastAPI()

# ✅ ROOT ROUTE
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
        # ✅ fallback if API key missing
        if not API_KEY:
            return {
                "questions": "1. Tell me about yourself\n2. Why do you want this job?\n3. What are your strengths?\n4. Describe a project\n5. How do you solve problems?"
            }

        prompt = f"Generate 5 interview questions for a {data.role} ({data.level}) candidate."

        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": "openrouter/auto",
                "messages": [
                    {"role": "user", "content": prompt}
                ],
            },
            timeout=10,  # 🔥 fast timeout
        )

        result = response.json()
        print("QUESTION RESPONSE:", result)

        if "choices" not in result:
            raise Exception("Invalid API response")

        return {
            "questions": result["choices"][0]["message"]["content"]
        }

    except Exception as e:
        print("ERROR:", e)

        # 🔥 always return fallback (never hang)
        return {
            "questions": "1. Tell me about yourself\n2. Why do you want this job?\n3. What are your strengths?\n4. Describe a project\n5. How do you solve problems?"
        }


# 🔥 EVALUATE ANSWERS
@app.post("/evaluate")
async def evaluate(data: EvaluateRequest):
    try:
        attempted = [
            (q, a) for q, a in zip(data.questions, data.answers)
            if a.strip() != ""
        ]

        attempt_count = len(attempted)
        total = len(data.questions)

        if total == 0:
            return {"result": "No questions available."}

        if attempt_count == 0:
            return {"result": "You did not attempt any questions."}

        qa_text = "\n\n".join([
            f"Question: {q}\nAnswer: {a}" for q, a in attempted
        ])

        # ✅ fallback if API key missing
        if not API_KEY:
            return {
                "result": f"Attempted: {attempt_count}/{total}\nScore: 5/10\nFeedback: Improve answers."
            }

        prompt = f"""
Evaluate this interview:

{qa_text}

Give:
- Score out of 10
- Feedback
- Strengths
- Improvements
"""

        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": "openrouter/auto",
                "messages": [
                    {"role": "user", "content": prompt}
                ],
            },
            timeout=12,
        )

        result = response.json()
        print("EVAL RESPONSE:", result)

        if "choices" not in result:
            raise Exception("Invalid API response")

        return {
            "result": result["choices"][0]["message"]["content"]
        }

    except Exception as e:
        print("ERROR:", e)

        # 🔥 fallback (never hang)
        return {
            "result": f"Attempted: {len(data.answers)}/{len(data.questions)}\nScore: 5/10\nBasic feedback generated."
        }