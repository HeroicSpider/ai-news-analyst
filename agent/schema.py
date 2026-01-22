from typing import List
from pydantic import BaseModel, Field, field_validator

class StoryAnalysis(BaseModel):
    bullets: List[str] = Field(description="Summary bullets. Empty list if context insufficient.")

    @field_validator('bullets')
    def check_bullet_count(cls, v):
        if len(v) == 0: return v
        if not (2 <= len(v) <= 3):
            raise ValueError(f"Bullet count {len(v)} is out of bounds (must be 0 or 2-3).")
        return v
