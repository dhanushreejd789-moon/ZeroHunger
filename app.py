import os
import sqlite3
import secrets
from functools import wraps
from datetime import datetime
from flask import (
    Flask, render_template, request, redirect,
    url_for, session, flash
)
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY") or secrets.token_hex(32)

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DATABASE = os.path.join(BASE_DIR, "donations.db")


def get_db():
    connection = sqlite3.connect(DATABASE)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def init_db():
    with get_db() as db:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS donations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            donor TEXT NOT NULL,
            food_name TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            unit TEXT NOT NULL,
            location TEXT NOT NULL,
            phone TEXT NOT NULL,
            expiry TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'Available',
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS distributions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            donation_id INTEGER NOT NULL,
            recipient TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            location TEXT NOT NULL,
            distribution_date TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'Pending',
            FOREIGN KEY (donation_id) REFERENCES donations(id)
        );

        CREATE TABLE IF NOT EXISTS volunteers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            phone TEXT NOT NULL,
            email TEXT NOT NULL,
            area TEXT NOT NULL,
            availability TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS needy_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            recipient TEXT NOT NULL,
            food_required TEXT NOT NULL,
            people_count INTEGER NOT NULL,
            location TEXT NOT NULL,
            phone TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'Pending',
            created_at TEXT NOT NULL
        );
        """)


def login_required(function):
    @wraps(function)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in to continue.", "error")
            return redirect(url_for("index"))
        return function(*args, **kwargs)
    return wrapper


@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        with get_db() as db:
            user = db.execute(
                "SELECT * FROM users WHERE username = ?",
                (username,)
            ).fetchone()

        if user and check_password_hash(user["password"], password):
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            return redirect(url_for("dashboard"))

        flash("Incorrect username or password.", "error")

    return render_template("index.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")

        if not username or not email or not password:
            flash("Please complete all fields.", "error")
        elif password != confirm_password:
            flash("Passwords do not match.", "error")
        elif len(password) < 8:
            flash("Use a password with at least 8 characters.", "error")
        else:
            try:
                with get_db() as db:
                    db.execute(
                        "INSERT INTO users (username, email, password) "
                        "VALUES (?, ?, ?)",
                        (username, email, generate_password_hash(password))
                    )
                flash("Registration successful. Please log in.", "success")
                return redirect(url_for("index"))
            except sqlite3.IntegrityError:
                flash("That username or email is already registered.", "error")

    return render_template("register.html")


@app.route("/dashboard")
@login_required
def dashboard():
    with get_db() as db:
        stats = {
            "donations": db.execute(
                "SELECT COUNT(*) FROM donations"
            ).fetchone()[0],
            "available": db.execute(
                "SELECT COUNT(*) FROM donations WHERE status='Available'"
            ).fetchone()[0],
            "volunteers": db.execute(
                "SELECT COUNT(*) FROM volunteers"
            ).fetchone()[0],
            "requests": db.execute(
                "SELECT COUNT(*) FROM needy_requests"
            ).fetchone()[0],
        }
        recent = db.execute(
            "SELECT * FROM donations ORDER BY id DESC LIMIT 5"
        ).fetchall()

    return render_template("dashboard.html", stats=stats, recent=recent)


@app.route("/donations", methods=["GET", "POST"])
@login_required
def donations():
    if request.method == "POST":
        donor = request.form.get("donor", "").strip()
        food_name = request.form.get("food_name", "").strip()
        quantity = request.form.get("quantity", type=int)
        unit = request.form.get("unit", "").strip()
        location = request.form.get("location", "").strip()
        phone = request.form.get("phone", "").strip()
        expiry = request.form.get("expiry", "").strip()

        if (not all([donor, food_name, unit, location, phone, expiry])
                or quantity is None or quantity <= 0):
            flash("Please enter valid information in every field.", "error")
        else:
            with get_db() as db:
                db.execute("""
                    INSERT INTO donations
                    (donor, food_name, quantity, unit, location,
                     phone, expiry, status, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, 'Available', ?)
                """, (
                    donor, food_name, quantity, unit, location,
                    phone, expiry, datetime.now().strftime("%Y-%m-%d %H:%M")
                ))
            flash("Food donation saved successfully.", "success")
            return redirect(url_for("donations"))

    with get_db() as db:
        records = db.execute(
            "SELECT * FROM donations ORDER BY id DESC"
        ).fetchall()

    return render_template("donations.html", records=records)


@app.route("/Distribution", methods=["GET", "POST"])
@login_required
def Distribution():
    if request.method == "POST":
        donation_id = request.form.get("donation_id", type=int)
        recipient = request.form.get("recipient", "").strip()
        quantity = request.form.get("quantity", type=int)
        location = request.form.get("location", "").strip()
        date = request.form.get("distribution_date", "").strip()

        if (not all([donation_id, recipient, location, date])
                or quantity is None or quantity <= 0):
            flash("Please complete the distribution form correctly.", "error")
        else:
            with get_db() as db:
                donation = db.execute(
                    "SELECT * FROM donations WHERE id=? AND status='Available'",
                    (donation_id,)
                ).fetchone()

                if not donation:
                    flash("That donation is no longer available.", "error")
                elif quantity > donation["quantity"]:
                    flash("Quantity exceeds the donated amount.", "error")
                else:
                    db.execute("""
                        INSERT INTO distributions
                        (donation_id, recipient, quantity, location,
                         distribution_date, status)
                        VALUES (?, ?, ?, ?, ?, 'Completed')
                    """, (donation_id, recipient, quantity, location, date))

                    remaining = donation["quantity"] - quantity
                    new_status = "Distributed" if remaining == 0 else "Available"
                    db.execute(
                        "UPDATE donations SET quantity=?, status=? WHERE id=?",
                        (remaining, new_status, donation_id)
                    )
                    flash("Distribution recorded successfully.", "success")
                    return redirect(url_for("Distribution"))

    with get_db() as db:
        available = db.execute(
            "SELECT * FROM donations WHERE status='Available' AND quantity > 0"
        ).fetchall()
        records = db.execute("""
            SELECT distributions.*, donations.food_name
            FROM distributions
            JOIN donations ON donations.id = distributions.donation_id
            ORDER BY distributions.id DESC
        """).fetchall()

    return render_template(
        "Distribution.html", available=available, records=records
    )


@app.route("/Volunteering", methods=["GET", "POST"])
@login_required
def Volunteering():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        phone = request.form.get("phone", "").strip()
        email = request.form.get("email", "").strip()
        area = request.form.get("area", "").strip()
        availability = request.form.get("availability", "").strip()

        if not all([name, phone, email, area, availability]):
            flash("Please complete all volunteer fields.", "error")
        else:
            with get_db() as db:
                db.execute("""
                    INSERT INTO volunteers
                    (name, phone, email, area, availability)
                    VALUES (?, ?, ?, ?, ?)
                """, (name, phone, email, area, availability))
            flash("Volunteer registered successfully.", "success")
            return redirect(url_for("Volunteering"))

    with get_db() as db:
        records = db.execute(
            "SELECT * FROM volunteers ORDER BY id DESC"
        ).fetchall()

    return render_template("Volunteering.html", records=records)


@app.route("/Donate_to_needy", methods=["GET", "POST"])
@login_required
def Donate_to_needy():
    if request.method == "POST":
        recipient = request.form.get("recipient", "").strip()
        food_required = request.form.get("food_required", "").strip()
        people_count = request.form.get("people_count", type=int)
        location = request.form.get("location", "").strip()
        phone = request.form.get("phone", "").strip()

        if (not all([recipient, food_required, location, phone])
                or people_count is None or people_count <= 0):
            flash("Please complete the form with valid details.", "error")
        else:
            with get_db() as db:
                db.execute("""
                    INSERT INTO needy_requests
                    (recipient, food_required, people_count, location,
                     phone, status, created_at)
                    VALUES (?, ?, ?, ?, ?, 'Pending', ?)
                """, (
                    recipient, food_required, people_count, location,
                    phone, datetime.now().strftime("%Y-%m-%d %H:%M")
                ))
            flash("Food assistance request submitted.", "success")
            return redirect(url_for("Donate_to_needy"))

    with get_db() as db:
        records = db.execute(
            "SELECT * FROM needy_requests ORDER BY id DESC"
        ).fetchall()

    return render_template("Donate_to_needy.html", records=records)


@app.route("/Reports")
@login_required
def Reports():
    with get_db() as db:
        summary = {
            "total_donations": db.execute(
                "SELECT COUNT(*) FROM donations"
            ).fetchone()[0],
            "available": db.execute(
                "SELECT COUNT(*) FROM donations WHERE status='Available'"
            ).fetchone()[0],
            "distributed": db.execute(
                "SELECT COUNT(*) FROM distributions"
            ).fetchone()[0],
            "volunteers": db.execute(
                "SELECT COUNT(*) FROM volunteers"
            ).fetchone()[0],
            "requests": db.execute(
                "SELECT COUNT(*) FROM needy_requests"
            ).fetchone()[0],
        }
        donations_list = db.execute(
            "SELECT * FROM donations ORDER BY id DESC"
        ).fetchall()
        distribution_list = db.execute("""
            SELECT distributions.*, donations.food_name
            FROM distributions
            JOIN donations ON donations.id = distributions.donation_id
            ORDER BY distributions.id DESC
        """).fetchall()
        request_list = db.execute(
            "SELECT * FROM needy_requests ORDER BY id DESC"
        ).fetchall()

    return render_template(
        "Reports.html",
        summary=summary,
        donations_list=donations_list,
        distribution_list=distribution_list,
        request_list=request_list
    )


@app.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        flash(
            "For this demo, contact the project administrator to reset "
            "your password. Email-based reset is not configured.",
            "info"
        )
    return render_template("forgot_password.html")


@app.route("/reset-password", methods=["GET", "POST"])
def reset_password():
    flash(
        "Secure password reset is not configured in this demo. "
        "Please use a registered account or contact the administrator.",
        "info"
    )
    return render_template("reset_password.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("You have logged out.", "success")
    return redirect(url_for("index"))

init_db()

if __name__ == "__main__":
    app.run(debug=True)

