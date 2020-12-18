import os
import psycopg2

from cs50 import SQL
from flask import Flask, flash, jsonify, redirect, render_template, request, session
from flask_session import Session

from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd, transaction
from datetime import datetime

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Ensure responses aren't cached


@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)

app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")
#db = SQL("postgres://fxoggjvieyvwky:df5e99dca0a476aa5ff8550924502e3dde9dd5a99d209ad98a0368a5f6024fc4@ec2-54-211-99-192.compute-1.amazonaws.com:5432/d9ehdd4v46qtrl")



@app.route("/operations")
@login_required
def operations():
    """home"""

    operations = db.execute("SELECT date, description, account, amount FROM operations WHERE user_id = :user_id ORDER BY date DESC", user_id=session["user_id"])
   
    return render_template("operations.html", operations=operations)

@app.route("/", methods=["GET", "POST"]) 
@login_required
def accounts():
    """displays accounts with their operations"""

    if request.method == "POST":
        newAccount = request.form.get('accountName')
    
        db.execute("INSERT INTO accounts (user_id, account_name) VALUES (:user_id, :account)", user_id=session["user_id"], account=newAccount)

        return redirect("/")

    else:


        operations = db.execute("SELECT date, description, account, amount FROM operations WHERE user_id = :user_id", user_id=session["user_id"])
        accounts = db.execute("SELECT account_name FROM accounts WHERE user_id = :user_id", user_id=session["user_id"])

        total = 0.00
        for i in range(len(accounts)):
            subtotal = 0.00        
            for j in range(len(operations)):
                if operations[j]['account'] == accounts[i]['account_name']:
                    subtotal = subtotal + operations[j]['amount']
            accounts[i]['sub_total'] = subtotal
            total = total + subtotal





    
        return render_template("accounts.html", operations=operations, accounts=accounts, total=total)


@app.route("/addincome", methods=["GET", "POST"])
@login_required
def addincome():
    """Let the user add funds"""
    accountsdict = db.execute("SELECT account_name FROM accounts WHERE user_id = :user_id", user_id=session["user_id"])
    accounts = []
    for i in range(len(accountsdict)):
        accounts.append(accountsdict[i]['account_name'])
    if request.method == "POST":
        account = request.form.get('account')
        return transaction(accounts, account, db, 1)
    else:
        return render_template("addincome.html", accounts=accounts)

@app.route("/addexpense", methods=["GET", "POST"])
@login_required
def addexpense():
    """Let the user add funds"""
    
    accountsdict = db.execute("SELECT account_name FROM accounts WHERE user_id = :user_id", user_id=session["user_id"])
    accounts = []
    for i in range(len(accountsdict)):
        accounts.append(accountsdict[i]['account_name'])
        
    if request.method == "POST":
        account = request.form.get('account')
        
        return transaction(accounts, account, db, -1)
    else:
        return render_template("addexpense.html", accounts=accounts)

@app.route("/transfer", methods=["GET", "POST"])
@login_required
def transfer():
    """Transfer funds among accounts"""
    
    accountsdict = db.execute("SELECT account_name FROM accounts WHERE user_id = :user_id", user_id=session["user_id"])
    accounts = []
    for i in range(len(accountsdict)):
        accounts.append(accountsdict[i]['account_name'])

    if request.method == "POST":
        origin_account = request.form.get('origin account')
        if origin_account not in accounts:
            return apology("Must enter existing account", 400)
        else:
            transaction(accounts, origin_account, db, -1)
     
        destination_account = request.form.get('destination account')
        return transaction(accounts, destination_account, db, 1)

    else:
        return render_template("transfer.html", accounts=accounts)



@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 400)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 400)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username",
                          username=request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 400)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]


        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")



@app.route("/register", methods=["GET", "POST"])
def register():
    # User reached route via POST
    if request.method == "POST":

        # Ensure user types username
        if not request.form.get("username"):
            return apology("must provide username", 400)

        # Ensure user types password
        elif not request.form.get("password"):
            return apology("must provide password", 400)

        # Ensure user confirms password
        elif not request.form.get("password2"):
            return apology("must confirm password", 400)

        # Ensure confirmation matches password
        elif not request.form.get("password") == request.form.get("password2"):
            return apology("password confirmation does not match", 400)

        # Store username inside variable
        username = request.form.get("username")

        # Ensure username is not already taken
        duplicate = db.execute("SELECT * FROM users WHERE username = :username", username=username)
        if duplicate:
            return apology("username already exists", 400)

        # Store password and hash inside variables
        password = request.form.get("password")
        hashpass = generate_password_hash(password, method='pbkdf2:sha256', salt_length=8)

        # Store default account names inside list
        def_accounts = ["Income", "Expenses", "Savings"]

        # Insert username and hash into database
        db.execute("INSERT INTO users (username, hash) VALUES (:username, :hashpass)", username=username, hashpass=hashpass)

        # Create default accounts for new user
        rows = db.execute("SELECT * FROM users WHERE username = :username", username=username)
        for account in def_accounts:
            db.execute("INSERT INTO accounts (user_id, account_name) VALUES (:user_id, :account)", user_id=rows[0]["id"], account=account)
        return redirect("/")

    # User reached route via GET
    else:
        return render_template("register.html")


def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
