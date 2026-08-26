import turtle
import random
import equalizer
import time
import os
import math
import numpy as np
a = int(input("enter a: "))
#a = 10
t = turtle.Turtle()
screen = turtle.Screen()
screen.tracer(0)
screen.setup(810,810)
#in order to set the speed
out_dir = "frames"
os.makedirs(out_dir, exist_ok=True)
frame_count = 200           # total frames
fps = 24
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
e = equalizer.equalizer(a)
op1 = turtle.Turtle()
op1.speed(0)
for i in range (a):
    for j in range(a):
            x = random.randint(0,100)
            g = float("{:.4f}".format(x))
            m = e.matrixcopy(g,j+1,i+1)
            op1.penup()
            op1.setposition(i*(sz/a)+((sz/a)/2+xax),j*(-(sz/a))-((sz/a)/2)+yax)
            op1.pendown()
            op1.penup()
            op1.right(180)
            op1.forward(x*0.395)
            op1.left(90)
            op1.begin_fill()
            op1.pendown()
            op1.begin_fill()
            op1.fillcolor(1, 1 - g / 100, 1 - g / 100)
            op1.circle(x * 0.395)
            op1.end_fill()
            op1.penup()
            op1.left(90)
            op1.forward(x*0.395)
            op1.write(x, align="center", font=("Arial", 10, "bold"))
            op1.setposition(xax,yax)
#time.sleep(4)
def save_frame(n):
    # turtle's Canvas can be grabbed via the tkinter canvas postscript
    canvas = screen.getcanvas()
    ps = canvas.postscript(colormode='color')
    img = Image.open(io.BytesIO(ps.encode('utf-8')))
    # Convert from EPS to RGBA and resize/crop if needed
    img = img.convert('RGB').resize((810, 810))
    fname = os.path.join(out_dir, f"frame_{n:04d}.png")
    img.save(fname)
    return fname
import io
for z in range(200):
    screen.tracer(0)
    time.sleep(0.05)
    op1.clear()
    n = e.comparator()
    s = np.transpose(n)
    for i in range (1,a+1):
        for j in range(1,a+1):
            x = s[i][j]
            if x > 100:
                x = 100
            g = float("{:.4f}".format(x))
            l=e.matrixcopy(g,j,i)
            op1.penup()
            op1.setposition((i-1) * (sz / a) + ((sz / a) / 2 + xax), (j-1) * (-(sz / a)) - ((sz / a) / 2) + yax)
            op1.pendown()
            op1.penup()
            op1.right(180)
            op1.forward(x * 0.395)
            op1.left(90)
            op1.begin_fill()
            op1.pendown()
            op1.begin_fill()
            op1.fillcolor(1, 1 - g / 100, 1 - g / 100)
            op1.circle(x * 0.395)
            op1.end_fill()
            op1.penup()
            op1.left(90)
            op1.forward(x * 0.395)
            op1.write(g, align="center", font=("Arial", 10, "bold"))
            op1.setposition(xax, yax)
    screen.update()

    for i in range (1,a+1):
        print()
        for j in range(1,a+1):
            print(l[i][j],end=",")
    print()

turtle.done()