import random

from game.food import Food
from game.snake import Snake


def test_spawn_inside_arena():
    f = Food(10, 8, random.Random(1))
    for _ in range(200):
        x, y = f.spawn([])
        assert 0 <= x < 10 and 0 <= y < 8


def test_never_spawns_on_snake():
    snake = Snake((5, 5), length=5)
    f = Food(12, 10, random.Random(2))
    for _ in range(500):
        assert f.spawn(snake.body) not in snake.body


def test_spawns_on_only_free_cell():
    f = Food(3, 3, random.Random(3))
    occupied = [(x, y) for x in range(3) for y in range(3) if (x, y) != (2, 1)]
    assert f.spawn(occupied) == (2, 1)


def test_full_board_returns_none():
    f = Food(2, 2)
    assert f.spawn([(0, 0), (1, 0), (0, 1), (1, 1)]) is None
    assert f.position is None


def test_is_eaten_by():
    f = Food(5, 5)
    f.position = (2, 3)
    assert f.is_eaten_by((2, 3))
    assert not f.is_eaten_by((3, 3))
