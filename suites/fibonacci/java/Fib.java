import java.nio.file.Files;
import java.nio.file.Path;

public class Fib {
    private static final boolean CHECKED = Boolean.getBoolean("checked");

    private static long add(long a, long b) {
        return CHECKED ? Math.addExact(a, b) : a + b;
    }

    private static long sub(long a, long b) {
        return CHECKED ? Math.subtractExact(a, b) : a - b;
    }

    private static long fibRec(long n) {
        return n <= 1 ? n : add(fibRec(sub(n, 1)), fibRec(sub(n, 2)));
    }

    private static long fibIter(long n) {
        long a = 0, b = 1;
        for (long i = 0; i < n; i = add(i, 1)) {
            long t = a;
            a = b;
            b = add(t, b);
        }
        return a;
    }

    public static void main(String[] args) throws Exception {
        if (args.length != 1) {
            System.err.println("usage: Fib recursive|iterative (reads n from input.txt)");
            System.exit(2);
        }
        long n = Long.parseLong(Files.readString(Path.of("input.txt")).trim());
        if (args[0].equals("recursive")) {
            System.out.println(fibRec(n));
            return;
        }
        long total = 0;
        for (long k = 0; k < n; k = add(k, 1)) {
            total = add(total, fibIter(add(30, k % 10)));
        }
        System.out.println(total);
    }
}