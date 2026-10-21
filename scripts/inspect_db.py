import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import sqlite3
from app.config import Config

conn = sqlite3.connect('instance/feedback.db')
cursor = conn.cursor()
cursor.execute("SELECT name, sql FROM sqlite_master WHERE type='table';")
for name, sql in cursor.fetchall():
    print(f"TABLE: {name}")
    print(sql)
    print("-" * 60)
conn.close()
