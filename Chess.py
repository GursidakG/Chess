from __future__ import annotations

import math
import queue
import threading
import time
from dataclasses import dataclass

try:
    import chess
    import pygame
except ImportError as exc:
    missing = str(exc).split("'")[1] if "'" in str(exc) else "pygame or python-chess"
    raise SystemExit(
        f"Missing dependency: {missing}\n"
        "Install everything with:\n"
        "  python3 -m pip install -r requirements.txt\n"
        "Then run:\n"
        "  python3 fast_tournament_chess.py"
    ) from exc


WIDTH, HEIGHT = 1220, 780
FPS = 60
BOARD_SIZE = 672
SQUARE = BOARD_SIZE // 8
BOARD_X, BOARD_Y = 34, 74
PANEL_X = BOARD_X + BOARD_SIZE + 28
PANEL_W = WIDTH - PANEL_X - 34

BG = (18, 12, 8)
PANEL = (30, 21, 16)
PANEL_2 = (40, 28, 20)
LINE = (68, 49, 36)
TEXT = (244, 231, 208)
MUTED = (184, 169, 143)
GOLD = (201, 168, 76)
GOLD_2 = (232, 207, 122)
LIGHT_SQ = (200, 169, 106)
DARK_SQ = (123, 79, 42)
SELECT = (201, 168, 76)
LEGAL = (232, 207, 122)
LAST = (154, 120, 56)
RED = (155, 61, 46)
GREEN = (76, 122, 69)
WHITE_PIECE = (248, 235, 211)
BLACK_PIECE = (20, 13, 9)

PIECE_GLYPHS = {
    chess.PAWN: ("♙", "♟"),
    chess.KNIGHT: ("♘", "♞"),
    chess.BISHOP: ("♗", "♝"),
    chess.ROOK: ("♖", "♜"),
    chess.QUEEN: ("♕", "♛"),
    chess.KING: ("♔", "♚"),
}
PIECE_VALUES = {
    chess.PAWN: 100,
    chess.KNIGHT: 320,
    chess.BISHOP: 330,
    chess.ROOK: 500,
    chess.QUEEN: 900,
    chess.KING: 0,
}
PIECE_TABLES = {
    chess.PAWN: [0, 5, 8, 12, 18, 26, 38, 0],
    chess.KNIGHT: [-24, -12, 8, 16, 16, 8, -12, -24],
    chess.BISHOP: [-12, 2, 8, 12, 12, 8, 2, -12],
    chess.ROOK: [0, 3, 5, 8, 8, 5, 3, 0],
    chess.QUEEN: [-4, 2, 5, 8, 8, 5, 2, -4],
    chess.KING: [8, 12, 4, 0, 0, 4, 12, 8],
}


@dataclass
class Button:
    rect: pygame.Rect
    label: str
    action: str
    active: bool = False


