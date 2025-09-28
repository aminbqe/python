import turtle
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
turtle.done()
