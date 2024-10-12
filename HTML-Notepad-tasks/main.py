from typing import Optional

import uvicorn
from fastapi import FastAPI, Request, Form, HTTPException, Depends, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field
from sqlite3 import connect
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from starlette.middleware.sessions import SessionMiddleware

app = FastAPI()

# Подключение шаблонов
templates = Jinja2Templates(directory="templates")

# Подключение статики для CSS
app.mount("/static", StaticFiles(directory="static"), name="static")

# Добавление поддержки сессий
app.add_middleware(SessionMiddleware, secret_key="supersecretkey")

# Токен авторизации (используется для проверки авторизованного пользователя)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# База данных
DATABASE = "tasks.db"


def get_db_connection():
    return connect(DATABASE)


# Pydantic модель для валидации данных задач
class TaskModel(BaseModel):
    title: str = Field(..., min_length=3, max_length=100)
    description: Optional[str] = Field(None, max_length=250)
    completed: bool = False


# Pydantic модель для регистрации пользователей
class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=6)


# Функция для получения текущего пользователя
def get_current_user(request: Request):
    user = request.session.get("user")
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    return user


# Маршрут для регистрации
@app.get("/register")
async def register_page(request: Request):
    return templates.TemplateResponse("register.html", {"request": request})


# Создание пользователя (регистрация)
@app.post("/register")
async def register_user(username: str = Form(...), password: str = Form(...)):
    conn = get_db_connection()
    conn.row_factory = None  # Для таблицы пользователей row_factory не требуется
    user = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()

    if user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Username already exists")

    # Пароль сохраняется без хэширования
    conn.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, password))
    conn.commit()
    conn.close()

    return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)


# Маршрут для авторизации
@app.get("/login")
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})


# Аутентификация пользователя
@app.post("/login")
async def login_user(request: Request, form_data: OAuth2PasswordRequestForm = Depends()):
    conn = get_db_connection()
    conn.row_factory = None  # Для пользователей row_factory не требуется
    user = conn.execute("SELECT * FROM users WHERE username = ?", (form_data.username,)).fetchone()

    if not user or form_data.password != user[2]:  # user[1] содержит пароль
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Incorrect username or password")

    request.session['user'] = form_data.username
    return RedirectResponse(url="/tasks", status_code=status.HTTP_303_SEE_OTHER)


# Выход из аккаунта
@app.get("/logout")
async def logout_user(request: Request):
    request.session.clear()
    return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)


# Защита маршрута с проверкой авторизации
@app.get("/tasks")
async def get_tasks(request: Request, user: str = Depends(get_current_user)):
    conn = get_db_connection()
    conn.row_factory = lambda cursor, row: {"id": row[0], "title": row[1], "description": row[2], "completed": row[3],
                                            "user_id": row[4]}
    tasks = conn.execute("SELECT * FROM tasks WHERE user_id = (SELECT id FROM users WHERE username = ?)",
                         (user,)).fetchall()
    conn.close()
    return templates.TemplateResponse("index.html", {"request": request, "tasks": tasks, "user": user})


# Создание новой задачи (только для авторизованных пользователей)
@app.post("/tasks/create")
async def create_task(request: Request, title: str = Form(...), description: str = Form(None),
                      user: str = Depends(get_current_user)):
    task_data = {"title": title, "description": description, "completed": False}

    # Валидация данных с Pydantic
    try:
        task = TaskModel(**task_data)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    conn = get_db_connection()
    conn.row_factory = None  # Для выполнения запросов без структуры задач
    user_id = conn.execute("SELECT id FROM users WHERE username = ?", (user,)).fetchone()[0]
    conn.execute("INSERT INTO tasks (title, description, completed, user_id) VALUES (?, ?, ?, ?)",
                 (task.title, task.description, task.completed, user_id))
    conn.commit()
    conn.close()

    return RedirectResponse(url="/tasks", status_code=303)


# Обновление задачи (пометить как выполненную/невыполненную)
@app.post("/tasks/{task_id}/update")
async def update_task(task_id: int, user: str = Depends(get_current_user)):
    conn = get_db_connection()
    conn.row_factory = lambda cursor, row: {"id": row[0], "title": row[1], "description": row[2], "completed": row[3],
                                            "user_id": row[4]}
    task = conn.execute("SELECT * FROM tasks WHERE id = ? AND user_id = (SELECT id FROM users WHERE username = ?)",
                        (task_id, user)).fetchone()

    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")

    conn.execute("UPDATE tasks SET completed = ? WHERE id = ?", (not task['completed'], task_id))
    conn.commit()
    conn.close()

    return RedirectResponse(url="/tasks", status_code=303)


# Удаление задачи
@app.post("/tasks/{task_id}/delete")
async def delete_task(task_id: int, user: str = Depends(get_current_user)):
    conn = get_db_connection()
    conn.execute("DELETE FROM tasks WHERE id = ? AND user_id = (SELECT id FROM users WHERE username = ?)",
                 (task_id, user))
    conn.commit()
    conn.close()

    return RedirectResponse(url="/tasks", status_code=303)


# Инициализация базы данных
def init_db():
    conn = get_db_connection()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT,
            completed BOOLEAN NOT NULL DEFAULT 0,
            user_id INTEGER NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    ''')
    conn.commit()
    conn.close()


# Инициализация базы данных при запуске приложения
init_db()
if __name__ == '__main__':
    uvicorn.run(
        "main:app",
        host="127.0.0.1",
        port=8000,
        reload=True
    )
