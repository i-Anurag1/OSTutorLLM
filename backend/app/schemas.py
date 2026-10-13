from typing import Literal

from pydantic import BaseModel, Field

EMAIL = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"


class RegisterIn(BaseModel):
    email: str = Field(pattern=EMAIL, max_length=255)
    password: str = Field(min_length=8, max_length=72)
    name: str = Field(min_length=1, max_length=120)


class LoginIn(BaseModel):
    email: str
    password: str


class ProfileIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)


class ChatIn(BaseModel):
    message: str = Field(min_length=2, max_length=4000)
    topic: str | None = None
    difficulty: Literal["easy", "medium", "hard", "adaptive"] = "adaptive"
    mode: Literal["teach", "socratic", "exam"] = "teach"
    conversation_id: int | None = None
    use_reranker: bool = True


class FeedbackIn(BaseModel):
    value: Literal[-1, 1]


class SearchIn(BaseModel):
    query: str = Field(min_length=2, max_length=500)
    k: int = Field(default=6, ge=1, le=20)
    source: str | None = None
    use_reranker: bool = True


class ProgressIn(BaseModel):
    topic: str
    score: float = Field(ge=0, le=100)
    activity: str = "quiz"


class QuizIn(BaseModel):
    topic: str
    difficulty: str = "any"
    count: int = Field(default=5, ge=1, le=20)
    kind: Literal["mcq", "viva"] = "mcq"


class QuizScoreIn(BaseModel):
    topic: str
    answers: dict[str, str]


class VivaIn(BaseModel):
    question_id: int
    answer: str = Field(max_length=4000)


class CPUIn(BaseModel):
    algorithm: str
    processes: list[dict] = Field(max_length=50)
    quantum: int = Field(default=2, ge=1, le=100)


class CompareIn(BaseModel):
    processes: list[dict] = Field(max_length=50)
    quantum: int = Field(default=2, ge=1, le=100)


class PageIn(BaseModel):
    algorithm: str
    reference_string: list[int] = Field(max_length=500)
    frames: int = Field(ge=1, le=20)


class PageCompareIn(BaseModel):
    reference_string: list[int] = Field(max_length=500)
    frames: int = Field(ge=1, le=20)


class BankerIn(BaseModel):
    allocation: list[list[int]]
    maximum: list[list[int]]
    available: list[int]
    request: dict | None = None


class DeadlockIn(BaseModel):
    allocation: list[list[int]]
    request: list[list[int]]
    available: list[int]


class DiskIn(BaseModel):
    algorithm: str
    requests: list[int] = Field(max_length=500)
    head: int
    disk_size: int = Field(default=200, ge=2, le=100000)
    direction: Literal["up", "down"] = "up"


class SyncIn(BaseModel):
    buffer_size: int = Field(ge=1, le=20)
    items: int = Field(ge=1, le=100)
    producer_period: int = Field(default=1, ge=1, le=10)
    consumer_period: int = Field(default=2, ge=1, le=10)


class DiningIn(BaseModel):
    n: int = Field(default=5, ge=2, le=8)
    strategy: str = "naive"
    meals: int = Field(default=2, ge=1, le=5)


class PagingIn(BaseModel):
    addresses: list[int] = Field(max_length=200)
    page_size: int = Field(default=4, ge=1)
    num_frames: int = Field(default=4, ge=1, le=64)
    tlb_size: int = Field(default=2, ge=0, le=16)


class SegIn(BaseModel):
    segments: list[dict]
    logical: list[dict]


class ThreadsIn(BaseModel):
    scenario: dict | None = None
    quantum: int = Field(default=2, ge=1, le=10)


class ShellIn(BaseModel):
    script: str = Field(max_length=4000)


class PythonIn(BaseModel):
    source: str = Field(max_length=8000)


class CodeTestIn(BaseModel):
    source: str = Field(max_length=8000)
    exercise_id: str | None = None
    expected_stdout: str = ""
    language: Literal["python", "shell"] = "python"