class ChessAI:
    def __init__(self, depth: int = 3) -> None:
        self.depth = depth
        self.nodes = 0

    def choose_move(self, board: chess.Board) -> chess.Move | None:
        moves = list(board.legal_moves)
        if not moves:
            return None
        self.nodes = 0
        ordered = self.order_moves(board, moves)
        best_move = ordered[0]
        best_score = -math.inf if board.turn == chess.WHITE else math.inf
        alpha, beta = -math.inf, math.inf

        for move in ordered:
            board.push(move)
            score = self.search(board, self.depth - 1, alpha, beta)
            board.pop()
            if board.turn == chess.WHITE:
                if score > best_score:
                    best_score, best_move = score, move
                alpha = max(alpha, best_score)
            else:
                if score < best_score:
                    best_score, best_move = score, move
                beta = min(beta, best_score)
        return best_move

    def search(self, board: chess.Board, depth: int, alpha: float, beta: float) -> float:
        self.nodes += 1
        if board.is_checkmate():
            return -100000 if board.turn == chess.WHITE else 100000
        if board.is_stalemate() or board.is_insufficient_material() or board.can_claim_draw():
            return 0
        if depth == 0:
            return self.evaluate(board)

        moves = self.order_moves(board, list(board.legal_moves))
        if board.turn == chess.WHITE:
            value = -math.inf
            for move in moves:
                board.push(move)
                value = max(value, self.search(board, depth - 1, alpha, beta))
                board.pop()
                alpha = max(alpha, value)
                if alpha >= beta:
                    break
            return value

        value = math.inf
        for move in moves:
            board.push(move)
            value = min(value, self.search(board, depth - 1, alpha, beta))
            board.pop()
            beta = min(beta, value)
            if alpha >= beta:
                break
        return value

    def order_moves(self, board: chess.Board, moves: list[chess.Move]) -> list[chess.Move]:
        def score(move: chess.Move) -> int:
            value = 0
            if board.is_capture(move):
                victim = board.piece_at(move.to_square)
                attacker = board.piece_at(move.from_square)
                if victim and attacker:
                    value += 10 * PIECE_VALUES[victim.piece_type] - PIECE_VALUES[attacker.piece_type]
                if board.is_en_passant(move):
                    value += 1000
            if move.promotion:
                value += PIECE_VALUES.get(move.promotion, 0)
            if board.gives_check(move):
                value += 50
            if chess.square_file(move.to_square) in (3, 4) and chess.square_rank(move.to_square) in (3, 4):
                value += 12
            return value

        return sorted(moves, key=score, reverse=True)

    def evaluate(self, board: chess.Board) -> float:
        score = 0
        for square, piece in board.piece_map().items():
            value = PIECE_VALUES[piece.piece_type]
            rank = chess.square_rank(square)
            file = chess.square_file(square)
            center = 7 - (abs(3.5 - rank) + abs(3.5 - file))
            table_rank = rank if piece.color == chess.WHITE else 7 - rank
            value += PIECE_TABLES[piece.piece_type][table_rank] + center * 2
            score += value if piece.color == chess.WHITE else -value

        score += 8 * (len(list(board.legal_moves)) if board.turn == chess.WHITE else -len(list(board.legal_moves)))
        if board.is_check():
            score += -35 if board.turn == chess.WHITE else 35
        return score


