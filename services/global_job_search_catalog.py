from __future__ import annotations


GLOBAL_JOB_SEARCH_CATALOG = {
    "Engineering & Development": {
        "Software Engineering": [
            "software engineer",
            "software developer",
        ],
        "Backend Development": [
            "backend developer",
            "backend engineer",
        ],
        "Frontend Development": [
            "frontend developer",
            "frontend engineer",
        ],
        "Full Stack Development": [
            "full stack developer",
            "full stack engineer",
        ],
        "DevOps / Cloud": [
            "devops engineer",
            "cloud engineer",
        ],
        "QA / Testing": [
            "qa engineer",
            "software tester",
        ],
    },

    "Data & Analytics": {
        "Data Analysis": [
            "data analyst",
            "data analytics",
        ],
        "Business Intelligence": [
            "business intelligence analyst",
            "bi analyst",
        ],
        "Data Engineering": [
            "data engineer",
        ],
        "Data Science": [
            "data scientist",
        ],
    },

    "IT & Technical Support": {
        "Technical Support": [
            "technical support",
            "support engineer",
            "technical support engineer",
        ],
        "Application Support": [
            "application support",
            "application support analyst",
        ],
        "IT Support": [
            "it support",
            "it support engineer",
        ],
        "Systems Support": [
            "systems support",
            "systems support analyst",
        ],
    },

    "Customer Support": {
        "Customer Service": [
            "customer service",
            "customer support",
        ],
        "Customer Operations": [
            "customer operations",
            "customer operations specialist",
        ],
        "Customer Success": [
            "customer success",
            "customer success specialist",
        ],
        "Seller Support": [
            "seller support",
            "merchant support",
        ],
    },

    "Operations": {
        "Operations": [
            "operations specialist",
            "operations analyst",
        ],
        "Process Improvement": [
            "process improvement",
            "process analyst",
        ],
        "Business Operations": [
            "business operations",
            "business operations analyst",
        ],
        "Service Operations": [
            "service operations",
            "service operations analyst",
        ],
    },

    "Fraud & Risk": {
        "Fraud Operations": [
            "fraud operations",
            "fraud analyst",
        ],
        "Fraud Analysis": [
            "fraud analysis",
            "fraud investigator",
        ],
        "Trust & Safety": [
            "trust and safety",
            "trust & safety",
        ],
        "Risk Operations": [
            "risk operations",
            "risk analyst",
        ],
        "Payments Risk": [
            "payments risk",
            "payment risk analyst",
        ],
    },

    "Compliance": {
        "Compliance": [
            "compliance analyst",
            "compliance specialist",
        ],
        "AML / KYC": [
            "aml analyst",
            "kyc analyst",
        ],
        "Financial Crime": [
            "financial crime analyst",
            "financial crime operations",
        ],
        "Regulatory Operations": [
            "regulatory operations",
            "regulatory analyst",
        ],
    },

    "Finance": {
        "Accounting": [
            "accountant",
            "accounting analyst",
        ],
        "Financial Analysis": [
            "financial analyst",
        ],
        "Payments": [
            "payments analyst",
            "payments operations",
        ],
        "Banking Operations": [
            "banking operations",
            "banking operations analyst",
        ],
    },

    "Sales": {
        "Sales": [
            "sales representative",
            "sales executive",
        ],
        "Account Management": [
            "account manager",
        ],
        "Business Development": [
            "business development",
            "business development representative",
        ],
    },

    "Marketing": {
        "Marketing": [
            "marketing specialist",
            "marketing executive",
        ],
        "Content": [
            "content specialist",
            "content manager",
        ],
        "Growth Marketing": [
            "growth marketing",
            "growth marketer",
        ],
    },

    "Product": {
        "Product Management": [
            "product manager",
            "product owner",
        ],
        "Product Operations": [
            "product operations",
            "product operations specialist",
        ],
    },

    "Project / Program Management": {
        "Project Management": [
            "project manager",
            "project coordinator",
        ],
        "Program Management": [
            "program manager",
            "program coordinator",
        ],
    },

    "HR / Recruitment": {
        "Human Resources": [
            "human resources",
            "hr specialist",
        ],
        "Recruitment": [
            "recruiter",
            "recruitment consultant",
        ],
        "Talent Acquisition": [
            "talent acquisition",
            "talent acquisition specialist",
        ],
    },
}


def iter_global_search_queries():
    for category, sub_categories in (
        GLOBAL_JOB_SEARCH_CATALOG.items()
    ):
        for sub_category, queries in (
            sub_categories.items()
        ):
            for query in queries:
                yield {
                    "category": category,
                    "sub_category": sub_category,
                    "query": query,
                }
