from models.app_user import AppUser


class AccessPolicy:
    @staticmethod
    def can_access_candidate(
        user: AppUser,
        candidate_id: str,
    ) -> bool:
        if user.access_level == "admin":
            return True

        return user.candidate_id == candidate_id

    @staticmethod
    def can_view_all_users(
        user: AppUser,
    ) -> bool:
        return user.access_level == "admin"

    @staticmethod
    def can_manage_users(
        user: AppUser,
    ) -> bool:
        return user.access_level == "admin"
