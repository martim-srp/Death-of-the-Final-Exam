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

## Run the tests

```bash
python -m pytest
```

## How it works

- `data/case.json` holds the story as data: clues, suspects, unlock rules and three variants with
  different culprits.
- `game/engine.py` holds the rules. It decides what is unlocked, what each action costs and whether an
  accusation is right.
- The AI only plays the suspects. It never sees the solution and never decides what unlocks.

All characters, the course and the companies in the game are fictional.
