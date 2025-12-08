import os
from flask import Flask, render_template, request, redirect, session, flash
from flask_session import Session
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from cs50 import SQL

app = Flask(__name__)

# confihure CS50 Library to use SQLite database
db = SQL("sqlite:///zamculture.db")

@app.route("/")
def index():
    """Render the homepage with featured and latest stories."""

    # fetch featured stories
    featured_stories = db.execute("""
        SELECT id, title, author, category, image_path, created_at, content
        FROM stories
        WHERE approved = 1
        ORDER BY created_at DESC
        LIMIT 3
    """)
    # fetch latest stories
    latest_stories = db.execute("""
        SELECT id, title, author, category, image_path, created_at, content
        FROM stories
        WHERE approved = 1
        ORDER BY created_at DESC
        LIMIT 9
    """)

    # convert created_at to readable format
    for story in featured_stories + latest_stories:
        if isinstance(story['created_at'], str):
            story['created_at'] = datetime.strptime(story['created_at'], '%Y-%m-%d %H:%M:%S')

    return render_template("index.html", featured_stories=featured_stories, latest_stories=latest_stories)