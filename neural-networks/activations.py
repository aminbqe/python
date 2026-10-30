"""Dimensionless custom piecewise-linear activation and software controls."""
import numpy as np

KNOTS = np.array([0.0, 0.2105263157894737, 0.3157894736842105, 0.5064090506176607, 0.5789473684210525, 0.7368421052631581, 1.0], dtype=float)
VALUES = np.array([0.025681236176887043, 0.1628914549971646, 0.2595767602449792, 0.504058539751913, 0.6349980768774987, 0.9339610399022219, 1.0], dtype=float)

def curve():
    return np.column_stack((KNOTS, VALUES))

def activation(z, kind="custom"):
    """Return value and derivative. Custom inputs must satisfy abs(z) <= 1.

    q=z**2; g(q) is linear between the stored normalized knots;
    h(z)=sqrt(g(q)). The derivative uses the selected segment's slope.
    """
    z=np.asarray(z)
    if kind=='relu':return np.maximum(z,0),(z>0).astype(float)
    if kind=='identity':return z,np.ones_like(z)
    if kind not in ('custom','matched_linear'):raise ValueError('Unknown activation '+kind)
    if not np.isfinite(z).all() or np.any(abs(z)>1+1e-10):
        raise ValueError('Custom activation requires finite abs(z) <= 1')
    q=z*z
    if kind=='matched_linear':
        # Affine control with the same endpoint values as the custom curve.
        slope=np.full_like(q,1-VALUES[0],dtype=float)
        f=VALUES[0]+slope*q
    else:
        ix=np.clip(np.searchsorted(KNOTS,q,side='right')-1,0,len(KNOTS)-2)
        slope=(VALUES[ix+1]-VALUES[ix])/(KNOTS[ix+1]-KNOTS[ix])
        f=VALUES[ix]+slope*(q-KNOTS[ix])
    h=np.sqrt(f)
    return h,slope*z/h
