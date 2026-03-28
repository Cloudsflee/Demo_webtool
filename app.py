from __future__ import annotations

from pathlib import Path

from flask import Flask, jsonify, render_template, request, send_from_directory

from agent import run_agent
from config import load_config


app = Flask(__name__)
config = load_config()
PIC_ROOT = (Path(__file__).resolve().parent / "pic").resolve()
PIC_ROOT.mkdir(parents=True, exist_ok=True)


@app.get("/")
def index():
    return render_template("index.html")


@app.post("/agent/run")
def agent_run():
    data = request.get_json(silent=True) or {}
    user_input = str(data.get("user_input") or "").strip()
    max_turns = int(data.get("max_turns") or config.agent_max_turns)
    debug = bool(data.get("debug", False))

    if not user_input:
        return jsonify({"error": "user_input is required"}), 400

    if max_turns <= 0:
        return jsonify({"error": "max_turns must be greater than 0"}), 400

    try:
        result = run_agent(
            user_input=user_input,
            max_turns=max_turns,
            debug=debug,
            config=config,
        )
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        return jsonify({"error": f"internal error: {exc}"}), 500

    return jsonify(result), 200


@app.get("/pic/<path:filename>")
def serve_pic(filename: str):
    return send_from_directory(PIC_ROOT, filename)


if __name__ == "__main__":
    app.run(host=config.flask_host, port=config.flask_port, debug=True)
