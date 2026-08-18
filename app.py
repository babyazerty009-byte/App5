import os
import json
import uuid
from datetime import datetime
from flask import Flask, render_template, request, jsonify, session
from services.agent import TaskAgent
from config import AVAILABLE_MODELS, DEFAULT_MODEL

app = Flask(__name__)
app.secret_key = "bitrix24-agent-app5-secret-key"

agent = TaskAgent()


#  Persistent conversation store (JSON file)
CONVERSATIONS_FILE = os.path.join(os.path.dirname(__file__), "conversations.json")

#Load conversations from JSON file.
def _load_conversations() -> dict:
    if os.path.exists(CONVERSATIONS_FILE):
        try:
            with open(CONVERSATIONS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {}
    return {}

#Save conversations to JSON file.
def _save_conversations(convs: dict):
    try:
        with open(CONVERSATIONS_FILE, "w", encoding="utf-8") as f:
            json.dump(convs, f, ensure_ascii=False, indent=2)
    except IOError:
        pass


# Load on startup
conversations = _load_conversations()

#Ensure the session has a thread_id and a conversation record.
def _get_or_create_thread(sess):
    global conversations
    if "thread_id" not in sess:
        sess["thread_id"] = str(uuid.uuid4())
    tid = sess["thread_id"]
    if tid not in conversations:
        conversations[tid] = {
            "title": "Nouvelle conversation",
            "created": datetime.now().strftime("%d/%m %H:%M"),
            "messages": [],
        }
        _save_conversations(conversations)
    return tid


@app.route("/")
def index():
    "Main chatbot page."
    _get_or_create_thread(session)

    # Test Bitrix24 connection
    try:
        user = agent.client.get_current_user()
        connected = True
        user_info = f"{user['name']} {user['last_name']} (ID: {user['id']})"
    except Exception:
        connected = False
        user_info = ""

    return render_template(
        "index.html",
        connected=connected,
        user_info=user_info,
        models=AVAILABLE_MODELS,
        default_model=DEFAULT_MODEL,
    )


@app.route("/api/chat", methods=["POST"])
def chat():
    """Chat API endpoint with conversation memory."""
    global conversations
    data = request.get_json()
    message = data.get("message", "").strip()
    model = data.get("model", "")

    if not message:
        return jsonify({"response": "Empty message."}), 400

    thread_id = _get_or_create_thread(session)

    # Store user message
    conv = conversations[thread_id]
    conv["messages"].append({"role": "user", "content": message})

    # Auto-title: use first user message (truncated)
    if conv["title"] == "Nouvelle conversation":
        conv["title"] = message[:40] + ("…" if len(message) > 40 else "")

    # Switch model if needed
    if model and model != agent.model:
        agent.set_model(model)

    try:
        response = agent.handle(message, thread_id=thread_id)
        # Store bot response
        conv["messages"].append({"role": "bot", "content": response})
        _save_conversations(conversations)
        return jsonify({"response": response, "model_used": agent.model})
    except Exception as e:
        _save_conversations(conversations)
        return jsonify({"response": f"❌ Server error: {e}"}), 500


@app.route("/api/new-chat", methods=["POST"])
def new_chat():
    """Reset conversation — start a new thread."""
    session["thread_id"] = str(uuid.uuid4())
    _get_or_create_thread(session)
    return jsonify({"status": "ok", "message": "New conversation started."})


@app.route("/api/conversations", methods=["GET"])
def get_conversations():
    """Return list of conversations that have at least 1 message."""
    conv_list = []
    for tid, conv in conversations.items():
        # Only show conversations with messages
        if len(conv["messages"]) > 0:
            conv_list.append({
                "id": tid,
                "title": conv["title"],
                "created": conv["created"],
                "message_count": len(conv["messages"]),
            })
    # Sort by most recent first
    conv_list.reverse()
    return jsonify({"conversations": conv_list})


@app.route("/api/conversations/<thread_id>", methods=["GET"])
def get_conversation(thread_id):
    """Load a specific conversation by thread_id."""
    if thread_id not in conversations:
        return jsonify({"error": "Conversation not found."}), 404
    conv = conversations[thread_id]
    return jsonify({
        "id": thread_id,
        "title": conv["title"],
        "messages": conv["messages"],
    })


@app.route("/api/conversations/<thread_id>/switch", methods=["POST"])
def switch_conversation(thread_id):
    """Switch to an existing conversation."""
    if thread_id not in conversations:
        return jsonify({"error": "Conversation not found."}), 404
    session["thread_id"] = thread_id
    conv = conversations[thread_id]
    return jsonify({
        "id": thread_id,
        "title": conv["title"],
        "messages": conv["messages"],
    })


@app.route("/api/conversations/<thread_id>", methods=["DELETE"])
def delete_conversation(thread_id):
    """Delete a conversation from history."""
    global conversations
    if thread_id not in conversations:
        return jsonify({"error": "Conversation not found."}), 404

    del conversations[thread_id]
    _save_conversations(conversations)

    # If we just deleted the active conversation, start a new one
    if session.get("thread_id") == thread_id:
        session["thread_id"] = str(uuid.uuid4())

    return jsonify({"status": "ok", "message": "Conversation deleted."})


if __name__ == "__main__":
    print("\n Bitrix24 Agent")
    print(" Open http://localhost:5000 in your browser\n")
    app.run(debug=True, port=5000)
