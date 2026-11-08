use std::env;
use std::fs;

fn fib_rec(n: i64) -> i64 {
    if n <= 1 {
        n
    } else {
        fib_rec(n - 1) + fib_rec(n - 2)
    }
}

fn fib_iter(n: i64) -> i64 {
    let (mut a, mut b) = (0i64, 1i64);
    let mut i = 0i64;
    while i < n {
        let t = a;
        a = b;
        b = t + b;
        i += 1;
    }
    a
}

fn main() {
    let mode = env::args().nth(1).expect("usage: fib recursive|iterative");
    let n: i64 = fs::read_to_string("input.txt")
        .expect("cannot read input.txt")
        .trim()
        .parse()
        .expect("input.txt must hold an integer");
    if mode == "recursive" {
        println!("{}", fib_rec(n));
        return;
    }
    let mut total = 0i64;
    let mut k = 0i64;
    while k < n {
        total += fib_iter(30 + k % 10);
        k += 1;
    }
    println!("{}", total);
}