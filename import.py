import os
import re

from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker


# Check for environment variable
if not os.getenv("DATABASE_URL"):
    raise RuntimeError("DATABASE_URL is not set")

# Set up database
engine = create_engine(os.getenv("DATABASE_URL"))
db = scoped_session(sessionmaker(bind=engine))


def main():
    # Create the authors table if it doesn't exist
    try:
        db.execute("SELECT * FROM authors")
    except:
        # Rollback if the previous SQL command had an error
        db.execute("rollback")
        db.execute("""CREATE TABLE authors (
                   id SERIAL PRIMARY KEY,
                   author_name TEXT NOT NULL)""")

    # Create the books table if it doesn't exist
    try:
        db.execute("SELECT * FROM books")
    except:
        # Rollback if the previous SQL command had an error
        db.execute("rollback")
        db.execute("""CREATE TABLE books (
                   isbn VARCHAR(10) UNIQUE NOT NULL,
                   title TEXT NOT NULL,
                   author INTEGER NOT NULL REFERENCES authors,
                   year INTEGER NOT NULL)""")

    # Open the csv file
    try:
        books_file = open("books.csv", "r")
    except OSError:
        raise RuntimeError("Cannot open 'books.csv'")

    # Skip the first row
    books_file.readline()

    books = []

    # Store in "books", a list for each book
    for book in books_file.readlines():
        # If the "book" string contains a quotation mark
        if '"' in book:
            # Get the quote pair(s)
            quoted_detail = re.findall("\".+?\"", book)[0]
            # Replace "," with the tab character and remove the quotes
            book = book.replace(quoted_detail, quoted_detail.replace(",", r"/t").replace("\"", ""))
        
        # Replace back the tab character with "," and append the book to "books"
        books.append([x.replace(r"/t", ",") for x in book[:-1].split(",")])
    
    books_file.close()
    
    # If the authors or books tables have anything in
    if db.execute("SELECT * FROM authors").fetchone() or db.execute("SELECT * FROM books").fetchone():
        # User chooses if the user wants to replace the table
        replace_tables = input("Do you want to replace the old books data with the new one? ").lower()

        # Empty the table if the user wants so
        if replace_tables == "y" or replace_tables == "yes":
            db.execute("DROP TABLE authors CASCADE")
            db.execute("TRUNCATE books CASCADE")
            
            db.execute("""CREATE TABLE authors (
                       id SERIAL PRIMARY KEY,
                       author_name TEXT UNIQUE NOT NULL)""")
            
            print("The tables were emptied.")
        else:
            print("Operation aborted. The tables are unchanged.")
            return

    print("Importing authors...")

    for book in books:
        author = db.execute("SELECT * FROM authors WHERE author_name=:author_name",
                            {"author_name": book[2]}).fetchone()
        
        # Insert the unique authors into the authors table
        if not author:
            db.execute("INSERT INTO authors (author_name) VALUES (:author_name)",
                       {"author_name": book[2]})
            db.commit()

    print("Authors imported.")
    print("Importing all books details...")

    for book in books:
        # Get the author id of the current author
        author_id = db.execute("SELECT id FROM authors WHERE author_name=:author_name",
                               {"author_name": book[2]}).fetchone()[0]
        
        # Insert the isbn, title, author id and year in the books table
        db.execute("""INSERT INTO books
                   (isbn, title, author, year)
                   VALUES (:isbn, :title, :author_id, :year)""",
                   {"isbn": book[0], "title": book[1], "author": author_id, "year": book[-1]})
        db.commit()

    print("All books details imported.")
  
if __name__== "__main__":
    main()
