import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

DB_HOST = os.getenv("POSTGRES_HOST", "localhost")
DB_PORT = os.getenv("POSTGRES_PORT", "5432")
DB_NAME = os.getenv("POSTGRES_DB", "chat_db")
DB_USER = os.getenv("POSTGRES_USER", "llmsecurity")
DB_PASSWORD = os.getenv("POSTGRES_PASSWORD")

def get_connection():
    return psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
    )


def init_db():

    conn = get_connection()
    cur = conn.cursor()

    
    cur.execute('CREATE EXTENSION IF NOT EXISTS "pgcrypto";')

    cur.execute("""CREATE TABLE IF NOT EXISTS users (id VARCHAR(255) PRIMARY KEY,created_at TIMESTAMP DEFAULT now());""")

    cur.execute("""CREATE TABLE IF NOT EXISTS chats (id UUID PRIMARY KEY DEFAULT gen_random_uuid(),user_id VARCHAR(255) REFERENCES users(id),title VARCHAR(255),created_at TIMESTAMP DEFAULT now());""")

    cur.execute("""CREATE TABLE IF NOT EXISTS messages (id UUID PRIMARY KEY DEFAULT gen_random_uuid(),chat_id UUID REFERENCES chats(id),role VARCHAR(20) NOT NULL,sent_from VARCHAR(255),content TEXT NOT NULL,blocked BOOLEAN DEFAULT false,created_at TIMESTAMP DEFAULT now());""")

    conn.commit()
    cur.close()
    conn.close()
    print("Db Success")


if __name__ == "__main__":
    init_db()