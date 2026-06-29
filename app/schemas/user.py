from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class LoginRequest(BaseModel):
    username: str
    password: str
    turnstile_token: Optional[str] = None


class RegisterRequest(BaseModel):
    username: str
    password: str
    display_name: Optional[str] = None
    email: Optional[str] = None
    verification_code: Optional[str] = None


class UserResponse(BaseModel):
    id: int
    username: str
    display_name: Optional[str] = None
    email: Optional[str] = None
    role: int
    status: int
    balance: int = 0  # micro-yuan
    total_spent: float = 0.0  # yuan
    group: str
    created_at: Optional[int] = None
    updated_at: Optional[int] = None


class LoginResponse(BaseModel):
    id: int
    username: str
    display_name: Optional[str] = None
    role: int
    status: int
    balance: int = 0  # micro-yuan
    group: str
    access_token: Optional[str] = None


class SelfResponse(BaseModel):
    id: int
    username: str
    display_name: Optional[str] = None
    email: Optional[str] = None
    role: int
    status: int
    balance: int = 0  # micro-yuan
    group: str
    created_at: Optional[int] = None
    updated_at: Optional[int] = None


class UpdateSelfRequest(BaseModel):
    username: Optional[str] = None
    display_name: Optional[str] = None
    password: Optional[str] = None


class TokenResponse(BaseModel):
    id: int
    name: str
    key: str
    status: int
    created_time: int
    accessed_time: int
    expired_time: int
    models: Optional[str] = None
    subnet: Optional[str] = None
    created_at: Optional[int] = None
    updated_at: Optional[int] = None
