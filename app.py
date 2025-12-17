import os
from flask import Flask, render_template, request, redirect, session, flash
from flask_session import Session
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime
from cs50 import SQL

app = Flask(__name__)

# set secret key for sessions
app.config["SECRET_KEY"] = os.urandom(24)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# confihure CS50 Library to use SQLite database
db = SQL("sqlite:///zamculture.db")
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
        user = rows[0]
        session["user_id"] = rows[0]["id"]
        session["role"] = user["role"]

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
    # submit a new story page
    if not session.get("user_id"):
        flash("login to submit a story")
        return redirect("/login")
    
    categories = db.execute("SELECT * FROM categories")
    
    if request.method == "POST":
        title = request.form.get("title")
        category = request.form.get("category")
        content = request.form.get("content")
        image = request.files.get("image") 

        if not title or not category or not content:
            flash("enter all fields")
            return redirect("/submit")
        
        image_path = None
        if image and image.filename != "":
            filename = secure_filename(image.filename)
            static_folder = os.path.join(app.root_path, 'static')
            image_folder = os.path.join(static_folder, 'images')
            image_path = f"images/{filename}"
            os.makedirs(image_folder, exist_ok=True)
            image.save(os.path.join(image_folder, filename))

        db.execute(
                    "INSERT INTO stories (user_id, title, category, content, image_path, approved, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    session["user_id"], title, category, content, image_path, 0, datetime.now()
        )

        flash("story submitted for review")
        return redirect("/")

    return render_template("submit.html", categories=categories)

@app.route("/story/<int:story_id>")
def story(story_id):
    """Render a specific story page."""

    user = session.get("user_id")

    story = db.execute("""
        SELECT stories.*, users.username AS author,
        COUNT(likes.id) AS like_count
        FROM stories
        JOIN users ON stories.user_id = users.id
        LEFT JOIN likes ON stories.id = likes.story_id
        WHERE stories.id = ? AND stories.approved = 1;
        """, story_id)  
        # if story not found show error
    if not story:
        return "story not found", 404
        
    story = story[0]

    # Get comments of the story
    comments = db.execute("""
        SELECT comments.content, comments.created_at, users.username AS author
        FROM comments
        JOIN users ON comments.user_id = users.id
        WHERE comments.story_id = ?
        ORDER BY comments.created_at ASC
        """, story_id)    
    return render_template("story.html", story=story, comments=comments, user=user)    

@app.route("/comment/<int:story_id>", methods=["POST"])
def comment(story_id):
    """Handle comment submision"""
    # check if user us logged in
    user = session.get("user_id")
    if not user:
        return redirect("/login")
    
    comment = request.form.get("comment")

    # Validate input
    if not comment:
        return redirect(f"/story/{story_id}")

    # Insert comment
    db.execute("""
        INSERT INTO comments (user_id, story_id, content)
        VALUES (?,?,?)
    """, session["user_id"], story_id, comment
    )
    return redirect(f"/story/{story_id}")

@app.route("/admin")
def admin():
    """admin approval page"""
    # check if user is logged in and is admin
    if not session.get("user_id"):
        flash("login to access admin page")
        return redirect("/login")
    
    #check if user is admin
    user = db.execute("SELECT * FROM users WHERE id = ?", session["user_id"])

    if not user or user[0]["role"] != "admin":
        flash("access denied")
        return redirect("/")

    # get unapproved stories
    stories = db.execute("""
        SELECT stories.id, stories.title, users.username AS author, stories.created_at, stories.content, stories.image_path, stories.category
        FROM stories
        JOIN users ON stories.user_id = users.id
        WHERE stories.approved = 0
        ORDER BY stories.created_at ASC;
    """)
    return render_template("admin.html", stories=stories)

@app.route("/approve/<int:story_id>")
def approve(story_id):
    """Approve a story route"""
    # must be logged in as admin
    if not session.get("user_id"):
        flash("login to access admin page")
        return redirect("/login")
    
    # confirm user is admin
    user = db.execute("SELECT * FROM users WHERE id = ?", session["user_id"])

    if not user or user[0]["role"] != "admin":
        flash("access denied")
        return redirect("/")
    
    # approve story
    db.execute("UPDATE stories SET approved = 1 WHERE id = ?", story_id)
    flash("Story approved successfully")
    return redirect("/admin")

@app.route("/like/<int:story_id>", methods=["POST"])
def like(story_id):
    # check if user is logged in
    if not session.get("user_id"):
        flash("login to like stories")
        return redirect("/login")

    db.execute("""
               INSERT OR IGNORE INTO likes (user_id, story_id)
               VALUES (?, ?)
               """, session["user_id"], story_id)
    return redirect(f"/story/{story_id}")

    

if __name__ == "__main__":
    app.run(debug=True)