from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import os
import time
import psycopg2

app = FastAPI(title="Review Management Service")

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://coderaptor:coderaptor@postgres:5432/coderaptor")

@app.get("/health")
def health_check():
    return {"service": "review-service", "status": "ok"}

def init_db():
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute('''CREATE TABLE IF NOT EXISTS reviews
                           (id TEXT PRIMARY KEY,
                            username TEXT NOT NULL,
                            code TEXT,
                            review_output TEXT,
                            run_output TEXT,
                            fixed_code TEXT,
                            timestamp TEXT)''')
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

class ReviewData(BaseModel):
    id: str
    code: str
    review_output: str
    run_output: str
    fixed_code: str
    timestamp: str

@app.get("/reviews/{username}")
def get_reviews(username: str):
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute('''SELECT id, code, review_output, run_output, fixed_code, timestamp
                           FROM reviews WHERE username=%s ORDER BY timestamp DESC''', (username,))
            reviews = cur.fetchall()
    
    tabs = {}
    for review in reviews:
        tabs[review[0]] = {
            "code": review[1],
            "review_output": review[2],
            "run_output": review[3],
            "fixed_code": review[4],
            "timestamp": review[5],
            "editor_key": 0
        }
    return tabs

@app.post("/reviews/{username}")
def save_review(username: str, review: ReviewData):
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute('''INSERT INTO reviews
                           (id, username, code, review_output, run_output, fixed_code, timestamp)
                           VALUES (%s, %s, %s, %s, %s, %s, %s)
                           ON CONFLICT (id) DO UPDATE SET
                           username = EXCLUDED.username,
                           code = EXCLUDED.code,
                           review_output = EXCLUDED.review_output,
                           run_output = EXCLUDED.run_output,
                           fixed_code = EXCLUDED.fixed_code,
                           timestamp = EXCLUDED.timestamp''',
                        (review.id, username, review.code,
                         review.review_output, review.run_output,
                         review.fixed_code, review.timestamp))
        conn.commit()
    return {"message": "Review saved"}

@app.delete("/reviews/{tab_id}")
def delete_review(tab_id: str):
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute('DELETE FROM reviews WHERE id=%s', (tab_id,))
        conn.commit()
    return {"message": "Review deleted"}
