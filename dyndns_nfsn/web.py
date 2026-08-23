import time
from datetime import timedelta

from flask import Flask, flash, jsonify, redirect, render_template, request, session, url_for

from .auth import get_admin_credentials, login_required
from .config import (
    DEFAULT_SETTINGS,
    EDITABLE_SETTINGS,
    HIDDEN_EDITABLE_SETTINGS,
    format_timestamp,
    get_flask_secret_key,
    get_settings_path,
    get_time_zones,
    load_settings,
    save_settings,
)
from .dns import check_and_update, parse_domains
from .log_service import configure_logging, read_log, rotate_log


def build_status_payload(settings: dict) -> dict:
    return {
        "enabled": bool(settings.get("ENABLE", False)),
        "domains": parse_domains(settings),
        "check_interval": settings.get("CHECK_INTERVAL"),
        "log_level": settings.get("LOG_LEVEL"),
        "last_run": settings.get("LAST_RUN"),
        "last_result": settings.get("LAST_RESULT"),
        "last_message": settings.get("LAST_MESSAGE"),
        "last_public_ip": settings.get("LAST_PUBLIC_IP"),
        "host_statuses": settings.get("HOST_STATUSES", {}),
    }


def create_app(config_path: str | None = None) -> Flask:
    app = Flask(__name__)
    app.config["SETTINGS_PATH"] = get_settings_path(config_path)
    app.secret_key = get_flask_secret_key(config_path)
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    app.config["SESSION_PERMANENT"] = True
    app.permanent_session_lifetime = timedelta(days=7)

    settings = load_settings(app.config["SETTINGS_PATH"])
    configure_logging(settings)

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok"}

    @app.get("/api/health")
    def api_health():
        settings = load_settings(app.config["SETTINGS_PATH"])
        return jsonify({
            "status": "ok",
            "enabled": bool(settings.get("ENABLE", False)),
            "last_run": settings.get("LAST_RUN"),
            "last_result": settings.get("LAST_RESULT"),
            "last_public_ip": settings.get("LAST_PUBLIC_IP"),
        })

    @app.get("/api/status")
    def api_status():
        settings = load_settings(app.config["SETTINGS_PATH"])
        return jsonify(build_status_payload(settings))

    @app.get("/login")
    def login():
        next_url = request.args.get("next", url_for("home"))
        return render_template("login.html", next_url=next_url)

    @app.post("/login")
    def login_post():
        username = str(request.form.get("username", "")).strip()
        password = str(request.form.get("password", "")).strip()
        next_url = request.form.get("next", url_for("home"))
        admin_username, admin_password = get_admin_credentials()

        if username == admin_username and password == admin_password:
            session["logged_in"] = True
            session.permanent = True
            return redirect(next_url)

        flash("Invalid username or password")
        return redirect(url_for("login", next=next_url))

    @app.get("/logout")
    def logout():
        session.clear()
        return redirect(url_for("login"))

    @app.get("/")
    @login_required
    def home():
        settings = load_settings(app.config["SETTINGS_PATH"])
        return render_template("home.html", settings=settings)

    @app.get("/settings")
    @login_required
    def settings():
        settings = load_settings(app.config["SETTINGS_PATH"])
        return render_template(
            "settings.html",
            settings=settings,
            editable_settings=EDITABLE_SETTINGS,
            hidden_editable_settings=HIDDEN_EDITABLE_SETTINGS,
            time_zones=get_time_zones(),
        )

    @app.post("/settings")
    @login_required
    def save_settings_route():
        settings = load_settings(app.config["SETTINGS_PATH"])
        for key in DEFAULT_SETTINGS:
            if key not in EDITABLE_SETTINGS:
                continue
            posted = request.form.get(key, None)
            if key == "ENABLE":
                settings[key] = str(posted or settings.get(key, DEFAULT_SETTINGS[key])).lower() in {"1", "true", "yes", "on"}
            elif key == "NFSN_API_KEY":
                if posted:
                    settings[key] = posted
            else:
                settings[key] = posted if posted is not None else settings.get(key, DEFAULT_SETTINGS[key])

        save_settings(settings, app.config["SETTINGS_PATH"])
        configure_logging(settings)
        return redirect(url_for("home"))

    @app.post("/run-now")
    @login_required
    def run_now():
        settings = load_settings(app.config["SETTINGS_PATH"])
        configure_logging(settings)
        try:
            check_and_update(settings, app.config["SETTINGS_PATH"])
        except Exception as exc:
            settings["LAST_RESULT"] = "failure"
            settings["LAST_MESSAGE"] = str(exc)
            settings["LAST_RUN"] = format_timestamp(settings.get("TIME_ZONE"))
            save_settings(settings, app.config["SETTINGS_PATH"])
        return redirect(url_for("home"))

    @app.get("/logs")
    @login_required
    def logs():
        log_contents = read_log()
        return render_template("logs.html", log_contents=log_contents)

    @app.post("/logs/clear")
    @login_required
    def clear_logs():
        rotate_log()
        return redirect(url_for("logs"))

    return app
