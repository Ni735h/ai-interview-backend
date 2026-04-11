from fastapi import FastAPI
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
import requests
import os
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("OPENROUTER_API_KEY")

app = FastAPI()

# ✅ CORS FIX
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


# 🔥 Generate Questions
@app.post("/generate-questions")
async def generate_questions(data: QuestionRequest):
    try:
        prompt = f"""
Generate 10 interview questions for a {data.role} candidate.

Difficulty level: {data.level}

Rules:
- If level is easy, ask beginner-friendly and simple questions.
- If level is medium, ask practical and moderate-level questions.
- If level is hard, ask advanced and challenging questions.
- Return only a numbered list.
"""

        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": "openrouter/free",
                "messages": [
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
            },
            timeout=30,
        )

        result = response.json()

        if "choices" not in result:
            return {
                "questions": "1. Tell me about yourself\n2. Why are you interested in this role?\n3. Describe a project you worked on\n4. What are your strengths?\n5. How do you solve problems?\n6. What tools do you use?\n7. What challenges have you faced?\n8. How do you debug issues?\n9. What have you learned recently?\n10. Why should we hire you?"
            }

        return {
            "questions": result["choices"][0]["message"]["content"]
        }

    except Exception as e:
        return {"error": str(e)}


# 🔥 FINAL EVALUATION (FULL INTERVIEW SCORECARD)
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
            return {
                "result": "Attempted: 0/0\n\nScore: 0/10\n\nOverall Feedback:\nNo interview questions were available.\n\nStrengths:\n- None\n\nImprovements:\n- Try again with valid interview questions."
            }

        if attempt_count == 0:
            return {
                "result": f"""Attempted: 0/{total}

Score: 0/10

Overall Feedback:
The candidate did not attempt any interview questions, so performance could not be evaluated.

Strengths:
- Interview session was started successfully.

Improvements:
- Attempt the questions instead of leaving them blank.
- Speak clearly and answer in complete sentences.
- Try to give practical examples from projects or learning.

Final Verdict:
Needs improvement before a proper assessment can be made."""
            }

        qa_text = "\n\n".join([
            f"Question: {q}\nAnswer: {a}" for q, a in attempted
        ])

        prompt = f"""
You are a professional interview evaluator.

A candidate attempted {attempt_count} out of {total} questions.

Evaluate the interview based only on the attempted answers.

You must judge:
- Communication skills
- Confidence
- Clarity
- Technical relevance
- Practical understanding
- Whether the answers feel genuine or weak

Give the response in EXACTLY this format:

Attempted: {attempt_count}/{total}

Score: <number out of 10>

Overall Feedback:
<short paragraph>

Strengths:
- <point 1>
- <point 2>
- <point 3>

Improvements:
- <point 1>
- <point 2>
- <point 3>

Final Verdict:
<one short line>

Here are the attempted answers:

{qa_text}
"""

        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": "openrouter/free",
                "messages": [
                    {"role": "user", "content": prompt}
                ],
            },
            timeout=40,
        )

        result = response.json()

        if "choices" not in result:
            fallback_score = round((attempt_count / total) * 10, 1)
            return {
                "result": f"""Attempted: {attempt_count}/{total}

Score: {fallback_score}/10

Overall Feedback:
The interview was partially completed. The candidate attempted some questions, but AI evaluation could not be generated fully.

Strengths:
- Attempted multiple questions.
- Participated in the interview flow.
- Showed willingness to answer.

Improvements:
- Give more complete and confident answers.
- Add practical examples from projects or experience.
- Improve consistency across all questions.

Final Verdict:
Decent attempt, but needs stronger responses."""
            }

        return {
            "result": result["choices"][0]["message"]["content"]
        }

    except Exception as e:
        fallback_total = len(data.questions)
        fallback_attempted = len([
            a for a in data.answers if a.strip() != ""
        ])
        fallback_score = round((fallback_attempted / fallback_total) * 10, 1) if fallback_total > 0 else 0

        return {
            "result": f"""Attempted: {fallback_attempted}/{fallback_total}

Score: {fallback_score}/10

Overall Feedback:
There was an error while generating the detailed AI evaluation, but the interview attempt was recorded.

Strengths:
- The interview was completed.
- Answers were submitted for evaluation.
- The system captured participation correctly.

Improvements:
- Try again for a full AI-generated review.
- Answer more questions completely.
- Speak with more clarity and confidence.

Final Verdict:
Interview completed, but detailed evaluation failed due to a system error.

Error: {str(e)}"""
        }