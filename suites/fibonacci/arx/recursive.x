fn fib_recursive(n: i64) -> i64:
  if n <= 1:
    return n
  return fib_recursive(n - 1) + fib_recursive(n - 2)

fn main() -> i32:
  print(fib_recursive(35))
  return 0