import sys

from numba import njit


@njit("int64(int64)", cache=False)
def fib_recursive(n):
    if n <= 1:
        return n
    return fib_recursive(n - 1) + fib_recursive(n - 2)


@njit("int64(int64)", cache=False)
def fib_iter(n):
    a = 0
    b = 1
    i = 0
    while i < n:
        t = a
        a = b
        b = t + b
        i += 1
    return a


@njit("int64(int64)", cache=False)
def iterative(n):
    total = 0
    k = 0
    while k < n:
        total += fib_iter(30 + k % 10)
        k += 1
    return total


mode = sys.argv[1]
with open("input.txt") as f:
    n = int(f.read())
print(fib_recursive(n) if mode == "recursive" else iterative(n))