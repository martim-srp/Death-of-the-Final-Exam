"""The rules of the game.

This module decides everything that is true in a game: which clues exist,
which are locked, what each action costs and whether an accusation is right.
It never calls the AI and never touches the database. The AI layer and the
UI call these functions, and the rules here have the final word.

Security rule: nothing in this module returns the text of a clue the player
has not opened, and nothing returns the solution while the game is running.
"""

import random
import re
import secrets
from dataclasses import asdict, dataclass, field

from game.case import load_case, option_ids, resolve_variant

COLUMNS = ("who", "how", "where", "why")

# Things that look like a password or an API key. Used for the Companion's password trap.
_KEY_PATTERN = re.compile(r"\b(sk|pk|rk|ghp|gho|xoxb|xoxp)[-_][A-Za-z0-9_-]{8,}", re.IGNORECASE)
_PASSWORD_WORDS = re.compile(
    r"\b(password|passwd|pwd|passcode|senha|palavra-passe)\b\s*(is|=|:|é)?\s*\S{4,}", re.IGNORECASE
)
# A whole word that is a card number (STU-2291, staff-0417, STU-2291's). Matched against the
# whole word, so a password with a card number glued on (Lisboa2026/STU-2291) is not exempt.
_CARD_NUMBER = re.compile(r"(stu|staff)-\d{4}(['’]s)?", re.IGNORECASE)
# A file name: a stem, then a known extension. The stem is still checked for passwords.
_FILE_NAME = re.compile(r"([\w.-]+)\.(pdf|docx?|xlsx?|csv|txt|png|jpe?g)", re.IGNORECASE)
_NAME_PARTS = re.compile(r"[._-]+")
_STRIP = ".,;:!?\"'()[]"
# Field names used in the case file's logs (job=88213, card=STU-2291, ...). Only these
# key=value words count as game data; token=..., pass=... and any other assignment do not.
_GAME_FIELDS = frozenset(
    {"admin", "card", "expires", "job", "owner", "pages", "queue", "staff", "station"}
)
_FIELD = re.compile(r"^([A-Za-z_]+)=")


def _words(text):
    """The words of a text, without surrounding punctuation."""
    return [w.strip(_STRIP) for w in text.split() if w.strip(_STRIP)]


def _looks_like_password(word, known_words):
    """True if one word looks like a password: 8+ characters mixing lowercase letters and digits.

    Game data is never a password: words from the case file and card numbers. Log fields
    (job=88213) and file names (SV_Final_v3.pdf) only wrap a value, so the value inside is
    checked instead: card=STU-2291 is fine, owner=Carcavelos2026 and secret2026.txt are not.
    A file name's stem is checked part by part (report_final2.docx is "report" and "final2").
    """
    if word.lower() in known_words or _CARD_NUMBER.fullmatch(word):
        return False
    field = _FIELD.match(word)
    if field and field.group(1).lower() in _GAME_FIELDS:
        return _looks_like_password(word[field.end():], known_words)
    file_name = _FILE_NAME.fullmatch(word)
    if file_name:
        parts = _NAME_PARTS.split(file_name.group(1))
        return any(_looks_like_password(part, known_words) for part in parts if part)
    has_lower = any(c.islower() for c in word)
    has_digit = any(c.isdigit() for c in word)
    return len(word) >= 8 and has_lower and has_digit


def looks_like_secret(text, known_words=frozenset()):
    """True if the text contains something that looks like a password or an API key.

    Explicit keys (sk-..., ghp_...) and phrases like "my password is ..." always count.
    Otherwise any word that looks like a password counts (see _looks_like_password).
    known_words is the vocabulary of the case file.
    """
    if _KEY_PATTERN.search(text) or _PASSWORD_WORDS.search(text):
        return True
    return any(_looks_like_password(word, known_words) for word in _words(text))


