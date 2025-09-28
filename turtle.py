import turtle
import random
import math
#a = int(input("enter a: "))
a = 10
t = turtle.Turtle()
screen = turtle.Screen()
screen.setup(810,810)
#in order to set the speed
t.speed(0)
t.penup()
sz = 790
xax = -395
yax = 395
t.setposition(xax,yax)
t.pendown()
for i in range(4):
    t.forward(sz)
    t.right(90)
for i in range(1,a):
    t.penup()
    t.setposition(xax,yax)
    t.forward((sz/a)*i)
    t.pendown()
    t.right(90)
    t.forward(sz)
    t.left(90)
for i in range(1,a):
    t.penup()
    t.setposition(xax,yax)
    t.right(90)
    t.forward((sz/a)*i)
    t.pendown()
    t.left(90)
    t.forward(sz)
t.speed(0)
for i in range (a):
    for j in range(a):
        t.penup()
        x = random.randint(0,100)
        t.setposition(i*(sz/a)+((sz/a)/2+xax),j*(-(sz/a))-((sz/a)/2)+yax)
        t.pendown()
        t.write(x,align="center",font=("Arial",10,"bold"))
        t.penup()
        t.left(90)
        t.forward(x*0.395)
        t.setposition(xax,yax)
turtle.done()
