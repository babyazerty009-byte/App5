
const chatArea = document.getElementById("chatArea");
const messageInput = document.getElementById("messageInput");
const sendBtn = document.getElementById("sendBtn");
const chatForm = document.getElementById("chatForm");
const sidebar = document.getElementById("sidebar");
const sidebarToggle = document.getElementById("sidebarToggle");
const sidebarOpenBtn = document.getElementById("sidebarOpenBtn");
const newChatSidebarBtn = document.getElementById("newChatSidebarBtn");
const sidebarConversations = document.getElementById("sidebarConversations");


async function sendMessage(event) {
    if (event) event.preventDefault();

    const message = messageInput.value.trim();
    if (!message) return;


    const welcomeCard = document.getElementById("welcomeCard");
    if (welcomeCard) {
        welcomeCard.style.animation = "fadeOut 0.3s ease forwards";
        setTimeout(() => welcomeCard.remove(), 300);
    }


    appendMessage("user", message);
    messageInput.value = "";
    messageInput.focus();


    sendBtn.disabled = true;


    const typingId = showTyping();

    try {
        const selectedModel = document.getElementById("modelSelect").value;
        const response = await fetch("/api/chat", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ message, model: selectedModel }),
        });

        const data = await response.json();


        removeTyping(typingId);


        appendMessage("bot", data.response);


        loadConversations();

    } catch (error) {
        removeTyping(typingId);
        appendMessage("bot", "❌ Erreur de connexion au serveur.");
    } finally {
        sendBtn.disabled = false;
    }
}

function sendExample(btn) {
    const text = btn.textContent.trim();
    messageInput.value = text;
    sendMessage();
}


async function startNewChat() {
    try {
        await fetch("/api/new-chat", { method: "POST" });
    } catch (e) {

    }


    chatArea.innerHTML = "";

    const welcomeHTML = `
        <div class="welcome-card" id="welcomeCard">
            <div class="welcome-icon">🚀</div>
            <h2>Nouvelle Conversation</h2>
            <p>La mémoire a été réinitialisée. Posez-moi vos questions :</p>
            <div class="examples">
                <button class="example-btn" onclick="sendExample(this)">Liste les tâches</button>
                <button class="example-btn" onclick="sendExample(this)">Tâches en retard</button>
                <button class="example-btn" onclick="sendExample(this)">Cherche scanner</button>
                <button class="example-btn" onclick="sendExample(this)">Qui est Karim ?</button>
            </div>
        </div>
    `;
    chatArea.insertAdjacentHTML("beforeend", welcomeHTML);


    loadConversations();
}

async function loadConversations() {
    try {
        const response = await fetch("/api/conversations");
        const data = await response.json();
        const convs = data.conversations || [];

        sidebarConversations.innerHTML = "";

        if (convs.length === 0) {
            sidebarConversations.innerHTML = `
                <div style="padding: 20px 12px; text-align: center; color: var(--text-muted); font-size: 12px;">
                    Aucune conversation
                </div>
            `;
            return;
        }

        convs.forEach(conv => {
            const item = document.createElement("div");
            item.className = "conv-item";
            item.dataset.id = conv.id;
            item.innerHTML = `
                <div class="conv-details">
                    <div class="conv-title">${escapeHtml(conv.title)}</div>
                    <div class="conv-meta">${conv.created} • ${conv.message_count} msgs</div>
                </div>
                <button class="conv-delete-btn" title="Supprimer" onclick="event.stopPropagation(); deleteConversation('${conv.id}')">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M3 6h18M8 6V4a2 2 0 012-2h4a2 2 0 012 2v2M19 6l-1 14a2 2 0 01-2 2H8a2 2 0 01-2-2L5 6"></path>
                    </svg>
                </button>
            `;
            item.addEventListener("click", () => switchConversation(conv.id));
            sidebarConversations.appendChild(item);
        });

    } catch (e) {

    }
}

async function deleteConversation(threadId) {
    try {
        await fetch(`/api/conversations/${threadId}`, { method: "DELETE" });
        loadConversations();
    } catch (e) {

    }
}


async function switchConversation(threadId) {
    try {
        const response = await fetch(`/api/conversations/${threadId}/switch`, {
            method: "POST",
        });
        const data = await response.json();

        if (data.error) return;


        chatArea.innerHTML = "";


        const messages = data.messages || [];
        if (messages.length === 0) {
            chatArea.innerHTML = `
                <div class="welcome-card" id="welcomeCard">
                    <div class="welcome-icon">💬</div>
                    <h2>${escapeHtml(data.title)}</h2>
                    <p>Conversation vide. Écrivez votre premier message.</p>
                </div>
            `;
        } else {
            messages.forEach(msg => {
                appendMessage(msg.role, msg.content);
            });
        }


        document.querySelectorAll(".conv-item").forEach(item => {
            item.classList.toggle("active", item.dataset.id === threadId);
        });


        if (window.innerWidth <= 768) {
            sidebar.classList.add("collapsed");
        }

    } catch (e) {

    }
}


function appendMessage(role, text) {
    const messageDiv = document.createElement("div");
    messageDiv.className = `message ${role}`;

    const avatar = document.createElement("div");
    avatar.className = "message-avatar";
    avatar.textContent = role === "user" ? "👤" : "🤖";

    const content = document.createElement("div");
    content.className = "message-content";
    content.textContent = text;

    messageDiv.appendChild(avatar);
    messageDiv.appendChild(content);

    chatArea.appendChild(messageDiv);
    scrollToBottom();
}

function showTyping() {
    const id = "typing-" + Date.now();
    const messageDiv = document.createElement("div");
    messageDiv.className = "message bot";
    messageDiv.id = id;

    const avatar = document.createElement("div");
    avatar.className = "message-avatar";
    avatar.textContent = "🤖";

    const content = document.createElement("div");
    content.className = "message-content";

    const typing = document.createElement("div");
    typing.className = "typing-indicator";
    typing.innerHTML = "<span></span><span></span><span></span>";

    content.appendChild(typing);
    messageDiv.appendChild(avatar);
    messageDiv.appendChild(content);

    chatArea.appendChild(messageDiv);
    scrollToBottom();

    return id;
}

function removeTyping(id) {
    const el = document.getElementById(id);
    if (el) el.remove();
}


function scrollToBottom() {
    chatArea.scrollTop = chatArea.scrollHeight;
}

function escapeHtml(text) {
    const div = document.createElement("div");
    div.textContent = text;
    return div.innerHTML;
}


const style = document.createElement("style");
style.textContent = `
    @keyframes fadeOut {
        to { opacity: 0; transform: translateY(-10px); height: 0; padding: 0; margin: 0; overflow: hidden; }
    }
`;
document.head.appendChild(style);


messageInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
    }
});


if (sidebarToggle) {
    sidebarToggle.addEventListener("click", () => {
        sidebar.classList.add("collapsed");
    });
}

if (sidebarOpenBtn) {
    sidebarOpenBtn.addEventListener("click", () => {
        sidebar.classList.remove("collapsed");
    });
}


if (newChatSidebarBtn) {
    newChatSidebarBtn.addEventListener("click", startNewChat);
}


document.addEventListener("DOMContentLoaded", () => {
    loadConversations();
});
