"""Check activation derivatives and analytical network gradients."""
import numpy as np
from activations import activation,KNOTS
import train_digits
import train_mnist
from train_breast_histology import gradient_check

def main():
    rng=np.random.default_rng(19)
    z=rng.uniform(-.97,.97,100)
    z=z[np.min(abs(z[:,None]**2-KNOTS[None,:]),axis=1)>1e-4]
    for kind in ['custom','matched_linear','relu','identity']:
        _,derivative=activation(z,kind)
        numeric=(activation(z+1e-6,kind)[0]-activation(z-1e-6,kind)[0])/2e-6
        assert np.max(abs(numeric-derivative))<1e-6
    print('Activation derivatives: passed')
    print('Digit gradient error:',train_digits.check_gradients())
    print('MNIST gradient error:',train_mnist.checks())
    x=rng.normal(size=(20,64));x/=np.linalg.norm(x,axis=1,keepdims=True)
    print('Weighted classifier gradient error:',gradient_check(x,np.tile([0,1],10),np.arange(20)))

if __name__=='__main__':main()
