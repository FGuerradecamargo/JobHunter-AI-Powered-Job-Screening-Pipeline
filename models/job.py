from dataclasses import dataclass


# Representa uma vaga extraída dos alertas de e-mail.
@dataclass
class Job:
    id: str
    raw_text: str
    url: str