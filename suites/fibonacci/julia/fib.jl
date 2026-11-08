@inline add(::Val{false}, a, b) = a + b
@inline add(::Val{true}, a, b) = Base.Checked.checked_add(a, b)
@inline sub(::Val{false}, a, b) = a - b
@inline sub(::Val{true}, a, b) = Base.Checked.checked_sub(a, b)

fib_rec(c, n::Int64) = n <= 1 ? n : add(c, fib_rec(c, sub(c, n, Int64(1))), fib_rec(c, sub(c, n, Int64(2))))

function fib_iter(c, n::Int64)
    a = Int64(0)
    b = Int64(1)
    i = Int64(0)
    while i < n
        t = a
        a = b
        b = add(c, t, b)
        i = add(c, i, Int64(1))
    end
    return a
end

function execute(c, mode::String, n::Int64)
    if mode == "recursive"
        println(fib_rec(c, n))
    else
        total = Int64(0)
        k = Int64(0)
        while k < n
            total = add(c, total, fib_iter(c, add(c, Int64(30), k % Int64(10))))
            k = add(c, k, Int64(1))
        end
        println(total)
    end
end

function main()
    checked = "--checked" in ARGS
    mode = ARGS[end]
    n = parse(Int64, strip(read("input.txt", String)))
    execute(Val(checked), mode, n)
end

main()