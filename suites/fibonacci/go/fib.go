package main

import (
	"fmt"
	"os"
	"strconv"
	"strings"
)

func fibRec(n int64) int64 {
	if n <= 1 {
		return n
	}
	return fibRec(n-1) + fibRec(n-2)
}

func fibIter(n int64) int64 {
	a, b := int64(0), int64(1)
	for i := int64(0); i < n; i++ {
		a, b = b, a+b
	}
	return a
}

func main() {
	if len(os.Args) != 2 {
		fmt.Fprintln(os.Stderr, "usage: fib recursive|iterative (reads n from input.txt)")
		os.Exit(2)
	}
	data, err := os.ReadFile("input.txt")
	if err != nil {
		fmt.Fprintln(os.Stderr, "cannot read input.txt")
		os.Exit(2)
	}
	n, err := strconv.ParseInt(strings.TrimSpace(string(data)), 10, 64)
	if err != nil {
		fmt.Fprintln(os.Stderr, "input.txt must hold an integer")
		os.Exit(2)
	}
	if os.Args[1] == "recursive" {
		fmt.Println(fibRec(n))
		return
	}
	var total int64
	for k := int64(0); k < n; k++ {
		total += fibIter(30 + k%10)
	}
	fmt.Println(total)
}