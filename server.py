from starlette.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from starlette.requests import Request
from starlette.responses import RedirectResponse
from fastapi import Form
from pydantic import BaseModel
from typing import Optional
from urllib.parse import quote_plus
import fastapi
import dataclasses
import secrets

app = fastapi.FastAPI()
secret_key = secrets.token_bytes()
app.add_middleware(SessionMiddleware, secret_key=secret_key)
templates = Jinja2Templates(directory="templates")
templates.env.trim_blocks = True
templates.env.lstrip_blocks = True
users = {}
transactions = {}


def get_user(request):
    username = request.session.get("user")
    if username:
        return users.get(username)


@dataclasses.dataclass
class User:
    username: str
    password: str
    balance: int


class TransactionPayload(BaseModel):
    amount: int
    redirect: str
    description: Optional[str]

class Transaction(TransactionPayload):
    id: str
    status: bool


@app.get("/")
async def index(request: Request):
    return templates.TemplateResponse(
        "index.html.jinja", {"request": request, "user": get_user(request)}
    )


@app.get("/login")
async def login_get(request: Request):
    return templates.TemplateResponse("login.html.jinja", {"request": request})


@app.post("/login")
async def login_post(
    request: Request,
    redirect: Optional[str] = "/",
    username: str = Form(...),
    password: str = Form(...),
):
    user = users.get(username)
    if not user:
        return RedirectResponse("/login", 301)
    elif not user.password == password:
        return RedirectResponse("/login", 301)
    request.session["user"] = user.username
    return RedirectResponse(redirect, 301)


@app.get("/register")
async def register_get(request: Request):
    return templates.TemplateResponse("register.html.jinja", {"request": request})


@app.post("/register")
async def register_post(
    request: Request,
    redirect: Optional[str] = "/",
    username: str = Form(...),
    password: str = Form(...),
):
    user = users.get(username)
    if user:
        return RedirectResponse("/register", 301)
    users[username] = User(username, password, 0)
    request.session["user"] = username
    users[username].balance = 100000
    return RedirectResponse(redirect, 301)


@app.post("/api/transactions")
async def add_transaction(transaction: TransactionPayload):
    transaction = Transaction(
        id=secrets.token_hex(6), status=False, **transaction.dict()
    )
    transactions[transaction.id] = transaction
    return transaction

@app.get("/pay")
async def pay_get(request: Request, transaction_id: str):
    transaction = transactions.get(transaction_id)
    if not transaction:
        raise fastapi.HTTPException(404)
    if not request.session.get("user"):
        redirect = quote_plus(transaction.redirect)
        return RedirectResponse(f"/login?redirect=/pay?redirect={redirect}%26transaction_id={transaction_id}")
    return templates.TemplateResponse("pay.html.jinja", {"request": request, "transaction": transaction})

@app.post("/pay")
async def pay_post(request: Request, transaction_id: str):
    user = get_user(request)
    if not user:
        raise fastapi.HTTPException(401)

    transaction = transactions.get(transaction_id)

    if not transaction:
        raise fastapi.HTTPException(404)
    elif user.balance - transaction.amount < 0:
        raise fastapi.HTTPException(403)
    user.balance -= transaction.amount
    transaction.status = True
    return RedirectResponse(transaction.redirect, 301)

