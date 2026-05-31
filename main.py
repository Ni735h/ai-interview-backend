from fastapi import FastAPI
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from typing import List
import requests
import os
import re
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


# =========================
# REQUEST MODELS
# =========================
class QuestionRequest(BaseModel):
    role: str
    level: str


class EvaluateRequest(BaseModel):
    questions: List[str]
    answers: List[str]


class ChatbotRequest(BaseModel):
    message: str
    context: str = "dashboard"  # dashboard, interview, landing, onboarding


# =========================
# CONSTANTS
# =========================
COMMON_FIXED_QUESTIONS = [
    "Tell me about yourself.",
    "Why do you want this role?",
    "What are your strengths?",
    "What is your biggest weakness?"
]

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
MODEL_NAME = "openrouter/auto"


# =========================
# HELPERS
# =========================
def clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def parse_questions(text: str) -> List[str]:
    lines = text.splitlines()
    questions = []

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # Remove numbering or bullets like:
        # 1. question
        # 1) question
        # - question
        # • question
        line = re.sub(r"^\d+[\.\)]\s*", "", line)
        line = re.sub(r"^[-•*]\s*", "", line)
        line = clean_text(line)

        if len(line) >= 8:
            questions.append(line)

    # Remove duplicates while keeping order
    unique_questions = []
    seen = set()

    for q in questions:
        key = q.lower()
        if key not in seen:
            seen.add(key)
            unique_questions.append(q)

    return unique_questions


def generic_fallback_questions(role: str, level: str) -> List[str]:
    role = clean_text(role) if role else "General Candidate"
    level = clean_text(level) if level else "Beginner"

    return [
        f"What are the main responsibilities of a {role}?",
        f"What skills are most important for a {role} at {level} level?",
        f"What tools, technologies, or concepts are commonly used in {role}?",
        f"What are some common challenges faced in {role} work?",
        f"How would you solve a real-world problem in the role of {role}?",
        f"What makes someone successful in a {role} position?"
    ]


def call_openrouter(system_prompt: str, user_prompt: str, temperature: float = 0.7, timeout: int = 25) -> str:
    if not API_KEY:
        raise Exception("OPENROUTER_API_KEY not found")

    response = requests.post(
        OPENROUTER_URL,
        headers={
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "model": MODEL_NAME,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": temperature,
        },
        timeout=timeout,
    )

    result = response.json()
    print("OPENROUTER RESPONSE:", result)

    if "choices" not in result or not result["choices"]:
        raise Exception(f"Invalid OpenRouter response: {result}")

    content = result["choices"][0]["message"]["content"].strip()

    if not content:
        raise Exception("Empty content from OpenRouter")

    return content


# =========================
# CHATBOT ENDPOINT
# =========================
@app.post("/chatbot/ask")
async def chatbot_ask(data: ChatbotRequest):
    try:
        user_message = clean_text(data.message)
        context = data.context if data.context else "dashboard"

        if not user_message:
            return {"response": "Please ask me something! 🎯"}

        if not API_KEY:
            return {"response": get_fallback_chatbot_response(user_message, context)}

        system_prompt = f"""
You are a friendly, professional AI assistant for an Interview Practice App called "AI Mock Interview".

Current screen: {context}

Your personality:
- Friendly and encouraging 😊
- Helpful and knowledgeable
- Keep responses short (2-3 sentences max)
- Use emojis occasionally but not excessively
- Focus on interview preparation

App features you can explain:
- Mock interviews with AI
- Voice and text answers
- Face monitoring for confidence tracking
- Instant feedback and scoring
- Dashboard with performance stats
- Leaderboard to compare with others
- Interview history tracking

Rules:
- Never give harmful advice
- Stay focused on interview preparation
- Be honest when you don't know something
- Don't pretend to be a human interviewer
"""

        user_prompt = f"""
User asked: "{user_message}"

Context: User is on the {context} screen.

Respond in a friendly, helpful way about interview preparation or app features.
Keep it short (2-3 sentences). Use emojis naturally.
"""

        ai_response = call_openrouter(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0.7,
            timeout=15,
        )

        return {"response": ai_response}

    except Exception as e:
        print("CHATBOT ERROR:", e)
        fallback_response = get_fallback_chatbot_response(data.message, data.context)
        return {"response": fallback_response, "warning": "Using fallback response"}


