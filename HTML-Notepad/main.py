import uvicorn
from fastapi import FastAPI, Request, Form
from moviepy.video.io.html_tools import templates
from pydantic import BaseModel
from starlette.responses import HTMLResponse
from starlette.staticfiles import StaticFiles
from starlette.templating import Jinja2Templates


class User(BaseModel):
    id: int
    name: str
    email: str
    password: str


users = []
for i in range(10):
    users.append(User(
        id=i + 1,
        name=f"Jhon{i + 1}",
        email=f"Jhon{i + 1}@mail.ru",
        password=f"pass{i + 1}"
        # Placeholder password for demonstration purposes. In a real-world application, you should store passwords securely.
    )
    )

app = FastAPI()
templates = Jinja2Templates(directory='templates')
app.mount('/static', StaticFiles(directory='static'), name='static')


@app.get('/users', response_class=HTMLResponse)
def get_users(request: Request):
    return templates.TemplateResponse('user.html', {'request': request, 'users': users})


@app.post('/users', response_class=HTMLResponse)
def delete_user(request: Request, user_id: int = Form(...)):
    for user in users:
        if user.id == user_id:
            users.remove(user)
            break
    return templates.TemplateResponse('user.html', {'request': request, 'users': users})


@app.get("/users/add", response_class=HTMLResponse)
def show_add_user_form(request: Request):
    return templates.TemplateResponse('add_user.html', {'request': request})


@app.post("/notepad_form")
async def process_form(request: Request):
    form_data = await request.form()
    name = form_data.get('name')
    email = form_data.get('email')
    password = form_data.get('password')
    users.append(
        User(
            id=len(users) + 1,
            name=name,
            email=email,
            password=password
        )
    )
    return templates.TemplateResponse('form_success.html', {'request': request})


if __name__ == '__main__':
    uvicorn.run(
        "main:app",
        host="127.0.0.1",
        port=8000,
        reload=True
    )
