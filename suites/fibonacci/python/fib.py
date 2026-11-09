import sys


def fib_recursive(n):
    return n if n <= 1 else fib_recursive(n - 1) + fib_recursive(n - 2)


def fib_iter(n):
    a, b = 0, 1
    for _ in range(n):
        a, b = b, a + b
    return a


def iterative(n):
    total = 0
    for k in range(n):
        total += fib_iter(30 + k % 10)
    return total


mode = sys.argv[1]
with open("input.txt") as f:
    n = int(f.read())
print(fib_recursive(n) if mode == "recursive" else iterative(n))