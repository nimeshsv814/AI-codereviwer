from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel, EmailStr
import hashlib
import os
import time
import psycopg2
from psycopg2 import errors

app = FastAPI(title="Auth Service")

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://coderaptor:coderaptor@postgres:5432/coderaptor")

@app.get("/health")
def health_check():
    return {"service": "auth-service", "status": "ok"}

def init_db():
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute('''CREATE TABLE IF NOT EXISTS users
                           (username TEXT PRIMARY KEY,
                            email TEXT UNIQUE NOT NULL,
                            password TEXT NOT NULL)''')
        conn.commit()

def get_db_connection():
    for _ in range(10):
        try:
            return psycopg2.connect(DATABASE_URL)
        except psycopg2.OperationalError:
            time.sleep(2)
    return psycopg2.connect(DATABASE_URL)

# Initialize DB on startup
init_db()

def hash_password(password: str) -> str:
    salt = "anthropic_secure_salt"
    return hashlib.sha256((password + salt).encode()).hexdigest()

class UserAuth(BaseModel):
    email: EmailStr
    password: str

class UserRegister(BaseModel):
    username: str
    email: EmailStr
    password: str

@app.post("/register")
def register_user(user: UserRegister):
    if not user.username or not user.email or not user.password:
        raise HTTPException(status_code=400, detail="Username, email, and password required")
    
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    'INSERT INTO users (username, email, password) VALUES (%s, %s, %s)',
                    (user.username, str(user.email), hash_password(user.password)),
                )
            conn.commit()
        return {"message": "Registration successful"}
    except errors.UniqueViolation:
        raise HTTPException(status_code=400, detail="Username or email already exists")

@app.post("/login")
def login(user: UserAuth):
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute('SELECT username, password FROM users WHERE email=%s', (str(user.email),))
            result = cur.fetchone()
    
    if result and result[1] == hash_password(user.password):
        # In a full production system, return a JWT token here
        # For simplicity, returning a success flag
        return {"message": "Login successful", "username": result[0], "email": str(user.email)}
    else:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")
