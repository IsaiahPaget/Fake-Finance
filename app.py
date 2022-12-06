import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.security import check_password_hash, generate_password_hash
from math import trunc
from helpers import apology, login_required, lookup, usd
from datetime import datetime

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""

    # gather portfolio values
    portfolio = db.execute("SELECT shares, company, symbol FROM portfolio JOIN users ON users.username=portfolio.username WHERE users.id = ?", session['user_id'])
    variable = db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"])

    for elements in variable:
        cash = elements['cash']

    totalValue = 0
    for item in portfolio:
        num = lookup(item['symbol'])
        price = num['price']
        item.update(price=price)
        totalValue += item['shares'] * price

    return render_template("index.html", portfolio=portfolio, totalValue=totalValue, cash=cash)

@app.route("/transfer", methods=["GET", "POST"])
@login_required
def transfer():
    """add or withdrawal"""

    if request.method == "POST":
        db.execute("UPDATE users SET cash = cash + ? WHERE id = ?", int(request.form.get("amount")), session['user_id'])
        return redirect("/")
    else:
        return render_template("transfer.html")

@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    # wallet amount
    res = db.execute("SELECT cash, username FROM users WHERE id = ?", session['user_id'])
    for elements in res:
        funds = dict(elements)
    print(funds)
    print(res)

    if request.method == "POST":

        # check if symbol, shares is correct and present
        if not lookup(request.form.get("symbol")):
            return apology("please enter correct ticker symbol and number of shares", 400)
        if not request.form.get('shares').isdigit():
            return apology("please enter correct ticker symbol and number of shares", 400)
        if not int(request.form.get("shares")) >= 1:
            return apology("please enter correct ticker symbol and number of shares", 400)

        # declaring look up variables
        quoted = lookup(request.form.get("symbol"))
        print(quoted)
        name = quoted['name']
        price = quoted['price']
        symbol = quoted['symbol']
        now = datetime.now()
        time = now.strftime("%d/%m/%Y %H:%M:%S")

        # insert purchase records
        if not funds['cash'] > float(price) * int(request.form.get('shares')):
            return apology("insuficient funds", 400)
        else:
            purchaseValue = funds['cash'] - float(price) * int(request.form.get("shares"))
            db.execute("UPDATE users SET cash = ? WHERE username = ?", purchaseValue, funds['username'])

            # weeding out duplicates so that multiple of the same company show up in index
            if not db.execute("SELECT company FROM portfolio JOIN users ON users.username = portfolio.username WHERE users.id = ? AND company = ?", session['user_id'], name):
                db.execute("INSERT INTO purchases (username, shares, company, symbol, time) VALUES (?, ?, ?, ?, ?)", funds['username'], request.form.get("shares"), name, symbol, time)
                db.execute("INSERT INTO portfolio (username, shares, company, symbol) VALUES (?, ?, ?, ?)", funds['username'], request.form.get("shares"), name, symbol)
            else:
                db.execute("UPDATE portfolio SET shares = shares + ? WHERE username = ? AND company = ?", int(request.form.get("shares")), funds['username'], name)
            return redirect("/")

    else:
        return render_template("buy.html", funds=funds["cash"], user=funds["username"])


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    query = db.execute("SELECT purchases.username, shares, company, symbol, time FROM purchases JOIN users ON users.username = purchases.username WHERE users.id = ?", session['user_id'])
    if not query:
        return apology("no history yet")
    else:
        for item in query:
            data = dict(item)
        quote = lookup(data['symbol'])
        price = quote['price']
        return render_template("history.html", query=query, price=price)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

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


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""
    if request.method == "POST":
        # check if text was valid
        if not lookup(request.form.get("symbol")):
            return apology("must enter correct ticker symbol", 400)

        # get info and render quoted
        else:
            quoted = lookup(request.form.get("symbol"))
            usdprice = usd(quoted['price'])
            return render_template("/quoted.html", name=quoted["name"], price=usdprice, symbol=quoted["symbol"])
    else:
        return render_template("/quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    # user reached route via POST
    if request.method == "POST":
        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 400)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 400)

        # storing username, password, and confirmation in variables
        varUsername = request.form.get("username")
        varPassword = request.form.get("password")
        varConfirmation = request.form.get("confirmation")

        # check if password == conpassword
        if not varPassword == varConfirmation:
            return apology("passwords dont match", 400)

        # check if username is already in use, and inserting login info
        if db.execute("SELECT username FROM users WHERE username = ?", varUsername):
            return apology("username already exists")
        else:
            db.execute("INSERT INTO users (username, hash) VALUES (?, ?)", varUsername, generate_password_hash(varPassword))

            # user did input username, password, and confirm password correctly
            return redirect("/")

    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    if request.method == "POST":

        # check for ticker symbol in portfolio

        if not db.execute("SELECT symbol FROM portfolio JOIN users ON users.username = portfolio.username WHERE users.id = ? AND portfolio.symbol = ?", session['user_id'], request.form.get('symbol').upper()):
            return apology("you don't own that stock", 404)
        elif not request.form.get("shares").isdigit():
            return apology("invalid amount", 400)
        else:
            # get the amount of shares and price in portfolio
            query = db.execute("SELECT symbol, shares, company, portfolio.username FROM portfolio JOIN users ON users.username = portfolio.username WHERE users.id = ? AND portfolio.symbol = ?", session['user_id'], request.form.get('symbol').upper())
            for items in query:
                data = dict(items)
            quoted = lookup(data['symbol'])

            # amount returned to wallet
            if not data['shares'] >= int(request.form.get("shares")) > 0:
                return apology("you dont have that many shares of that company", 400)
            else:
                # time thingy
                now = datetime.now()
                time = now.strftime("%d/%m/%Y %H:%M:%S")

                # update database so that shares are subtracted and sold is added to cash
                sold = int(request.form.get('shares')) * quoted['price']
                db.execute("UPDATE portfolio SET shares = shares - ? WHERE symbol = ?", int(request.form.get("shares")), data['symbol'])
                db.execute("UPDATE users SET cash = cash + ?", sold)
                db.execute("INSERT INTO purchases (company, username, shares, symbol, time) VALUES (?, ?, -?, ?, ?)", data["company"], data["username"], data['shares'], data["symbol"], time)

                listshares2 = db.execute("SELECT shares FROM portfolio JOIN users ON users.username = portfolio.username WHERE users.id = ? AND portfolio.symbol = ?", session['user_id'], request.form.get('symbol').upper())
                dictshares2 = listshares2[0]
                if dictshares2['shares'] == 0:
                    db.execute("DELETE FROM portfolio WHERE symbol = ? AND username IN (SELECT portfolio.username FROM portfolio JOIN users ON users.username = portfolio.username WHERE users.id = ?)", data['symbol'], session['user_id'])

        return redirect("/")
    else:
        query = db.execute("SELECT symbol, shares, company, portfolio.username FROM portfolio JOIN users ON users.username = portfolio.username WHERE users.id = ?", session['user_id'])
        return render_template("sell.html", query=query)
