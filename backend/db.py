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

# db.py'nin sonuna eklenecek

def get_all_users():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT id FROM users ORDER BY created_at;")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return [row[0] for row in rows]


def create_user(user_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT id FROM users WHERE id = %s;", (user_id,))
    if cur.fetchone():
        cur.close()
        conn.close()
        return False  # zaten var

    cur.execute("INSERT INTO users (id) VALUES (%s);", (user_id,))
    conn.commit()
    cur.close()
    conn.close()
    return True


def get_user_chats(user_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT id, title, created_at FROM chats WHERE user_id = %s ORDER BY created_at DESC;",
        (user_id,)
    )
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return [{"id": str(r[0]), "title": r[1], "created_at": r[2].isoformat()} for r in rows]


def create_chat(user_id, title):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO chats (user_id, title) VALUES (%s, %s) RETURNING id;",
        (user_id, title)
    )
    chat_id = cur.fetchone()[0]
    conn.commit()
    cur.close()
    conn.close()
    return str(chat_id)


def get_chat_messages(chat_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT role, sent_from, content, blocked, created_at FROM messages WHERE chat_id = %s ORDER BY created_at;",
        (chat_id,)
    )
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return [
        {
            "role": r[0],
            "sent_from": r[1],
            "content": r[2],
            "blocked": r[3],
            "created_at": r[4].isoformat(),
        }
        for r in rows
    ]


def save_message(chat_id, role, sent_from, content, blocked, created_at):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO messages (chat_id, role, sent_from, content, blocked, created_at) VALUES (%s, %s, %s, %s, %s, %s);",
        (chat_id, role, sent_from, content, blocked, created_at)
    )
    conn.commit()
    cur.close()
    conn.close()


def delete_chat(chat_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM messages WHERE chat_id = %s;", (chat_id,))
    cur.execute("DELETE FROM chats WHERE id = %s;", (chat_id,))
    conn.commit()
    cur.close()
    conn.close()


if __name__ == "__main__":
    init_db()