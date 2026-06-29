from entropia.config import Settings


def test_cors_origins_parsed_to_list() -> None:
    s = Settings(API_CORS_ORIGINS="http://a.test, http://b.test")
    assert s.cors_origin_list == ["http://a.test", "http://b.test"]


def test_sync_database_url_strips_async_driver() -> None:
    s = Settings(DATABASE_URL="postgresql+asyncpg://u:p@h:5432/db")
    assert "asyncpg" not in s.sync_database_url
    assert s.sync_database_url.startswith("postgresql")
