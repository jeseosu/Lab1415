# Wolk-Talk — форум про суші та азійську кухню (Flask)

## Запуск
```bash
python -m venv venv
venv\Scripts\activate        
pip install -r requirements.txt
python app.py
```
Відкрити: http://127.0.0.1:5000 — база `forum.db` і розділи створюються автоматично.

## Структура
- `app.py` — моделі (User, Category, Board, Topic, Post), маршрути, авторизація
- `templates/` — Jinja2-шаблони (`base.html` + сторінки)
- `static/` — твій `main.css` та картинки
- `test_app.py` — автотест (`python test_app.py`)

## Що вміє
Реєстрація/вхід (паролі хешуються), розділи дошки, створення тем, відповіді,
статистика з бази, CSRF-захист, редірект на вхід для гостей.