def get_fallback_chatbot_response(message: str, context: str) -> str:
    lower_msg = message.lower().strip()
    
    # Greetings
    if any(word in lower_msg for word in ["hello", "hi", "hey", "greetings"]):
        return "Hello! 👋 I'm your AI assistant. How can I help with your interview preparation today?"
    
    # Help
    if "help" in lower_msg:
        return "I can help you with:\n• Starting interviews\n• Understanding your scores\n• Dashboard features\n• Leaderboard rankings\n• Interview tips\n\nWhat would you like to know? 🎯"
    
    # How to start interview
    if "start interview" in lower_msg or "how to practice" in lower_msg:
        return "To start an interview, click the 'Start Interview' button. Choose your role (e.g., Flutter Developer) and difficulty level, then answer questions using voice or text. Good luck! 🚀"
    
    # Score related
    if "score" in lower_msg or "rating" in lower_msg:
        return "Your interview scores range from 0 to 10. They're calculated based on answer relevance, completeness, and delivery. The higher the score, the better your performance! 📊"
    
    # Dashboard
    if "dashboard" in lower_msg or "stat" in lower_msg or "performance" in lower_msg:
        return "The Dashboard shows your total interviews, average score, questions attempted, attempt rate, and recent interview history. It's your personal performance tracker! 📈"
    
    # Leaderboard
    if "leaderboard" in lower_msg or "rank" in lower_msg or "top" in lower_msg:
        return "The Leaderboard shows top performers based on their average interview scores. Practice more to climb the ranks! 🏆"
    
    # Tips
    if "tip" in lower_msg or "advice" in lower_msg or "improve" in lower_msg:
        return "Interview tips: Use STAR method (Situation, Task, Action, Result), speak clearly, give specific examples, and take a moment to think before answering. You've got this! 💪"
    
    # Camera
    if "camera" in lower_msg or "face" in lower_msg:
        return "The camera feature helps analyze your facial expressions and eye contact during interviews. You can enable it in the interview setup. Look at the camera and smile! 📸"
    
    # Thank you
    if "thank" in lower_msg:
        return "You're welcome! 😊 Keep practicing and you'll ace your interviews! 🎉"
    
    # Goodbye
    if any(word in lower_msg for word in ["bye", "goodbye", "see you"]):
        return "Goodbye! 👋 Come back anytime to practice. Best of luck with your interviews! 🌟"
    
    # Delete interview
    if "delete" in lower_msg:
        return "You can delete any interview from your history by clicking the delete icon (trash can) next to it. This will automatically update your stats. 🗑️"
    
    # Context-specific responses
    if context == "dashboard":
        return "Welcome to your Dashboard! 📊 Here you can see your total interviews, average score, and recent history. Want to start a new interview or check the leaderboard? 🚀"
    elif context == "interview":
        return "You're in an interview session! 🎤 Speak clearly, take your time, and answer each question thoughtfully. You're doing great! 💪"
    elif context == "onboarding":
        return "Welcome to AI Mock Interview! 🎉 Let's set up your profile. Enter your name, choose practice time, and select your preferred language. Just 3 quick steps! ✨"
    elif context == "landing":
        return "Welcome to AI Mock Interview! 🎯 Practice with smart questions, get instant feedback, and improve your interview skills. Click Start Practice to begin! 🚀"
    
    # Default response
    return "I'm here to help! You can ask me about:\n\n📌 How to start an interview\n📌 Understanding your scores\n📌 Dashboard features\n📌 Leaderboard rankings\n📌 Interview tips & advice\n📌 Camera usage\n\nWhat would you like to know? 🎯"


