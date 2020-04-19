# ***************************************************************
# Copyright (c) 2020 Jittor. Authors: 
#     Wenyang Zhou <576825820@qq.com>
#     Dun Liang <randonlang@gmail.com>. 
# All Rights Reserved.
# This file is subject to the terms and conditions defined in
# file 'LICENSE.txt', which is part of this source code package.
# ***************************************************************
import unittest
import jittor as jt
import numpy as np
import jittor.models as jtmodels

try:
    jt.dirty_fix_pytorch_runtime_error()
    import torch
    import torchvision.models as tcmodels
    from torch import nn
except:
    torch = None
    

skip_this_test = False


@unittest.skipIf(skip_this_test, "skip_this_test")
class test_models(unittest.TestCase):
    @classmethod
    def setUpClass(self):
        self.models = [
            ['inception_v3','inception_v3'],
            ['squeezenet1_0','squeezenet1_0'],
            ['squeezenet1_1','squeezenet1_1'],
            ['alexnet','alexnet'],
            ['resnet18','Resnet18'],
            ['resnet34','Resnet34'],
            ['resnet50','Resnet50'],
            ['resnet101','Resnet101'],
            ['resnet152','Resnet152'],
            ['resnext50_32x4d','Resnext50_32x4d'],
            ['resnext101_32x8d','Resnext101_32x8d'],
            ['vgg11','VGG11'],
            ['vgg11_bn','VGG11_bn'],
            ['vgg13','VGG13'],
            ['vgg13_bn','VGG13_bn'],
            ['vgg16','VGG16'],
            ['vgg16_bn','VGG16_bn'],
            ['vgg19','VGG19'],
            ['vgg19_bn','VGG19_bn'],
            ['wide_resnet50_2','Wide_resnet50_2'],
            ['wide_resnet101_2','Wide_resnet101_2'],
            ['googlenet','googlenet'],
            ['mobilenet_v2','mobilenet_v2'],
            ['mnasnet0_5','mnasnet0_5'],
            ['mnasnet0_75','mnasnet0_75'],
            ['mnasnet1_0','mnasnet1_0'],
            ['mnasnet1_3','mnasnet1_3'],
            ['shufflenet_v2_x0_5','shufflenet_v2_x0_5'],
            ['shufflenet_v2_x1_0','shufflenet_v2_x1_0'],
            ['shufflenet_v2_x1_5','shufflenet_v2_x1_5'],
            ['shufflenet_v2_x2_0','shufflenet_v2_x2_0']
        ]

    @unittest.skipIf(not jt.has_cuda, "Cuda not found")
    @jt.flag_scope(use_cuda=1, use_stat_allocator=1)
    def test_models(self):
        threshold = 1e-2
        # Define numpy input image
        bs = 1
        test_img = np.random.random((bs,3,224,224)).astype('float32')
        # Define pytorch & jittor input image
        pytorch_test_img = torch.Tensor(test_img).cuda()
        jittor_test_img = jt.array(test_img)
        for test_model in self.models:
            if test_model[0] == "inception_v3":
                test_img = np.random.random((bs,3,300,300)).astype('float32')
                pytorch_test_img = torch.Tensor(test_img).cuda()
                jittor_test_img = jt.array(test_img)
            # Define pytorch & jittor model
            pytorch_model = tcmodels.__dict__[test_model[0]]().cuda()
            if 'resne' in test_model[0]:
                jittor_model = jtmodels.resnet.__dict__[test_model[1]]()
            elif 'vgg' in test_model[0]:
                jittor_model = jtmodels.vgg.__dict__[test_model[1]]()
            elif 'alexnet' in test_model[0]:
                jittor_model = jtmodels.alexnet.__dict__[test_model[1]]()
            elif 'squeezenet' in test_model[0]:
                jittor_model = jtmodels.squeezenet.__dict__[test_model[1]]()
            elif 'inception' in test_model[0]:
                jittor_model = jtmodels.inception.__dict__[test_model[1]]()
            elif 'googlenet' in test_model[0]:
                jittor_model = jtmodels.googlenet.__dict__[test_model[1]]()
            elif 'mobilenet' in test_model[0]:
                jittor_model = jtmodels.mobilenet.__dict__[test_model[1]]()
            elif 'mnasnet' in test_model[0]:
                jittor_model = jtmodels.mnasnet.__dict__[test_model[1]]()
            elif 'shufflenet' in test_model[0]:
                jittor_model = jtmodels.shufflenetv2.__dict__[test_model[1]]()
            # Set eval to avoid dropout layer
            pytorch_model.eval()
            jittor_model.eval()
            # Jittor loads pytorch parameters to ensure forward alignment
            jittor_model.load_parameters(pytorch_model.state_dict())
            # Judge pytorch & jittor forward relative error. If the differece is lower than threshold, this test passes.
            pytorch_result = pytorch_model(pytorch_test_img)
            jittor_result = jittor_model(jittor_test_img)
            x = pytorch_result.detach().cpu().numpy() + 1
            y = jittor_result.data + 1
            relative_error = abs(x - y) / abs(y)
            diff = relative_error.mean()
            assert diff < threshold, f"[*] {test_model[1]} forward fails..., Relative Error: {diff}"
            print(f"[*] {test_model[1]} forword passes with Relative Error {diff}")
        print('all models pass test.')
        
if __name__ == "__main__":
    unittest.main()
