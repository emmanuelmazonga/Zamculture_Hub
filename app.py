import os
from flask import Flask, render_template, request, redirect, session, flash
from flask_session import Session
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from cs50 import SQL

app = Flask(__name__)

# set secret key for sessions
app.secret_key = os.urandom(24)


# confihure CS50 Library to use SQLite database
db = SQL("sqlite:///zamculture.db")

@app.route("/")
def index():
    """Render the homepage with featured and latest stories."""

    # fetch featured stories
    featured_stories = db.execute("""
        SELECT stories.id,
               stories.title,
               users.username AS author,
               stories.category,
               stories.image_path,
               stories.created_at,
               stories.content
        FROM stories
        JOIN users ON stories.user_id = users.id
        WHERE stories.approved = 1
        ORDER BY stories.created_at DESC
        LIMIT 3;
    """)
    # fetch latest stories
    latest_stories = db.execute("""
        SELECT stories.id,
               stories.title,
               users.username AS author,
               stories.category,
               stories.image_path,
               stories.created_at,
               stories.content
        FROM stories
        JOIN users ON stories.user_id = users.id
        WHERE stories.approved = 1
        ORDER BY stories.created_at DESC
        LIMIT 9;
    """)

    # convert created_at to readable format
    for story in featured_stories + latest_stories:
        if isinstance(story['created_at'], str):
            story['created_at'] = datetime.strptime(story['created_at'], '%Y-%m-%d %H:%M:%S')

    return render_template("index.html", featured_stories=featured_stories, latest_stories=latest_stories)

@app.route("/register", methods=["GET", "POST"])
def register():
    """Register a new user."""
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        confirmation = request.form.get("confirmation")

        # Validate input
        if not username or not password or not confirmation:
            flash("enter all fields")
            return redirect("/register")
        
        if password != confirmation:
            flash("passowrd mismatch")
            return redirect("/register")
        
        #check if user exists
        rows = db.execute("SELECT * FROM users WHERE username = ?", username)
        if len(rows) != 0:
            flash("username taken")
            return redirect("/register")
        
        # inserrt
        hash_pw = generate_password_hash(password)
        db.execute("INSERT INTO users (username, hash) VALUES (?, ?)", username, hash_pw)

        flash("registered successfully")
        return redirect("/login")
    
    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():

    # forget any user_id
    session.clear()
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        # Validate input
        if not username or not password:
            flash("Must provide username and password")
            return redirect("/login")
        
        # check if user exists
        rows = db.execute("SELECT * FROM users WHERE username = ?", username)
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], password):
            flash("invalid username and/or password")
            return redirect("/login")
        
        # remember user
        session["user_id"] = rows[0]["id"]

        flash("logged in successfully")
        return redirect("/")
    return render_template("login.html")

@app.route("/logout")
def logout():
    """Log user out."""
    session.clear()
    flash("logged out successfully")
    return redirect("/")

@app.route("/submit", methods=["GET", "POST"])
def submit():
    # For now, just render a placeholder template
    return render_template("submit.html")


if __name__ == "__main__":
    app.run(debug=True)