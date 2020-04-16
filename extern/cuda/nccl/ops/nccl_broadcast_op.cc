// ***************************************************************
// Copyright (c) 2020 
//     Guoye Yang <498731903@qq.com>. 
//     Dun Liang <randonlang@gmail.com>. 
// All Rights Reserved.
// This file is subject to the terms and conditions defined in
// file 'LICENSE.txt', which is part of this source code package.
// ***************************************************************
#include "var.h"
#include "nccl_broadcast_op.h"
#include "misc/str_utils.h"

#include <nccl.h>
#include <cuda_runtime.h>
#include <helper_cuda.h>
#include "nccl_warper.h"
namespace jittor {

#ifndef JIT
NcclBroadcastOp::NcclBroadcastOp(Var* x, int root) : x(x), root(root) {
    flags.set(NodeFlags::_cpu, 0);
    flags.set(NodeFlags::_cuda, 1);
    y = create_output(nullptr, x->dtype());
}

void NcclBroadcastOp::infer_shape() {
    y->set_shape(x->shape);
}

void NcclBroadcastOp::jit_prepare() {
    add_jit_define("Tx", x->dtype());
    add_jit_define("XDIM", JK::hex1(x->shape.size()));
}

#else // JIT
#ifdef JIT_cuda

void NcclBroadcastOp::jit_run() {
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
    checkCudaErrors(ncclBroadcast(xp, yp, size, @T_NCCL, root, comm, 0));
}

#endif
#endif // JIT

} // jittor
