import os
from flask import Flask, render_template, request, redirect, session, flash
from flask_session import Session
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime
from cs50 import SQL
import feedparser

app = Flask(__name__)

# Configure secret key and sessions
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY") or os.urandom(24)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure database
DATABASE_URL = "postgresql://zamculture_user:rkolBCyFvGDQhSJ4mUt2fa3U44InXVnT@dpg-d54ic615pdvs73bir6bg-a.frankfurt-postgres.render.com/zamculture_pxun"
if DATABASE_URL:
    # Render/Postgres
    db = SQL(DATABASE_URL)
else:
    # Local development (SQLite fallback)
    db = SQL("sqlite:///zamculture.db")

# Ensure timezone is UTC
db.execute("SET timezone = 'UTC'")

# --------------------------------------------------
# Context processor for category counts
# --------------------------------------------------
@app.context_processor
def inject_category_counts():
    """Inject category counts into all templates."""
    rows = db.execute("""
        SELECT category, COUNT(*) AS count
        FROM stories
        WHERE approved = TRUE
        GROUP BY category;
    """)
    category_counts = {row['category']: row['count'] for row in rows}
    return dict(category_counts=category_counts)

# --------------------------------------------------
# Helper function for story images
# --------------------------------------------------
def get_story_image(story):
    """Return story image path or category default."""
    if story.get('image_path'):
        return story['image_path']

    category_defaults = {
        'Art': 'images/categories/art_story.jpg',
        'Music': 'images/categories/music_story.jpg',
        'Food': 'images/categories/food_story.jpg',
        'Literature': 'images/categories/literature_story.jpg',
        'History': 'images/categories/history_story.jpg',
        'Travel': 'images/categories/travel_story.jpg'
    }
    return category_defaults.get(story.get('category'), 'images/categories/default_story.jpg')

# --------------------------------------------------
# Homepage
# --------------------------------------------------
@app.route("/")
def index():
    """Render homepage with featured and latest stories."""
    featured_stories = db.execute("""
        SELECT stories.id, stories.title, stories.category, stories.image_path,
               stories.content, stories.created_at, users.username AS author
        FROM stories
        JOIN users ON stories.user_id = users.id
        WHERE stories.approved = TRUE
        ORDER BY stories.created_at DESC
        LIMIT 3;
    """)
    latest_stories = db.execute("""
        SELECT stories.id, stories.title, stories.category, stories.image_path,
               stories.content, stories.created_at, users.username AS author
        FROM stories
        JOIN users ON stories.user_id = users.id
        WHERE stories.approved = TRUE
        ORDER BY stories.created_at DESC
        LIMIT 9;
    """)

    for story in featured_stories + latest_stories:
        story['image_path'] = get_story_image(story)
        if isinstance(story['created_at'], str):
            story['created_at'] = datetime.strptime(story['created_at'], "%Y-%m-%d %H:%M:%S")

    return render_template("index.html", featured_stories=featured_stories, latest_stories=latest_stories)

# --------------------------------------------------
# About
# --------------------------------------------------
@app.route("/about")
def about():
    return render_template("about.html")

# --------------------------------------------------
# Test DB connection
# --------------------------------------------------
@app.route("/test-db")
def test_db():
    try:
        result = db.execute("SELECT 1;")
        return f"Database connected! Result: {result}"
    except Exception as e:
        return f"Error: {e}"

# --------------------------------------------------
# Registration
# --------------------------------------------------
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        confirmation = request.form.get("confirmation")

        if not username or not password or not confirmation:
            flash("Enter all fields")
            return redirect("/register")
        if password != confirmation:
            flash("Password mismatch")
            return redirect("/register")

        # Check username availability
        rows = db.execute("SELECT * FROM users WHERE username = $1", username)
        if rows:
            flash("Username taken")
            return redirect("/register")

        # Insert user
        hash_pw = generate_password_hash(password)
        db.execute("INSERT INTO users (username, hash) VALUES ($1, $2)", username, hash_pw)
        flash("Registered successfully")
        return redirect("/login")
    return render_template("register.html")

