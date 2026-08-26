class equalizer:
    def __init__(self,n):
        self.n = n
        self.l = [[401] * (n+2) for o in range(n+2)]
        self.k = [[401] * (n+2) for o in range(n+2)]
    def matrixcopy(self,x,i,j):
        self.l[i][j] = x
        self.k[i][j] = x
        return self.l
    def comparator(self):
        for i in range(1, self.n + 1):
            for j in range(1,self.n +1):
                if self.l[i][j] >= self.l[i+1][j]:
                    self.k[i + 1][j] +=(self.l[i][j] / 4)
                    self.k[i][j] -= (self.l[i][j]/4)
                    #print(self.k[i + 1][j])
                    #print(self.l[i][j])
                    #print(i)
                    #print(j)


                if self.l[i][j] >=self.l[i-1][j]:
                    self.k[i][j] -= (self.l[i][j]/4)
                    self.k[i -1][j] += (self.l[i][j]/4)
                    #print(self.k[i -1][j])
                    #print(self.l[i][j])
                    #print(i)
                    #print(j)


                if self.l[i][j] >=self.l[i][j+1]:
                    self.k[i][j] -= (self.l[i][j]/4)
                    self.k[i][j+1] += (self.l[i][j]/4)
                    #print(self.k[i][j+1])
                    #print(self.l[i][j])
                    #print(i)
                    #print(j)


                if self.l[i][j] >=self.l[i][j-1]:
                    self.k[i][j] -= (self.l[i][j]/4)
                    self.k[i][j-1] += (self.l[i][j]/4)
                    #print(self.k[i][j-1])
                    #print(self.l[i][j])
                    #print(i)
                    #print(j)



        return self.k