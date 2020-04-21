// ***************************************************************
// Copyright (c) 2020 
//     Guoye Yang <498731903@qq.com>. 
//     Dun Liang <randonlang@gmail.com>. 
// All Rights Reserved.
// This file is subject to the terms and conditions defined in
// file 'LICENSE.txt', which is part of this source code package.
// ***************************************************************
#include "var.h"
#include "nccl_all_reduce_op.h"
#include "misc/str_utils.h"

#include <nccl.h>
#include <cuda_runtime.h>
#include <helper_cuda.h>
#include "nccl_warper.h"
#include "ops/op_register.h"
namespace jittor {

#ifndef JIT
NcclAllReduceOp::NcclAllReduceOp(Var* x) : x(x) {
    flags.set(NodeFlags::_cpu, 0);
    flags.set(NodeFlags::_cuda, 1);
    y = create_output(nullptr, x->dtype());
}

void NcclAllReduceOp::infer_shape() {
    y->set_shape(x->shape);
}

VarPtr NcclAllReduceOp::grad(Var* out, Var* dout, Var* v, int v_index) {
    static VarPtr(*nccl_all_reduce)(Var*) = 
        get_op_info("nccl_all_reduce").get_constructor<VarPtr, Var*>();
    return nccl_all_reduce(dout);
}

void NcclAllReduceOp::jit_prepare() {
    add_jit_define("Tx", x->dtype());
    add_jit_define("XDIM", JK::hex1(x->shape.size()));
}

#else // JIT
#ifdef JIT_cuda

void NcclAllReduceOp::jit_run() {
    @define(T_NCCL,
        @if(@strcmp(@Tx,float)==0 || @strcmp(@Tx,float32)==0, ncclFloat)
        @if(@strcmp(@Tx,int)==0 || @strcmp(@Tx,int32)==0, ncclInt)
        @if(@strcmp(@Tx,float64)==0, ncclFloat64)
        @if(@strcmp(@Tx,int64)==0, ncclInt64)
    )
    @for(i, 0, XDIM, index_t xshape@i = x->shape[@i];)
    int size = 1 @for(i, 0, XDIM,  * xshape@{i});
    auto* __restrict__ xp = x->ptr<Tx>();
    auto* __restrict__ yp = y->ptr<Tx>();
    checkCudaErrors(ncclAllReduce(xp, yp, size, @T_NCCL, ncclSum, comm, 0));
}

#endif
#endif // JIT

} // jittor
