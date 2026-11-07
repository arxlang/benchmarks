fn fib_range(n: i64) -> i64:
  var a: i64 = 0
  var b: i64 = 1
  for i in range(0, cast(n, i32)):
    var temp: i64 = a
    a = b
    b = temp + b
  return a

fn main() -> i32:
  var total: i64 = 0
  var k: i64 = 0
  while k < 1000000:
    total = total + fib_range(30 + (k - (k / 10) * 10))
    k = k + 1
  print(total)
  return 0