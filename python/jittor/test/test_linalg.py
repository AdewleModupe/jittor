import jittor as jt
import numpy as np
import autograd.numpy as anp
from autograd import jacobian
import unittest

class TestCodeOp(unittest.TestCase):
    def test_svd(self):
        def check_svd(a):
            u,s,v = anp.linalg.svd(a, full_matrices=0)
            return u,s,v

        def check_u(a):
            u,s,v = anp.linalg.svd(a, full_matrices=0)
            return u

        def check_s(a):
            u,s,v = anp.linalg.svd(a, full_matrices=0)
            return s

        def check_v(a):
            u,s,v = anp.linalg.svd(a, full_matrices=0)
            return v

        for i in range(50):
            #not for full-matrices!
            a = jt.random((2,2,5,4))
            c_a = anp.array(a.data)
            u,s,v = jt.linalg.svd(a)
            tu,ts,tv = check_svd(c_a)
            assert np.allclose(tu,u.data)
            assert np.allclose(ts,s.data)
            assert np.allclose(tv,v.data)
            ju = jt.grad(u,a)
            js = jt.grad(s,a)
            jv = jt.grad(v,a)
            grad_u = jacobian(check_u)
            gu = grad_u(c_a)
            gu = np.sum(gu, 4)
            gu = np.sum(gu, 4)
            gu = np.sum(gu, 2)
            gu = np.sum(gu, 2)
            grad_s = jacobian(check_s)
            gs = grad_s(c_a)
            gs = np.sum(gs, 4)
            gs = np.sum(gs, 2)
            gs = np.sum(gs, 2)
            grad_v = jacobian(check_v)
            gv = grad_v(c_a)
            gv = np.sum(gv, 4)
            gv = np.sum(gv, 4)
            gv = np.sum(gv, 2)
            gv = np.sum(gv, 2)
            try:
                assert np.allclose(ju.data,gu,atol=1e-5)
            except AssertionError:
                print(ju.data)
                print(gu)
            try:
                assert np.allclose(js.data,gs,atol=1e-5)
            except AssertionError:
                print(js.data)
                print(gs)
            try:
                assert np.allclose(jv.data,gv,atol=1e-5)
            except AssertionError:
                print(jv.data)
                print(gv)

    def test_eigh(self):
        def check_eigh(a,UPLO='L'):
            w, v = anp.linalg.eigh(a,UPLO)
            return w, v

        def check_w(a,UPLO='L'):
            w, v = anp.linalg.eigh(a,UPLO)
            return w

        def check_v(a,UPLO='L'):
            w, v = anp.linalg.eigh(a,UPLO)
            return v

        for i in range(50):
            a = jt.random((2,2,3,3))
            c_a = a.data
            w, v = jt.linalg.eigh(a)
            tw, tv = check_eigh(c_a)
            assert np.allclose(w.data,tw)
            assert np.allclose(v.data,tv)
            jw = jt.grad(w, a)
            jv = jt.grad(v, a)
            check_gw = jacobian(check_w)
            check_gv = jacobian(check_v)
            gw = check_gw(c_a)
            gw = np.sum(gw,4)
            gw = np.sum(gw,2)
            gw = np.sum(gw,2)
            assert np.allclose(gw,jw.data,rtol = 1,atol = 5e-8)
            gv = check_gv(c_a)
            gv = np.sum(gv,4)
            gv = np.sum(gv,4)
            gv = np.sum(gv,2)
            gv = np.sum(gv,2)
            assert np.allclose(gv,jv.data,rtol = 1,atol = 5e-8)

    def test_pinv(self):
        def check_pinv(a):
            w = anp.linalg.pinv(a)
            return w

        for i in range(50):
            x = jt.random((2,2,4,4))
            c_a = x.data
            mx = jt.linalg.pinv(x)
            tx = check_pinv(c_a)
            np.allclose(mx.data,tx)
            jx = jt.grad(mx,x)
            check_grad = jacobian(check_pinv)
            gx = check_grad(c_a)
            np.allclose(gx,jx.data)

    def test_inv(self):
        def check_inv(a):
            w = anp.linalg.inv(a)
            return w
        for i in range(50):
            tn = np.random.randn(4,4).astype('float32')*5
            while np.allclose(np.linalg.det(tn),0):
                tn = np.random.randn((4,4)).astype('float32')*5
            x = jt.array(tn)
            x = x.reindex([2,2,x.shape[0],x.shape[1]],["i2","i3"])
            c_a = x.data
            mx = jt.linalg.inv(x)
            tx = check_inv(c_a)
            np.allclose(mx.data,tx)
            jx = jt.grad(mx,x)
            check_grad = jacobian(check_inv)
            gx = check_grad(c_a)
            np.allclose(gx,jx.data)

    def test_slogdet(self):
        def check_ans(a):
            s, w = anp.linalg.slogdet(a)
            return s, w

        def check_slogdet(a):
            s, w = anp.linalg.slogdet(a)
            return w

        for i in range(50):
            tn = np.random.randn(4,4).astype('float32')*10
            while np.allclose(np.linalg.det(tn),0):
                tn = np.random.randn((4,4)).astype('float32')*10
            x = jt.array(tn)
            x = x.reindex([2,2,x.shape[0],x.shape[1]],["i2","i3"])
            s = jt.array(x.shape).data.tolist()
            det_s = s[:-2]
            if len(det_s) == 0:
                det_s.append(1)
            sign, mx = jt.linalg.slogdet(x)
            ts, ta = check_ans(x.data)
            assert np.allclose(sign.data, ts)
            assert np.allclose(mx.data, ta)
            jx = jt.grad(mx,x)
            check_sgrad = jacobian(check_slogdet)
            gx = check_sgrad(x.data)
            gx = np.sum(gx,2)
            gx = np.sum(gx,2)
            assert np.allclose(gx,jx.data)

if __name__ == "__main__":
    unittest.main()

