from flask import Flask, flash, redirect, render_template, request, session, url_for
from flask_session import Session
from passlib.apps import custom_app_context as pwd_context
from tempfile import mkdtemp
import sqlite3 as sql

from helpers import *

# configure application
app = Flask(__name__)

# ensure responses aren't cached
if app.config["DEBUG"]:
    @app.after_request
    def after_request(response):
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Expires"] = 0
        response.headers["Pragma"] = "no-cache"
        return response

# custom filter
app.jinja_env.filters["usd"] = usd

# configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# configure CS50 Library to use SQLite database
connect = sql.connect('finance.db')
c = connect.cursor()


# c.execute("DROP TABLE users;")
# connect.commit()
# c.execute(
#     "CREATE TABLE users (id INTEGER PRIMARY KEY, username TEXT UNIQUE NOT NULL, hash TEXT NOT NULL, cash DECIMAL(13,2) DEFAULT 10000);")
# connect.commit()
# c.execute("CREATE TABLE stocks (id INTEGER NOT NULL, symbol TEXT(10) NOT NULL, name TEXT NOT NULL, share INTEGER NOT NULL, price DECIMAL(15,2) NOT NULL, total DECIMAL(15,2) NOT NULL)")
# connect.commit()
# c.execute("CREATE TABLE transactions (id INTEGER NOT NULL, symbol TEXT(10) NOT NULL, name TEXT NOT NULL, share INTEGER NOT NULL, price DECIMAL(15,2) NOT NULL, total DECIMAL(15,2) NOT NULL, time TIME NOT NULL)")
# connect.commit()

@app.route("/")
@login_required
def index():
    lister = c.execute("SELECT symbol,name,share,price,total FROM stocks WHERE id=?",
                       (session["user_id"],)).fetchall()
    cash = c.execute("SELECT cash FROM users WHERE id = ?", (session["user_id"],)).fetchone()
    cash = cash[0]
    return render_template("index.html", x=lister, cash=cash)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock."""
    if request.method == "POST":
        shares = request.form.get("shares")
        symbol = request.form.get("symbol")
        look = lookup(symbol)
        if int(shares) <= 0:
            return apology("Enter a positive Integer")
        # lookup
        if look is None:
            return apology("Non Existent stock")
        total = -float(look.get("price")) * int(shares)
        cash = c.execute("SELECT * FROM users WHERE id = ?", (session["user_id"],)).fetchone()[3]
        if float(total) > float(cash):
            return apology("can't afford")
        # insert transaction into database
        c.execute(
            "INSERT INTO transactions (id, symbol, name, share, price, total, time) VALUES(?,?,?,?,?,?,CURRENT_TIMESTAMP)",
            (int(session["user_id"]), look.get("symbol"), look.get("name"), shares, float(look.get("price")),
             total))
        connect.commit()
        c.execute("UPDATE users SET cash = ? WHERE id = ?", (float(cash) + float(total), session["user_id"]))
        connect.commit()
        # insert into other database
        try:
            c.execute("INSERT INTO stocks (id, symbol, name, share, price, total) VALUES(?,?,?,?,?,?)",
                      (int(session["user_id"]), look.get("symbol"), look.get("name"), int(shares),
                       float(look.get("price")),
                       total))
            connect.commit()
        except:
            c.execute("UPDATE stocks SET share = share + ?, total = total + ? WHERE id = ?",
                      (int(shares), total, session["user_id"]))
            connect.commit()
            # add something here
        return redirect(url_for("index"))
    else:
        return render_template("buy.html")


@app.route("/history")
@login_required
def history():
    """Show history of transactions."""
    lister = c.execute("SELECT symbol,name,share,price,total,time FROM transactions WHERE id=?",
                       (session["user_id"],)).fetchall()
    cash = c.execute("SELECT cash FROM users WHERE id = ?", (session["user_id"],)).fetchone()
    cash = cash[0]
    return render_template("history.html", x=lister, cash=cash)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in."""

    # forget any user_id
    session.clear()

    # if user reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username")

        # ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password")

        # query database for username
        rows = c.execute("SELECT * FROM users WHERE username = ?", (request.form.get("username"),)).fetchall()

        # ensure username exists and password is correct
        if len(rows) != 1 or not pwd_context.verify(request.form.get("password"), rows[0][2]):
            return apology("invalid username and/or password")

        # remember which user has logged in
        session["user_id"] = rows[0][0]

        # redirect user to home page
        flash("logged in")
        return redirect(url_for("index"))

    # else if user reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out."""

    # forget any user_id
    session.clear()

    # redirect user to login form
    return redirect(url_for("login"))


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""
    if request.method == "POST":
        # getting quote
        symbol = request.form.get("quote")
        look = lookup(symbol)
        if look is None:
            return apology("Wrong Symbol")
        n = {"symbol": look.get("symbol"), "price": look.get("price")}
        return render_template('quote1.html', n=n)
    else:
        return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user."""
    if request.method == "POST":
        # check for username
        if len(request.form.get("username")) == 0 or len(request.form.get("password")) == 0:
            return apology("No Username")

        if request.form.get("verify_password") != request.form.get("password"):
            return apology("Different passwords")
        password = pwd_context.encrypt(request.form.get("password"))
        # insert into table
        try:
            username = c.execute("INSERT INTO users (username, hash) VALUES (?,?)",
                                 (request.form.get("username"), password))
        except:
            return apology("Already taken username")
        connect.commit()

        rows = c.execute("SELECT * FROM users WHERE username = ?", (request.form.get("username"),)).fetchall()
        # remember which user has logged in
        session["user_id"] = rows[0][0]
        # redirect user to home page
        return redirect(url_for("index"))
    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock."""
    if request.method == "POST":
        shares = int(request.form.get("shares"))
        symbol = request.form.get("symbol")
        look = lookup(symbol)
        share = c.execute("SELECT share FROM stocks where id = ? AND symbol=?",
                          (session["user_id"], symbol)).fetchone()
        if int(share[0]) < shares:
            return apology("Too much stock")
        total = float(look.get("price")) * int(shares)
        # have to reduce stocks by amount
        c.execute(
            "INSERT INTO transactions (id, symbol, name, share, price, total,time) VALUES(?,?,?,?,?,?,CURRENT_TIMESTAMP)",
            (int(session["user_id"]), look.get("symbol"), look.get("name"), shares, float(look.get("price")),
             total))
        connect.commit()
        c.execute("UPDATE users SET cash = cash + ? WHERE id = ?", (float(total), session["user_id"]))
        connect.commit()
        c.execute("UPDATE stocks SET share = share - ?, total = total + ?", (int(shares), total)) # error
        connect.commit()
        return redirect(url_for("index"))
    else:  # stocks from db
        stocks = c.execute("SELECT symbol FROM stocks WHERE id=?", (session["user_id"],)).fetchall()
        stocks = [str(i[0]) for i in stocks]
        return render_template("sell.html", stocks=stocks)


app.run("0.0.0.0", "8080")
