import os
import math
import sqlite3
from pathlib import Path
from datetime import date
from functools import wraps

from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    session,
    flash,
    g,
    abort,
    jsonify,
)
from werkzeug.security import generate_password_hash, check_password_hash


# =========================================================
# APPLICATION CONFIGURATION
# =========================================================

BASE_DIR = Path(__file__).resolve().parent

app = Flask(
    __name__,
    template_folder=str(BASE_DIR / "templates"),
    static_folder=str(BASE_DIR / "static"),
)

app.config["SECRET_KEY"] = os.environ.get(
    "SECRET_KEY",
    "dev-only-change-this-secret-key"
)

INSTANCE_DIR = BASE_DIR / "instance"
INSTANCE_DIR.mkdir(parents=True, exist_ok=True)

DATABASE = INSTANCE_DIR / "freelancehub.db"


SERVICE_CATEGORIES = [
    "Web Development",
    "Mobile App Development",
    "UI/UX Design",
    "Graphic Design",
    "Writing",
    "Digital Marketing",
    "Data Entry",
    "Video Editing",
    "Programming",
    "Other",
]

PROJECT_CATEGORIES = SERVICE_CATEGORIES.copy()


# =========================================================
# DATABASE CONNECTION
# =========================================================

def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(str(DATABASE), timeout=15)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
        g.db.execute("PRAGMA busy_timeout = 15000")

    return g.db


@app.teardown_appcontext
def close_db(exception=None):
    db = g.pop("db", None)

    if db is not None:
        db.close()


