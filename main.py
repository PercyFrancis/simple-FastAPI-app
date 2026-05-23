from fastapi import FastAPI


app = FastAPI()

@app.get("/health/")
async def get_health():
    return {"status": "ok"}