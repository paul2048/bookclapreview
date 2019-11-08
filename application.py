import os
import re
import requests

from flask import Flask, session, render_template, redirect, request, jsonify
from flask_session import Session
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
from statistics import mean

app = Flask(__name__)

# Check for environment variable
if not os.getenv("DATABASE_URL"):
    raise RuntimeError("DATABASE_URL is not set")

# Configure session to use filesystem
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Set up database
engine = create_engine(os.getenv("DATABASE_URL"))
db = scoped_session(sessionmaker(bind=engine))

# Goodreads key
KEY = "Lk6ArPlaG84JG57baFKYZQ"

def when_posted(timestamp):
    """ Returns the date (if the number of days >= 7) or how long ago a review was posted """
    # How long ago the review was posted
    posted_ago = [datetime.now() - timestamp][0]

    if posted_ago.days >= 7:
        return f"{str(timestamp.day)}/{str(timestamp.month)}/{str(timestamp.year)}"
    elif posted_ago.days >= 1:
        return str(posted_ago.days) + " days ago"
    elif posted_ago.seconds >= 3600:
        return str(posted_ago.seconds // 3600) + " hours ago"
    elif posted_ago.seconds >= 60:
        return str(posted_ago.seconds // 60) + " minutes ago"
    return str(posted_ago.seconds) + " seconds ago"


@app.route("/")
def index():
    """ Stats and information about reviews """
    reviews_number = db.execute("SELECT COUNT(*) FROM reviews").fetchone()[0]
    average_rating = db.execute("SELECT ROUND(AVG(rating), 5) FROM reviews").fetchone()[0]
    most_reviewed = db.execute("""SELECT books.isbn, title, COUNT(title) FROM reviews
                               JOIN books ON reviews.isbn=books.isbn
                               GROUP BY books.isbn, title ORDER BY COUNT(title) DESC""").fetchone()
    best_rated = db.execute("""SELECT books.isbn, title, ROUND(AVG(rating), 5) FROM reviews
                            JOIN books ON reviews.isbn=books.isbn
                            GROUP BY books.isbn, title ORDER BY AVG(rating) DESC""").fetchone()
    latest_reviews = db.execute("""SELECT username, title, rating, timestamp, opinion, reviews.isbn
                                FROM reviews
                                JOIN users ON reviews.uid=users.id
                                JOIN books ON reviews.isbn=books.isbn
                                ORDER BY timestamp DESC LIMIT 5""").fetchall()

    # Convert the tuples to lists so the timestamp can be replaced
    latest_reviews = [list(review) for review in latest_reviews]

    # Replace the timestamps of the latest reviews with when each were posted (the date or how long ago)
    for review in latest_reviews:
        review[3] = when_posted(review[3])

    # Object that contains all the reviews stats for the page
    reviews_stats = {
        "reviews_number": reviews_number,
        "average_rating": average_rating,
        # Example: ('0425267040', 'Rush', 4)
        "most_reviewed": most_reviewed,
        # Example: ('0743484355', 'A Cry in the Night', Decimal('5.00000')
        "best_rated": best_rated
    }

    return render_template("index.html",
                            active_home="active",
                            reviews_stats=reviews_stats,
                            latest_reviews=latest_reviews)

@app.route("/books", methods=["GET", "POST"])
def books():
    """ Displays results for the user's query """
    if request.method == "POST":
        q = "%" + request.form.get("book_query").lower() + "%"

        books = db.execute("""SELECT isbn, title, author_name FROM books
                           JOIN authors ON books.author_id=authors.id
                           WHERE (LOWER(isbn) LIKE :query) OR
                           (LOWER(title) LIKE :query) OR
                           (LOWER(author_name) LIKE :query)""",
                           {"query": q}).fetchall()

        return render_template("books.html", active_books="active", matched_books=books) 

    return render_template("books.html", active_books="active")

@app.route("/books/<isbn>", methods=["GET", "POST"])
def book(isbn):
    """ Displays details about the selected book """
    # Select the isbn, title and author_name of a specific book
    book_details = db.execute("""SELECT isbn, title, author_name, year FROM books
                              JOIN authors ON books.author_id=authors.id
                              WHERE isbn=:isbn""",
                              {"isbn": isbn}).fetchone()

    # Select all the reviews on the book
    book_reviews = db.execute("""SELECT username, opinion, rating, timestamp FROM reviews
                              JOIN users ON reviews.uid=users.id
                              WHERE isbn=:isbn
                              ORDER BY timestamp DESC""",
                              {"isbn": isbn}).fetchall()

    # Convert the tuples to lists so the timestamp can be replaced
    book_reviews = [list(review) for review in book_reviews]

    # Replace the timestamps of the latest reviews with when each were posted (the date or how long ago)
    for review in book_reviews:
        review[3] = when_posted(review[3])
    
    # Make a API request to Goodreads
    res = requests.get("https://www.goodreads.com/book/review_counts.json", params={"key": KEY, "isbns": isbn})

    if res.status_code != 200:
        raise Exception("ERROR: API request unsuccessful.")

    # Get the number of ratings and average rating of the book from Goodreads
    book_stats_goodreads = res.json()["books"][0]

    # If the review posting form was submitted
    if request.method == "POST" and "post_review" in request.form:
        if not session:
            return render_template("error.html", msg="You must be logged in to post reviews")

        opinion = request.form.get("opinion")
        rating = request.form.get("rating")

        # A review on the book from the user exists or not
        review = db.execute("""SELECT EXISTS(SELECT * FROM reviews
                            WHERE isbn=:isbn AND uid=:uid)""",
                            {"isbn": isbn, "uid": session["user_id"]})

        # If the user already made a review on the book
        if review.fetchone()[0]:
            return render_template("error.html", msg="You've already posted a review on this book")
        # Else, add the review to the "reviews" table
        else:
            # Get the current date and time so it can be used as a timestamp for reviews
            timestamp = datetime.now()

            db.execute("""INSERT INTO reviews
                       (uid, isbn, opinion, rating, timestamp)
                       VALUES (:uid, :isbn, :opinion, :rating, :timestamp)""",
                       {"uid": session["user_id"], "isbn": isbn, "opinion": opinion, "rating": rating, "timestamp": timestamp})
            db.commit()

    # If the isbn isn't found in the "books" table
    if not book_details:
        return render_template("error.html", msg="The selected book doesn't exists in the database")
    
    book_reviews = {
        "reviews": book_reviews,
        "reviews_number": len(book_reviews),
        # x[2] is the rating of each review of the book
        "reviews_average": round(mean([x[2] for x in book_reviews]), 2) if len(book_reviews) else None
    }

    return render_template("books.html",
                           active_books="active",
                           book_details=book_details,
                           book_reviews=book_reviews,
                           book_stats_goodreads=book_stats_goodreads)

@app.route("/api/<isbn>")
def api(isbn):
    """ Returns a JSON file with details and stats about a book """
    # Get the title, author name and publishing year
    details = db.execute("""SELECT title, author_name, year FROM books
                         JOIN authors ON books.author_id=authors.id
                         WHERE isbn=:isbn""",
                         {"isbn": isbn}).fetchone()
    # Get the number of reviews and average rating
    stats = db.execute("""SELECT COUNT(*), AVG(rating) FROM reviews
                       WHERE isbn=:isbn GROUP BY isbn""",
                       {"isbn": isbn}).fetchone()
    
    # If the isbn specified can't be found in the database
    if not details:
        return render_template("error.html", msg="No book found with the specified isbn (ERROR 404)")

    book_data = {
        "title": details[0],
        "author": details[1],
        "year": details[2],
        "isbn": isbn,
        "review_count": stats[0],
        "average_score": str(stats[1])
    }

    return jsonify(book_data)

@app.route("/error")
def error():
    """ Renders error message """
    return render_template("error.html")

@app.route("/register", methods=["POST"])
def register():
    """ Registers users """
    usern = request.form.get("inp_usern_register")
    email = request.form.get("inp_email_register")
    passw = request.form.get("inp_passw_register")
    confirm = request.form.get("inp_confirm_register")
    hsh = generate_password_hash(passw)

    # Fields must be filled
    if not (usern and email and passw and confirm):
        return render_template("error.html", msg="All fields must be filled")

    # Simple email validator
    if not re.match(r"^[A-Za-z0-9-._]+@[A-Za-z0-9]+(\.[A-Za-z0-9]+){1,}$", email):
        return render_template("error.html", msg="The email is not valid")

    # Password must have at least: 8 characters; 1 upper and 1 lower char; 1 digit or 1 symbol 
    if not re.match(r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d|.*[!@#$%^&*()`~,.<>?/;':|\\\[\]{}\-=_+]).{8,}$", passw):
        return render_template("error.html", msg="The password must have at least: 8 characters; 1 uppercase and 1 lowercase letter; 1 digit or 1 symbol")

    # Passwords must match
    if passw != confirm:
        return render_template("error.html", msg="The passwords don't match")

    # Insert user data in the table
    try:
        db.execute("INSERT INTO users (username, email, hash) VALUES (:usern, :email, :hash)",
                   {"usern": usern, "email": email, "hash": hsh})
        db.commit()
    # If the email or username already exists
    except:
        return render_template("error.html", msg="Username or email is already taken")

    # Log the new user in
    session["user_id"] = db.execute("SELECT id FROM users WHERE username=:usern",
                                    {"usern": usern}).fetchone()[0]
    session["username"] = db.execute("SELECT username FROM users WHERE id=:uid",
                                     {"uid": session["user_id"]}).fetchone()[0]

    return redirect("/books")

@app.route("/login", methods=["POST"])
def login():
    """ Logs in users """
    usern = request.form.get("inp_usern_login")
    passw = request.form.get("inp_passw_login")
    
    # Fields must be filled
    if not (usern and passw):
        return render_template("error.html", msg="All fields must be filled")

    try:
        # Catches "TypeError: 'NoneType' object is not subscriptable" if the id can't be found
        uid = db.execute("SELECT id FROM users WHERE username=:usern",
                         {"usern": usern}).fetchone()[0]
    except TypeError:
        return render_template("error.html", msg="The username wasn't found")

    # Fetch the user's hash from the database
    hsh = db.execute("SELECT hash FROM users WHERE id=:id",
                     {"id": uid}).fetchone()[0]

    # The password is wrong
    if not check_password_hash(hsh, passw):
        return render_template("error.html", msg="The password is wrong")

    session["user_id"] = uid
    session["username"] = db.execute("SELECT username FROM users WHERE id=:uid",
                                     {"uid": uid}).fetchone()[0]

    return redirect("/books")

@app.route("/signout")
def signout():
    """ Signs the user out """
    session.clear()

    return redirect("/")
