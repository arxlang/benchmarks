local function fib_rec(n)
  if n <= 1 then return n end
  return fib_rec(n - 1) + fib_rec(n - 2)
end

local function fib_iter(n)
  local a, b = 0, 1
  for _ = 1, n do
    a, b = b, a + b
  end
  return a
end

local mode = arg[1]
local f = assert(io.open("input.txt", "r"))
local n = math.tointeger(tonumber(f:read("a")))
f:close()

if mode == "recursive" then
  print(fib_rec(n))
else
  local total = 0
  for k = 0, n - 1 do
    total = total + fib_iter(30 + k % 10)
  end
  print(total)
end