# BOOK 👏 REVIEW
This is a web application that provides the users the possibility to give their opinions about books, rate them, and see what others think about different books.


## application.py
This file imports packages, gets linked to a database and handles all the user requests.


## layout.html
This is a layout for all the templates. It retains the navigation bar, the footer, and the login, register and sign out modals.


## index.html
This is the home page template. It contains all-time stats about the books and its reviews, like the best rated book and the total number of reviews.

## books.html
This template contains a search form that displays matches based on the author name and the title of the book. When a matched book was click, the browser will render a new page that contains:
* book details
* stats from [GoodReads](http://goodreads.com/)
* a form to submit reviews
* reviews from users


## error.html
It's a template that displays error messages.


## import.py
The program imports details about books from a file and stores them in an online database. The URL to the database must be stored in an environment variable called `DATABASE_URL`.
1. When the **authors** and **books** tables __don't exist__:
    1. A table for **authors** and one for **books** will be created
    2. Each line (which looks something like `0752849190,Darkest Fear,Harlan Coben,1999`) will be parsed
    3. The parsed data will be stored in the **authors** and **books** tables

2. When the authors and books tables __exist__:
    1. Ask the user if he wants to replace the old books data with the new one
    2. If he approves, go to 1/ii, else the operation will be aborted and nothing will be change in the database


## books.csv
This file contains a fairly big list of books and some details. One line from the file looks something like this: `0752849190,Darkest Fear,Harlan Coben,1999`. Starting from left, separated by commas, we have: the book's ISBN (International Standard Book Number), the title, the author and the publishing year.
`books.csv` can be used as an argument for `import.py`.


## requirement.txt
This is a text file that contains a list of required packages. You can install them by running `pip install -r requirements.txt`


## crab_rave.gif
![Crab Rave](/static/crab_rave.gif)
