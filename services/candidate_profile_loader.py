import json
from pathlib import Path

from models.candidate_profile import CandidateProfile


def load_candidate_profile(
    file_path: Path,
) -> CandidateProfile:
    if not file_path.exists():
        raise FileNotFoundError(
            f"Perfil do candidato não encontrado: {file_path}"
        )

    profile_data = json.loads(
        file_path.read_text(encoding="utf-8")
    )

    return CandidateProfile(**profile_data)


if __name__ == "__main__":
    base_dir = Path(__file__).resolve().parent.parent
    profile_file = base_dir / "candidate_profile.json"

    profile = load_candidate_profile(profile_file)

    print(profile)