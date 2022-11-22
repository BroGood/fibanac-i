fib = int(input())

n = 1
a = 0
b = 1

if fib <= 1:
    if fib == 0:
        print(0)
    else:
        print(1)

elif fib > 1:
    while fib != n:
        c = a + b
        a = b
        b = c
        n += 1
    print(c)
