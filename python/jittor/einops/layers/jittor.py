from typing import Optional, Dict

import jittor as jt
from jittor import nn
import numpy as np

from jittor.einops.layers import RearrangeMixin, ReduceMixin
from jittor.einops.layers._einmix import _EinmixMixin

__author__ = 'Ruiyang Liu'


class Rearrange(RearrangeMixin, jt.nn.Module):
    def execute(self, input):
        return self._apply_recipe(input)

    
class Reduce(ReduceMixin, jt.nn.Module):
    def execute(self, input):
        return self._apply_recipe(input)


class EinMix(_EinmixMixin, jt.nn.Module):
    def _create_parameters(self, weight_shape, weight_bound, bias_shape, bias_bound):
        self.weight = jt.zeros(weight_shape)
        nn.init.uniform_(self.weight, low = -weight_bound, high = weight_bound)
        if bias_shape is not None:
            self.bias = jt.zeros(bias_shape)
            nn.init.uniform_(self.bias, low = -bias_bound, high = bias_bound)
        else:
            self.bias = None

    def _create_rearrange_layers(self,
                                 pre_reshape_pattern: Optional[str],
                                 pre_reshape_lengths: Optional[Dict],
                                 post_reshape_pattern: Optional[str],
                                 post_reshape_lengths: Optional[Dict],
                                 ):
        self.pre_rearrange = None
        if pre_reshape_pattern is not None:
            self.pre_rearrange = Rearrange(pre_reshape_pattern, **pre_reshape_lengths)

        self.post_rearrange = None
        if post_reshape_pattern is not None:
            self.post_rearrange = Rearrange(post_reshape_pattern, **post_reshape_lengths)

    def execute(self, input):
        if self.pre_rearrange is not None:
            input = self.pre_rearrange(input)
        result = jt.linalg.einsum(self.einsum_pattern, input, self.weight)
        if self.bias is not None:
            result += self.bias
        if self.post_rearrange is not None:
            result = self.post_rearrange(result)
        return result
