```
title: Recursive Fibonacci
summary: Reads n from input.txt and prints the n-th Fibonacci number using naive double recursion.
```

fn fib_recursive(n: i64) -> i64:
  ```
  title: fib_recursive
  summary: Returns the n-th Fibonacci number by naive double recursion.
  ```
  if n <= 1:
    return n
  return fib_recursive(n - 1) + fib_recursive(n - 2)

fn main() -> i32:
  ```
  title: main
  summary: Reads n from input.txt, prints fib(n) and returns success.
  ```
  f: File = open("input.txt")
  text: str = f.read()
  f.close()
  n: i64 = int(text)
  print(fib_recursive(n))
  return 0