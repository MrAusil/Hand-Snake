from game.snake import Direction, Snake


def make():
    return Snake((10, 10), length=3, direction=Direction.RIGHT)


def test_initial_position():
    s = make()
    assert list(s.body) == [(10, 10), (9, 10), (8, 10)]
    assert s.head == (10, 10)
    assert s.direction is Direction.RIGHT


def test_movement_keeps_length_and_head_first():
    s = make()
    s.move()
    assert list(s.body) == [(11, 10), (10, 10), (9, 10)]
    assert s.head == (11, 10)


def test_growth_adds_one_cell():
    s = make()
    s.grow()
    s.move()
    assert s.length == 4
    s.move()
    assert s.length == 4


def test_reverse_is_rejected():
    s = make()
    assert s.set_direction(Direction.LEFT) is False
    s.move()
    assert s.direction is Direction.RIGHT


def test_reverse_of_queued_turn_is_rejected():
    s = make()
    assert s.set_direction(Direction.UP) is True
    assert s.set_direction(Direction.DOWN) is False  # would be a 180 after UP


def test_two_quick_turns_are_both_applied():
    s = make()
    assert s.set_direction(Direction.UP)
    assert s.set_direction(Direction.LEFT)
    s.move()
    assert s.direction is Direction.UP
    s.move()
    assert s.direction is Direction.LEFT


def test_same_direction_and_none_ignored():
    s = make()
    assert s.set_direction(Direction.RIGHT) is False
    assert s.set_direction(None) is False


def test_all_four_opposites():
    for d in Direction:
        s = Snake((10, 10), direction=d)
        assert s.set_direction(d.opposite()) is False


def test_self_collision_detected():
    s = Snake((10, 10), length=5, direction=Direction.RIGHT)
    s.set_direction(Direction.DOWN)
    s.move()
    s.set_direction(Direction.LEFT)
    s.move()
    s.set_direction(Direction.UP)
    s.move()  # head runs into its own body
    assert s.check_self_collision() is True


def test_no_collision_when_chasing_tail():
    s = Snake((10, 10), length=4, direction=Direction.RIGHT)
    s.set_direction(Direction.DOWN)
    s.move()
    s.set_direction(Direction.LEFT)
    s.move()
    s.set_direction(Direction.UP)
    s.move()  # enters the cell the tail just left
    assert s.check_self_collision() is False


def test_reset_restores_start():
    s = make()
    s.grow(2)
    s.move()
    s.move()
    s.reset()
    assert list(s.body) == [(10, 10), (9, 10), (8, 10)]
