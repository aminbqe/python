import turtle
import random
a = int(input("enter a: "))
t = turtle.Turtle()
#in order to set the speed
#t.speed(0)
for i in range(4):
    t.forward(250)
    t.right(90)
for i in range(1,a):
    t.penup()
    t.home()
    t.forward((250/a)*i)
    t.pendown()
    t.right(90)
    t.forward(250)
for i in range(1,a):
    t.penup()
    t.home()
    t.right(90)
    t.forward((250/a)*i)
    t.pendown()
    t.left(90)
    t.forward(250)
for i in range (a):
    for j in range(a):
        t.penup()
        x = random.randint(0,100)
        t.setpos(i*(250/a)+((250/a)/2),j*(-(250/a))-((250/a)/2 + 4))
        t.write(x,align="center",font=("Arial",10,"bold"))
        t.home()
turtle.done()
