# Death of the Final Exam

A detective game. The night before the Semiconductor Valuation final, the exam leaks in the cohort
group chat. You have until 09:00 to question five suspects, played by AI, and name who did it, how,
where and why. The culprit changes from game to game.

**Play it:** https://carcavelos-paper.streamlit.app

## Team

| Name | Student number |
| --- | --- |
| Duarte Furtado | 80573 |
| Lúcia Pereira | 78729 |
| Martim Pereira | 62329 |
| Salvador Rendeiro | 62548 |

## Run it locally

```bash
python -m pip install -r requirements.txt
streamlit run app.py
```

The game runs without an AI key: the suspects then answer with their scripted lines. To let the AI play
them, copy `.env.example` to `.env` and put a [Requesty](https://requesty.ai) key in it. `.env` is
ignored by git.

## Run the tests

```bash
python -m pytest
```

## How to play

The screen is laid out like a board game. The campus map is the board, the clues are a hand of evidence
cards, and the five suspects sit across the top. Tap anything to open it in the side panel.

It is midnight. Every action costs time: searching a place or opening a document costs 30 minutes, and
each question to a suspect (or showing them a card) costs 10. Tap a red **?** card or pin to search it.
Tap a face to interrogate: pick a question, show them a card, or type your own. Show a suspect the card
that breaks their story and you catch them lying. Stuck on a locked card? A 💡 hint costs 15 minutes,
and 🔎 shows your free leads. Cross off what it cannot be on the 📋 case sheet.

When you are ready, press **Accuse** and pick who, how, where and why. You must accuse before 09:00,
so you have 540 minutes. A wrong accusation shows which of the four parts are right. After three
wrong ones, or at 09:00, the case goes cold.

## How it works

- `data/case.json` holds the story as data: clues, suspects, unlock rules and three variants with
  different culprits.
- `game/engine.py` holds the rules. It decides what is unlocked, what each action costs and whether an
  accusation is right.
- The AI only plays the suspects. It never sees the solution and never decides what unlocks.

All characters, the course and the companies in the game are fictional.

## Where things are

| Part | File | What it does |
| --- | --- | --- |
| Screens | `app.py` | The Streamlit interface: the side panel, the accusation and the reveal. Only shows what the engine returns. |
| Board | `board.py` | Builds the board's HTML (status bar, map, evidence cards, suspects) and turns taps into panel ids. |
| Rules | `game/engine.py` | Clock, unlocks, questions, evidence, contradictions, accusations, badges. |
| Story | `data/case.json`, `game/case.py` | Clues, suspects, claims, the three variants, and the loader that merges a variant. |
| AI | `game/ai.py` | Sends one question to the model through Requesty and checks the reply. |
| Storage | `db.py` | Saved games in SQLite. All database code is here. |
| Live reload | `reloading.py` | Rebuilds the engine when Streamlit Cloud pulls new code without restarting. |
| Tests | `tests/` | pytest. They never call the real AI and use a temporary database. |
| Rules for the team and agents | `AGENTS.md` | Branches, reviews, secrets, and the game's design rules. |

## Design decisions and limits

### The engine decides, the AI only acts

The model never decides what is true. `game/ai.py` asks it for a reply and a topic tag from the
list in `case.json`. The engine then decides what that question costs and what it unlocks, and
rejects any topic that is not on the list.

- **Why:** model output can be wrong or in the wrong format. If the AI decided unlocks, a lucky
  or manipulated reply could solve the case.
- **What the model sees:** only `Engine.character_brief()`. That is one suspect's persona, mood,
  cover story and the reveals the player has earned. It never sees the solution, the variant or
  clue text. The leaked PDF has a hidden prompt injection on purpose, and it never reaches the
  model.
- **Bad replies:** a reply that is not valid JSON, or has no `reply` field, is thrown away. The
  suspect then answers with a scripted line.

### What happens when the AI is unavailable

If there is no key, the call fails or times out (15 seconds), or the reply cannot be parsed, the
game keeps working. The suspect answers with scripted lines from `case.json`, and the topic is
picked from keywords in the question.

- **Limit:** the free Requesty plan allows 200 requests per day, shared by the whole account.
- **Per game:** each game makes at most 25 AI calls (`MAX_AI_CALLS`). After that, the suspects
  use the scripted lines.

### Where the data is stored

Saved games are stored in SQLite (`db.py`), in `data/app.db` or the file named by
`DATABASE_PATH`. Each game gets a random 32-character id, which becomes its private resume link
(`?game=<id>`).

- **Access:** there are no accounts. Anyone with the link can resume that game, and nobody can
  list or guess other games. Ids that do not have the right shape are rejected before any query.
- **What is not saved:** the text the player types to the suspects. History only records the
  topic, so a password typed into the game never reaches the database or the model.
- **Limit:** Streamlit Community Cloud has a temporary disk, so saved games are lost when the
  app restarts. That is acceptable for a game that lasts minutes.
- **How it could change:** move `db.py` to a hosted database such as Supabase. Both use SQL, and
  all database code is already in one file.

### Security

- **Secrets:** the Requesty key is read from `REQUESTY_API_KEY` (environment, `.env`, or
  Streamlit secrets) and is never committed. `.env` and `.streamlit/secrets.toml` are in
  `.gitignore`.
- **Input:** questions are limited to 300 characters, and empty questions are rejected.
- **Password trap:** the Companion asks for your password. Anything that looks like a password
  or an API key is stopped by `Engine.check_secret()` before it reaches the model.
- **Hidden content:** locked clue text never reaches the browser. The interface reads clues only
  through `Engine.clue_list()` and `Engine.read_clue()`.
- **Dependencies:** four, each pinned to an exact version in `requirements.txt`.

### What the tests cover, and what they do not

**Covered:**
- the rules: costs, unlocks, locked clues, wrong and repeated actions, the three-strike limit,
  and running out of time
- each variant's story consistency, and claims and contradictions
- the AI layer, with fake model replies: bad JSON, code fences, failures, the call limit, and
  the password trap
- that briefs never contain the solution
- saving and resuming, including malformed ids and old saves
- the main screens, through Streamlit's `AppTest`

**Not covered:**
- the real model's replies, which change from run to run
- how the pages look in a real browser
- the taps inside the board's HTML component (the tap parser itself is tested)
- the deployed host (sleep, restarts)

These are checked by hand on the live app before a demo.

### Known limits and next steps

- **One player per game:** there are no accounts and no shared games.
- **Temporary saves:** saved games are lost when the host restarts. See *Where the data is
  stored* above.
- **Hand-written story:** the three variants are hand-written in `case.json`. A new variant
  means new data and new consistency tests, not new code.
- **AI quota:** the 200 requests per day are shared by everyone playing the deployed app.