def init_db():
    connection = sqlite3.connect(str(DATABASE), timeout=15)

    try:
        connection.execute("PRAGMA foreign_keys = ON")

        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE COLLATE NOCASE,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL
                    CHECK (role IN ('client', 'freelancer')),
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS services (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                category TEXT NOT NULL,
                description TEXT NOT NULL,
                price REAL NOT NULL CHECK (price >= 0),
                contact_phone TEXT NOT NULL DEFAULT '',
                contact_email TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id)
                    REFERENCES users(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS project_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                client_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                category TEXT NOT NULL,
                description TEXT NOT NULL,
                budget REAL NOT NULL CHECK (budget >= 0),
                deadline TEXT NOT NULL,
                contact_phone TEXT NOT NULL DEFAULT '',
                contact_email TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'open'
                    CHECK (
                        status IN (
                            'open',
                            'assigned',
                            'completed',
                            'cancelled'
                        )
                    ),
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (client_id)
                    REFERENCES users(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS proposals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL,
                freelancer_id INTEGER NOT NULL,
                message TEXT NOT NULL,
                proposed_price REAL NOT NULL
                    CHECK (proposed_price >= 0),
                delivery_days INTEGER NOT NULL
                    CHECK (delivery_days > 0),
                status TEXT NOT NULL DEFAULT 'pending'
                    CHECK (
                        status IN (
                            'pending',
                            'accepted',
                            'rejected'
                        )
                    ),
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

                UNIQUE(project_id, freelancer_id),

                FOREIGN KEY (project_id)
                    REFERENCES project_requests(id) ON DELETE CASCADE,

                FOREIGN KEY (freelancer_id)
                    REFERENCES users(id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_services_category
                ON services(category);

            CREATE INDEX IF NOT EXISTS idx_services_user
                ON services(user_id);

            CREATE INDEX IF NOT EXISTS idx_projects_client
                ON project_requests(client_id);

            CREATE INDEX IF NOT EXISTS idx_projects_status
                ON project_requests(status);

            CREATE INDEX IF NOT EXISTS idx_projects_category
                ON project_requests(category);

            CREATE INDEX IF NOT EXISTS idx_proposals_project
                ON proposals(project_id);

            CREATE INDEX IF NOT EXISTS idx_proposals_freelancer
                ON proposals(freelancer_id);
            """
        )

        # Migrate existing databases without deleting saved records.
        for table_name in ("services", "project_requests"):
            existing_columns = {
                row[1]
                for row in connection.execute(
                    f"PRAGMA table_info({table_name})"
                ).fetchall()
            }

            for column_name in ("contact_phone", "contact_email"):
                if column_name not in existing_columns:
                    connection.execute(
                        f"""
                        ALTER TABLE {table_name}
                        ADD COLUMN {column_name} TEXT NOT NULL DEFAULT ''
                        """
                    )

        connection.commit()

    finally:
        connection.close()


# IMPORTANT:
# Initialize the database when this module is imported by Gunicorn.
# This fixes the "no such table: services" error on Render.
init_db()


# =========================================================
# AUTHENTICATION AND ROLE CHECKS
# =========================================================

def login_required(view):
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        if not session.get("user_id"):
            flash("Please log in to continue.", "warning")
            return redirect(url_for("login"))

        return view(*args, **kwargs)

    return wrapped_view


def role_required(required_role):
    def decorator(view):
        @wraps(view)
        @login_required
        def wrapped_view(*args, **kwargs):
            if session.get("user_role") != required_role:
                flash(
                    "You do not have permission to perform this action.",
                    "danger",
                )
                return redirect(url_for("dashboard"))

            return view(*args, **kwargs)

        return wrapped_view

    return decorator


def get_current_user():
    user_id = session.get("user_id")

    if not user_id:
        return None

    return get_db().execute(
        """
        SELECT id, name, email, role, created_at
        FROM users
        WHERE id = ?
        """,
        (user_id,),
    ).fetchone()


@app.context_processor
def inject_global_template_values():
    return {
        "current_user": get_current_user(),
        "current_role": session.get("user_role"),
        "today": date.today().isoformat(),
    }


# =========================================================
# HOME PAGE
# =========================================================

@app.route("/", endpoint="home")
@app.route("/", endpoint="index")
def homepage():
    db = get_db()

    services = db.execute(
        """
        SELECT
            services.*,
            users.name AS freelancer_name
        FROM services
        JOIN users ON users.id = services.user_id
        ORDER BY services.id DESC
        LIMIT 6
        """
    ).fetchall()

    projects = db.execute(
        """
        SELECT
            project_requests.*,
            users.name AS client_name
        FROM project_requests
        JOIN users
            ON users.id = project_requests.client_id
        WHERE project_requests.status = 'open'
        ORDER BY project_requests.id DESC
        LIMIT 6
        """
    ).fetchall()

    return render_template(
        "index.html",
        services=services,
        projects=projects,
    )


# =========================================================
# REGISTER
# =========================================================

@app.route("/register", methods=["GET", "POST"])
def register():
    if session.get("user_id"):
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        role = request.form.get("role", "").strip().lower()

        errors = []

        if not name:
            errors.append("Please enter your name.")

        if not email or "@" not in email:
            errors.append("Please enter a valid email address.")

        if len(password) < 8:
            errors.append("Password must contain at least 8 characters.")

        if role not in ("client", "freelancer"):
            errors.append("Please select a valid account type.")

        db = get_db()

        if email:
            existing = db.execute(
                "SELECT id FROM users WHERE email = ?",
                (email,),
            ).fetchone()

            if existing:
                errors.append("This email is already registered.")

        if errors:
            for error in errors:
                flash(error, "danger")

            return render_template("register.html")

        try:
            db.execute(
                """
                INSERT INTO users (name, email, password_hash, role)
                VALUES (?, ?, ?, ?)
                """,
                (
                    name,
                    email,
                    generate_password_hash(password),
                    role,
                ),
            )

            db.commit()

        except sqlite3.IntegrityError:
            db.rollback()
            flash("This email is already registered.", "danger")
            return render_template("register.html")

        flash("Registration successful. Please log in.", "success")
        return redirect(url_for("login"))

    return render_template("register.html")


# =========================================================
# LOGIN
# =========================================================

@app.route("/login", methods=["GET", "POST"])
def login():
    if session.get("user_id"):
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        user = get_db().execute(
            "SELECT * FROM users WHERE email = ?",
            (email,),
        ).fetchone()

        if user and check_password_hash(user["password_hash"], password):
            session.clear()
            session["user_id"] = user["id"]
            session["user_name"] = user["name"]
            session["user_role"] = user["role"]

            flash(f"Welcome back, {user['name']}!", "success")
            return redirect(url_for("dashboard"))

        flash("Invalid email or password.", "danger")

    return render_template("login.html")


# =========================================================
# LOGOUT
# =========================================================

@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for("home"))


# =========================================================
# DASHBOARD
# =========================================================

@app.route("/dashboard")
@login_required
def dashboard():
    db = get_db()
    user_id = session["user_id"]
    role = session["user_role"]

    user_services = []
    user_projects = []
    user_proposals = []

    if role == "freelancer":
        user_services = db.execute(
            """
            SELECT *
            FROM services
            WHERE user_id = ?
            ORDER BY id DESC
            """,
            (user_id,),
        ).fetchall()

        user_proposals = db.execute(
            """
            SELECT
                proposals.*,
                project_requests.title AS project_title,
                project_requests.status AS project_status,
                project_requests.budget AS project_budget
            FROM proposals
            JOIN project_requests
                ON project_requests.id = proposals.project_id
            WHERE proposals.freelancer_id = ?
            ORDER BY proposals.id DESC
            """,
            (user_id,),
        ).fetchall()

    elif role == "client":
        user_projects = db.execute(
            """
            SELECT
                project_requests.*,
                (
                    SELECT COUNT(*)
                    FROM proposals
                    WHERE proposals.project_id = project_requests.id
                ) AS proposal_count
            FROM project_requests
            WHERE project_requests.client_id = ?
            ORDER BY project_requests.id DESC
            """,
            (user_id,),
        ).fetchall()

    return render_template(
        "dashboard.html",
        user_services=user_services,
        user_projects=user_projects,
        user_proposals=user_proposals,
    )


# =========================================================
# BROWSE AND SEARCH SERVICES
# =========================================================

@app.route("/services")
def services():
    db = get_db()

    search_query = request.args.get("q", "").strip()
    selected_category = request.args.get("category", "").strip()

    sql = """
        SELECT services.*, users.name AS freelancer_name
        FROM services
        JOIN users ON users.id = services.user_id
        WHERE 1 = 1
    """

    params = []

    if search_query:
        pattern = f"%{search_query}%"

        sql += """
            AND (
                services.title LIKE ?
                OR services.description LIKE ?
                OR services.category LIKE ?
                OR users.name LIKE ?
            )
        """

        params.extend([pattern, pattern, pattern, pattern])

    if selected_category:
        sql += " AND services.category = ?"
        params.append(selected_category)

    sql += " ORDER BY services.id DESC"

    service_list = db.execute(sql, params).fetchall()

    return render_template(
        "services.html",
        services=service_list,
        categories=SERVICE_CATEGORIES,
        search_query=search_query,
        selected_category=selected_category,
    )


# =========================================================
# SERVICE DETAILS
# =========================================================

@app.route("/service/<int:service_id>")
def service_detail(service_id):
    service = get_db().execute(
        """
        SELECT
            services.*,
            users.name AS freelancer_name,
            users.email AS freelancer_email
        FROM services
        JOIN users ON users.id = services.user_id
        WHERE services.id = ?
        """,
        (service_id,),
    ).fetchone()

    if service is None:
        abort(404)

    return render_template(
        "service_detail.html",
        service=service,
    )


# =========================================================
# POST A SERVICE
# =========================================================

@app.route("/add-service", methods=["GET", "POST"])
@role_required("freelancer")
def add_service():
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        category = request.form.get("category", "").strip()
        description = request.form.get("description", "").strip()
        price_text = request.form.get("price", "").strip()
        contact_phone = request.form.get("contact_phone", "").strip()
        contact_email = request.form.get(
            "contact_email", ""
        ).strip().lower()

        errors = []

        if not title:
            errors.append("Please enter a service title.")

        if category not in SERVICE_CATEGORIES:
            errors.append("Please select a valid category.")

        if not description:
            errors.append("Please enter a description.")

        if not contact_phone:
            errors.append("Please enter a contact phone number.")
        elif len(contact_phone) > 30:
            errors.append("The contact phone number is too long.")

        if not contact_email or "@" not in contact_email:
            errors.append("Please enter a valid contact email address.")

        try:
            price = float(price_text)

            if not math.isfinite(price) or price < 0:
                errors.append("Enter a valid non-negative price.")

        except (ValueError, TypeError):
            price = None
            errors.append("Please enter a valid price.")

        if errors:
            for error in errors:
                flash(error, "danger")

            return render_template(
                "add_service.html",
                categories=SERVICE_CATEGORIES,
            )

        db = get_db()

        db.execute(
            """
            INSERT INTO services (
                user_id,
                title,
                category,
                description,
                price,
                contact_phone,
                contact_email
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                session["user_id"],
                title,
                category,
                description,
                price,
                contact_phone,
                contact_email,
            ),
        )

        db.commit()

        flash("Your service has been published.", "success")
        return redirect(url_for("services"))

    return render_template(
        "add_service.html",
        categories=SERVICE_CATEGORIES,
    )


# =========================================================
# DELETE YOUR SERVICE
# =========================================================

@app.route("/delete-service/<int:service_id>", methods=["POST"])
@role_required("freelancer")
def delete_service(service_id):
    db = get_db()

    result = db.execute(
        """
        DELETE FROM services
        WHERE id = ? AND user_id = ?
        """,
        (service_id, session["user_id"]),
    )

    db.commit()

    if result.rowcount == 0:
        abort(404)

    flash("Your service has been deleted.", "success")
    return redirect(url_for("dashboard"))


# =========================================================
# BROWSE AND SEARCH PROJECTS
# =========================================================

@app.route("/projects")
def projects():
    db = get_db()

    search_query = request.args.get("q", "").strip()
    selected_category = request.args.get("category", "").strip()

    sql = """
        SELECT
            project_requests.*,
            users.name AS client_name
        FROM project_requests
        JOIN users ON users.id = project_requests.client_id
        WHERE project_requests.status = 'open'
    """

    params = []

    if search_query:
        pattern = f"%{search_query}%"

        sql += """
            AND (
                project_requests.title LIKE ?
                OR project_requests.description LIKE ?
                OR project_requests.category LIKE ?
                OR users.name LIKE ?
            )
        """

        params.extend([pattern, pattern, pattern, pattern])

    if selected_category:
        sql += " AND project_requests.category = ?"
        params.append(selected_category)

    sql += " ORDER BY project_requests.id DESC"

    project_list = db.execute(sql, params).fetchall()

    return render_template(
        "projects.html",
        projects=project_list,
        categories=PROJECT_CATEGORIES,
        search_query=search_query,
        selected_category=selected_category,
    )


# =========================================================
# CLIENT POSTS A PROJECT
# =========================================================

@app.route("/projects/new", methods=["GET", "POST"])
@role_required("client")
def create_project():
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        category = request.form.get("category", "").strip()
        description = request.form.get("description", "").strip()
        budget_text = request.form.get("budget", "").strip()
        deadline = request.form.get("deadline", "").strip()
        contact_phone = request.form.get("contact_phone", "").strip()
        contact_email = request.form.get(
            "contact_email", ""
        ).strip().lower()

        errors = []

        if not title:
            errors.append("Please enter a project title.")
        elif len(title) > 150:
            errors.append("The project title must be 150 characters or fewer.")

        if category not in PROJECT_CATEGORIES:
            errors.append("Please select a valid project category.")

        if not description:
            errors.append("Please describe your project.")
        elif len(description) > 10000:
            errors.append("The project description is too long.")

        if not contact_phone:
            errors.append("Please enter a contact phone number.")
        elif len(contact_phone) > 30:
            errors.append("The contact phone number is too long.")

        if not contact_email or "@" not in contact_email:
            errors.append("Please enter a valid contact email address.")

        try:
            budget = float(budget_text)

            if not math.isfinite(budget) or budget <= 0:
                errors.append("The budget must be greater than zero.")

        except (ValueError, TypeError):
            budget = None
            errors.append("Please enter a valid project budget.")

        try:
            deadline_date = date.fromisoformat(deadline)

            if deadline_date < date.today():
                errors.append("The deadline cannot be in the past.")

        except (ValueError, TypeError):
            deadline_date = None
            errors.append("Please enter a valid project deadline.")

        if errors:
            for error in errors:
                flash(error, "danger")

            return render_template(
                "create_project.html",
                categories=PROJECT_CATEGORIES,
                today=date.today().isoformat(),
            )

        db = get_db()

        try:
            cursor = db.execute(
                """
                INSERT INTO project_requests (
                    client_id,
                    title,
                    category,
                    description,
                    budget,
                    deadline,
                    contact_phone,
                    contact_email,
                    status
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'open')
                """,
                (
                    session["user_id"],
                    title,
                    category,
                    description,
                    budget,
                    deadline_date.isoformat(),
                    contact_phone,
                    contact_email,
                ),
            )

            project_id = cursor.lastrowid
            db.commit()

        except sqlite3.Error:
            db.rollback()
            app.logger.exception("Unable to create project")

            flash(
                "Unable to save the project. Please try again.",
                "danger",
            )

            return render_template(
                "create_project.html",
                categories=PROJECT_CATEGORIES,
                today=date.today().isoformat(),
            )

        flash("Your project has been posted successfully!", "success")

        return redirect(
            url_for("project_detail", project_id=project_id)
        )

    return render_template(
        "create_project.html",
        categories=PROJECT_CATEGORIES,
        today=date.today().isoformat(),
    )


# =========================================================
# VIEW PROJECT DETAILS
# =========================================================

@app.route("/projects/<int:project_id>")
def project_detail(project_id):
    db = get_db()

    project = db.execute(
        """
        SELECT
            project_requests.*,
            users.name AS client_name
        FROM project_requests
        JOIN users
            ON users.id = project_requests.client_id
        WHERE project_requests.id = ?
        """,
        (project_id,),
    ).fetchone()

    if project is None:
        abort(404)

    is_owner = (
        session.get("user_role") == "client"
        and session.get("user_id") == project["client_id"]
    )

    proposals = []

    if is_owner:
        proposals = db.execute(
            """
            SELECT
                proposals.*,
                users.name AS freelancer_name
            FROM proposals
            JOIN users
                ON users.id = proposals.freelancer_id
            WHERE proposals.project_id = ?
            ORDER BY proposals.id DESC
            """,
            (project_id,),
        ).fetchall()

    my_proposal = None

    if session.get("user_role") == "freelancer":
        my_proposal = db.execute(
            """
            SELECT *
            FROM proposals
            WHERE project_id = ? AND freelancer_id = ?
            """,
            (project_id, session["user_id"]),
        ).fetchone()

    return render_template(
        "project_detail.html",
        project=project,
        proposals=proposals,
        is_owner=is_owner,
        my_proposal=my_proposal,
    )


# =========================================================
# FREELANCER SUBMITS A PROPOSAL
# =========================================================

@app.route(
    "/projects/<int:project_id>/propose",
    methods=["POST"],
)
@role_required("freelancer")
def submit_proposal(project_id):
    db = get_db()

    project = db.execute(
        "SELECT * FROM project_requests WHERE id = ?",
        (project_id,),
    ).fetchone()

    if project is None:
        abort(404)

    if project["status"] != "open":
        flash("This project is not accepting proposals.", "warning")
        return redirect(
            url_for("project_detail", project_id=project_id)
        )

    message = request.form.get("message", "").strip()

    price_text = request.form.get(
        "proposed_price",
        request.form.get("price", ""),
    ).strip()

    delivery_text = request.form.get("delivery_days", "").strip()

    errors = []

    if not message:
        errors.append("Please enter your proposal message.")

    try:
        proposed_price = float(price_text)

        if not math.isfinite(proposed_price) or proposed_price < 0:
            errors.append("Enter a valid proposal price.")

    except (ValueError, TypeError):
        proposed_price = None
        errors.append("Please enter a valid proposal price.")

    try:
        delivery_days = int(delivery_text)

        if delivery_days <= 0:
            errors.append("Delivery time must be at least one day.")

    except (ValueError, TypeError):
        delivery_days = None
        errors.append("Please enter delivery time in days.")

    if errors:
        for error in errors:
            flash(error, "danger")

        return redirect(
            url_for("project_detail", project_id=project_id)
        )

    try:
        db.execute(
            """
            INSERT INTO proposals (
                project_id,
                freelancer_id,
                message,
                proposed_price,
                delivery_days,
                status
            )
            VALUES (?, ?, ?, ?, ?, 'pending')
            """,
            (
                project_id,
                session["user_id"],
                message,
                proposed_price,
                delivery_days,
            ),
        )

        db.commit()

    except sqlite3.IntegrityError:
        db.rollback()

        flash(
            "You have already submitted a proposal for this project.",
            "warning",
        )

        return redirect(
            url_for("project_detail", project_id=project_id)
        )

    flash("Your proposal has been submitted.", "success")
    return redirect(url_for("my_proposals"))


# =========================================================
# CLIENT ACCEPTS A PROPOSAL
# =========================================================

@app.route(
    "/proposals/<int:proposal_id>/accept",
    methods=["POST"],
)
@role_required("client")
def accept_proposal(proposal_id):
    db = get_db()

    try:
        db.execute("BEGIN IMMEDIATE")

        proposal = db.execute(
            """
            SELECT
                proposals.*,
                project_requests.client_id,
                project_requests.status AS project_status
            FROM proposals
            JOIN project_requests
                ON project_requests.id = proposals.project_id
            WHERE proposals.id = ?
            """,
            (proposal_id,),
        ).fetchone()

        if proposal is None:
            db.rollback()
            abort(404)

        if proposal["client_id"] != session["user_id"]:
            db.rollback()
            abort(403)

        if (
            proposal["project_status"] != "open"
            or proposal["status"] != "pending"
        ):
            db.rollback()

            flash(
                "This proposal is no longer available for acceptance.",
                "warning",
            )

            return redirect(
                url_for(
                    "project_detail",
                    project_id=proposal["project_id"],
                )
            )

        db.execute(
            """
            UPDATE project_requests
            SET status = 'assigned'
            WHERE id = ? AND status = 'open'
            """,
            (proposal["project_id"],),
        )

        db.execute(
            """
            UPDATE proposals
            SET status = 'accepted'
            WHERE id = ?
            """,
            (proposal_id,),
        )

        db.execute(
            """
            UPDATE proposals
            SET status = 'rejected'
            WHERE project_id = ?
              AND id != ?
              AND status = 'pending'
            """,
            (
                proposal["project_id"],
                proposal_id,
            ),
        )

        db.commit()

    except sqlite3.Error:
        db.rollback()
        app.logger.exception("Unable to accept proposal")

        flash(
            "Unable to accept this proposal. Please try again.",
            "danger",
        )

        return redirect(url_for("dashboard"))

    flash("Proposal accepted and project assigned.", "success")

    return redirect(
        url_for(
            "project_detail",
            project_id=proposal["project_id"],
        )
    )


# =========================================================
# CLIENT: MY PROJECTS
# =========================================================

@app.route("/my-projects")
@role_required("client")
def my_projects():
    projects_list = get_db().execute(
        """
        SELECT
            project_requests.*,
            (
                SELECT COUNT(*)
                FROM proposals
                WHERE proposals.project_id = project_requests.id
            ) AS proposal_count
        FROM project_requests
        WHERE project_requests.client_id = ?
        ORDER BY project_requests.id DESC
        """,
        (session["user_id"],),
    ).fetchall()

    return render_template(
        "my_projects.html",
        projects=projects_list,
    )


# =========================================================
# FREELANCER: MY PROPOSALS
# =========================================================

@app.route("/my-proposals")
@role_required("freelancer")
def my_proposals():
    proposals_list = get_db().execute(
        """
        SELECT
            proposals.*,
            project_requests.title AS project_title,
            project_requests.status AS project_status,
            project_requests.budget AS project_budget,
            project_requests.deadline AS project_deadline
        FROM proposals
        JOIN project_requests
            ON project_requests.id = proposals.project_id
        WHERE proposals.freelancer_id = ?
        ORDER BY proposals.id DESC
        """,
        (session["user_id"],),
    ).fetchall()

    return render_template(
        "my_proposals.html",
        proposals=proposals_list,
    )


# =========================================================
# CLIENT UPDATES PROJECT STATUS
# =========================================================

@app.route(
    "/projects/<int:project_id>/status",
    methods=["POST"],
)
@role_required("client")
def update_project_status(project_id):
    new_status = request.form.get("status", "").strip().lower()

    allowed_transitions = {
        "open": {"cancelled"},
        "assigned": {"completed"},
    }

    if new_status not in ("cancelled", "completed"):
        flash("Invalid project status.", "danger")
        return redirect(
            url_for("project_detail", project_id=project_id)
        )

    db = get_db()

    project = db.execute(
        """
        SELECT *
        FROM project_requests
        WHERE id = ? AND client_id = ?
        """,
        (project_id, session["user_id"]),
    ).fetchone()

    if project is None:
        abort(404)

    if new_status not in allowed_transitions.get(project["status"], set()):
        flash("This status change is not allowed.", "warning")
        return redirect(
            url_for("project_detail", project_id=project_id)
        )

    db.execute(
        """
        UPDATE project_requests
        SET status = ?
        WHERE id = ? AND client_id = ?
        """,
        (
            new_status,
            project_id,
            session["user_id"],
        ),
    )

    db.commit()

    flash("Project status updated.", "success")

    return redirect(
        url_for("project_detail", project_id=project_id)
    )


# =========================================================
# PROJECT JSON API
# =========================================================

@app.route("/api/projects")
def api_projects():
    rows = get_db().execute(
        """
        SELECT
            project_requests.id,
            project_requests.title,
            project_requests.category,
            project_requests.budget,
            project_requests.deadline,
            project_requests.status,
            project_requests.created_at,
            users.name AS client_name
        FROM project_requests
        JOIN users
            ON users.id = project_requests.client_id
        WHERE project_requests.status = 'open'
        ORDER BY project_requests.id DESC
        """
    ).fetchall()

    return jsonify({
        "projects": [
            {
                "id": row["id"],
                "title": row["title"],
                "category": row["category"],
                "budget": row["budget"],
                "deadline": row["deadline"],
                "status": row["status"],
                "created_at": row["created_at"],
                "client_name": row["client_name"],
                "url": url_for(
                    "project_detail",
                    project_id=row["id"],
                ),
            }
            for row in rows
        ]
    })


# =========================================================
# ERROR HANDLERS
# =========================================================

@app.errorhandler(403)
def forbidden(error):
    return (
        render_template(
            "404.html",
            error_message="You do not have permission to access this page.",
        ),
        403,
    )


@app.errorhandler(404)
def not_found(error):
    return (
        render_template(
            "404.html",
            error_message="The requested page or item was not found.",
        ),
        404,
    )


# =========================================================
# START APPLICATION
# =========================================================

if __name__ == "__main__":
    app.run(
        debug=True,
        host="127.0.0.1",
        port=5000,
    )
