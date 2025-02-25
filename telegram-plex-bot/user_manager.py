from enum import Enum
from typing import Dict, Optional, List, Any
import json
import os
import logging
from dataclasses import dataclass, asdict
from datetime import datetime

logger = logging.getLogger(__name__)

class UserRole(Enum):
    """User role enumeration for permission management"""
    USER = "user"
    ADMIN = "admin"

@dataclass
class User:
    """
    User data class to store user information
    
    Attributes:
        user_id: Unique Telegram user ID
        username: Telegram username
        role: User role (USER or ADMIN)
        max_file_size: Maximum allowed file size in bytes
        created_at: ISO format timestamp of when the user was created
        last_active: ISO format timestamp of when the user was last active
    """
    user_id: int
    username: str
    role: UserRole
    max_file_size: int  # in bytes
    created_at: str
    last_active: str

class UserManager:
    """
    Manages user registration, permissions, and activity tracking.
    Stores user data in a JSON file for persistence.
    """
    # Default file size limits
    DEFAULT_USER_SIZE_LIMIT = 53_687_091_200  # 50GB for regular users
    DEFAULT_ADMIN_SIZE_LIMIT = 1_099_511_627_776  # 1TB for admins
    
    def __init__(self, users_file="users.json"):
        """
        Initialize the user manager with the specified users file.
        
        Args:
            users_file: Path to the JSON file for storing user data
        """
        self.users_file = users_file
        self.users: Dict[int, User] = {}
        self.load_users()
    
    def load_users(self) -> None:
        """
        Load users from the JSON file.
        If the file doesn't exist or is invalid, an empty user dictionary is used.
        """
        try:
            if os.path.exists(self.users_file):
                with open(self.users_file, 'r') as f:
                    users_data = json.load(f)
                    for user_id, data in users_data.items():
                        try:
                            self.users[int(user_id)] = User(
                                user_id=int(user_id),
                                username=data['username'],
                                role=UserRole(data['role']),
                                max_file_size=data['max_file_size'],
                                created_at=data['created_at'],
                                last_active=data['last_active']
                            )
                        except (KeyError, ValueError) as e:
                            logger.error(f"Error loading user {user_id}: {e}")
                logger.info(f"Loaded {len(self.users)} users from {self.users_file}")
            else:
                logger.warning(f"Users file {self.users_file} not found. Starting with empty user list.")
        except Exception as e:
            logger.error(f"Failed to load users: {e}")
            # Continue with empty users dictionary
    
    def save_users(self) -> bool:
        """
        Save users to the JSON file.
        
        Returns:
            True if successful, False otherwise
        """
        try:
            users_data = {
                str(user_id): {
                    **asdict(user),
                    'role': user.role.value
                }
                for user_id, user in self.users.items()
            }
            
            # Create directory if it doesn't exist
            os.makedirs(os.path.dirname(os.path.abspath(self.users_file)), exist_ok=True)
            
            with open(self.users_file, 'w') as f:
                json.dump(users_data, f, indent=2)
            
            logger.debug(f"Saved {len(self.users)} users to {self.users_file}")
            return True
        except Exception as e:
            logger.error(f"Failed to save users: {e}")
            return False
    
    def add_user(self, user_id: int, username: str, role: UserRole = UserRole.USER) -> User:
        """
        Add a new user or update an existing user.
        
        Args:
            user_id: Telegram user ID
            username: Telegram username
            role: User role (defaults to regular USER)
            
        Returns:
            The created or updated User object
        """
        # Determine max file size based on role
        max_file_size = (
            self.DEFAULT_ADMIN_SIZE_LIMIT if role == UserRole.ADMIN 
            else self.DEFAULT_USER_SIZE_LIMIT
        )
        
        # Check if user already exists
        if existing_user := self.users.get(user_id):
            logger.info(f"Updating existing user: {user_id} ({username})")
            # Update username but keep other settings
            existing_user.username = username
            existing_user.last_active = datetime.now().isoformat()
            self.save_users()
            return existing_user
        
        # Create new user
        now = datetime.now().isoformat()
        user = User(
            user_id=user_id,
            username=username,
            role=role,
            max_file_size=max_file_size,
            created_at=now,
            last_active=now
        )
        
        self.users[user_id] = user
        logger.info(f"Added new user: {user_id} ({username}) with role {role.value}")
        self.save_users()
        return user
    
    def get_user(self, user_id: int) -> Optional[User]:
        """
        Get a user by ID.
        
        Args:
            user_id: Telegram user ID
            
        Returns:
            User object if found, None otherwise
        """
        return self.users.get(user_id)
    
    def update_last_active(self, user_id: int) -> bool:
        """
        Update the last active timestamp for a user.
        
        Args:
            user_id: Telegram user ID
            
        Returns:
            True if successful, False if user not found
        """
        if user := self.users.get(user_id):
            user.last_active = datetime.now().isoformat()
            self.save_users()
            return True
        return False
    
    def is_admin(self, user_id: int) -> bool:
        """
        Check if a user has admin privileges.
        
        Args:
            user_id: Telegram user ID
            
        Returns:
            True if the user is an admin, False otherwise
        """
        if user := self.get_user(user_id):
            return user.role == UserRole.ADMIN
        return False
    
    def can_access_file_size(self, user_id: int, file_size: int) -> bool:
        """
        Check if a user can access a file of the given size.
        
        Args:
            user_id: Telegram user ID
            file_size: File size in bytes
            
        Returns:
            True if the user can access the file, False otherwise
        """
        if user := self.get_user(user_id):
            return file_size <= user.max_file_size
        return False
    
    def set_user_role(self, user_id: int, role: UserRole) -> bool:
        """
        Set the role for a user.
        
        Args:
            user_id: Telegram user ID
            role: New role to assign
            
        Returns:
            True if successful, False if user not found
        """
        if user := self.get_user(user_id):
            user.role = role
            
            # Update max file size based on new role
            if role == UserRole.ADMIN:
                user.max_file_size = self.DEFAULT_ADMIN_SIZE_LIMIT
            
            self.save_users()
            logger.info(f"Updated user {user_id} role to {role.value}")
            return True
        return False
    
    def set_max_file_size(self, user_id: int, max_size: int) -> bool:
        """
        Set the maximum file size for a user.
        
        Args:
            user_id: Telegram user ID
            max_size: Maximum file size in bytes
            
        Returns:
            True if successful, False if user not found
        """
        if user := self.get_user(user_id):
            user.max_file_size = max_size
            self.save_users()
            logger.info(f"Updated user {user_id} max file size to {max_size} bytes")
            return True
        return False
    
    def get_all_users(self) -> List[User]:
        """
        Get all registered users.
        
        Returns:
            List of all User objects
        """
        return list(self.users.values())

# Create global instance
user_manager = UserManager() 