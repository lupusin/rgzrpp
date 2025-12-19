import secrets
from urllib.parse import urlparse

from flask import Flask, jsonify, request, redirect, abort
from flask_caching import Cache
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

from models import init_db, insert_link, get_original_url, add_click, get_stats

CACHE_TTL_SECONDS = 3600  # 1 час

def is_valid_url(u: str) -> bool:
    p = urlparse(u)
    return p.scheme in ("http", "https") and bool(p.netloc)

def create_app():
    app = Flask(__name__)

    # Flask-Caching: общий дефолтный таймаут и SimpleCache 
    app.config.update(
        CACHE_TYPE="SimpleCache",
        CACHE_DEFAULT_TIMEOUT=CACHE_TTL_SECONDS,
    )
    cache = Cache(app)  # Flask-Caching инициализация через Cache(app) 

    # Flask-Limiter: key_func по умолчанию IP
    limiter = Limiter(
        app=app,
        key_func=get_remote_address,
        default_limits=[],
        storage_uri="memory://",  # чтобы убрать warning в тестах 
    )  # key_func и лимиты на декораторе поддерживаются 

    init_db()

    # Ключ лимита на создание: user_id, а если не передали — IP
    def user_key():
        data = request.get_json(silent=True) or {}
        user_id = data.get("user_id")
        return str(user_id) if user_id else get_remote_address()

    @app.post("/shorten")
    @limiter.limit("10/day", key_func=user_key)  # 10 созданий в сутки на пользователя 
    def shorten():
        data = request.get_json(force=True)
        original_url = data.get("url")
        user_id = data.get("user_id")

        if not original_url or not is_valid_url(original_url):
            return jsonify({"error": "Invalid or missing url"}), 400

        short_code = secrets.token_urlsafe(6)
        insert_link(short_code, original_url, str(user_id) if user_id else None)

        # Кэшируем редирект на 1 час (timeout в секундах) 
        cache.set(f"redir:{short_code}", original_url, timeout=CACHE_TTL_SECONDS)
        return jsonify({"short_code": short_code}), 201

    @app.get("/")
    @limiter.limit(
        "100/day",
        key_func=lambda: f"{get_remote_address()}:{request.args.get('short','')}",
    )  # 100 кликов в сутки по одной ссылке с одного IP 
    def follow_root():
        short_code = request.args.get("short")
        if not short_code:
            return jsonify({"error": "Missing short parameter"}), 400

        # 1) Сначала кэш: если есть — редирект без чтения links из БД
        cached_url = cache.get(f"redir:{short_code}")
        if cached_url:
            add_click(short_code, get_remote_address())
            return redirect(cached_url, code=302)  # редирект через redirect() 

        # 2) Если нет — читаем БД, кладём в кэш на 1 час
        original_url = get_original_url(short_code)
        if not original_url:
            abort(404)

        cache.set(f"redir:{short_code}", original_url, timeout=CACHE_TTL_SECONDS)  
        add_click(short_code, get_remote_address())
        return redirect(original_url, code=302)   

    @app.get("/stats/")
    def stats_slash():
        short_code = request.args.get("short")
        if not short_code:
            return jsonify({"error": "Missing short parameter"}), 400

        st = get_stats(short_code)
        if not st:
            abort(404)

        clicks, ips = st
        return jsonify({"short_code": short_code, "clicks": clicks, "unique_ips": ips})

    return app

app = create_app()

if __name__ == "__main__":
    app.run(debug=True)
