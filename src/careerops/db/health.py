from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine


class DatabaseReadinessChecker:
    def __init__(self, database_url: str) -> None:
        self._database_url = database_url

    async def is_ready(self) -> bool:
        engine = create_async_engine(self._database_url, pool_pre_ping=True)
        try:
            async with engine.connect() as connection:
                await connection.execute(text("select 1"))
        except Exception:
            return False
        finally:
            await engine.dispose()
        return True