# =========================
# GENERATE QUESTIONS
# 4 fixed + 6 AI-generated = 10 total
# =========================
@app.post("/generate-questions")
async def generate_questions(data: QuestionRequest):
    try:
        role = clean_text(data.role)
        level = clean_text(data.level)

        if not role:
            role = "General Candidate"

        system_prompt = """
You are an expert professional interviewer.

Your job is to generate high-quality interview questions based on the user's role and difficulty level.

Important rules:
- Questions must strictly match the role given by the user
- Do not ask generic HR questions unless requested
- Keep questions clear, short, professional, and interview-ready
- Avoid repeated questions
"""

        user_prompt = f"""
Generate exactly 6 interview questions.

Role: {role}
Difficulty Level: {level}

Strict instructions:
- Questions must be specifically relevant to the role "{role}"
- Match the difficulty level "{level}"
- Do NOT include these questions:
  1. Tell me about yourself
  2. Why do you want this role?
  3. What are your strengths?
  4. What is your biggest weakness?
- Do not repeat ideas
- Return only a numbered list from 1 to 6
"""

        ai_content = call_openrouter(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0.7,
            timeout=25,
        )

        ai_questions = parse_questions(ai_content)

        if len(ai_questions) < 6:
            ai_questions = generic_fallback_questions(role, level)

        ai_questions = ai_questions[:6]

        final_questions = COMMON_FIXED_QUESTIONS + ai_questions

        return {
            "role": role,
            "level": level,
            "questions": final_questions
        }

    except Exception as e:
        print("QUESTION ERROR:", e)

        role = clean_text(data.role) if data.role else "General Candidate"
        level = clean_text(data.level) if data.level else "Beginner"

        final_questions = COMMON_FIXED_QUESTIONS + generic_fallback_questions(role, level)[:6]

        return {
            "role": role,
            "level": level,
            "questions": final_questions,
            "warning": f"Fallback used because AI question generation failed: {str(e)}"
        }


