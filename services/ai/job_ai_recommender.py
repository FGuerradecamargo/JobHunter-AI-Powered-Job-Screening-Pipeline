from models.ai_job_recommendation import AIJobRecommendation


class JobAIRecommender:

    def __init__(self, recommendation_service):
        self.recommendation_service = recommendation_service

    def recommend(
        self,
        jobs,
        candidate_profile,
    ) -> list[AIJobRecommendation]:
        recommendations = []

        for job in jobs:
            analysis = self.recommendation_service.analyze(
                job,
                candidate_profile,
            )

            recommendations.append(
                AIJobRecommendation(
                    job=job,
                    analysis=analysis,
                )
            )

        return recommendations