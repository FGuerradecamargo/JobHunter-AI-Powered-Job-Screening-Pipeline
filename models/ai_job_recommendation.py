from dataclasses import dataclass

from models.ai_recommendation import AIRecommendation
from models.job import Job


@dataclass
class AIJobRecommendation:
    job: Job
    analysis: AIRecommendation