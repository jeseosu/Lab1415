
import os
import secrets
from datetime import datetime
from functools import wraps

from flask import (Flask, abort, flash, g, redirect, render_template,
                   request, session, url_for)
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import check_password_hash, generate_password_hash

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "change-me-in-production")
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get(
    "DATABASE_URL", "sqlite:///" + os.path.join(BASE_DIR, "forum.db"))
db = SQLAlchemy(app)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(20), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    topics = db.relationship("Topic", backref="author", lazy=True)
    posts = db.relationship("Post", backref="author", lazy=True)


class Category(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(60), nullable=False)
    position = db.Column(db.Integer, default=0)
    boards = db.relationship("Board", backref="category", lazy=True,
                             order_by="Board.position")


class Board(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(40), unique=True, nullable=False)
    title = db.Column(db.String(60), nullable=False)
    position = db.Column(db.Integer, default=0)
    category_id = db.Column(db.Integer, db.ForeignKey("category.id"), nullable=False)
    topics = db.relationship("Topic", backref="board", lazy=True,
                             order_by="desc(Topic.created_at)")


class Topic(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(120), nullable=False)
    body = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    board_id = db.Column(db.Integer, db.ForeignKey("board.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    posts = db.relationship("Post", backref="topic", lazy=True,
                            cascade="all, delete-orphan", order_by="Post.created_at")


class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    body = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    topic_id = db.Column(db.Integer, db.ForeignKey("topic.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)

SEED = [
    ("Японська культура", [("Аніме та манґа", "anime"), ("Косплей", "cosplay"),
                           ("Мова", "language"), ("Їжа", "food")]),
    ("Рецепти & Кухня", [("Суші & Роли", "sushi"), ("Рецепти & Кухня", "recipes"),
                         ("Супи & Рамен", "ramen"), ("Чайні церемонії", "tea")]),
    ("Інтереси", [("Технології", "tech"), ("Кіно & Серіали", "movies"),
                  ("Міфологія", "mythology"), ("Історія Японії", "history")]),
    ("Творчість", [("Малюнки & Скечі", "art"), ("Фотографія", "photo"),
                   ("Музика", "music"), ("Мода", "fashion")]),
    ("Спільнота", [("Балачки", "chat"), ("Обговорення сайту", "site"),
                   ("Новини Wolk-Talk", "news")]),
]


def seed_boards():
    if Category.query.first():
        return
    for ci, (cat_title, boards) in enumerate(SEED):
        cat = Category(title=cat_title, position=ci)
        db.session.add(cat)
        for bi, (title, slug) in enumerate(boards):
            cat.boards.append(Board(title=title, slug=slug, position=bi))
    db.session.commit()

@app.before_request
def load_user():
    uid = session.get("user_id")
    g.user = db.session.get(User, uid) if uid else None


@app.before_request
def check_csrf():
    if request.method == "POST":
        token = session.get("csrf_token")
        if not token or token != request.form.get("csrf_token"):
            abort(400, "Недійсний CSRF-токен")


@app.context_processor
def inject_globals():
    if "csrf_token" not in session:
        session["csrf_token"] = secrets.token_hex(16)
    return {
        "csrf_token": session["csrf_token"],
        "stats": {
            "users": User.query.count(),
            "topics": Topic.query.count(),
            "messages": Topic.query.count() + Post.query.count(),
        },
        "categories": Category.query.order_by(Category.position).all(),
    }


@app.template_filter("dt")
def format_dt(value):
    return value.strftime("%d.%m.%Y %H:%M")


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if g.user is None:
            flash("Спочатку увійдіть до системи.", "error")
            return redirect(url_for("login", next=request.path))
        return view(*args, **kwargs)
    return wrapped


def safe_next(target):
    """Редірект тільки на внутрішні адреси."""
    if target and target.startswith("/") and not target.startswith("//"):
        return target
    return url_for("index")


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/boards")
def boards():
    return render_template("boards.html")


@app.route("/statistic")
def statistic():
    latest = Topic.query.order_by(Topic.created_at.desc()).limit(5).all()
    return render_template("statistic.html", latest=latest)


@app.route("/board/<slug>")
def board_view(slug):
    board = Board.query.filter_by(slug=slug).first_or_404()
    return render_template("board.html", board=board)


@app.route("/board/<slug>/new", methods=["GET", "POST"])
@login_required
def new_topic(slug):
    board = Board.query.filter_by(slug=slug).first_or_404()
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        body = request.form.get("body", "").strip()
        if not (3 <= len(title) <= 120):
            flash("Назва теми має містити від 3 до 120 символів.", "error")
        elif not body:
            flash("Текст теми не може бути порожнім.", "error")
        else:
            topic = Topic(title=title, body=body, board=board, author=g.user)
            db.session.add(topic)
            db.session.commit()
            return redirect(url_for("topic_view", topic_id=topic.id))
    return render_template("new_topic.html", board=board)


@app.route("/topic/<int:topic_id>", methods=["GET", "POST"])
def topic_view(topic_id):
    topic = db.get_or_404(Topic, topic_id)
    if request.method == "POST":
        if g.user is None:
            flash("Щоб відповісти, увійдіть до системи.", "error")
            return redirect(url_for("login", next=request.path))
        body = request.form.get("body", "").strip()
        if not body:
            flash("Повідомлення не може бути порожнім.", "error")
        else:
            db.session.add(Post(body=body, topic=topic, author=g.user))
            db.session.commit()
            return redirect(url_for("topic_view", topic_id=topic.id) + "#last")
    return render_template("topic.html", topic=topic)


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        password2 = request.form.get("password2", "")
        if not (3 <= len(username) <= 20):
            flash("Ім'я користувача: від 3 до 20 символів.", "error")
        elif len(password) < 6:
            flash("Пароль має містити щонайменше 6 символів.", "error")
        elif password != password2:
            flash("Паролі не збігаються.", "error")
        elif User.query.filter(db.func.lower(User.username) == username.lower()).first():
            flash("Користувач з таким іменем вже існує.", "error")
        else:
            user = User(username=username,
                        password_hash=generate_password_hash(password))
            db.session.add(user)
            db.session.commit()
            session["user_id"] = user.id
            flash(f"Ласкаво просимо, {user.username}!", "success")
            return redirect(url_for("index"))
    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = User.query.filter(db.func.lower(User.username) == username.lower()).first()
        if user and check_password_hash(user.password_hash, password):
            session["user_id"] = user.id
            flash(f"Раді бачити, {user.username}!", "success")
            return redirect(safe_next(request.args.get("next")))
        flash("Невірне ім'я користувача або пароль.", "error")
    return render_template("login.html")


@app.route("/logout", methods=["POST"])
def logout():
    session.pop("user_id", None)
    flash("Ви вийшли з системи.", "success")
    return redirect(url_for("index"))


with app.app_context():
    db.create_all()
    seed_boards()

if __name__ == "__main__":
    app.run(debug=True)
