import json
from pathlib import Path
from typing import Any

from services.database import (
    import_recommendations,
    initialize_database,
)


AI_RECOMMENDATIONS_FILE = Path(
    "jobs_ai_recommended.json"
)


def load_recommendations() -> list[dict[str, Any]]:
    if not AI_RECOMMENDATIONS_FILE.exists():
        print(
            "Arquivo jobs_ai_recommended.json "
            "não encontrado."
        )
        return []

    try:
        content = AI_RECOMMENDATIONS_FILE.read_text(
            encoding="utf-8"
        )

        data = json.loads(content)

    except json.JSONDecodeError as error:
        print(
            "Erro ao interpretar "
            "jobs_ai_recommended.json:"
        )
        print(error)
        return []

    except OSError as error:
        print(
            "Erro ao ler "
            "jobs_ai_recommended.json:"
        )
        print(error)
        return []

    if not isinstance(data, list):
        print(
            "O arquivo de recomendações "
            "não contém uma lista."
        )
        return []

    return data


def main() -> None:
    initialize_database()

    recommendations = load_recommendations()

    if not recommendations:
        print(
            "Nenhuma recomendação disponível "
            "para sincronização."
        )
        return

    imported = import_recommendations(
        recommendations
    )

    print("=" * 60)
    print("JOBHUNTER — DATABASE SYNC")
    print("=" * 60)
    print(
        f"Análises encontradas: {len(recommendations)}"
    )
    print(
        f"Vagas elegíveis importadas: {imported}"
    )
    print(
        "Banco atualizado: data/jobhunter.db"
    )
    print("=" * 60)


if __name__ == "__main__":
    main()