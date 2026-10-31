import asyncio
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
import uvicorn
from fastapi import FastAPI

from database import DatabaseBootstrap, DatabaseSettings
from db import Database
from routes import router


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncIterator[None]:
    settings = DatabaseSettings.from_env()
    await asyncio.to_thread(DatabaseBootstrap(settings).verify)
    database = Database(settings)
    await database.open()
    application.state.database = database
    try:
        yield
    finally:
        await database.close()


app = FastAPI(title="ShopOS API", version="0.1.0", lifespan=lifespan)
app.include_router(router)

def main() -> None:
    uvicorn.run(
        "main:app",
        host=os.getenv("API_HOST", "127.0.0.1"),
        port=int(os.getenv("API_PORT", "8080")),
        reload=False,
    )


if __name__ == "__main__":
    main()
