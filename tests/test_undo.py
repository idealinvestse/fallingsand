from collections import deque


def test_undo_stack_keeps_latest_five() -> None:
    stack = deque(maxlen=5)
    for i in range(7):
        stack.append(i)

    assert list(stack) == [2, 3, 4, 5, 6]


def test_undo_pop_order() -> None:
    stack = deque(maxlen=5)
    for i in [10, 20, 30]:
        stack.append(i)

    assert stack.pop() == 30
    assert stack.pop() == 20
    assert stack.pop() == 10
