from uuid import uuid4
from pydantic import BaseModel, Field, ConfigDict, model_validator
from config import generate, StudyError


class Question(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    prompt: str = Field(min_length=5)
    topic: str
    options: list[str] = Field(min_length=4, max_length=4)
    correct_index: int = Field(ge=0, le=3, strict=True)
    explanation: str = Field(min_length=8)

    @model_validator(mode="after")
    def check_options(self):
        choices = {o.strip().casefold() for o in self.options}
        if "" in choices or len(choices) != 4:
            raise ValueError("Four distinct choices required")
        return self


class Questions(BaseModel):
    items: list[Question] = Field(min_length=1, max_length=10)


def generate_quiz(subject, topics, count, ask=generate):
    if not 1 <= count <= 10 or not topics:
        raise StudyError("Choose 1–10 questions and at least one topic.")
    batch = ask("Write an exam practice quiz on the supplied subject and listed topics. "
                "Use the exact topic labels, four plausible options, one unambiguous answer, "
                "a zero-based correct_index and an explanation of the reasoning. "
                "Return exactly the requested count of distinct questions.",
                dict(subject=subject, topics=topics, count=count), Questions)
    prompts = {q.prompt.casefold() for q in batch.items}
    if len(batch.items) != count or len(prompts) != count or any(q.topic not in topics for q in batch.items):
        raise StudyError("The generated quiz did not match your request. Please regenerate it.")
    return dict(id=uuid4().hex, subject=subject, items=[q.model_dump() for q in batch.items])


def evaluate(quiz, answers):
    if len(answers) != len(quiz["items"]) or any(type(i) is not int or i not in range(4) for i in answers):
        raise StudyError("Select one answer for every question before submitting.")
    review = [dict(**q, chosen=a, correct=a == q["correct_index"]) for q, a in zip(quiz["items"], answers)]
    return dict(id=quiz["id"], subject=quiz["subject"], score=sum(r["correct"] for r in review),
                total=len(review), review=review)
