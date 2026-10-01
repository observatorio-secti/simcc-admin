from fastapi import FastAPI

from simcc_admin.routers import academic, auth, users

app = FastAPI()

app.include_router(users.router)
app.include_router(auth.router)
app.include_router(academic.router)


@app.get("/")
def read_root():
    return {"message": "Olá Mundo!"}
