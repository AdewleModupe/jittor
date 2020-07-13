// ***************************************************************
// Copyright (c) 2020 Jittor. Authors: Dun Liang <randonlang@gmail.com>. All Rights Reserved.
// This file is subject to the terms and conditions defined in
// file 'LICENSE.txt', which is part of this source code package.
// ***************************************************************
#include "pybind/py_var_tracer.h"
#include "grad.h"
#include "var.h"
#include "op.h"
#include "graph.h"
#include "ops/op_register.h"

namespace jittor {

#define PREVENT_LARGE_FUSED_OP 16

static auto make_binary = get_op_info("binary")
    .get_constructor<VarPtr, Var*, Var*, NanoString>();
static auto make_number = get_op_info("number")
    .get_constructor<VarPtr, float, Var*>();


VarPtr make_grad(Op* op, Var* out, Var* dout, Var* x, int x_index) {
    if (dout == nullptr) return nullptr;
    LOGvvvv << "Make grad op:" >> op->name() << "inputs:" >> op->inputs()
        << "out:" >> out << "dout:" >> dout << "x:" >> x << "xid:" >> x_index;
    auto dx = op->grad(out, dout, x, x_index);
    if (x->loop_options)
        dx->loop_options = x->loop_options;
    return dx;
}

inline static void assign_attrs(Var* a, Var* b) {
    if (b->flags.get(NodeFlags::_stop_fuse))
        a->flags.set(NodeFlags::_stop_fuse);
}

void tape_together(
    const vector<VarHolder*>& taped_inputs,
    const vector<VarHolder*>& taped_outputs,
    GradCallback&& grad_callback
) {
    auto tapes = new Tapes();
    tapes->total = tapes->ref = taped_inputs.size() + taped_outputs.size();
    tapes->callback = move(grad_callback);
    tapes->flags.set(NodeFlags::_grads);
    for (int i=0; i<taped_inputs.size(); i++) {
        auto v = taped_inputs[i]->var;
        auto op = (TapeOp*)v->input();
        ASSERT(op);
        op->flags.set(NodeFlags::_tape);
        tapes->_inputs.emplace_back(op->inputs().front());
        op->tapes = tapes;
    }
    for (int i=0; i<taped_outputs.size(); i++) {
        auto v = taped_outputs[i]->var;
        auto op = (TapeOp*)v->input();
        ASSERT(op);
        op->flags.set(NodeFlags::_tape);
        tapes->_outputs.emplace_back(v,0);
        op->tapes = tapes;
    }
}


template <typename Func>
void bfs_backward_with_tape(vector<Node*>& queue, Func&& func) {
    auto t = ++Node::tflag_count;
    size_t i=0;
    for (Node* node : queue) node->tflag = t;
    while (i < queue.size()) {
        Node* node = queue[i++];
        for (auto i : node->_inputs) {
            auto inode = i.node;
            if (inode->flags.get(NodeFlags::_tape)) {
                Tapes* t = ((TapeOp*)inode)->tapes;
                inode = t;
                ASSERT(t->ref == t->total);
            }
            if (inode->tflag != t && func(inode)) {
                inode->tflag = t;
                queue.push_back(inode);
            }
        }
    }
}

template <typename Func>
void bfs_backward_with_tape(vector<Node*>& seed, vector<Node*>& queue, Func&& func) {
    for (Node* node : seed)
        if (func(node)) queue.push_back(node);
    bfs_backward_with_tape(queue, func);
}

template <typename Func>
void bfs_forward_with_tape(vector<Node*>& queue, Func&& func) {
    auto t = ++Node::tflag_count;
    size_t i=0;
    for (Node* node : queue) node->tflag = t;
    while (i < queue.size()) {
        Node* node = queue[i++];
        for (auto o : node->_outputs) {
            auto onode = o.node;
            if (onode->flags.get(NodeFlags::_tape)) {
                Tapes* t = ((TapeOp*)onode)->tapes;
                ASSERT(t->ref == t->total) << t->ref << t->total;
                onode = t;
            }
            if (onode->tflag != t && func(onode)) {
                onode->tflag = t;
                queue.push_back(onode);
            }
        }
    }
}


template <typename Func>
void toplogical_sort_backward_with_tape(vector<Node*>& nodes, vector<Node*>& sorted, Func&& func) {
    auto t = ++Node::tflag_count;
    sorted.reserve(nodes.size());
    for (auto node : nodes) node->tflag = t;
    for (auto node : nodes) {
        auto& deps = node->custom_data;
        deps = 0;
        for (auto o : node->_outputs) {
            auto onode = o.node;
            if (onode->flags.get(NodeFlags::_tape)) {
                Tapes* t = ((TapeOp*)onode)->tapes;
                onode = t;
            }
            if (onode->tflag == t)
                deps++;
        }
        if (deps == 0) sorted.push_back(node);
    }
    size_t i=0;
    while (i < sorted.size()) {
        Node* node = sorted[i++];
        for (auto i : node->_inputs) {
            auto inode = i.node;
            if (inode->flags.get(NodeFlags::_tape)) {
                Tapes* t = ((TapeOp*)inode)->tapes;
                inode = t;
            }
            if (inode->tflag == t) {
                inode->custom_data--;
                if (inode->custom_data == 0)
                    sorted.push_back(inode);
            }
        }
        func(node);
    }
    ASSERTop(nodes.size(),==,sorted.size());
}

vector<VarPtr> grad(Var* loss, vector<Var*> targets) {
    LOGvv << "loss:" >> loss << "targets:" >> targets;
    CHECK(loss->is_float()) << "Loss should be float";
    for (Var* var : targets)
        CHECK(var->is_float()) << "Targets of grad should be float";
    // successors of targets
    vector<Node*> ts(targets.begin(), targets.end());
    // bfs visit find all successors of targets
    LOGvv << "Size of successors:" << ts.size();
    bfs_forward_with_tape(ts, [](Node*){ return true; });
    vector<Node*> gnodes;
    gnodes.reserve(ts.size());
    auto nt = Node::tflag_count;
    if (loss->tflag == nt)
        gnodes.push_back(loss);
    bfs_backward_with_tape(gnodes, [&](Node* node) {
        if (node->tflag != nt)
            return false;
        if (node->is_stop_grad())
            return false;
        // int value has zero grad
        if (node->is_var())
            return node->var()->is_float();
        return true;
    });
    LOGvv << "Size of grad nodes:" << gnodes.size();
    
    vector<Node*> sorted;
    toplogical_sort_backward_with_tape(gnodes, sorted, [](Node*){});
    nt = Node::tflag_count;
    vector<Var*> gvars;
    gvars.reserve(sorted.size());
    for (Node* node : sorted)
        if (node->is_var()) {
            Var* v = node->var();
            v->custom_data = gvars.size();
            gvars.push_back(v);
        }
    LOGvv << "Size of grad vars:" << gvars.size();
    
    vector<VarPtr> grads(gvars.size());
    vector<VarPtr> results(targets.size());
    vector<int> target_id(targets.size());
    for (int i=0; i<targets.size(); i++) {
        Var* var = targets[i];
        target_id[i] = (var->tflag == nt) ?
            var->custom_data : -1;
    }

    if (grads.size()) {
        grads[0] = make_number(1.f, loss);
        assign_attrs(grads[0].ptr, loss);
        registe_node_trace_grad(grads[0].ptr, loss, 0);
    }

    vector<pair<Node*, int64>> id_buffer;
    id_buffer.reserve(sorted.size()+10);

    // backup id in custum data
    for (int i=1; i<gvars.size(); i++) {
        Var* var = gvars[i];
        for (auto it : var->outputs_with_index()) {
            Op* op = it.op;
            if (op->flags.get(NodeFlags::_tape)) {
                op = ((TapeOp*)op)->tapes;
            }
            auto index = it.index;
            if (op->tflag != nt) continue;
            id_buffer.emplace_back(op, index);
        
            // backward together
            if (op->flags.get(NodeFlags::_grads)) {
                // dont backward next time
                op->tflag = 0;
                for (Var* out : op->outputs()) {
                    id_buffer.emplace_back(
                        out, 
                        out->tflag == nt ? out->custom_data : -1);
                }
                for (Var* in : op->inputs()) {
                    id_buffer.emplace_back(
                        in, 
                        in->tflag == nt ? in->custom_data : -1);
                }
            } else {
                // single var backward
                for (Var* out : op->outputs()) {
                    id_buffer.emplace_back(
                        out, 
                        out->tflag == nt ? out->custom_data : -1);
                }
            }
        }
        // end of var output
        id_buffer.emplace_back(nullptr, 0);
    }
    
    // real backward construction from prev backuped ids
    int j=0;
    for (int i=1; i<gvars.size(); i++,j++) {
        Var* var = gvars[i];
        auto& grad = grads[i];
        #ifdef PREVENT_LARGE_FUSED_OP
        int gsum = 0;
        #endif
        // dump  "for (auto it : var->outputs_with_index())"
        while (id_buffer[j].first) {
            Op* op = id_buffer[j].first->op();
            auto index = id_buffer[j].second;
            j++;
            auto n_o = op->outputs().size();
        
            if (op->flags.get(NodeFlags::_grads)) {
                // backward together
                auto n_i = op->inputs().size();
                Var* douts[n_o];
                VarPtr dins[n_i];
                // dump "for (Var* out : op->outputs())"
                for (int i=0; i<n_o; i++,j++) {
                    auto id = id_buffer[j].second;
                    if (id>=0) {
                        douts[i] = grads[id];
                    } else
                        douts[i] = nullptr;
                }
                op->grads(douts, dins);
                // dump "for (Var* in : op->inputs())"
                for (int i=0; i<n_i; i++,j++) {
                    auto id = id_buffer[j].second;
                    if (id>=0) {
                        auto& din = dins[i];
                        auto& grad = grads[id];
                        if (din && grad) {
                            grad = make_binary(grad, din, ns_add);
                        } else
                            grad = move(din);
                    }
                }
            } else {
                // single var backward
                // dump "for (Var* out : op->outputs())"
                for (int i=0; i<n_o; i++,j++) {
                    auto id = id_buffer[j].second;
                    auto out = id_buffer[j].first->var();
                    if (id<0) continue;
                    Var* dout = grads[id];
                    VarPtr dvar = make_grad(op, out, dout, var, index);
                    registe_node_trace_grad(dvar.ptr, op, index);
                    if (dvar)
                        ASSERT(dvar->num==var->num && dvar->shape.size()==var->shape.size())
                        << "dvar" << dvar << "var" << var;
                    if (!grad)
                        grad = move(dvar);
                    else if (dvar) {
                        grad = make_binary(grad, dvar, ns_add);
                        #ifdef PREVENT_LARGE_FUSED_OP
                        gsum ++;
                        if (gsum>=PREVENT_LARGE_FUSED_OP) {
                            // TODO: this is a dirty fix for
                            // stopping fuse lots of op together,
                            // try to find a better solution
                            grad->flags.set(NodeFlags::_stop_fuse);
                        }
                        #endif
                        assign_attrs(grad.ptr, var);
                        registe_node_trace_grad(grad.ptr, var, index);
                    }
                }
            }
        }
    }
    // set zero grad
    for (size_t i=0; i<results.size(); i++) {
        Var* var = targets[i];
        VarPtr& grad = results[i];
        auto id = target_id[i];
        if (id>=0)
            grad = move(grads[id]);
        if (!grad) {
            LOGw << "grads[">>i>>"] '">> var->name>>"' doesn't have gradient. It will be set to zero:" << var;
            grad = make_number(0.f, var);
            assign_attrs(grad.ptr, var);
            registe_node_trace_grad(grad.ptr, var, 0);
        }
    }
    return results;
}

} // jittor