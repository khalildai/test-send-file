import os

from waitress import serve

from app import app


if __name__ == "__main__":
    serve(
        app,
        host="0.0.0.0",
        port=int(os.environ.get("MATURITY_PORT", "5000")),
        threads=int(os.environ.get("MATURITY_THREADS", "12")),
        channel_timeout=120,
    )
