from user_manager import user_manager, UserRole
from config import ADMIN_USER_IDS

def initialize_users():
    # Set up admin users
    for admin_id in ADMIN_USER_IDS:
        if not user_manager.get_user(admin_id):
            user_manager.add_user(
                user_id=admin_id,
                username="admin",  # This will be updated on first login
                role=UserRole.ADMIN
            )
            print(f"Added admin user: {admin_id}")
    
    # Add regular users
    regular_users = [
        (123456789, "user1"),
        (987654321, "user2"),
    ]
    
    for user_id, username in regular_users:
        if not user_manager.get_user(user_id):
            user_manager.add_user(
                user_id=user_id,
                username=username,
                role=UserRole.USER  # This sets them as regular users
            )
            print(f"Added regular user: {user_id}")

if __name__ == "__main__":
    initialize_users() 