# =========================
# EVALUATE ANSWERS
# FULL AI-BASED SCOREBOARD
# =========================
@app.post("/evaluate")
async def evaluate(data: EvaluateRequest):
    try:
        questions = data.questions or []
        answers = data.answers or []

        total = len(questions)

        if total == 0:
            return {"result": "No questions available."}

        qa_blocks = []
        attempted_count = 0

        for i, question in enumerate(questions, start=1):
            answer = answers[i - 1].strip() if i - 1 < len(answers) else ""

            if answer:
                attempted_count += 1
            else:
                answer = "[No answer provided]"

            qa_blocks.append(
                f"Question {i}: {question}\nAnswer {i}: {answer}"
            )

        qa_text = "\n\n".join(qa_blocks)

        if not API_KEY:
            return {
                "result": f"""Attempted: {attempted_count}/{total}

Score: 0/10

Overall Feedback:
AI evaluation is currently unavailable because the OpenRouter API key is missing or not configured properly.

Strengths:
- Interview session was completed.
- Questions and answers were captured successfully.
- The system recorded the interview attempt.

Improvements:
- Configure the OpenRouter API key correctly.
- Retry the interview evaluation once AI access is available.
- Submit complete and question-focused answers for accurate assessment.

Question-wise Notes:
- AI-based evaluation is unavailable at the moment.

Final Verdict:
Interview completed, but professional AI scorecard could not be generated."""
            }

        system_prompt = """
You are a professional interview evaluator.

Your job is to evaluate a candidate's interview answers strictly, fairly, and intelligently.

You must judge every answer based on:
- relevance to the exact question
- correctness
- clarity
- confidence
- completeness
- practical understanding
- technical depth where applicable

Important rules:
- Do NOT give marks blindly just because the candidate typed something.
- If an answer does not match the question, clearly say it is not aligned with the question.
- If an answer is random, meaningless, filler, vague, or non-serious, mention that professionally.
- If an answer is partially correct, say it is partially relevant or partially correct.
- If an answer is strong and relevant, say so.
- If no answer is provided, count it as unattempted.
- Score must depend on answer quality, relevance, and clarity, not only on how many answers were attempted.
- Be strict but fair.
"""

        user_prompt = f"""
Evaluate this interview carefully.

Total Questions: {total}
Attempted Questions: {attempted_count}

Interview Data:
{qa_text}

Return the result in EXACTLY this format:

Attempted: <attempted>/<total>

Relevant Answers: <number>
Partially Relevant Answers: <number>
Weak/Irrelevant Answers: <number>
Unattempted: <number>

Score: <number out of 10>

Overall Feedback:
<one professional paragraph>

Strengths:
- <point 1>
- <point 2>
- <point 3>

Improvements:
- <point 1>
- <point 2>
- <point 3>

Question-wise Notes:
- Q1: <short professional note>
- Q2: <short professional note>
- Q3: <short professional note>
- Q4: <short professional note>
- Q5: <short professional note>
- Q6: <short professional note>
- Q7: <short professional note>
- Q8: <short professional note>
- Q9: <short professional note>
- Q10: <short professional note>

Final Verdict:
<one short professional line>

Evaluation instructions:
- For each question, judge whether the answer matches the question or not.
- Mention if the response is unrelated to the question.
- Mention if the response is too weak, too vague, incomplete, or random.
- Mention if the response is strong and relevant.
- Mention if the response is partially relevant but lacks depth.
- Be professional, realistic, and fair.
- Do not inflate marks.
- The final score must depend on quality, relevance, clarity, and seriousness of the answers.
"""

        ai_result = call_openrouter(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0.3,
            timeout=40,
        )

        return {"result": ai_result}

    except Exception as e:
        print("EVALUATION ERROR:", e)

        fallback_total = len(data.questions) if data.questions else 0
        fallback_attempted = len([a for a in (data.answers or []) if a.strip() != ""])

        return {
            "result": f"""Attempted: {fallback_attempted}/{fallback_total}

Score: 0/10

Overall Feedback:
The interview data was captured, but the AI evaluator could not generate the professional scorecard because of a backend issue.

Strengths:
- The interview session was completed.
- Questions and answers were recorded successfully.
- The system captured the interview attempt correctly.

Improvements:
- Retry the evaluation once the backend issue is resolved.
- Ensure OpenRouter is available and responding properly.
- Re-run the scorecard generation for full AI-based feedback.

Question-wise Notes:
- Detailed AI-based evaluation could not be generated due to a backend error.

Final Verdict:
Interview completed, but AI scorecard generation failed."""
        }


# =========================
# CHATBOT TIP ENDPOINT
# =========================
@app.get("/chatbot/tip")
async def get_tip():
    tips = [
        "Use the STAR method: Situation, Task, Action, Result! 🌟",
        "Speak clearly and maintain eye contact with the camera! 👀",
        "Practice answering common questions in your field! 📝",
        "Record yourself to identify areas for improvement! 🎥",
        "Take deep breaths before answering to stay calm! 😌",
        "Research the company before your interview! 🔍",
        "Prepare 2-3 questions to ask the interviewer! ❓",
        "Dress professionally even for virtual interviews! 👔",
        "Test your camera and microphone before starting! 🎙️",
        "Use specific examples from your experience! 💼"
    ]
    import random
    return {"tip": random.choice(tips)}


# =========================
# CHATBOT QUOTE ENDPOINT
# =========================
@app.get("/chatbot/quote")
async def get_quote():
    quotes = [
        "Believe in yourself! You've got this! 💪",
        "Every expert was once a beginner! 🌱",
        "Practice makes progress, not perfection! 🎯",
        "Your next interview could be your best one yet! ✨",
        "Confidence comes from preparation! 📚",
        "Each interview is a learning opportunity! 🎓",
        "Stay positive and keep growing! 🌈",
        "You are capable of amazing things! ⭐"
    ]
    import random
    return {"quote": random.choice(quotes)}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5000)