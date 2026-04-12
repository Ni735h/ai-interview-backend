from fastapi import FastAPI
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
import requests
import os
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("OPENROUTER_API_KEY")

app = FastAPI()


@app.get("/")
def home():
    return {"message": "Backend running ✅"}


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class QuestionRequest(BaseModel):
    role: str
    level: str


class EvaluateRequest(BaseModel):
    questions: list[str]
    answers: list[str]


def fallback_role_questions(role: str) -> str:
    role_lower = role.lower()

    if "python" in role_lower:
        return (
            "1. What is the difference between a list and a tuple in Python?\n"
            "2. What are decorators in Python?\n"
            "3. How does exception handling work in Python?\n"
            "4. What is the difference between deep copy and shallow copy in Python?\n"
            "5. Explain OOP concepts in Python with an example."
        )

    if "java" in role_lower:
        return (
            "1. What is the difference between JDK, JRE, and JVM?\n"
            "2. What is method overloading and method overriding in Java?\n"
            "3. What is the difference between ArrayList and LinkedList?\n"
            "4. Explain exception handling in Java.\n"
            "5. What are the main OOP concepts in Java?"
        )

    if "flutter" in role_lower:
        return (
            "1. What is the difference between StatelessWidget and StatefulWidget?\n"
            "2. What is BuildContext in Flutter?\n"
            "3. How does setState work in Flutter?\n"
            "4. What is the difference between hot reload and hot restart?\n"
            "5. What is pubspec.yaml used for?"
        )

    return (
        "1. Tell me about your role and responsibilities.\n"
        "2. What are the main skills required for this role?\n"
        "3. Describe a project you worked on.\n"
        "4. What challenges have you faced in your work?\n"
        "5. How do you solve problems in your field?"
    )


@app.post("/generate-questions")
async def generate_questions(data: QuestionRequest):
    try:
        if not API_KEY:
            return {"questions": fallback_role_questions(data.role)}

        prompt = f"""
Generate exactly 5 interview questions for the role: {data.role}

Difficulty level: {data.level}

Rules:
- Questions must be strictly related to {data.role}
- Do not ask generic HR questions like "Tell me about yourself"
- Do not ask repeated questions
- Questions must match {data.level} difficulty
- Keep questions short, clear, and professional
- Return only a numbered list from 1 to 5
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
                    {
                        "role": "system",
                        "content": "You are an expert technical interviewer."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
            },
            timeout=10,
        )

        result = response.json()
        print("QUESTION RESPONSE:", result)

        if "choices" not in result:
            return {"questions": fallback_role_questions(data.role)}

        content = result["choices"][0]["message"]["content"].strip()

        if not content:
            return {"questions": fallback_role_questions(data.role)}

        return {"questions": content}

    except Exception as e:
        print("QUESTION ERROR:", e)
        return {"questions": fallback_role_questions(data.role)}


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
            return {
                "result": f"""Attempted: 0/{total}

Score: 0/10

Overall Feedback:
The candidate did not attempt any interview questions, so performance could not be evaluated.

Strengths:
- Interview session started successfully.

Improvements:
- Attempt the questions instead of leaving them blank.
- Speak clearly and answer in complete sentences.
- Give practical examples where possible.

Final Verdict:
Needs improvement before a proper assessment can be made."""
            }

        qa_text = "\n\n".join([
            f"Question: {q}\nAnswer: {a}" for q, a in attempted
        ])

        if not API_KEY:
            fallback_score = round((attempt_count / total) * 10, 1)
            return {
                "result": f"""Attempted: {attempt_count}/{total}

Score: {fallback_score}/10

Overall Feedback:
The interview was partially evaluated using fallback logic because AI evaluation is unavailable.

Strengths:
- Attempted multiple questions.
- Participated in the interview flow.
- Showed willingness to answer.

Improvements:
- Give more complete and confident answers.
- Add practical examples from projects or experience.
- Improve clarity and structure.

Final Verdict:
Decent attempt, but needs stronger responses."""
            }

        prompt = f"""
You are a professional interview evaluator.

A candidate attempted {attempt_count} out of {total} questions.

Evaluate the interview based only on the attempted answers.

Judge:
- Communication skills
- Confidence
- Clarity
- Technical relevance
- Practical understanding
- Whether answers are genuine, weak, or strong

Give the response in exactly this format:

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
                "model": "openrouter/auto",
                "messages": [
                    {
                        "role": "system",
                        "content": "You are a strict but fair interview evaluator."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
            },
            timeout=12,
        )

        result = response.json()
        print("EVALUATE RESPONSE:", result)

        if "choices" not in result:
            raise Exception("Invalid API response")

        content = result["choices"][0]["message"]["content"].strip()

        if not content:
            raise Exception("Empty evaluation content")

        return {"result": content}

    except Exception as e:
        print("EVALUATION ERROR:", e)

        fallback_total = len(data.questions)
        fallback_attempted = len([a for a in data.answers if a.strip() != ""])
        fallback_score = round((fallback_attempted / fallback_total) * 10, 1) if fallback_total > 0 else 0

        return {
            "result": f"""Attempted: {fallback_attempted}/{fallback_total}

Score: {fallback_score}/10

Overall Feedback:
There was an error while generating the detailed AI evaluation, but the interview attempt was recorded.

Strengths:
- The interview was completed.
- Answers were submitted for evaluation.
- Participation was captured correctly.

Improvements:
- Try again for a full AI-generated review.
- Answer more questions completely.
- Speak with more clarity and confidence.

Final Verdict:
Interview completed, but detailed evaluation used fallback logic."""
        }