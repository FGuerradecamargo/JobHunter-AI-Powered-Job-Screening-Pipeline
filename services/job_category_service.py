from __future__ import annotations

from dataclasses import dataclass


JOB_CATEGORIES = {
    "Engineering & Development": [
        "Software Engineering",
        "Backend Development",
        "Frontend Development",
        "Full Stack Development",
        "DevOps / Cloud",
        "QA / Testing",
    ],
    "Data & Analytics": [
        "Data Analysis",
        "Business Intelligence",
        "Data Engineering",
        "Data Science",
    ],
    "IT & Technical Support": [
        "Technical Support",
        "Application Support",
        "IT Support",
        "Systems Support",
    ],
    "Customer Support": [
        "Customer Service",
        "Customer Operations",
        "Customer Success",
        "Seller Support",
    ],
    "Operations": [
        "Operations",
        "Process Improvement",
        "Business Operations",
        "Service Operations",
    ],
    "Fraud & Risk": [
        "Fraud Operations",
        "Fraud Analysis",
        "Trust & Safety",
        "Risk Operations",
        "Payments Risk",
    ],
    "Compliance": [
        "Compliance",
        "AML / KYC",
        "Financial Crime",
        "Regulatory Operations",
    ],
    "Finance": [
        "Accounting",
        "Financial Analysis",
        "Payments",
        "Banking Operations",
    ],
    "Sales": [
        "Sales",
        "Account Management",
        "Business Development",
    ],
    "Marketing": [
        "Marketing",
        "Content",
        "Growth Marketing",
    ],
    "Product": [
        "Product Management",
        "Product Operations",
    ],
    "Project / Program Management": [
        "Project Management",
        "Program Management",
    ],
    "HR / Recruitment": [
        "Human Resources",
        "Recruitment",
        "Talent Acquisition",
    ],
    "Other": [
        "Other",
    ],
}


@dataclass(frozen=True)
class JobCategory:
    category: str
    sub_category: str


class JobCategoryService:
    CATEGORY_RULES = [
        (
            "Fraud & Risk",
            "Fraud Operations",
            [
                "fraud",
                "chargeback",
                "trust and safety",
                "trust & safety",
                "risk operations",
                "transaction review",
            ],
        ),
        (
            "Compliance",
            "AML / KYC",
            [
                "aml",
                "kyc",
                "compliance",
                "financial crime",
                "anti-money laundering",
            ],
        ),
        (
            "IT & Technical Support",
            "Technical Support",
            [
                "technical support",
                "application support",
                "support engineer",
                "technical support engineer",
                "troubleshooting",
                "incident support",
            ],
        ),
        (
            "Data & Analytics",
            "Data Analysis",
            [
                "data analyst",
                "data analysis",
                "business intelligence",
                "sql analyst",
                "reporting analyst",
            ],
        ),
        (
            "Engineering & Development",
            "Software Engineering",
            [
                "software engineer",
                "software developer",
                "backend developer",
                "frontend developer",
                "full stack",
                "python developer",
            ],
        ),
        (
            "Customer Support",
            "Customer Service",
            [
                "customer support",
                "customer service",
                "customer care",
                "seller support",
                "customer success",
            ],
        ),
        (
            "Operations",
            "Operations",
            [
                "operations analyst",
                "operations specialist",
                "business operations",
                "process improvement",
                "service operations",
            ],
        ),
        (
            "Product",
            "Product Management",
            [
                "product manager",
                "product owner",
                "product operations",
            ],
        ),
        (
            "Project / Program Management",
            "Project Management",
            [
                "project manager",
                "program manager",
                "project coordinator",
            ],
        ),
        (
            "Sales",
            "Sales",
            [
                "sales representative",
                "account executive",
                "business development",
                "sales manager",
            ],
        ),
        (
            "Marketing",
            "Marketing",
            [
                "marketing",
                "content marketing",
                "growth marketing",
                "seo",
            ],
        ),
        (
            "HR / Recruitment",
            "Recruitment",
            [
                "recruiter",
                "recruitment",
                "talent acquisition",
                "human resources",
            ],
        ),
    ]

    @staticmethod
    def categories() -> list[str]:
        return list(JOB_CATEGORIES.keys())

    @staticmethod
    def sub_categories(
        category: str,
    ) -> list[str]:
        return JOB_CATEGORIES.get(
            category,
            [],
        )

    def classify(
        self,
        title: str = "",
        description: str = "",
        raw_text: str = "",
    ) -> JobCategory:
        searchable_text = " ".join(
            [
                title or "",
                description or "",
                raw_text or "",
            ]
        ).lower()

        best_match = None
        best_score = 0

        for (
            category,
            sub_category,
            keywords,
        ) in self.CATEGORY_RULES:
            score = sum(
                1
                for keyword in keywords
                if keyword in searchable_text
            )

            if score > best_score:
                best_score = score
                best_match = JobCategory(
                    category=category,
                    sub_category=sub_category,
                )

        if best_match is not None:
            return best_match

        return JobCategory(
            category="Other",
            sub_category="Other",
        )
