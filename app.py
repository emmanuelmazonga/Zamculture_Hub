import os
from flask import Flask, render_template, request, redirect, session, flash
from flask_session import Session
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime
from cs50 import SQL
import feedparser

app = Flask(__name__)

# set secret key for sessions
app.config["SECRET_KEY"] = os.urandom(24)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)
# confihure CS50 Library to use SQLite database
DATABASE_URL = os.getenv("DATABASE_URL")

if DATABASE_URL:
    # Render/Postgres
    db = SQL(DATABASE_URL)
else:
    # Local development (SQLite)
    db = SQL("sqlite:///zamculture.db")

db.execute("SET timezone = 'UTC'")

# set secret key for sessions
app.secret_key = os.urandom(24)


@app.context_processor
def inject_category_counts():
    """Inject category counts into all templates."""
    
    rows = db.execute("""
        SELECT category, COUNT(*) AS count
        FROM stories
        WHERE approved = 1
        GROUP BY category;
    """)

    # change to dictionary
    category_counts = {row['category']: row['count'] for row in rows}

    return dict(category_counts=category_counts)

def get_story_image(story):
    """Get the image path for a story, or a default if none exists."""
    if story['image_path']:
        return story['image_path']

    category_defaults = {
            'Art': 'images/categories/art_story.jpg',
            'Music': 'images/categories/music_story.jpg',
            'Food': 'images/categories/food_story.jpg',
            'literature': 'images/categories/literature_story.jpg',
            'History': 'images/categories/history_story.jpg',
            'Travel': 'images/categories/travel_story.jpg'
    }
    return category_defaults.get(story['category'], 'images/categories/default_story.jpg')


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
        story['image_path'] = get_story_image(story)
        if isinstance(story['created_at'], str):
            story['created_at'] = datetime.strptime(story['created_at'], '%Y-%m-%d %H:%M:%S')

    return render_template("index.html", featured_stories=featured_stories, latest_stories=latest_stories)

@app.route("/about")
def about():
    """Render the about page."""
    return render_template("about.html")

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

    rows = db.execute("""
        SELECT stories.*, users.username AS author,
        COUNT(likes.id) AS like_count
        FROM stories
        JOIN users ON stories.user_id = users.id
        LEFT JOIN likes ON stories.id = likes.story_id
        WHERE stories.id = ? AND stories.approved = 1
        GROUP BY stories.id
        """, story_id)  
        # if story not found show error
    if not rows:
        return "story not found", 404
        
    story = rows[0]

    story['image_path'] = get_story_image(story)

    # convert created_at to readable format
    if isinstance(story['created_at'], str):
        story['created_at'] = datetime.strptime(story['created_at'], '%Y-%m-%d %H:%M:%S')

    # Get comments of the story
    comments = db.execute("""
        SELECT comments.content, comments.created_at, users.username AS author
        FROM comments
        JOIN users ON comments.user_id = users.id
        WHERE comments.story_id = ?
        ORDER BY comments.created_at ASC
        """, story_id) 
    # comment created_at to readable format
    for comment in comments:
        if isinstance(comment["created_at"], str):
            comment["created_at"] = datetime.strptime(comment["created_at"], "%Y-%m-%d %H:%M:%S")
       
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

    approved_stories = db.execute("""
        SELECT stories.id, stories.title, users.username AS author, stories.created_at, stories.content, stories.image_path, stories.category
        FROM stories
        JOIN users ON stories.user_id = users.id
        WHERE stories.approved = 1
        ORDER BY stories.created_at ASC;
    """)
    return render_template("admin.html", stories=stories, approved_stories=approved_stories)

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

@app.route("/category/<string:category>")
def category(category):
    # filter stories by category
    stories = db.execute("""
        SELECT stories.*, users.username AS author,
        (SELECT COUNT(*) FROM likes WHERE likes.story_id = stories.id) AS like_count
        FROM stories JOIN users ON stories.user_id = users.id
        WHERE stories.category = ? AND stories.approved = 1
        ORDER BY stories.created_at DESC
        """, category)
    
    # Format story dates
    for story in stories:
        story['image_path'] = get_story_image(story)
        if isinstance(story["created_at"], str):
            story["created_at"] = datetime.strptime(story["created_at"], "%Y-%m-%d %H:%M:%S")
            
    return render_template("category.html", stories=stories, category=category)

@app.route("/profile")
def profile():
    """ Show user's profile page """

    # check if user is logged in
    if not session.get("user_id"):
        flash("login required to access profile")
        return redirect("/login")
    user_id = session["user_id"]

    # Get user information
    user = db.execute("SELECT * FROM users WHERE id = ?", user_id)[0]
    
    # Get stories submitted by user
    stories = db.execute("""
    SELECT stories.id,
        stories.title,
        stories.category,
        stories.created_at,
        stories.approved,
        users.username,
        COUNT(likes.id) AS like_count
    FROM stories
    JOIN users ON stories.user_id = users.id
    LEFT JOIN likes ON stories.id = likes.story_id
    WHERE stories.user_id = ?
    GROUP BY stories.id, users.username
    ORDER BY stories.created_at DESC
""", session["user_id"])

    # convert created_at to readable format
    for story in stories:
        if isinstance(story['created_at'], str):
            story['created_at'] = datetime.strptime(story['created_at'], '%Y-%m-%d %H:%M:%S')
    return render_template("profile.html", user=user, stories=stories)

@app.route("/password", methods=["GET", "POST"])
def password():
    # check if user is logged  in
    if not session.get("user_id"):
        flash("login required to change password")
        return redirect("/login")
    
    if request.method == "POST":
        current_password = request.form.get("current_password")
        new_password = request.form.get("new_password")
        confirm_password = request.form.get("confirm_password")

        # server-side validation
        if not current_password or not new_password or not confirm_password:
            flash("all field required")
            return redirect("/password")

        if new_password != confirm_password:
            flash("Password mismatch")
            return redirect("/password")
        
        # get user's current hash
        user = db.execute(
            "SELECT * FROM users WHERE id = ?", session["user_id"]
        )[0]

        # curernt password
        if not check_password_hash(user["hash"], current_password):
            flash("current password incorrect")
            return redirect("/password")
        
        # change password
        new_hash = generate_password_hash(new_password)
        db.execute(
            "UPDATE users SET hash = ? WHERE id = ?", new_hash, session["user_id"]
        )

        flash("password changed successfully")
        return
    return render_template("password.html")



@app.route("/podcast")
def podcast():
    feed_url = "https://open.spotify.com/show/6iw09g8C70aBz7knGBUgzd?si=cc9c60f8726e414c"
    feed = feedparser.parse(feed_url)
    episodes = feed.entries[:10]  # Latest 10 episodes
    return render_template("podcast.html", episodes=episodes)




if __name__ == "__main__":
    app.run(debug=True)