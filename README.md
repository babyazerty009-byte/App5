# Agent Bitrix24 — Gestion de tâches en langage naturel

Agent conversationnel connecté à l'API Bitrix24, capable de gérer des tâches (CRUD) en langage naturel.
L'agent interprète les requêtes, résout les dépendances entre outils de manière autonome, et interagit avec Bitrix24 via un client API.

---

## Table des matières

1. [Présentation et technologies](#1-Présentation-et-technologies)
2. [Architecture de l'agent](#2-architecture-de-lagent)
3. [Le pattern ReAct — Boucle décisionnelle](#3-le-pattern-react--boucle-décisionnelle)
4. [Les 7 outils de l'agent](#4-les-7-outils-de-lagent)
5. [Composants clés du code](#5-composants-clés-du-code)
6. [Client API Bitrix24 — Pagination et filtrage](#6-client-api-bitrix24--pagination-et-filtrage)
7. [Gestion de la mémoire conversationnelle](#7-gestion-de-la-mémoire-conversationnelle)
8. [Interface utilisateur](#8-interface-utilisateur)
9. [Installation et configuration](#9-installation-et-configuration)
10. [Structure du projet](#10-structure-du-projet)
11. [API REST du serveur Flask](#11-api-rest-du-serveur-flask)

---

## 1. Présentation et technologies

### Technologies utilisées

| Couche | Technologie | Rôle |
|---|---|---|
| Frontend | HTML, CSS, JavaScript | Interface chat avec sidebar d'historique |
| Backend | Flask | API REST, sessions |
| Agent | LangGraph | Orchestration ReAct des outils |
| LLM | Groq API (multi-modèles) | Raisonnement et tool calling |
| API externe | Bitrix24 REST (webhook) | CRUD tâches + recherche utilisateurs |
| Mémoire | MemorySaver (RAM) + JSON (disque) | Contexte conversationnel + historique |

### LangGraph — Orchestration de l'agent

L'agent utilise `langgraph.prebuilt.create_react_agent`. Cette architecture offre trois avantages :

1. **Gestion du contexte** — `MemorySaver` avec `thread_id` gère automatiquement le contexte conversationnel par session.
2. **Graphe cyclique** — Le LLM enchaîne plusieurs outils de manière autonome (Par exemple: l'agent peut d'abord utiliser `find_user` pour retrouver un utilisateur, puis appeler `create_task` avec l'ID obtenu.).
3. **Extensibilité** — la structure de LangGraph permet d'ajouter par la suite des étapes supplémentaires (une validation avant une opération sensible).



### Groq — Inférence LLM gratuite et stratégie multi-modèles

L'inférence LLM est assurée par **Groq** (gratuit). L'utilisation de l'infrastructure LPU de Groq permet d'obtenir des temps de réponse rapides. Le **tool calling** est également utilisé afin que le modèle puisse sélectionner et appeler les fonctions disponibles dans l'agent.

Pour garantir la disponibilité continue, l'application propose **3 modèles** accessibles via un sélecteur dans l'interface :


| Modèle | Taille | Fournisseur | Rôle |
|---|---|---|---|
| **GPT-OSS 120B** (défaut) | 120B | OpenAI (open-source) | Modèle principal |
| **GPT-OSS 20B** | 20B | OpenAI (open-source) | Fallback rapide et léger |
| **Qwen 3.6 27B** | 27B | Alibaba | Alternative avec bon raisonnement |

Les modèles disponibles utilisé sont soumis à des limites de requêtes et de tokens. Si une requête retourne une erreur 429, l'agent détecte l'erreur et invite l'utilisateur à basculer vers un autre modèle pour poursuivre la conversation. 
---

## 2. Architecture de l'agent

<p align="center">
  <img src="Architecture%20de%20l'agent.png"
       alt="Architecture de l'agent"
       width="1600">
</p>

---

### Client Bitrix24

Un seul `Bitrix24Client()` est partagé par tous les outils :

- **Réutilise la session HTTP** (TCP keep-alive) → évite de recréer une connexion à chaque appel.
- **Centralise le rate limiting** → un seul point de contrôle du débit API.
- **Simplifie la configuration** → le webhook est défini à un seul endroit (`.env`).

Le client est **stateless** : chaque appel API est indépendant, donc il n'y a pas de conflit en cas d'accès concurrent.

---

## 3. Le pattern ReAct — Boucle décisionnelle

`create_react_agent` crée un graphe à 2 nœuds avec une boucle :

```
START ──► [AGENT/LLM] ──► tool_call? ──YES──► [TOOLS] ──► exécute
               ▲                                  │
               └──────────────────────────────────┘
               │
               └── pas de tool_call ──► réponse finale ──► END
```

Le **State** (dictionnaire `{messages: [...]}`) est partagé entre les nœuds. Chaque nœud lit et enrichit ce State.

### Exemple — Requête simple (1 outil)

```
User: "Supprime la tâche 12"

  Boucle 1:
    AGENT → analyse → tool_call: delete_task(task_id=12)
    TOOLS → exécute → Bitrix24 API → "Deleted"
  
  Retour à AGENT:
    AGENT → pas besoin d'autre outil → "✅ Tâche #12 supprimée"
```

### Exemple — Requête multi-étapes (2+ outils)

```
User: "Crée une tâche pour Karim : vérifier le scanner, pour vendredi"

  Boucle 1:
    AGENT → "Je ne connais pas l'ID de Karim"
           → tool_call: find_user(name="Karim")
    TOOLS → exécute → Bitrix24 API → {id: 3, name: "Karim"}

  Boucle 2:
    AGENT → "Maintenant j'ai l'ID, je crée la tâche"
           → tool_call: create_task(
               title="Vérifier le scanner",
               assignee_id=3,
               deadline="vendredi"
             )
    TOOLS → exécute → Bitrix24 API → {id: 15, title: "Vérifier le scanner"}

  Sortie:
    AGENT → "✅ Tâche #15 créée : 'Vérifier le scanner', 
              assignée à Karim, deadline vendredi"
```

### Exemple — Mise à jour en masse

```
User: "Marque toutes les tâches de Karim comme terminées"

  Boucle 1: find_user("Karim") → ID=3
  Boucle 2: list_tasks(assignee_id=3) → [tâche 5, 8, 12, 15, 19]
  Boucle 3: update_task(task_id=5, status="completed")
  Boucle 4: update_task(task_id=8, status="completed")
  Boucle 5: update_task(task_id=12, status="completed")
  Boucle 6: update_task(task_id=15, status="completed")
  Boucle 7: update_task(task_id=19, status="completed")
  Sortie: "✅ 5 tâches de Karim marquées comme terminées"
```

L'agent collecte d'abord toutes les tâches, puis fait les mises à jour une par une. La pagination est encapsulée dans `list_tasks` — le LLM ne voit que la liste complète de résultats.

---

## 4. Les 7 outils de l'agent

Chaque outil est décoré avec `@tool` de LangChain. Le LLM lit le **docstring** de chaque outil pour décider quand et comment l'appeler.

### 4.1 `create_task`

Crée une tâche avec résolution intelligente des dates et des assignees.

| Paramètre | Type | Description |
|---|---|---|
| `title` | str | Titre de la tâche (obligatoire) |
| `assignee_name` | str | Prénom de l'assignee (résolu automatiquement en ID) |
| `deadline` | str | Date en langage naturel ("vendredi", "lundi prochain") |
| `priority` | str | "low", "normal", "high" |
| `group_name` | str | Nom du projet/groupe |
| `tags` | str | Tags séparés par des virgules |

L'outil résout les dates relatives ("vendredi", "demain") en dates ISO via `python-dateutil`.

### 4.2 `list_tasks`

Liste les tâches avec **filtres server-side** envoyés à l'API Bitrix24.

| Paramètre | Type | Description |
|---|---|---|
| `status` | str | "new", "pending", "in_progress", "completed", "deferred" |
| `assignee_name` | str | Filtrer par assignee |
| `group_name` | str | Filtrer par projet |
| `limit` | int | Nombre max de résultats (défaut: 20) |

Les filtres sont traduits en paramètres API (`RESPONSIBLE_ID`, `STATUS`, `GROUP_ID`) et envoyés avec la requête. Bitrix24 filtre dans sa base de données SQL avant de retourner les résultats.

### 4.3 `list_overdue_tasks`

Liste les tâches en retard (deadline passée, non terminées). Utilise le filtre `<DEADLINE: now()` + `!STATUS: 5`.

### 4.4 `search_tasks`

Recherche par mot-clé dans le titre via le filtre Bitrix24 `%TITLE%`.

### 4.5 `update_task`

Modifie une tâche existante. Champs modifiables : titre, description, status, deadline, priorité, assignee, groupe, tags.

Exemple de flux pour `« Repousse la tâche 12 à lundi et mets-la en haute priorité »` :

```
Boucle 1:
  AGENT → analyse la requête, identifie: task_id=12, deadline="lundi", priority="high"
         → tool_call: update_task(
             task_id=12,
             deadline="lundi",    ← résolu en ISO: "2026-08-18T18:00:00"
             priority="high"      ← traduit en code Bitrix24: 2
           )
  TOOLS → exécute:
         bitrix24_client.update_task(12, {
             "DEADLINE": "2026-08-18T18:00:00",
             "PRIORITY": 2
         })
         → Bitrix24 API → OK

Sortie:
  AGENT → "✅ Tâche #12 mise à jour : deadline → lundi 18/08, priorité → haute"
```

L'outil résout les dates relatives et traduit les priorités textuelles en codes numériques avant d'appeler l'API.

### 4.6 `delete_task`

Supprime une tâche par son ID.

### 4.7 `find_user`

Cherche un utilisateur par prénom ou nom de famille. Retourne l'ID, le nom complet et l'email. Utilisé implicitement par les autres outils quand l'utilisateur mentionne un prénom.

---

## 5. Composants clés du code

### Les briques principales de LangChain / LangGraph

| Composant | Rôle | Exemple dans l'agent |
|---|---|---|
| **LLM / ChatModel** | Le cerveau qui génère du texte | `ChatGroq(model="openai/gpt-oss-120b")` |
| **Prompt Template** | Instructions données au LLM | `SYSTEM_PROMPT` dans `prompt.py` |
| **Tools** | Fonctions que le LLM peut appeler | `list_tasks`, `create_task`, `find_user`, etc. |
| **Memory** | Garder le contexte conversationnel | `MemorySaver()` |

### 5.1 `services/agent.py` — Le cerveau de l'agent

Ce fichier crée et configure l'agent ReAct avec mémoire conversationnelle :

```python
from langchain_groq import ChatGroq                  # LLM via Groq (gratuit)
from langgraph.prebuilt import create_react_agent     # Agent ReAct (graphe cyclique)
from langgraph.checkpoint.memory import MemorySaver   # Mémoire par thread

class TaskAgent:
    def __init__(self):
        self.memory = MemorySaver()                   # Stockage en RAM
        llm = ChatGroq(model="openai/gpt-oss-120b")
        self.agent = create_react_agent(
            model=llm,                                # Le LLM qui raisonne
            tools=ALL_TOOLS,                          # 7 outils disponibles
            prompt=SYSTEM_PROMPT,                     # Instructions de comportement
            checkpointer=self.memory,                 # Mémoire par thread_id
        )
```

- `checkpointer=self.memory` → sauvegarde automatiquement l'état (messages) après chaque nœud du graphe.
- `thread_id` dans le `config` → isole la mémoire de chaque conversation.
- Le client Bitrix24 est une **instance unique partagée** par tous les outils (Singleton pattern).

### 5.2 `services/bitrix24_client.py` — Performance et résilience

Client API optimisé pour les gros volumes de données :

```python
# 3 techniques d'optimisation implémentées :
#
# 1. Pagination avec start=-1 + filtre >ID (pas de COUNT)
#    → Complexité O(1) par page au lieu de O(n)
#
# 2. Filtrage server-side (status, assignee, group)
#    → Bitrix24 filtre dans sa BDD SQL, pas Python en mémoire
#    → Sur 1M de tâches avec filtre: 1 page vs 20 000 pages
#
# 3. Retry avec exponential backoff (1s, 2s, 3s)
#    → Gère les erreurs QUERY_LIMIT_EXCEEDED (429)
```

**Exemple concret de filtrage server-side** :

```
User: "Montre les tâches en cours de Karim"

  L'outil list_tasks traduit en paramètres Bitrix24:
  ┌─────────────────────────────────────────────────────┐
  │  POST tasks.task.list                               │
  │  filter[STATUS] = 3              ← En cours         │
  │  filter[RESPONSIBLE_ID] = 3      ← ID de Karim      │
  │  start = -1                      ← Pas de COUNT     │
  └─────────────────────────────────────────────────────┘
                    ↓
  Bitrix24 exécute dans sa BDD SQL:
    SELECT * FROM tasks WHERE status=3 AND responsible_id=3
                    ↓
  Résultat: 8 tâches (sur 1 million) → retournées au LLM
```

**Exemple concret de pagination** :

```
  Page 1: filter[>ID] = 0   → reçoit tâches ID 1 à 50
  Page 2: filter[>ID] = 50  → reçoit tâches ID 51 à 100
  Page 3: filter[>ID] = 100 → reçoit tâches ID 101 à 130 (fin)
  
  Total: 3 requêtes pour 130 résultats (filtrés par la BDD)
```

### 5.3 Les 7 outils (`tools/`)

Chaque outil est décoré avec `@tool` de LangChain. Le LLM lit le docstring pour décider quand et comment l'appeler :

| Outil | Décorateur | Ce qu'il fait |
|---|---|---|
| `create_task` | `@tool` | Crée une tâche (titre, priorité, deadline, groupe, tags) |
| `list_tasks` | `@tool` | Liste avec filtres server-side (status, assignee, group) |
| `list_overdue_tasks` | `@tool` | Tâches en retard (deadline passée) |
| `search_tasks` | `@tool` | Recherche par mot-clé (filtre `%TITLE%`) |
| `update_task` | `@tool` | Modifie titre, status, priorité, deadline, tags, assignee |
| `delete_task` | `@tool` | Supprime une tâche par ID |
| `find_user` | `@tool` | Cherche un utilisateur par nom/prénom |

---

## 6. Client API Bitrix24 — Pagination et filtrage

### 6.1 Filtrage server-side

Les filtres ne sont **jamais appliqués en Python**. Ils sont envoyés comme paramètres de la requête API, et c'est Bitrix24 qui filtre dans sa base de données SQL **avant** de retourner les résultats.

Flux complet d'un filtrage :

```
User: "Montre les tâches en cours de Karim"
  ↓
LLM → find_user("Karim") → ID=3
LLM → list_tasks(status="in_progress", assignee_id=3)
  ↓
list_tasks.py traduit en paramètres Bitrix24:
  filter = {"STATUS": 3, "RESPONSIBLE_ID": 3}
  ↓
Requête API envoyée:
  POST tasks.task.list
  {"filter": {"STATUS": 3, "RESPONSIBLE_ID": 3}, "start": -1}
  ↓
Bitrix24 exécute côté serveur:
  SELECT * FROM tasks WHERE status=3 AND responsible_id=3 LIMIT 50
  ↓
Résultat: 8 tâches (sur 1 million) → renvoyées directement au LLM
```

Sur 1 million de tâches, si le filtre retourne 25 résultats :
- **Sans filtre server-side** : 20 000 pages × 50 résultats à télécharger, puis Python filtre → très lent
- **Avec filtre server-side** : 1 seule page de 25 résultats directement → rapide

Exemples de filtres utilisés :

| Requête utilisateur | Filtre envoyé à l'API | Opérateur Bitrix24 |
|---|---|---|
| Tâches de Karim | `{"RESPONSIBLE_ID": 3}` | Égalité |
| Tâches en retard | `{"<DEADLINE": "2026-08-17...", "!STATUS": 5}` | Inférieur + Négation |
| Cherche "scanner" | `{"%TITLE": "scanner"}` | Contient (LIKE) |
| Tâches du projet X | `{"GROUP_ID": 10}` | Égalité |
| Tâches urgentes | `{"TAG": "urgent"}` | Égalité |
| Tâches en cours | `{"STATUS": 3}` | Égalité |

### 6.2 Pagination optimisée (`start=-1`)

Problème de la pagination standard (`start=0, 50, 100...`) : Bitrix24 calcule le **total** de résultats à chaque requête → O(n) sur les gros datasets.

Solution implémentée — pagination par `>ID` :

```python
def _call_paginated(self, method, params, max_items=200):
    last_id = 0
    while len(all_items) < max_items:
        params["start"] = -1            # Désactive le calcul de total
        params["filter"][">ID"] = last_id  # Commence après le dernier ID
        params["order"] = {"ID": "asc"}    # Tri stable

        data = self._call(method, params)
        items = data["result"]["tasks"]

        if not items:
            break

        all_items.extend(items)
        last_id = items[-1]["id"]       # Prochain point de départ

        if len(items) < 50:             # Dernière page
            break
```

| Méthode | Requête SQL côté Bitrix24 | Complexité |
|---|---|---|
| `start=0` | `SELECT ... LIMIT 50 OFFSET 0` + `COUNT(*)` | O(n) per page |
| `start=-1` + `>ID` | `SELECT ... WHERE ID > 150 LIMIT 50` | O(1) per page |

### 6.3 Retry avec exponential backoff

Si Bitrix24 retourne une erreur `QUERY_LIMIT_EXCEEDED` (429), le client réessaie avec des délais croissants :

```python
def _call_with_retry(self, method, params, max_retries=3):
    for attempt in range(max_retries):
        try:
            return self._call(method, params)
        except Exception as e:
            if "QUERY_LIMIT_EXCEEDED" in str(e):
                wait_time = (attempt + 1) * 1.0   # 1s, 2s, 3s
                time.sleep(wait_time)
                continue
            raise
```

Cela laisse le temps au serveur Bitrix24 de récupérer au lieu de le surcharger avec des requêtes immédiates.

---

## 7. Gestion de la mémoire conversationnelle

### Deux niveaux de mémoire

| Niveau | Stockage | Persistance | Contenu |
|---|---|---|---|
| **MemorySaver** | RAM (dict Python) | Perdu au redémarrage | Messages LLM par `thread_id` |
| **conversations.json** | Fichier disque | Persiste au redémarrage | Titres, dates, messages affichés |

### MemorySaver — Contexte LLM

Le checkpointer `MemorySaver` sauvegarde automatiquement tous les messages (user, AI, tool) après chaque nœud du graphe. Chaque `thread_id` a son propre historique isolé.

```python
# L'agent charge automatiquement la mémoire du thread
result = agent.invoke(
    {"messages": [{"role": "user", "content": message}]},
    config={"configurable": {"thread_id": thread_id}}
)
```

Cela permet les références contextuelles :

```
User: "Crée une tâche : vérifier le scanner"
Bot:  "✅ Tâche #15 créée"
User: "Change son titre en 'vérifier les imprimantes'"
       ↑ Le LLM sait que "son" = tâche #15 grâce à la mémoire
```

### conversations.json — Historique persisté

L'historique de la sidebar est sauvegardé sur disque pour survivre aux redémarrages. Seules les conversations avec au moins 1 message sont affichées.

### Auto-recovery

Si l'historique en mémoire est corrompu (ex: changement de compte Bitrix24 mid-session), l'agent détecte l'erreur `INVALID_CHAT_HISTORY`, efface la mémoire du thread concerné, et réessaie automatiquement.

---

## 8. Interface utilisateur

- **Thème** : Dark grey premium avec design sombre épuré.
- **Sidebar** : Historique des conversations avec suppression (icône trash au hover).
- **Exemples catégorisés** : Suggestions de commandes organisées par catégorie (Gestion, Recherche, Modification) pour guider l'utilisateur.
- **Responsive** : Sidebar escamotable sur mobile.
- **Sélecteur de modèle** : Changement de LLM en temps réel (GPT-OSS 120B, GPT-OSS 20B, Qwen 3.6).
- **Indicateur de connexion** : Vérifie le webhook Bitrix24 au démarrage et affiche le nom de l'utilisateur connecté.

---

## 9. Installation et configuration

### Prérequis

- Python 3.10+
- Un compte Bitrix24 avec un webhook entrant (inbound webhook) avec les permissions `task` et `user`
- Une clé API Groq gratuite — [console.groq.com](https://console.groq.com)

### Installation

```bash
git clone <url-du-repo>
cd App5
pip install -r requirements.txt
```

### Configuration

Créer un fichier `.env` à la racine :

```env
BITRIX24_WEBHOOK_URL=https://votre-domaine.bitrix24.com/rest/1/votre-cle/
GROQ_API_KEY=gsk_votre_cle_groq
```

### Lancement

```bash
python app.py
```

Ouvrir [http://localhost:5000](http://localhost:5000) dans le navigateur.

---

## 10. Structure du projet

```
App5/
├── app.py                      # Serveur Flask — routes API, sessions, persistance JSON
├── config.py                   # Chargement des variables d'environnement (.env)
├── prompt.py                   # System prompt de l'agent (instructions, codes status, exemples)
├── requirements.txt            # Dépendances Python
│
├── services/
│   ├── agent.py                # TaskAgent — LangGraph ReAct + MemorySaver + auto-recovery
│   └── bitrix24_client.py      # Client API — pagination start=-1, retry, filtres server-side
│
├── tools/
│   ├── create_task.py          # Création avec résolution dates + assignees
│   ├── list_tasks.py           # Liste avec filtres server-side + résolution noms de groupes
│   ├── search_tasks.py         # Recherche par mot-clé (%TITLE%)
│   ├── update_task.py          # Modification multi-champs (titre, status, deadline, tags...)
│   ├── delete_task.py          # Suppression par ID
│   └── find_user.py            # Recherche utilisateur par nom/prénom
│
├── templates/
│   └── index.html              # Interface chat avec sidebar et exemples catégorisés
│
└── static/
    ├── style.css               # Thème dark grey premium, sidebar responsive
    └── script.js               # Logique frontend — chat, sidebar, CRUD conversations
```

---

## 11. API REST du serveur Flask

| Endpoint | Méthode | Description |
|---|---|---|
| `/` | GET | Page principale (interface chat) |
| `/api/chat` | POST | Envoyer un message à l'agent (body: `{message, model?}`) |
| `/api/new-chat` | POST | Créer une nouvelle conversation |
| `/api/conversations` | GET | Lister les conversations non vides |
| `/api/conversations/<id>/switch` | POST | Changer de conversation active |
| `/api/conversations/<id>` | GET | Récupérer les messages d'une conversation |
| `/api/conversations/<id>` | DELETE | Supprimer une conversation |

---

## Dépendances

```
requests>=2.28.0          # Appels HTTP vers Bitrix24
python-dateutil>=2.8.0    # Résolution des dates relatives
python-dotenv>=1.0.0      # Chargement des variables .env
flask>=3.0.0              # Serveur web
groq>=0.4.0               # SDK Groq (optionnel)
langchain>=0.3.0          # Framework LLM
langchain-groq>=0.2.0     # Intégration Groq pour LangChain
langchain-core>=0.3.0     # Core LangChain
langgraph>=0.2.0          # Orchestration agent ReAct
```
