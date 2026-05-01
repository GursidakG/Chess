# Tournament Hall Chess

A playable Python chess app with a dark tournament hall aesthetic.

The recommended version is `Chess.py`, which uses Pygame for smooth rendering and `python-chess` for fast, reliable legal move logic.

## Run

```bash
python3 -m pip install -r requirements.txt
python3 fast_tournament_chess.py
```

## Features

- `python-chess` legal move generation
- Check, checkmate, and stalemate detection
- Castling, en passant, and pawn promotion
- Click-to-select and click-to-move
- Highlighted valid moves and last move
- Local 2-player mode
- Play vs basic AI mode
- Threaded minimax AI with alpha-beta pruning
- Move history sidebar
- Captured pieces display
- Evaluation bar
- Player timers
- Flip board option

## Controls

Use the mouse to select a piece and then click a highlighted square to move.

The AI plays Black when **Play vs AI** is enabled.

Keyboard shortcuts:

- `N` new game
- `F` flip board
- `A` toggle AI
- `Esc` clear selection
- `Q`, `R`, `B`, `N` choose promotion piece
