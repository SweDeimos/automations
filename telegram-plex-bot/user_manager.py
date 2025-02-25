from enum import Enum
from typing import Dict, Optional
import json
import os
from dataclasses import dataclass, asdict
from datetime import datetime

class UserRole(Enum):
    USER = "user"
    ADMIN = "admin"

@dataclass
class User:
    user_id: int
    username: str
    role: UserRole
    max_file_size: int  # in bytes
    created_at: str
    last_active: str

class UserManager:
    def __init__(self, users_file="users.json"):
        self.users_file = users_file
        self.users: Dict[int, User] = {}
        self.load_users()
    
    def load_users(self):
        if os.path.exists(self.users_file):
            with open(self.users_file, 'r') as f:
                users_data = json.load(f)
                for user_id, data in users_data.items():
                    self.users[int(user_id)] = User(
                        user_id=int(user_id),
                        username=data['username'],
                        role=UserRole(data['role']),
                        max_file_size=data['max_file_size'],
                        created_at=data['created_at'],
                        last_active=data['last_active']
                    )
    
    def save_users(self):
        users_data = {
            str(user_id): {
                **asdict(user),
                'role': user.role.value
            }
            for user_id, user in self.users.items()
        }
        with open(self.users_file, 'w') as f:
            json.dump(users_data, f, indent=2)
    
    def add_user(self, user_id: int, username: str, role: UserRole = UserRole.USER) -> User:
        max_file_size = 53_687_091_200 if role == UserRole.USER else 1_099_511_627_776  # 50GB for users, 1TB for admins
        user = User(
            user_id=user_id,
            username=username,
            role=role,
            max_file_size=max_file_size,
            created_at=datetime.now().isoformat(),
            last_active=datetime.now().isoformat()
        )
        self.users[user_id] = user
        self.save_users()
        return user
    
    def get_user(self, user_id: int) -> Optional[User]:
        return self.users.get(user_id)
    
    def update_last_active(self, user_id: int):
        if user := self.users.get(user_id):
            user.last_active = datetime.now().isoformat()
            self.save_users()
    
    def is_admin(self, user_id: int) -> bool:
        if user := self.get_user(user_id):
            return user.role == UserRole.ADMIN
        return False
    
    def can_access_file_size(self, user_id: int, file_size: int) -> bool:
        if user := self.get_user(user_id):
            return file_size <= user.max_file_size
        return False

# Create global instance
user_manager = UserManager() 