# --------------------------------------------------
# Login
# --------------------------------------------------
@app.route("/login", methods=["GET", "POST"])
def login():
    session.clear()
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        if not username or not password:
            flash("Must provide username and password")
            return redirect("/login")

        rows = db.execute("SELECT * FROM users WHERE username = $1", username)
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], password):
            flash("Invalid username or password")
            return redirect("/login")

        user = rows[0]
        session["user_id"] = user["id"]
        session["role"] = user["role"]
        flash("Logged in successfully")
        return redirect("/")
    return render_template("login.html")

# --------------------------------------------------
# Logout
# --------------------------------------------------
@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out successfully")
    return redirect("/")

# --------------------------------------------------
# Submit story
# --------------------------------------------------
@app.route("/submit", methods=["GET", "POST"])
def submit():
    if not session.get("user_id"):
        flash("Login to submit a story")
        return redirect("/login")

    categories = db.execute("SELECT * FROM categories")
    if request.method == "POST":
        title = request.form.get("title")
        category = request.form.get("category")
        content = request.form.get("content")
        image = request.files.get("image")

        if not title or not category or not content:
            flash("Enter all fields")
            return redirect("/submit")

        image_path = None
        if image and image.filename != "":
            filename = secure_filename(image.filename)
            static_folder = os.path.join(app.root_path, 'static')
            image_folder = os.path.join(static_folder, 'images')
            os.makedirs(image_folder, exist_ok=True)
            image_path = f"images/{filename}"
            image.save(os.path.join(image_folder, filename))

        db.execute("""
            INSERT INTO stories (user_id, title, category, content, image_path, approved, created_at)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
        """, session["user_id"], title, category, content, image_path, FALSE, datetime.utcnow())
        flash("Story submitted for review")
        return redirect("/")
    return render_template("submit.html", categories=categories)

# --------------------------------------------------
# View story
# --------------------------------------------------
@app.route("/story/<int:story_id>")
def story(story_id):
    user = session.get("user_id")
    rows = db.execute("""
        SELECT stories.*, users.username AS author,
        COUNT(likes.id) AS like_count
        FROM stories
        JOIN users ON stories.user_id = users.id
        LEFT JOIN likes ON stories.id = likes.story_id
        WHERE stories.id = $1 AND stories.approved = TRUE
        GROUP BY stories.id, users.username
    """, story_id)
    if not rows:
        return "Story not found", 404

    story = rows[0]
    story['image_path'] = get_story_image(story)

    if isinstance(story['created_at'], str):
        story['created_at'] = datetime.strptime(story['created_at'], "%Y-%m-%d %H:%M:%S")

    comments = db.execute("""
        SELECT comments.content, comments.created_at, users.username AS author
        FROM comments
        JOIN users ON comments.user_id = users.id
        WHERE comments.story_id = $1
        ORDER BY comments.created_at ASC
    """, story_id)

    for comment in comments:
        if isinstance(comment["created_at"], str):
            comment["created_at"] = datetime.strptime(comment["created_at"], "%Y-%m-%d %H:%M:%S")

    return render_template("story.html", story=story, comments=comments, user=user)

# --------------------------------------------------
# Admin
# --------------------------------------------------
@app.route("/admin")
def admin():
    if not session.get("user_id"):
        flash("Login to access admin page")
        return redirect("/login")

    user = db.execute("SELECT * FROM users WHERE id = $1", session["user_id"])
    if not user or user[0]["role"] != "admin":
        flash("Access denied")
        return redirect("/")

    stories = db.execute("""
        SELECT stories.id, stories.title, users.username AS author, stories.created_at,
               stories.content, stories.image_path, stories.category
        FROM stories
        JOIN users ON stories.user_id = users.id
        WHERE stories.approved = FALSE
        ORDER BY stories.created_at ASC;
    """)
    approved_stories = db.execute("""
        SELECT stories.id, stories.title, users.username AS author, stories.created_at,
               stories.content, stories.image_path, stories.category
        FROM stories
        JOIN users ON stories.user_id = users.id
        WHERE stories.approved = TRUE
        ORDER BY stories.created_at ASC;
    """)
    return render_template("admin.html", stories=stories, approved_stories=approved_stories)