def case_vocabulary(case):
    """Every word that appears in the case file's text, lowercased.

    Players copy these words from clues into their questions, so they are never secrets.
    """
    words = set()

    def walk(value):
        if isinstance(value, str):
            words.update(w.lower() for w in _words(value))
        elif isinstance(value, dict):
            for item in value.values():
                walk(item)
        elif isinstance(value, list):
            for item in value:
                walk(item)

    walk(case)
    return frozenset(words)


class GameError(Exception):
    """An action the rules do not allow. The message is safe to show to the player."""


@dataclass
class Game:
    """Everything that changes during one game. Plain data, so it can be saved."""

    seed: int
    variant: str
    variables: dict
    clock: int = 0
    opened: list = field(default_factory=list)
    unlocked: list = field(default_factory=list)
    presented: list = field(default_factory=list)
    strikes: int = 0
    status: str = "playing"  # playing, solved or cold
    history: list = field(default_factory=list)
    badges: list = field(default_factory=list)
    contradictions: list = field(default_factory=list)  # [suspect, claim_id], in the order caught

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, data):
        return cls(**data)


class Engine:
    """Applies the rules of one case file to games."""

    def __init__(self, case=None):
        self.case = case if case is not None else load_case()
        self.clock_rules = self.case["clock"]
        self._resolved = {v: resolve_variant(self.case, v) for v in self.case["variants"]}
        self._vocabulary = case_vocabulary(self.case)

    # ---- Starting a game -------------------------------------------------

    def new_game(self, seed=None, variant=None):
        """Start a game. The seed decides the culprit and every random detail."""
        if seed is None:
            seed = secrets.randbelow(2**31)
        rng = random.Random(seed)
        variants = sorted(self.case["variants"])
        chosen = rng.choice(variants)
        if variant is not None:
            if variant not in self.case["variants"]:
                raise GameError(f"Unknown variant: {variant}")
            chosen = variant
        return Game(seed=seed, variant=chosen, variables=self._random_variables(rng))

    def _random_variables(self, rng):
        r = self.case["random"]
        cards = rng.sample(range(1000, 10000), 3)
        alias = rng.choice(r["alias"])
        initials = "".join(part[0] + "." for part in alias.replace(".", "").split())
        variables = {
            "rep_card": str(cards[0]),
            "ta_card": str(cards[1]),
            "noise_card": str(cards[2]),
            "alias": alias,
            "alias_initials": initials,
            "pastry": rng.choice(r["pastry"]),
            "weather": rng.choice(r["weather"]),
        }
        for suspect, moods in r["moods"].items():
            variables[f"mood_{suspect}"] = rng.choice(moods)
        return variables

    # ---- Reading the state ----------------------------------------------

    def _clues(self, game):
        return self._resolved[game.variant]["clues"]

    def _suspects(self, game):
        return self._resolved[game.variant]["suspects"]

    def _fill(self, game, text):
        return text.format_map(game.variables) if text else text

    def clue_state(self, game, clue_id):
        """open, available or locked."""
        clues = self._clues(game)
        if clue_id not in clues:
            raise GameError(f"There is no clue called {clue_id}.")
        if clue_id in game.opened:
            return "open"
        unlock = clues[clue_id]["unlock"]
        if unlock.get("start"):
            return "available"
        if "requires" in unlock:
            if all(c in game.opened for c in unlock["requires"]):
                return "available"
            return "locked"
        return "available" if clue_id in game.unlocked else "locked"

    def clue_list(self, game):
        """Every clue with its title and state. Locked clues show no content."""
        return [
            {
                "id": clue_id,
                "title": clue["title"],
                "kind": clue["kind"],
                "state": self.clue_state(game, clue_id),
            }
            for clue_id, clue in self._clues(game).items()
        ]

    def read_clue(self, game, clue_id):
        """The full text of a clue the player has already opened. Free."""
        if self.clue_state(game, clue_id) != "open":
            raise GameError("You have not opened that clue yet.")
        clue = self._clues(game)[clue_id]
        return {
            "id": clue_id,
            "title": clue["title"],
            "kind": clue["kind"],
            "text": self._fill(game, clue.get("text")),
            "log": self._fill(game, clue.get("log")),
            "hidden_text": self._fill(game, clue.get("hidden_text")),
            "chart": clue.get("chart"),
        }

    def time_left(self, game):
        return self.clock_rules["limit_minutes"] - game.clock

    def clock_label(self, game):
        """The in-game time, starting at 00:00."""
        hours, minutes = divmod(game.clock, 60)
        return f"{hours:02d}:{minutes:02d}"

    # ---- Actions ------------------------------------------------------------

    def _spend(self, game, minutes):
        if game.status != "playing":
            raise GameError("The case is closed.")
        if minutes > self.time_left(game):
            raise GameError("Not enough time left before 09:00. Make your accusation.")
        game.clock += minutes

    def _check_suspect(self, game, suspect):
        if suspect not in self._suspects(game):
            raise GameError(f"There is no suspect called {suspect}.")

    def _award(self, game, badge_id):
        if badge_id not in game.badges:
            game.badges.append(badge_id)

    def badge_list(self, game):
        """The badges earned in this game, with their titles."""
        return [{"id": b, **self.case["badges"][b]} for b in game.badges]

    def _unlock(self, game, clue_id):
        if clue_id in game.unlocked or clue_id in game.opened:
            return []
        game.unlocked.append(clue_id)
        return [clue_id]

    def open_clue(self, game, clue_id):
        """Open an available clue. Costs clue_cost minutes."""
        state = self.clue_state(game, clue_id)
        if state == "open":
            raise GameError("That clue is already open.")
        if state == "locked":
            raise GameError("That clue is still locked.")
        self._spend(game, self.clock_rules["clue_cost"])
        game.opened.append(clue_id)
        game.history.append({"action": "open", "clue": clue_id, "clock": game.clock})
        return self.read_clue(game, clue_id)

    def ask(self, game, suspect, topic):
        """Record a question to a suspect, tagged with a topic.

        The AI layer writes the answer. It must pass the topic it detected;
        the engine checks the tag against the allowed list and decides what
        it unlocks. Returns the clues it unlocked and the scripted line for
        that topic, if there is one.
        """
        self._check_suspect(game, suspect)
        if topic not in self.case["topics"]:
            raise GameError(f"Unknown topic: {topic}")
        self._spend(game, self.clock_rules["question_cost"])
        s = self._suspects(game)[suspect]
        unlocked = []
        clue_id = s.get("topic_unlocks", {}).get(topic)
        if clue_id:
            unlocked = self._unlock(game, clue_id)
        game.history.append({"action": "ask", "suspect": suspect, "topic": topic, "clock": game.clock})
        return {"unlocked": unlocked, "line": self._fill(game, s.get("topic_lines", {}).get(topic))}

    def present(self, game, suspect, clue_id):
        """Show an opened clue to a suspect. Costs one question.

        Returns the clues it unlocked and the suspect's scripted reaction. If the
        clue breaks claims of that suspect not caught before, they are recorded
        and returned under "contradictions"; the key is left out when there are
        none, so use result.get("contradictions", []).
        """
        self._check_suspect(game, suspect)
        if self.clue_state(game, clue_id) != "open":
            raise GameError("You can only show a suspect a clue you have opened.")
        self._spend(game, self.clock_rules["question_cost"])
        if [suspect, clue_id] not in game.presented:
            game.presented.append([suspect, clue_id])
        unlocked = []
        for other_id, other in self._clues(game).items():
            rule = other["unlock"].get("present")
            if rule and rule["suspect"] == suspect and rule["clue"] == clue_id:
                unlocked += self._unlock(game, other_id)
        reveal = self._suspects(game)[suspect].get("reveals", {}).get(clue_id)
        if suspect == "professor" and clue_id == "D8":
            self._award(game, "honey_trap")
        caught = self._catch_contradictions(game, suspect, clue_id)
        game.history.append({"action": "present", "suspect": suspect, "clue": clue_id, "clock": game.clock})
        result = {"unlocked": unlocked, "reveal": self._fill(game, reveal)}
        if caught:
            result["contradictions"] = caught
        return result

    def _catch_contradictions(self, game, suspect, clue_id):
        """Record each claim of the suspect that this clue breaks. Each claim counts once."""
        caught = []
        for claim in self._suspects(game)[suspect].get("claims", []):
            if clue_id in claim["broken_by"] and [suspect, claim["id"]] not in game.contradictions:
                game.contradictions.append([suspect, claim["id"]])
                caught.append(self._claim_view(game, suspect, claim, clue_id))
        return caught

    def _claim_view(self, game, suspect, claim, clue_id):
        return {
            "suspect": suspect,
            "claim": claim["id"],
            "text": self._fill(game, claim["text"]),
            "clue": clue_id,
        }

    def contradiction_list(self, game):
        """The contradictions caught so far, oldest first, with each claim's text.

        Only lists claims the player has broken, so it never gives away which
        clue breaks a claim they have not caught yet.
        """
        result = []
        for suspect, claim_id in game.contradictions:
            claims = {c["id"]: c for c in self._suspects(game)[suspect].get("claims", [])}
            if claim_id not in claims:
                continue
            claim = claims[claim_id]
            # The first clue shown to this suspect that breaks the claim is the one that caught it.
            clue_id = next(
                (c for s, c in game.presented if s == suspect and c in claim["broken_by"]), None
            )
            result.append(self._claim_view(game, suspect, claim, clue_id))
        return result

    def accuse(self, game, who, how, where, why):
        """Make an accusation. Free, but three wrong ones and the case goes cold.

        A wrong accusation only says how many of the four choices are right.
        """
        if game.status != "playing":
            raise GameError("The case is closed.")
        choice = {"who": who, "how": how, "where": where, "why": why}
        for column in COLUMNS:
            if choice[column] not in option_ids(self.case, column):
                raise GameError(f"That is not a valid option for {column}.")
        solution = self._resolved[game.variant]["solution"]
        correct = sum(choice[c] == solution[c] for c in COLUMNS)
        if correct == len(COLUMNS):
            game.status = "solved"
            if game.clock < self.case["hedge_fund_minutes"]:
                self._award(game, "hedge_fund")
        else:
            game.strikes += 1
            if game.strikes >= self.case["max_strikes"]:
                game.status = "cold"
        game.history.append({"action": "accuse", "correct": correct, "clock": game.clock})
        return {
            "correct": correct,
            "status": game.status,
            "strikes_left": self.case["max_strikes"] - game.strikes,
        }

    def solution(self, game):
        """The answer. Only available once the game is over."""
        if game.status == "playing":
            raise GameError("The solution is only shown when the case is closed.")
        return dict(self._resolved[game.variant]["solution"])

    # ---- For the AI layer ---------------------------------------------------

    def check_secret(self, game, suspect, text):
        """Run before any player message is sent to the AI.

        Returns True if the message looks like a password or key. The AI layer must
        then not send the message anywhere. Typing one to the Companion, who asks
        for passwords, earns the badge.
        """
        self._check_suspect(game, suspect)
        if not looks_like_secret(text, self._vocabulary):
            return False
        if self._suspects(game)[suspect].get("asks_password"):
            self._award(game, "spy_password")
        return True

    def character_brief(self, game, suspect):
        """What the AI needs to play one suspect, and nothing more.

        Contains the suspect's persona, mood, cover story, topic lines and only
        the reveals the player has earned by presenting clues to them. It never
        contains the solution or the text of any clue.
        """
        self._check_suspect(game, suspect)
        s = self._suspects(game)[suspect]
        earned = {
            clue_id: self._fill(game, s["reveals"][clue_id])
            for presented_to, clue_id in game.presented
            if presented_to == suspect and clue_id in s.get("reveals", {})
        }
        return {
            "name": s["name"],
            "persona": s["persona"],
            "mood": game.variables.get(f"mood_{suspect}"),
            "cover": self._fill(game, s["cover"]),
            "topic_lines": {k: self._fill(game, v) for k, v in s.get("topic_lines", {}).items()},
            "earned_reveals": earned,
            "asks_password": bool(s.get("asks_password")),
        }
