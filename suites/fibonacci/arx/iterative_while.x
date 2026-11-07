```
title: Iterative Fibonacci with while loops
summary: Reads the call count from input.txt and prints the checksum of fib(30 + k % 10) over all calls.
```

fn fib_while(n: i64) -> i64:
  ```
  title: fib_while
  summary: Returns the n-th Fibonacci number using a while loop.
  ```
  var a: i64 = 0
  var b: i64 = 1
  var i: i64 = 0
  while i < n:
    var temp: i64 = a
    a = b
    b = temp + b
    i = i + 1
  return a

fn main() -> i32:
  ```
  title: main
  summary: Reads the call count from input.txt, prints the checksum and returns success.
  ```
  var f: File = open("input.txt")
  var text: str = f.read()
  f.close()
  var count: i64 = int(text)
  var total: i64 = 0
  var k: i64 = 0
  while k < count:
    total = total + fib_while(30 + (k - (k / 10) * 10))
    k = k + 1
  print(total)
  return 0