# --------------------------------------------------
# Approve story
# --------------------------------------------------
@app.route("/approve/<int:story_id>")
def approve(story_id):
    if not session.get("user_id"):
        flash("Login to access admin page")
        return redirect("/login")

    user = db.execute("SELECT * FROM users WHERE id = $1", session["user_id"])
    if not user or user[0]["role"] != "admin":
        flash("Access denied")
        return redirect("/")

    db.execute("UPDATE stories SET approved = TRUE WHERE id = $1", story_id)
    flash("Story approved successfully")
    return redirect("/admin")

# --------------------------------------------------
# Like a story
# --------------------------------------------------
@app.route("/like/<int:story_id>", methods=["POST"])
def like(story_id):
    if not session.get("user_id"):
        flash("Login to like stories")
        return redirect("/login")

    db.execute("""
        INSERT INTO likes (user_id, story_id)
        VALUES ($1, $2)
        ON CONFLICT DO NOTHING
    """, session["user_id"], story_id)

    return redirect(f"/story/{story_id}")

# --------------------------------------------------
# Category page
# --------------------------------------------------
@app.route("/category/<string:category>")
def category(category):
    stories = db.execute("""
        SELECT stories.id, stories.title, stories.category, stories.image_path,
               stories.content, stories.created_at, users.username AS author,
               (SELECT COUNT(*) FROM likes WHERE likes.story_id = stories.id) AS like_count
        FROM stories
        JOIN users ON stories.user_id = users.id
        WHERE stories.category = $1 AND stories.approved = TRUE
        ORDER BY stories.created_at DESC
    """, category)

    for story in stories:
        story['image_path'] = get_story_image(story)
        if isinstance(story["created_at"], str):
            story["created_at"] = datetime.strptime(story["created_at"], "%Y-%m-%d %H:%M:%S")

    return render_template("category.html", stories=stories, category=category)

# --------------------------------------------------
# Profile page
# --------------------------------------------------
@app.route("/profile")
def profile():
    if not session.get("user_id"):
        flash("Login required to access profile")
        return redirect("/login")

    user_id = session["user_id"]
    user = db.execute("SELECT * FROM users WHERE id = $1", user_id)[0]

    stories = db.execute("""
        SELECT stories.id, stories.title, stories.category, stories.created_at,
               stories.approved, users.username,
               COUNT(likes.id) AS like_count
        FROM stories
        JOIN users ON stories.user_id = users.id
        LEFT JOIN likes ON stories.id = likes.story_id
        WHERE stories.user_id = $1
        GROUP BY stories.id, stories.title, stories.category, stories.created_at, stories.approved, users.username
        ORDER BY stories.created_at DESC
    """, user_id)

    for story in stories:
        if isinstance(story['created_at'], str):
            story['created_at'] = datetime.strptime(story['created_at'], "%Y-%m-%d %H:%M:%S")

    return render_template("profile.html", user=user, stories=stories)

# --------------------------------------------------
# Change password
# --------------------------------------------------
@app.route("/password", methods=["GET", "POST"])
def password():
    if not session.get("user_id"):
        flash("Login required to change password")
        return redirect("/login")

    if request.method == "POST":
        current_password = request.form.get("current_password")
        new_password = request.form.get("new_password")
        confirm_password = request.form.get("confirm_password")

        if not current_password or not new_password or not confirm_password:
            flash("All fields required")
            return redirect("/password")
        if new_password != confirm_password:
            flash("Password mismatch")
            return redirect("/password")

        user = db.execute("SELECT * FROM users WHERE id = $1", session["user_id"])[0]
        if not check_password_hash(user["hash"], current_password):
            flash("Current password incorrect")
            return redirect("/password")

        new_hash = generate_password_hash(new_password)
        db.execute("UPDATE users SET hash = $1 WHERE id = $2", new_hash, session["user_id"])
        flash("Password changed successfully")
        return redirect("/profile")

    return render_template("password.html")

# --------------------------------------------------
# Podcast
# --------------------------------------------------
@app.route("/podcast")
def podcast():
    feed_url = "https://open.spotify.com/show/6iw09g8C70aBz7knGBUgzd?si=cc9c60f8726e414c"
    feed = feedparser.parse(feed_url)
    episodes = feed.entries[:10]
    return render_template("podcast.html", episodes=episodes)

# --------------------------------------------------
# Run app
# --------------------------------------------------
if __name__ == "__main__":
    app.run(debug=True)