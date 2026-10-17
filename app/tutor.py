"""Ustad's brain: understand the question and explain it in simple Urdu (one AI call)."""
from typing import Literal

from pydantic import BaseModel, Field

from app import config
from app.llm import generate_structured
from app.prompts import CHECK_ANSWER_PROMPT, SAFE_REFUSAL_URDU, TUTOR_SYSTEM_PROMPT

# Subjects Ustad recognises. Ustad can answer ANY question:
# anything that doesn't fit a listed subject is labelled "general".
Subject = Literal[
    # Core school subjects
    "maths", "english", "urdu", "islamiat", "computer",
    # Sciences
    "science", "physics", "chemistry", "biology",
    # Social subjects
    "social_studies", "pakistan_studies", "history", "geography",
    "economics", "civics",
    # Commerce
    "accounting", "business",
    # Everyday learning
    "health", "environment", "arts", "general",
]


class TutorReply(BaseModel):
    """Everything Ustad decides about a question, returned in ONE AI call.

    Before, 'understand' and 'explain' were two separate calls. Combining them
    halves the number of requests, which saves free quota and makes replies faster.
    """
    subject: Subject = Field(description="Best matching subject; 'general' if none fits")
    is_safe: bool = Field(description="False for violence, adult/sexual content, self-harm, drugs, hate, or requests for personal information")
    is_math_problem: bool = Field(description="True if a calculation must be solved")
    explanation_urdu: str = Field(description="Simple explanation in Urdu script; empty if not safe")
    check_question_urdu: str = Field(description="One simple question to check understanding, in Urdu; empty if not safe")
    expected_answer_urdu: str = Field(description="Short correct answer to the check question, in Urdu; empty if not safe")


def ask_ustad(question: str, image_bytes: bytes | None = None, image_mime: str | None = None) -> dict:
    """Understand + explain in a single call, then enforce safety in code.

    An optional picture (homework, textbook page, diagram, object) can be sent too.
    """
    if image_bytes:
        # With a picture, the question is optional: "explain this picture" by default
        user_text = (
            "The learner has shared a picture. "
            f"Learner's question about it: {question or 'Please explain this picture to me.'}"
        )
    else:
        user_text = question

    reply = generate_structured(
        TUTOR_SYSTEM_PROMPT, user_text, TutorReply,
        model=config.CHAT_MODEL, image_bytes=image_bytes, image_mime=image_mime,
    )

    # Safety is enforced here, not left to the model's wording:
    # unsafe questions always get our fixed, gentle refusal.
    if not reply.is_safe:
        return {
            "subject": reply.subject,
            "safe": False,
            "explanation_urdu": SAFE_REFUSAL_URDU,
            "check_question_urdu": "",
            "expected_answer_urdu": "",
        }

    return {
        "subject": reply.subject,
        "safe": True,
        "is_math_problem": reply.is_math_problem,
        "explanation_urdu": reply.explanation_urdu,
        "check_question_urdu": reply.check_question_urdu,
        "expected_answer_urdu": reply.expected_answer_urdu,
    }


class AnswerCheck(BaseModel):
    """Result of checking the learner's answer to the quiz question."""
    is_correct: bool = Field(description="True if the learner's answer is correct")
    feedback_urdu: str = Field(description="Short, kind feedback in Urdu, with the correct answer if wrong")


def check_answer(check_question: str, expected_answer: str, child_answer: str) -> AnswerCheck:
    """Compare the learner's answer with the expected answer and give feedback.

    This is an easy job, so it uses the lighter FAST_MODEL (its own free quota).
    """
    user_text = (
        f"Quiz question: {check_question}\n"
        f"Correct answer: {expected_answer}\n"
        f"Learner's answer: {child_answer}"
    )
    return generate_structured(CHECK_ANSWER_PROMPT, user_text, AnswerCheck, model=config.FAST_MODEL)