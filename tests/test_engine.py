import random

from config import settings as cfg
from game.engine import DeathReason, EngineEvent, GameEngine
from game.snake import Direction


def engine():
    return GameEngine(cols=20, rows=12, rng=random.Random(5))


def test_moves_continuously_right():
    e = engine()
    head = e.snake.head
    e.step()
    assert e.snake.head == (head[0] + 1, head[1])


def test_eating_scores_and_grows_immediately():
    e = engine()
    hx, hy = e.snake.head
    e.food.position = (hx + 1, hy)
    length = e.length
    events = e.step()
    assert EngineEvent.ATE in events
    assert e.score.score == cfg.FOOD_SCORE
    assert e.length == length + 1
    assert e.food.position not in e.snake.body


def test_wall_collision_ends_game():
    e = engine()
    e.food.position = (0, 0)
    events = []
    for _ in range(40):
        events += e.step()
        if not e.alive:
            break
    assert EngineEvent.DIED in events
    assert e.death_reason is DeathReason.WALL


def test_self_collision_ends_game():
    e = engine()
    e.snake.grow(5)
    for _ in range(5):
        e.step()
    e.food.position = (0, 0)
    for d in (Direction.DOWN, Direction.LEFT, Direction.UP):
        e.set_direction(d)
        e.step()
    assert not e.alive and e.death_reason is DeathReason.SELF


def test_illegal_reverse_blocked_in_engine():
    e = engine()
    assert e.set_direction(Direction.LEFT) is False


def test_speed_scales_and_is_capped():
    e = engine()
    assert e.speed == cfg.INITIAL_SPEED
    e.score.score = 200
    assert e.speed == cfg.INITIAL_SPEED + 2
    e.score.score = 10_000_000
    assert e.speed == cfg.MAX_SPEED


def test_update_uses_fixed_timestep_and_clamps_lag():
    e = engine()
    start = e.snake.head
    for _ in range(8):  # 8 frames of 1/60 s = 0.133 s > one 0.125 s step
        e.update(1 / 60)
    assert e.snake.head[0] == start[0] + 1
    before = e.snake.head
    e.update(5.0)  # giant hitch must not teleport the snake
    assert abs(e.snake.head[0] - before[0]) <= cfg.MAX_STEPS_PER_FRAME


def test_dead_engine_does_not_update():
    e = engine()
    e.alive = False
    assert e.update(1.0) == []


def test_reset_is_clean():
    e = engine()
    e.score.add(50)
    e.alive = False
    e.reset()
    assert e.alive and e.score.score == 0 and e.length == cfg.INITIAL_SNAKE_LENGTH
