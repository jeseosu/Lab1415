
import os, re, tempfile
os.environ["SECRET_KEY"] = "test"
os.environ["DATABASE_URL"] = "sqlite:///" + os.path.join(tempfile.mkdtemp(), "t.db")
import app as m

m.app.config["TESTING"] = True

def token(client, path):
    html = client.get(path).get_data(as_text=True)
    return re.search(r'name="csrf_token" value="([^"]+)"', html).group(1)

with m.app.app_context():
    m.db.session.remove(); m.db.drop_all(); m.db.create_all(); m.seed_boards()

c = m.app.test_client()
for p in ["/", "/boards", "/statistic", "/login", "/register", "/board/sushi"]:
    assert c.get(p).status_code == 200, p
assert c.post("/register", data={}).status_code == 400          # без CSRF
t = token(c, "/register")
r = c.post("/register", data={"csrf_token": t, "username": "sakura", "password": "secret1", "password2": "secret1"}, follow_redirects=True)
assert "Ласкаво просимо, sakura" in r.get_data(as_text=True)
t = token(c, "/board/sushi/new")
r = c.post("/board/sushi/new", data={"csrf_token": t, "title": "Який рис для суші?", "body": "Calrose чи короткозернистий?"}, follow_redirects=True)
assert "Який рис для суші?" in r.get_data(as_text=True)
r = c.post("/topic/1", data={"csrf_token": t, "body": "Беріть для суші спеціальний рис"}, follow_redirects=True)
assert "спеціальний рис" in r.get_data(as_text=True)
html = c.get("/").get_data(as_text=True)
assert "Користувачів: 1" in html and "Повідомлень: 2" in html and "Тем: 1" in html
c.post("/logout", data={"csrf_token": t})
assert c.get("/board/sushi/new").status_code == 302              # потрібен вхід
r = c.post("/login", data={"csrf_token": token(c, "/login"), "username": "sakura", "password": "bad"})
assert "Невірне" in r.get_data(as_text=True)
r = c.post("/login", data={"csrf_token": token(c, "/login"), "username": "SAKURA", "password": "secret1"}, follow_redirects=True)
assert "Раді бачити" in r.get_data(as_text=True)
print("ALL OK")
