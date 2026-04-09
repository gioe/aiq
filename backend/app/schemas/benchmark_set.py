"""Pydantic schemas for benchmark set admin API."""

from datetime import datetime
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class CreateBenchmarkSetRequest(BaseModel):
    name: str = Field(
        ..., max_length=200, description="Unique name for the benchmark set."
    )
    description: Optional[str] = Field(None, description="Optional description.")
    question_ids: List[int] = Field(
        ...,
        min_length=1,
        description="Ordered list of question IDs to include.",
    )


class BenchmarkSetQuestionDetail(BaseModel):
    position: int
    question_id: int
    question_type: str
    difficulty_level: str
    question_text: str

    model_config = {"from_attributes": True}


class BenchmarkSetResponse(BaseModel):
    id: int
    name: str
    description: Optional[str]
    is_active: bool
    total_questions: int
    domain_distribution: Dict[str, int]
    difficulty_distribution: Dict[str, int]
    created_at: datetime
    updated_at: datetime


class BenchmarkSetDetailResponse(BenchmarkSetResponse):
    questions: List[BenchmarkSetQuestionDetail]


class BenchmarkSetListResponse(BaseModel):
    sets: List[BenchmarkSetResponse]
    total_count: int
