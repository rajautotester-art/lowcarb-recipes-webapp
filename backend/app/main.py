from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.recipe_store import chat_response, get_all_recipes, get_recipe_by_id, search_recipes


app = FastAPI(title="Low-Carb Recipe Chatbot")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    message: str


class ChatResponse(BaseModel):
    reply: str
    recipes: list[dict[str, Any]]


@app.get("/")
def root() -> dict[str, str]:
    return {"message": "Low-Carb Recipe Chatbot API is running"}


@app.get("/recipes")
def recipes() -> list[dict[str, Any]]:
    return get_all_recipes()


@app.get("/recipes/{recipe_id}")
def recipe(recipe_id: str) -> dict[str, Any]:
    result = get_recipe_by_id(recipe_id)
    if not result:
        raise HTTPException(status_code=404, detail="Recipe not found")
    return result


@app.get("/search")
def search(q: str = Query(default="")) -> list[dict[str, Any]]:
    return search_recipes(q)


@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest) -> dict[str, Any]:
    return chat_response(request.message)
