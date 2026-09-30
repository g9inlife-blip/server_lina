"""FastAPI 엔트리포인트."""
from fastapi import FastAPI

from .routes import login_router, allin1_router, anon_router, cdn_router

app = FastAPI(title="server_lina", description="JusticeSchool 오프라인 로컬 서버")

app.include_router(login_router, prefix="/api", tags=["login"])
app.include_router(allin1_router, prefix="/api", tags=["allin1"])
app.include_router(anon_router, prefix="/api", tags=["anon"])
app.include_router(cdn_router, tags=["cdn"])


@app.get("/health")
def health():
    return {"status": "ok"}