class TournamentHallChess:
    def __init__(self) -> None:
        pygame.init()
        pygame.display.set_caption("Tournament Hall Chess")
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT), pygame.RESIZABLE)
        self.clock = pygame.time.Clock()
        self.board = chess.Board()
        self.ai = ChessAI(depth=3)
        self.vs_ai = True
        self.flipped = False
        self.selected: chess.Square | None = None
        self.legal_targets: list[chess.Move] = []
        self.pending_promotion: tuple[chess.Move, list[chess.Move]] | None = None
        self.status = "White to move"
        self.move_history: list[str] = []
        self.captured_white: list[chess.Piece] = []
        self.captured_black: list[chess.Piece] = []
        self.white_seconds = 0.0
        self.black_seconds = 0.0
        self.last_timer = time.time()
        self.ai_queue: queue.Queue[chess.Move | None] = queue.Queue()
        self.ai_thread: threading.Thread | None = None
        self.ai_thinking = False
        self.last_ai_nodes = 0
        self.buttons: list[Button] = []
        self.layout = self.compute_layout(WIDTH, HEIGHT)
        self.fonts = self.load_fonts()
        self.running = True

    def load_fonts(self) -> dict[str, pygame.font.Font]:
        return {
            "title": pygame.font.SysFont("Georgia", 34, bold=True),
            "heading": pygame.font.SysFont("Georgia", 22, bold=True),
            "body": pygame.font.SysFont("Menlo", 15, bold=True),
            "mono": pygame.font.SysFont("Menlo", 13),
            "small": pygame.font.SysFont("Menlo", 11, bold=True),
            "piece": pygame.font.SysFont("Arial", 64, bold=True),
            "piece_small": pygame.font.SysFont("Arial", 24, bold=True),
        }

    def compute_layout(self, width: int, height: int) -> dict[str, pygame.Rect | int]:
        margin = 26
        header_h = 58
        board_size = min(height - header_h - margin * 2, width - PANEL_W - margin * 3)
        board_size = max(480, min(BOARD_SIZE, board_size))
        board_x = margin
        board_y = header_h + margin // 2
        panel_x = board_x + board_size + margin
        panel_w = max(300, width - panel_x - margin)
        return {
            "board": pygame.Rect(board_x, board_y, board_size, board_size),
            "panel": pygame.Rect(panel_x, board_y, panel_w, board_size),
            "header": pygame.Rect(margin, 14, width - margin * 2, header_h),
            "square": board_size // 8,
        }

    def square_to_rect(self, square: chess.Square) -> pygame.Rect:
        board_rect: pygame.Rect = self.layout["board"]  # type: ignore[assignment]
        sq = self.layout["square"]  # type: ignore[assignment]
        file = chess.square_file(square)
        rank = chess.square_rank(square)
        col = 7 - file if self.flipped else file
        row = rank if self.flipped else 7 - rank
        return pygame.Rect(board_rect.x + col * sq, board_rect.y + row * sq, sq, sq)

    def pixel_to_square(self, pos: tuple[int, int]) -> chess.Square | None:
        board_rect: pygame.Rect = self.layout["board"]  # type: ignore[assignment]
        sq = self.layout["square"]  # type: ignore[assignment]
        if not board_rect.collidepoint(pos):
            return None
        col = (pos[0] - board_rect.x) // sq
        row = (pos[1] - board_rect.y) // sq
        file = 7 - col if self.flipped else col
        rank = row if self.flipped else 7 - row
        return chess.square(file, rank)

    def run(self) -> None:
        while self.running:
            dt = self.clock.tick(FPS) / 1000
            self.handle_events()
            self.update(dt)
            self.draw()
        pygame.quit()

    def handle_events(self) -> None:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type == pygame.VIDEORESIZE:
                self.screen = pygame.display.set_mode((event.w, event.h), pygame.RESIZABLE)
                self.layout = self.compute_layout(event.w, event.h)
            elif event.type == pygame.KEYDOWN:
                self.handle_key(event.key)
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                self.handle_click(event.pos)

    def handle_key(self, key: int) -> None:
        if self.pending_promotion:
            mapping = {
                pygame.K_q: chess.QUEEN,
                pygame.K_r: chess.ROOK,
                pygame.K_b: chess.BISHOP,
                pygame.K_n: chess.KNIGHT,
                pygame.K_ESCAPE: None,
            }
            if key in mapping:
                if mapping[key] is None:
                    self.pending_promotion = None
                    self.status = self.turn_text()
                else:
                    self.complete_promotion(mapping[key])
            return

        if key == pygame.K_n:
            self.new_game()
        elif key == pygame.K_f:
            self.flipped = not self.flipped
        elif key == pygame.K_a:
            self.vs_ai = not self.vs_ai
            self.maybe_start_ai()
        elif key in (pygame.K_ESCAPE, pygame.K_BACKSPACE):
            self.clear_selection()

    def handle_click(self, pos: tuple[int, int]) -> None:
        if self.pending_promotion:
            self.handle_promotion_click(pos)
            return

        for button in self.buttons:
            if button.rect.collidepoint(pos):
                self.activate_button(button.action)
                return

        if self.ai_thinking or self.board.is_game_over():
            return
        if self.vs_ai and self.board.turn == chess.BLACK:
            return

        square = self.pixel_to_square(pos)
        if square is None:
            return
        piece = self.board.piece_at(square)

        if self.selected is not None:
            move = self.find_move(self.selected, square)
            if move:
                self.try_play_move(move)
                return
            if piece and piece.color == self.board.turn:
                self.select(square)
            else:
                self.clear_selection()
        elif piece and piece.color == self.board.turn:
            self.select(square)

    def activate_button(self, action: str) -> None:
        if action == "new":
            self.new_game()
        elif action == "flip":
            self.flipped = not self.flipped
        elif action == "ai":
            self.vs_ai = not self.vs_ai
            self.maybe_start_ai()
        elif action == "depth":
            self.ai.depth = 2 if self.ai.depth >= 4 else self.ai.depth + 1

    def select(self, square: chess.Square) -> None:
        self.selected = square
        self.legal_targets = [move for move in self.board.legal_moves if move.from_square == square]

    def clear_selection(self) -> None:
        self.selected = None
        self.legal_targets = []

    def find_move(self, start: chess.Square, end: chess.Square) -> chess.Move | None:
        candidates = [move for move in self.legal_targets if move.to_square == end]
        if not candidates:
            return None
        promotion_moves = [move for move in candidates if move.promotion]
        if promotion_moves:
            self.pending_promotion = (candidates[0], promotion_moves)
            self.status = "Promote: click a piece or press Q, R, B, N"
            return None
        return candidates[0]

    def complete_promotion(self, piece_type: int) -> None:
        if not self.pending_promotion:
            return
        _, options = self.pending_promotion
        for move in options:
            if move.promotion == piece_type:
                self.pending_promotion = None
                self.try_play_move(move)
                return

    def handle_promotion_click(self, pos: tuple[int, int]) -> None:
        panel: pygame.Rect = self.layout["panel"]  # type: ignore[assignment]
        rect = pygame.Rect(panel.x + 18, panel.bottom - 134, min(panel.w - 36, 292), 112)
        x = rect.x + 14
        y = rect.y + 54
        for i, piece_type in enumerate([chess.QUEEN, chess.ROOK, chess.BISHOP, chess.KNIGHT]):
            rect = pygame.Rect(x + i * 58, y, 48, 48)
            if rect.collidepoint(pos):
                self.complete_promotion(piece_type)
                return

    def try_play_move(self, move: chess.Move) -> None:
        if move not in self.board.legal_moves:
            return
        self.push_move(move)
        self.clear_selection()
        self.update_game_status()
        self.maybe_start_ai()

    def push_move(self, move: chess.Move) -> None:
        captured_piece = self.board.piece_at(move.to_square)
        if self.board.is_en_passant(move):
            offset = -8 if self.board.turn == chess.WHITE else 8
            captured_piece = self.board.piece_at(move.to_square + offset)
        san = self.board.san(move)
        mover = self.board.turn
        self.board.push(move)
        if captured_piece:
            if mover == chess.WHITE:
                self.captured_white.append(captured_piece)
            else:
                self.captured_black.append(captured_piece)
        self.move_history.append(san)

    def maybe_start_ai(self) -> None:
        if not self.vs_ai or self.board.turn != chess.BLACK or self.board.is_game_over() or self.ai_thinking:
            return
        self.ai_thinking = True
        self.status = "Black is thinking..."
        board_copy = self.board.copy(stack=False)

        def worker() -> None:
            move = self.ai.choose_move(board_copy)
            self.last_ai_nodes = self.ai.nodes
            self.ai_queue.put(move)

        self.ai_thread = threading.Thread(target=worker, daemon=True)
        self.ai_thread.start()

    def update(self, _dt: float) -> None:
        now = time.time()
        elapsed = now - self.last_timer
        self.last_timer = now
        if not self.board.is_game_over() and not self.ai_thinking and not self.pending_promotion:
            if self.board.turn == chess.WHITE:
                self.white_seconds += elapsed
            else:
                self.black_seconds += elapsed

        try:
            move = self.ai_queue.get_nowait()
        except queue.Empty:
            return
        self.ai_thinking = False
        if move and move in self.board.legal_moves:
            self.push_move(move)
        self.update_game_status()

    def update_game_status(self) -> None:
        if self.board.is_checkmate():
            self.status = "Checkmate. White wins." if self.board.turn == chess.BLACK else "Checkmate. Black wins."
        elif self.board.is_stalemate():
            self.status = "Stalemate."
        elif self.board.is_insufficient_material():
            self.status = "Draw by insufficient material."
        elif self.board.can_claim_draw():
            self.status = "Draw can be claimed."
        else:
            self.status = self.turn_text()

    def turn_text(self) -> str:
        turn = "White" if self.board.turn == chess.WHITE else "Black"
        suffix = " in check" if self.board.is_check() else " to move"
        return f"{turn}{suffix}"

    def new_game(self) -> None:
        self.board.reset()
        self.selected = None
        self.legal_targets = []
        self.pending_promotion = None
        self.move_history = []
        self.captured_white = []
        self.captured_black = []
        self.white_seconds = 0
        self.black_seconds = 0
        self.last_ai_nodes = 0
        self.ai_thinking = False
        while not self.ai_queue.empty():
            self.ai_queue.get_nowait()
        self.status = "White to move"

    def draw(self) -> None:
        self.screen.fill(BG)
        self.buttons = []
        self.draw_header()
        self.draw_board()
        self.draw_panel()
        if self.pending_promotion:
            self.draw_promotion_overlay()
        pygame.display.flip()

    def draw_header(self) -> None:
        header: pygame.Rect = self.layout["header"]  # type: ignore[assignment]
        self.draw_text("Tournament Hall Chess", self.fonts["title"], TEXT, header.x, header.y)
        self.draw_text("Fast Pygame board • python-chess rules • minimax AI", self.fonts["mono"], MUTED, header.x + 392, header.y + 18)

    def draw_board(self) -> None:
        board_rect: pygame.Rect = self.layout["board"]  # type: ignore[assignment]
        sq = self.layout["square"]  # type: ignore[assignment]
        pygame.draw.rect(self.screen, PANEL, board_rect.inflate(24, 24), border_radius=8)
        pygame.draw.rect(self.screen, GOLD, board_rect.inflate(24, 24), width=2, border_radius=8)

        selected_targets = {move.to_square for move in self.legal_targets}
        last_move = self.board.peek() if self.board.move_stack else None

        for square in chess.SQUARES:
            rect = self.square_to_rect(square)
            file = chess.square_file(square)
            rank = chess.square_rank(square)
            color = LIGHT_SQ if (file + rank) % 2 else DARK_SQ
            pygame.draw.rect(self.screen, color, rect)

            if last_move and square in (last_move.from_square, last_move.to_square):
                overlay = pygame.Surface((sq, sq), pygame.SRCALPHA)
                overlay.fill((*LAST, 120))
                self.screen.blit(overlay, rect)

            if square == self.selected:
                pygame.draw.rect(self.screen, SELECT, rect.inflate(-8, -8), width=4, border_radius=4)

            if square in selected_targets:
                target_piece = self.board.piece_at(square)
                if target_piece:
                    pygame.draw.circle(self.screen, LEGAL, rect.center, sq // 2 - 9, width=5)
                else:
                    pygame.draw.circle(self.screen, LEGAL, rect.center, max(8, sq // 8))

            piece = self.board.piece_at(square)
            if piece:
                self.draw_piece(piece, rect)

        self.draw_coordinates(board_rect, sq)

    def draw_piece(self, piece: chess.Piece, rect: pygame.Rect) -> None:
        glyph = PIECE_GLYPHS[piece.piece_type][0 if piece.color == chess.WHITE else 1]
        shadow_color = BLACK_PIECE if piece.color == chess.WHITE else GOLD_2
        fill_color = WHITE_PIECE if piece.color == chess.WHITE else BLACK_PIECE
        shadow = self.fonts["piece"].render(glyph, True, shadow_color)
        text = self.fonts["piece"].render(glyph, True, fill_color)
        shadow_rect = shadow.get_rect(center=(rect.centerx + 2, rect.centery + 3))
        text_rect = text.get_rect(center=rect.center)
        self.screen.blit(shadow, shadow_rect)
        self.screen.blit(text, text_rect)

    def draw_coordinates(self, board_rect: pygame.Rect, sq: int) -> None:
        for i in range(8):
            file_label = chess.FILE_NAMES[7 - i] if self.flipped else chess.FILE_NAMES[i]
            rank_label = str(i + 1) if self.flipped else str(8 - i)
            self.draw_text(file_label, self.fonts["small"], BLACK_PIECE, board_rect.x + i * sq + sq - 18, board_rect.bottom - 18)
            self.draw_text(rank_label, self.fonts["small"], BLACK_PIECE, board_rect.x + 8, board_rect.y + i * sq + 7)

    def draw_panel(self) -> None:
        panel: pygame.Rect = self.layout["panel"]  # type: ignore[assignment]
        pygame.draw.rect(self.screen, PANEL, panel, border_radius=8)
        pygame.draw.rect(self.screen, LINE, panel, width=1, border_radius=8)

        y = panel.y + 20
        self.draw_text(self.status, self.fonts["heading"], GOLD_2, panel.x + 20, y)
        y += 46
        self.draw_eval_bar(panel.x + 20, y, panel.w - 40, 28)
        y += 48

        self.draw_button(panel.x + 20, y, 126, 42, "New", "new")
        self.draw_button(panel.x + 158, y, 126, 42, "Flip", "flip")
        self.draw_button(panel.x + 296, y, max(96, panel.w - 316), 42, f"AI {'On' if self.vs_ai else 'Off'}", "ai", active=self.vs_ai)
        y += 56
        self.draw_button(panel.x + 20, y, panel.w - 40, 40, f"AI Depth: {self.ai.depth}", "depth")
        y += 58

        self.draw_player_card(panel.x + 20, y, panel.w - 40, "White", self.white_seconds, self.board.turn == chess.WHITE)
        y += 62
        self.draw_player_card(panel.x + 20, y, panel.w - 40, "Black", self.black_seconds, self.board.turn == chess.BLACK)
        y += 82

        self.draw_text("Captured", self.fonts["heading"], TEXT, panel.x + 20, y)
        y += 34
        self.draw_captured(panel.x + 20, y, panel.w - 40)
        y += 82

        self.draw_text("Move History", self.fonts["heading"], TEXT, panel.x + 20, y)
        y += 34
        self.draw_history(panel.x + 20, y, panel.w - 40, panel.bottom - y - 22)

    def draw_button(self, x: int, y: int, w: int, h: int, label: str, action: str, active: bool = False) -> None:
        rect = pygame.Rect(x, y, w, h)
        color = GOLD if active else PANEL_2
        text_color = BG if active else TEXT
        pygame.draw.rect(self.screen, color, rect, border_radius=6)
        pygame.draw.rect(self.screen, GOLD if active else LINE, rect, width=2, border_radius=6)
        text = self.fonts["body"].render(label, True, text_color)
        self.screen.blit(text, text.get_rect(center=rect.center))
        self.buttons.append(Button(rect, label, action, active))

    def draw_player_card(self, x: int, y: int, w: int, name: str, seconds: float, active: bool) -> None:
        rect = pygame.Rect(x, y, w, 52)
        pygame.draw.rect(self.screen, PANEL_2, rect, border_radius=6)
        pygame.draw.rect(self.screen, GOLD if active else LINE, rect, width=2, border_radius=6)
        self.draw_text(name, self.fonts["heading"], TEXT, x + 14, y + 13)
        timer = self.format_time(seconds)
        timer_text = self.fonts["body"].render(timer, True, GOLD_2)
        self.screen.blit(timer_text, (rect.right - timer_text.get_width() - 14, y + 17))

    def draw_eval_bar(self, x: int, y: int, w: int, h: int) -> None:
        score = max(-1200, min(1200, self.ai.evaluate(self.board)))
        white_w = int(w * (0.5 + score / 2400))
        pygame.draw.rect(self.screen, (20, 13, 9), (x, y, w, h), border_radius=5)
        pygame.draw.rect(self.screen, GOLD, (x, y, white_w, h), border_radius=5)
        pygame.draw.rect(self.screen, LINE, (x, y, w, h), width=1, border_radius=5)
        label = f"Eval {score / 100:+.1f}"
        if self.ai_thinking:
            label += f" • thinking"
        elif self.last_ai_nodes:
            label += f" • {self.last_ai_nodes:,} nodes"
        text = self.fonts["small"].render(label, True, TEXT)
        self.screen.blit(text, text.get_rect(center=(x + w // 2, y + h // 2)))

    def draw_captured(self, x: int, y: int, w: int) -> None:
        rect = pygame.Rect(x, y, w, 64)
        pygame.draw.rect(self.screen, PANEL_2, rect, border_radius=6)
        pygame.draw.rect(self.screen, LINE, rect, width=1, border_radius=6)
        white = "".join(PIECE_GLYPHS[p.piece_type][1] for p in self.captured_white) or "None"
        black = "".join(PIECE_GLYPHS[p.piece_type][0] for p in self.captured_black) or "None"
        self.draw_text(f"White: {white}", self.fonts["mono"], MUTED, x + 12, y + 10)
        self.draw_text(f"Black: {black}", self.fonts["mono"], MUTED, x + 12, y + 36)

    def draw_history(self, x: int, y: int, w: int, h: int) -> None:
        rect = pygame.Rect(x, y, w, h)
        pygame.draw.rect(self.screen, PANEL_2, rect, border_radius=6)
        pygame.draw.rect(self.screen, LINE, rect, width=1, border_radius=6)
        rows = max(1, (h - 18) // 24)
        pairs = []
        for i in range(0, len(self.move_history), 2):
            white = self.move_history[i]
            black = self.move_history[i + 1] if i + 1 < len(self.move_history) else ""
            pairs.append(f"{i // 2 + 1:02d}. {white:<10} {black}")
        visible = pairs[-rows:]
        for idx, item in enumerate(visible):
            color = GOLD_2 if idx == len(visible) - 1 else TEXT
            self.draw_text(item, self.fonts["mono"], color, x + 12, y + 12 + idx * 24)

    def draw_promotion_overlay(self) -> None:
        panel: pygame.Rect = self.layout["panel"]  # type: ignore[assignment]
        width, height = self.screen.get_size()
        overlay = pygame.Surface((width, height), pygame.SRCALPHA)
        overlay.fill((18, 12, 8, 110))
        self.screen.blit(overlay, (0, 0))
        rect = pygame.Rect(panel.x + 18, panel.bottom - 134, min(panel.w - 36, 292), 112)
        pygame.draw.rect(self.screen, PANEL, rect, border_radius=8)
        pygame.draw.rect(self.screen, GOLD, rect, width=2, border_radius=8)
        self.draw_text("Promote pawn", self.fonts["heading"], GOLD_2, rect.x + 14, rect.y + 12)
        for i, piece_type in enumerate([chess.QUEEN, chess.ROOK, chess.BISHOP, chess.KNIGHT]):
            piece = chess.Piece(piece_type, self.board.turn)
            box = pygame.Rect(rect.x + 14 + i * 58, rect.y + 54, 48, 48)
            pygame.draw.rect(self.screen, GOLD, box, border_radius=6)
            glyph = PIECE_GLYPHS[piece.piece_type][0 if piece.color == chess.WHITE else 1]
            text = self.fonts["piece_small"].render(glyph, True, BG)
            self.screen.blit(text, text.get_rect(center=box.center))

    def draw_text(self, text: str, font: pygame.font.Font, color: tuple[int, int, int], x: int, y: int) -> None:
        surface = font.render(text, True, color)
        self.screen.blit(surface, (x, y))

    def format_time(self, seconds: float) -> str:
        total = int(seconds)
        return f"{total // 60:02d}:{total % 60:02d}"


if __name__ == "__main__":
    TournamentHallChess().run()
