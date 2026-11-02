import os
import calendar
from datetime import date, datetime, timedelta
from functools import wraps
from urllib.parse import urlsplit

import click
from flask import Flask, abort, flash, redirect, render_template, request, url_for
from flask_login import (
    LoginManager,
    UserMixin,
    current_user,
    login_required,
    login_user,
    logout_user,
)
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func, inspect, text
from werkzeug.security import check_password_hash, generate_password_hash

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-change-me")

# Cloud DB: đặt DATABASE_URL trỏ tới PostgreSQL trên cloud (Neon, Supabase, Render, ...).
# Nếu không đặt, dùng SQLite để chạy thử ở máy local.
db_url = os.environ.get("DATABASE_URL", "sqlite:///tasks.db")
if db_url.startswith("postgres://"):  # SQLAlchemy cần "postgresql://"
    db_url = db_url.replace("postgres://", "postgresql://", 1)

app.config["SQLALCHEMY_DATABASE_URI"] = db_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {"pool_pre_ping": True}
app.config["REMEMBER_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = "login"
login_manager.login_message = "Vui lòng đăng nhập để tiếp tục."
login_manager.login_message_category = "warning"


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(254), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    is_admin = db.Column(db.Boolean, nullable=False, default=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


@login_manager.user_loader
def load_user(user_id):
    try:
        return db.session.get(User, int(user_id))
    except (TypeError, ValueError):
        return None


class Task(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    subject = db.Column(db.String(100), default="")
    description = db.Column(db.Text, default="")
    due_date = db.Column(db.Date, nullable=False)
    done = db.Column(db.Boolean, default=False, nullable=False)
    completed_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    user = db.relationship(User, backref="tasks")

    @property
    def overdue(self):
        return (not self.done) and self.due_date < date.today()

    @property
    def days_left(self):
        return (self.due_date - date.today()).days


with app.app_context():
    db.create_all()
    if "user_id" not in {column["name"] for column in inspect(db.engine).get_columns("task")}:
        with db.engine.begin() as connection:
            connection.execute(text('ALTER TABLE task ADD COLUMN user_id INTEGER REFERENCES "user" (id)'))
    if "completed_at" not in {column["name"] for column in inspect(db.engine).get_columns("task")}:
        with db.engine.begin() as connection:
            connection.execute(text("ALTER TABLE task ADD COLUMN completed_at TIMESTAMP NULL"))
    if "is_admin" not in {column["name"] for column in inspect(db.engine).get_columns("user")}:
        with db.engine.begin() as connection:
            connection.execute(
                text('ALTER TABLE "user" ADD COLUMN is_admin BOOLEAN NOT NULL DEFAULT FALSE')
            )


@app.cli.command("make-admin")
@click.argument("email")
def make_admin(email):
    """Grant admin access to an existing account."""
    user = User.query.filter_by(email=email.strip().lower()).first()
    if user is None:
        raise click.ClickException(
            f"Không tìm thấy tài khoản {email}. Hãy đăng ký tài khoản trước."
        )
    if user.is_admin:
        click.echo(f"{user.email} đã có quyền admin.")
        return
    user.is_admin = True
    db.session.commit()
    click.echo(f"Đã cấp quyền admin cho {user.email}.")


def admin_required(view):
    @wraps(view)
    @login_required
    def wrapped(*args, **kwargs):
        if not current_user.is_admin:
            abort(403)
        return view(*args, **kwargs)

    return wrapped


def safe_next_url(target):
    if not target:
        return url_for("index")
    parsed = urlsplit(target)
    if parsed.scheme or parsed.netloc:
        if parsed.scheme != request.scheme or parsed.netloc != request.host:
            return url_for("index")
        target = parsed.path or "/"
        if parsed.query:
            target += f"?{parsed.query}"
        if parsed.fragment:
            target += f"#{parsed.fragment}"
        parsed = urlsplit(target)
    if (
        not parsed.path.startswith("/")
        or parsed.path.startswith("//")
        or "\\" in parsed.path
    ):
        return url_for("index")
    return target


@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("index"))
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user = User.query.filter_by(email=email).first()
        if user is None or not user.check_password(password):
            flash("Email hoặc mật khẩu không chính xác.", "danger")
        else:
            login_user(user, remember=request.form.get("remember") == "on")
            return redirect(safe_next_url(request.args.get("next")))
    return render_template("login.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("index"))
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")
        if "@" not in email or any(character.isspace() for character in email):
            flash("Vui lòng nhập địa chỉ email hợp lệ.", "danger")
        elif len(password) < 8:
            flash("Mật khẩu cần có ít nhất 8 ký tự.", "danger")
        elif password != confirm_password:
            flash("Mật khẩu xác nhận không khớp.", "danger")
        elif User.query.filter_by(email=email).first():
            flash("Email này đã được đăng ký.", "danger")
        else:
            first_user = User.query.first() is None
            user = User(email=email)
            user.set_password(password)
            db.session.add(user)
            db.session.flush()
            if first_user:
                Task.query.filter_by(user_id=None).update(
                    {"user_id": user.id}, synchronize_session=False
                )
            db.session.commit()
            login_user(user)
            flash("Tạo tài khoản thành công. Chào mừng bạn!", "success")
            return redirect(url_for("index"))
    return render_template("register.html")


@app.route("/logout", methods=["POST"])
@login_required
def logout():
    logout_user()
    flash("Bạn đã đăng xuất.", "success")
    return redirect(url_for("login"))


@app.route("/forgot-password")
def forgot_password():
    return render_template("forgot_password.html")


@app.route("/admin")
@admin_required
def admin_dashboard():
    total_tasks = Task.query.count()
    done_tasks = Task.query.filter_by(done=True).count()
    overdue_tasks = Task.query.filter(
        Task.done.is_(False), Task.due_date < date.today()
    ).count()
    pending_tasks = total_tasks - done_tasks - overdue_tasks
    done_percent = round(done_tasks / total_tasks * 100, 1) if total_tasks else 0
    overdue_percent = round(overdue_tasks / total_tasks * 100, 1) if total_tasks else 0
    pending_percent = round(pending_tasks / total_tasks * 100, 1) if total_tasks else 0
    user_task_counts = (
        db.session.query(
            User.id,
            User.email,
            func.count(Task.id).label("task_count"),
        )
        .outerjoin(Task, Task.user_id == User.id)
        .group_by(User.id, User.email)
        .order_by(func.count(Task.id).desc(), User.id.asc())
        .limit(6)
        .all()
    )
    users = User.query.order_by(User.id.desc()).limit(10).all()
    tasks = Task.query.order_by(Task.id.desc()).limit(10).all()
    return render_template(
        "admin.html",
        users=users,
        tasks=tasks,
        total_users=User.query.count(),
        total_tasks=total_tasks,
        done_tasks=done_tasks,
        overdue_tasks=overdue_tasks,
        pending_tasks=pending_tasks,
        done_percent=done_percent,
        overdue_percent=overdue_percent,
        pending_percent=pending_percent,
        user_task_counts=user_task_counts,
    )


def parse_form():
    title = request.form.get("title", "").strip()
    due = request.form.get("due_date", "")
    if not title or not due:
        return None
    try:
        due_date = datetime.strptime(due, "%Y-%m-%d").date()
    except ValueError:
        return None
    return {
        "title": title,
        "subject": request.form.get("subject", "").strip(),
        "description": request.form.get("description", "").strip(),
        "due_date": due_date,
    }


@app.route("/")
@login_required
def index():
    today = date.today()
    flt = request.args.get("filter", "all")
    user_tasks = Task.query.filter_by(user_id=current_user.id).all()
    matching_tasks = user_tasks
    query_text = request.args.get("q", "").strip()
    if query_text:
        search_text = query_text.casefold()
        matching_tasks = [
            task for task in user_tasks
            if any(
                search_text in (field or "").casefold()
                for field in (task.title, task.subject, task.description)
            )
        ]
    if flt == "pending":
        matching_tasks = [task for task in matching_tasks if not task.done]
    elif flt == "done":
        matching_tasks = [task for task in matching_tasks if task.done]
    tasks = sorted(matching_tasks, key=lambda task: (task.done, task.due_date))

    total = len(user_tasks)
    done_count = sum(task.done for task in user_tasks)
    overdue_count = sum(task.overdue for task in user_tasks)
    active_count = total - done_count - overdue_count
    today_count = sum(
        not task.done and task.due_date == today for task in user_tasks
    )
    upcoming_count = sum(
        not task.done and task.due_date > today for task in user_tasks
    )
    today_tasks = sorted(
        (task for task in user_tasks if not task.done and task.due_date == today),
        key=lambda task: task.title.casefold(),
    )
    coming_tasks = sorted(
        (
            task for task in user_tasks
            if not task.done and today < task.due_date <= today + timedelta(days=7)
        ),
        key=lambda task: (task.due_date, task.title.casefold()),
    )[:5]
    done_percent = round(done_count / total * 100, 1) if total else 0
    overdue_percent = round(overdue_count / total * 100, 1) if total else 0
    active_percent = round(active_count / total * 100, 1) if total else 0
    subject_progress_map = {}
    for task in user_tasks:
        subject_name = task.subject.strip() or "Chưa phân loại"
        subject_stats = subject_progress_map.setdefault(
            subject_name, {"subject": subject_name, "total": 0, "completed": 0}
        )
        subject_stats["total"] += 1
        subject_stats["completed"] += int(task.done)
    subject_progress = sorted(
        subject_progress_map.values(),
        key=lambda subject: (-subject["total"], subject["subject"].casefold()),
    )[:6]
    for subject in subject_progress:
        subject["percent"] = round(
            subject["completed"] / subject["total"] * 100
        )

    current_week_start = today - timedelta(days=today.weekday())
    completion_weeks = []
    for weeks_ago in reversed(range(8)):
        start = current_week_start - timedelta(weeks=weeks_ago)
        end = start + timedelta(days=7)
        completed_count = sum(
            task.completed_at is not None
            and start <= task.completed_at.date() < end
            for task in user_tasks
        )
        completion_weeks.append({
            "start": start,
            "end": end,
            "label": "Tuần này" if weeks_ago == 0 else start.strftime("%d/%m"),
            "completed": completed_count,
        })
    max_weekly_completed = max(
        (week["completed"] for week in completion_weeks), default=0
    )
    untracked_done_count = sum(
        task.done and task.completed_at is None for task in user_tasks
    )

    weekday_labels = (
        "Thứ 2", "Thứ 3", "Thứ 4", "Thứ 5", "Thứ 6", "Thứ 7", "Chủ nhật"
    )
    week_start = today
    weekly_due = []
    for offset in range(7):
        due_day = week_start + timedelta(days=offset)
        day_tasks = [
            task for task in user_tasks
            if task.due_date == due_day and not task.done
        ]
        weekly_due.append({
            "date": due_day,
            "label": weekday_labels[due_day.weekday()],
            "count": len(day_tasks),
            "done_count": sum(
                task.due_date == due_day and task.done for task in user_tasks
            ),
        })
    max_weekly_due = max((day["count"] + day["done_count"] for day in weekly_due), default=0)
    monthly_due = {}
    for task in user_tasks:
        if task.due_date.year == today.year and task.due_date.month == today.month:
            monthly_due[task.due_date.day] = monthly_due.get(task.due_date.day, 0) + 1
    calendar_rows = [
        [
            {
                "date": day,
                "outside_month": day.month != today.month,
                "due_count": monthly_due.get(day.day, 0) if day.month == today.month else 0,
            }
            for day in week
        ]
        for week in calendar.Calendar(firstweekday=0).monthdatescalendar(
            today.year, today.month
        )
    ]
    priority_tasks = sorted(
        (
            task for task in user_tasks
            if not task.done and task.due_date <= today
        ),
        key=lambda task: task.due_date,
    )[:5]
    return render_template(
        "index.html",
        tasks=tasks,
        flt=flt,
        total=total,
        done_count=done_count,
        overdue_count=overdue_count,
        active_count=active_count,
        today_count=today_count,
        upcoming_count=upcoming_count,
        done_percent=done_percent,
        overdue_percent=overdue_percent,
        active_percent=active_percent,
        subject_progress=subject_progress,
        completion_weeks=completion_weeks,
        max_weekly_completed=max_weekly_completed,
        untracked_done_count=untracked_done_count,
        weekly_due=weekly_due,
        max_weekly_due=max_weekly_due,
        priority_tasks=priority_tasks,
        today_tasks=today_tasks,
        coming_tasks=coming_tasks,
        calendar_rows=calendar_rows,
        calendar_month=today.strftime("%m/%Y"),
        today=today,
        query_text=query_text,
    )


@app.route("/add", methods=["GET", "POST"])
@login_required
def add():
    if request.method == "POST":
        data = parse_form()
        if not data:
            flash("Vui lòng nhập tiêu đề và hạn nộp hợp lệ.", "danger")
            return render_template("form.html", task=None)
        db.session.add(Task(**data, user_id=current_user.id))
        db.session.commit()
        flash("Đã thêm bài tập.", "success")
        return redirect(url_for("index"))
    return render_template("form.html", task=None)


@app.route("/edit/<int:task_id>", methods=["GET", "POST"])
@login_required
def edit(task_id):
    task = Task.query.filter_by(id=task_id, user_id=current_user.id).first_or_404()
    if request.method == "POST":
        data = parse_form()
        if not data:
            flash("Vui lòng nhập tiêu đề và hạn nộp hợp lệ.", "danger")
            return render_template("form.html", task=task)
        for k, v in data.items():
            setattr(task, k, v)
        db.session.commit()
        flash("Đã cập nhật bài tập.", "success")
        return redirect(url_for("index"))
    return render_template("form.html", task=task)


@app.route("/toggle/<int:task_id>", methods=["POST"])
@login_required
def toggle(task_id):
    task = Task.query.filter_by(id=task_id, user_id=current_user.id).first_or_404()
    task.done = not task.done
    task.completed_at = datetime.utcnow() if task.done else None
    db.session.commit()
    return redirect(request.referrer or url_for("index"))


@app.route("/delete/<int:task_id>", methods=["POST"])
@login_required
def delete(task_id):
    task = Task.query.filter_by(id=task_id, user_id=current_user.id).first_or_404()
    db.session.delete(task)
    db.session.commit()
    flash("Đã xóa bài tập.", "warning")
    return redirect(url_for("index"))


@app.route("/health")
def health():
    return {"status": "ok"}


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
