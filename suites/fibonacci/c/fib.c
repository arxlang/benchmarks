#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#ifdef CHECKED
__attribute__((noinline, cold, noreturn)) static void overflow_fail(void) {
    fprintf(stderr, "integer overflow\n");
    exit(1);
}
static inline __attribute__((always_inline)) long long chk_add(long long a, long long b) {
    long long r;
    if (__builtin_add_overflow(a, b, &r)) overflow_fail();
    return r;
}
static inline __attribute__((always_inline)) long long chk_sub(long long a, long long b) {
    long long r;
    if (__builtin_sub_overflow(a, b, &r)) overflow_fail();
    return r;
}
#define ADD(a, b) chk_add((a), (b))
#define SUB(a, b) chk_sub((a), (b))
#else
#define ADD(a, b) ((a) + (b))
#define SUB(a, b) ((a) - (b))
#endif

static long long fib_rec(long long n) {
    return n <= 1 ? n : ADD(fib_rec(SUB(n, 1)), fib_rec(SUB(n, 2)));
}

static long long fib_iter(long long n) {
    long long a = 0, b = 1;
    for (long long i = 0; i < n; i = ADD(i, 1)) {
        long long t = a;
        a = b;
        b = ADD(t, b);
    }
    return a;
}

static long long read_n(void) {
    FILE *f = fopen("input.txt", "r");
    long long n;
    if (!f || fscanf(f, "%lld", &n) != 1) {
        fprintf(stderr, "cannot read n from input.txt\n");
        exit(2);
    }
    fclose(f);
    return n;
}

int main(int argc, char **argv) {
    if (argc != 2) {
        fprintf(stderr, "usage: fib recursive|iterative (reads n from input.txt)\n");
        return 2;
    }
    long long n = read_n();
    if (strcmp(argv[1], "recursive") == 0) {
        printf("%lld\n", fib_rec(n));
        return 0;
    }
    long long total = 0;
    for (long long k = 0; k < n; k = ADD(k, 1)) total = ADD(total, fib_iter(ADD(30, k % 10)));
    printf("%lld\n", total);
    return 0;
}