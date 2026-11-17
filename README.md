# The Carcavelos Paper

A detective game. The night before the Semiconductor Valuation final, the exam leaks in the cohort
group chat. You have until 09:00 to question five suspects, played by AI, and name who did it, how,
where and why. The culprit changes from game to game.

**Play it:** _deployed URL goes here_

## Team

| Name | Student number |
| --- | --- |
| _name_ | _number_ |
| _name_ | _number_ |
| _name_ | _number_ |
| _name_ | _number_ |

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
