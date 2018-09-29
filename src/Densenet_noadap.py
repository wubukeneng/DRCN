# -*- coding: utf-8 -*-

import argparse
import os

import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
import network
import loss
import pre_process as prep
import torch.utils.data as util_data
import lr_schedule
from data_list import ImageList
from torch.autograd import Variable

optim_dict = {"SGD": optim.SGD}


def image_classification_predict(loader, model, test_10crop=True, gpu=True):
    start_test = True
    if test_10crop:
        iter_test = [iter(loader['test' + str(i)]) for i in xrange(10)]
        for i in xrange(len(loader['test0'])):
            data = [iter_test[j].next() for j in xrange(10)]
            inputs = [data[j][0] for j in xrange(10)]
            if gpu:
                for j in xrange(10):
                    inputs[j] = Variable(inputs[j].cuda())
            else:
                for j in xrange(10):
                    inputs[j] = Variable(inputs[j])
            outputs = []
            for j in xrange(10):
                outputs.append(model(inputs[j]))
            outputs = sum(outputs)
            if start_test:
                all_output = outputs.data.float()
                start_test = False
            else:
                all_output = torch.cat((all_output, outputs.data.float()), 0)
    else:
        iter_val = iter(loader["test"])
        for i in xrange(len(loader['test'])):
            data = iter_val.next()
            inputs = data[0]
            if gpu:
                inputs = Variable(inputs.cuda())
            else:
                inputs = Variable(inputs)
            outputs = model(inputs)
            if start_test:
                all_output = outputs.data.cpu().float()
                start_test = False
            else:
                all_output = torch.cat((all_output, outputs.data.cpu().float()), 0)
    _, predict = torch.max(all_output, 1)
    return all_output, predict


def image_classification_test(loader, model, test_10crop=True, gpu=True):
    start_test = True
    if test_10crop:
        iter_test = [iter(loader['test' + str(i)]) for i in xrange(10)]
        for i in xrange(len(loader['test0'])):
            data = [iter_test[j].next() for j in xrange(10)]
            inputs = [data[j][0] for j in xrange(10)]
            labels = data[0][1]
            if gpu:
                for j in xrange(10):
                    inputs[j] = Variable(inputs[j].cuda())
                labels = Variable(labels.cuda())
            else:
                for j in xrange(10):
                    inputs[j] = Variable(inputs[j])
                labels = Variable(labels)
            outputs = []
            for j in xrange(10):
                outputs.append(model(inputs[j]))
            outputs = sum(outputs)
            if start_test:
                all_output = outputs.data.float()
                all_label = labels.data.float()
                start_test = False
            else:
                all_output = torch.cat((all_output, outputs.data.float()), 0)
                all_label = torch.cat((all_label, labels.data.float()), 0)
    else:
        iter_test = iter(loader["test"])
        data = iter_test.next()
        inputs = data[0]
        labels = data[1]
        if gpu:
            inputs = Variable(inputs.cuda())
            labels = Variable(labels.cuda())
        else:
            inputs = Variable(inputs)
            labels = Variable(labels)
        outputs = model(inputs)
        if start_test:
            all_output = outputs.data.float()
            all_label = labels.data.float()
            start_test = False
        else:
            all_output = torch.cat((all_output, outputs.data.float()), 0)
            all_label = torch.cat((all_label, labels.data.float()), 0)

    _, predict = torch.max(all_output, 1)
    accuracy = torch.sum(torch.squeeze(predict).float() == all_label) / float(all_label.size()[0])
    return accuracy


def transfer_classification(config,name):
    ## set pre-process
    prep_dict = {}
    for prep_config in config["prep"]:
        prep_dict[prep_config["name"]] = {}
        if prep_config["type"] == "image":
            prep_dict[prep_config["name"]]["test_10crop"] = prep_config["test_10crop"]
            prep_dict[prep_config["name"]]["train"] = prep.image_train(resize_size=prep_config["resize_size"],
                                                                       crop_size=prep_config["crop_size"])
            if prep_config["test_10crop"]:
                prep_dict[prep_config["name"]]["test"] = prep.image_test_10crop(resize_size=prep_config["resize_size"],
                                                                                crop_size=prep_config["crop_size"])
            else:
                prep_dict[prep_config["name"]]["test"] = prep.image_test(resize_size=prep_config["resize_size"],
                                                                         crop_size=prep_config["crop_size"])

    ## set loss
    class_criterion = nn.CrossEntropyLoss()
    loss_config = config["loss"]
    transfer_criterion = loss.loss_dict[loss_config["name"]]
    if "params" not in loss_config:
        loss_config["params"] = {}

    ## prepare data
    dsets = {}
    dset_loaders = {}
    for data_config in config["data"]:
        dsets[data_config["name"]] = {}
        dset_loaders[data_config["name"]] = {}
        ## image data
        if data_config["type"] == "image":
            # dsets[data_config["name"]]["train"]为ImageList类，其中含有source中数据及标签和预处理过程
            dsets[data_config["name"]]["train"] = ImageList(open(data_config["list_path"]["train"]).readlines(),
                                                            transform=prep_dict[data_config["name"]]["train"])
            # dset_loaders含有数据batchsize信息等
            dset_loaders[data_config["name"]]["train"] = util_data.DataLoader(dsets[data_config["name"]]["train"],
                                                                              batch_size=data_config["batch_size"][
                                                                                  "train"], shuffle=True, num_workers=4)
            if "test" in data_config["list_path"]:
                if prep_dict[data_config["name"]]["test_10crop"]:
                    for i in range(10):
                        dsets[data_config["name"]]["test" + str(i)] = ImageList(
                            open(data_config["list_path"]["test"]).readlines(),
                            transform=prep_dict[data_config["name"]]["test"]["val" + str(i)]
                            )
                        dset_loaders[data_config["name"]]["test" + str(i)] = util_data.DataLoader(
                            dsets[data_config["name"]]["test" + str(i)], batch_size=data_config["batch_size"]["test"],
                            shuffle=False, num_workers=4)
                else:
                    dsets[data_config["name"]]["test"] = ImageList(open(data_config["list_path"]["test"]).readlines(),
                                                                   transform=prep_dict[data_config["name"]]["test"])
                    dset_loaders[data_config["name"]]["test"] = util_data.DataLoader(dsets[data_config["name"]]["test"],
                                                                                     batch_size=
                                                                                     data_config["batch_size"]["test"],
                                                                                     shuffle=False, num_workers=4)
            else:
                if prep_dict[data_config["name"]]["test_10crop"]:
                    for i in range(10):
                        dsets[data_config["name"]]["test" + str(i)] = ImageList(
                            open(data_config["list_path"]["train"]).readlines(),
                            transform=prep_dict[data_config["name"]]["test"]["val" + str(i)])
                        dset_loaders[data_config["name"]]["test" + str(i)] = util_data.DataLoader(
                            dsets[data_config["name"]]["test" + str(i)], batch_size=data_config["batch_size"]["test"],
                            shuffle=False, num_workers=4)
                else:
                    dsets[data_config["name"]]["test"] = ImageList(open(data_config["list_path"]["train"]).readlines(),
                                                                   transform=prep_dict[data_config["name"]]["test"])
                    dset_loaders[data_config["name"]]["test"] = util_data.DataLoader(dsets[data_config["name"]]["test"],
                                                                                     batch_size=
                                                                                     data_config["batch_size"]["test"],
                                                                                     shuffle=False, num_workers=4)
    class_num = 12

    ## set base network
    net_config = config["network"]
    base_network = network.network_dict[net_config["name"]]()
    if net_config["use_bottleneck"]:
        # 在最后一层前加入2048->256的隐藏层
        bottleneck_layer = nn.Linear(base_network.output_num(), net_config["bottleneck_dim"])
        classifier_layer = nn.Linear(bottleneck_layer.out_features, class_num)
    else:
        print 'outputnum:',base_network.output_num()
        classifier_layer = nn.Linear(base_network.output_num(), class_num)

    ## initialization
    if net_config["use_bottleneck"]:
        # 初始化bottlenect层weight
        bottleneck_layer.weight.data.normal_(0, 0.005)
        bottleneck_layer.bias.data.fill_(0.1)
        # nn.sequential按次序封装层
        bottleneck_layer = nn.Sequential(bottleneck_layer, nn.ReLU(), nn.Dropout(0.5))
    classifier_layer.weight.data.normal_(0, 0.01)
    classifier_layer.bias.data.fill_(0.0)

    use_gpu = torch.cuda.is_available()
    if use_gpu:
        if net_config["use_bottleneck"]:
            bottleneck_layer = bottleneck_layer.cuda()
        classifier_layer = classifier_layer.cuda()
        base_network = base_network.cuda()

    ## collect parameters
    if net_config["use_bottleneck"]:
        parameter_list = [{"params": base_network.parameters(), "lr": 1},
                          {"params": bottleneck_layer.parameters(), "lr": 10},
                          {"params": classifier_layer.parameters(), "lr": 10}]

    else:
        parameter_list = [{"params": base_network.parameters(), "lr": 1},
                          {"params": classifier_layer.parameters(), "lr": 10}]

    ## add additional network for some methods
    if loss_config["name"] == "JAN":
        softmax_layer = nn.Softmax()
        if use_gpu:
            softmax_layer = softmax_layer.cuda()

    ## set optimizer
    optimizer_config = config["optimizer"]
    # optimizer初始化了所有权重
    optimizer = optim_dict[optimizer_config["type"]](parameter_list, **(optimizer_config["optim_params"]))
    param_lr = []
    for param_group in optimizer.param_groups:
        param_lr.append(param_group["lr"])
    schedule_param = optimizer_config["lr_param"]
    lr_scheduler = lr_schedule.schedule_dict[optimizer_config["lr_type"]]

    ## train
    len_train_source = len(dset_loaders["source"]["train"]) - 1
    len_train_target = len(dset_loaders["target"]["train"]) - 1
    transfer_loss_value = classifier_loss_value = total_loss_value = 0.0
    max_accuracy = 0
    import codecs
    f = codecs.open('../result/' +'noada', 'w', 'utf-8')
    for i in range(config["num_iterations"]+1):
        ## test in the train
        if i % 100 == 0:
            print '第',i,'次'
        if i % config["test_interval"] == 0 and i!=0:
        # if i ==config["test_interval"]-1:

            base_network.train(False)
            classifier_layer.train(False)

            if net_config["use_bottleneck"]:
                bottleneck_layer.train(False)

                accuracy=image_classification_test(dset_loaders["target"],
                                          nn.Sequential(base_network, bottleneck_layer, classifier_layer),
                                          test_10crop=prep_dict["target"]["test_10crop"], gpu=use_gpu)

                torch.save(base_network, '../save/nobottle_base_network_' + name + '.pkl')
                torch.save(classifier_layer, '../save/nobottle_classifier_layer_' + name + '.pkl')
                print 'save',i
                if(accuracy>max_accuracy):
                    max_accuracy=accuracy

                    # torch.save(bottleneck_layer, '../../save/bottleneck_layer_'+name+'.pkl')
                print '第{0}次accuracy:'.format(i),accuracy,'max_accuracy:',max_accuracy



            else:

                torch.save(base_network, '../save/nobottle_base_network_' + name + '.pkl')
                torch.save(classifier_layer, '../save/nobottle_classifier_layer_' + name + '.pkl')
                print 'save', i
                accuracy = image_classification_test(dset_loaders["target"],
                                                     nn.Sequential(base_network, classifier_layer),
                                                     test_10crop=prep_dict["target"]["test_10crop"], gpu=use_gpu)
                if (accuracy > max_accuracy):
                    max_accuracy = accuracy


                    # torch.save(bottleneck_layer, '../../save/bottleneck_layer_'+name+'.pkl')
                print '第{0}次accuracy:'.format(i), accuracy, 'max_accuracy:', max_accuracy
                f.write(str(i) + ':' + str(accuracy) + '\n')



                # print image_classification_test(dset_loaders["target"], nn.Sequential(base_network, classifier_layer),
                #                                 test_10crop=prep_dict["target"]["test_10crop"], gpu=use_gpu)

        loss_test = nn.BCELoss()
        ## train one iter
        base_network.train(True)
        if net_config["use_bottleneck"]:
            bottleneck_layer.train(True)
        classifier_layer.train(True)
        optimizer = lr_scheduler(param_lr, optimizer, i, **schedule_param)
        optimizer.zero_grad()
        if i % len_train_source == 0:
            iter_source = iter(dset_loaders["source"]["train"])
        if i % len_train_target == 0:
            iter_target = iter(dset_loaders["target"]["train"])
        inputs_source, labels_source = iter_source.next()
        inputs_target, labels_target = iter_target.next()
        if use_gpu:
            inputs_source, inputs_target, labels_source = Variable(inputs_source).cuda(), Variable(
                inputs_target).cuda(), Variable(labels_source).cuda()
        else:
            inputs_source, inputs_target, labels_source = Variable(inputs_source), Variable(inputs_target), Variable(
                labels_source)

        inputs = torch.cat((inputs_source, inputs_target), dim=0)
        features = base_network(inputs)
        if net_config["use_bottleneck"]:
            features = bottleneck_layer(features)

        outputs = classifier_layer(features)

        classifier_loss = class_criterion(outputs.narrow(0, 0, inputs.size(0) / 2), labels_source)
        ## switch between different transfer loss


        total_loss =classifier_loss
        total_loss.backward()
        optimizer.step()


if __name__ == "__main__":
    print 'hello'
    # parser = argparse.ArgumentParser(description='Transfer Learning')
    # parser.add_argument('gpu_id', type=str, nargs='?', default='0', help="device id to run")
    # args = parser.parse_args()
    os.environ["CUDA_VISIBLE_DEVICES"] = '1'

    config = {}
    config["num_iterations"] = 300
    config["test_interval"] = 300
    config["prep"] = [{"name": "source", "type": "image", "test_10crop": True, "resize_size": 256, "crop_size": 224},
                      {"name": "target", "type": "image", "test_10crop": True, "resize_size": 256, "crop_size": 224}]
    config["loss"] = {"name": "DAN", "trade_off": 1.0}
    config["data"] = [{"name": "source", "type": "image", "list_path": {"train": "../data/office/real12_list.txt"},
                       "batch_size": {"train": 36, "test": 4}},
                      {"name": "target", "type": "image", "list_path": {"train": "../data/office/synthetic6_list.txt"},
                       "batch_size": {"train": 36, "test": 4}}]
    config["network"] = {"name": "ResNet50", "use_bottleneck": False, "bottleneck_dim": 256}
    config["optimizer"] = {"type": "SGD",
                           "optim_params": {"lr": 1.0, "momentum": 0.9, "weight_decay": 0.0005, "nesterov": True},
                           "lr_type": "inv", "lr_param": {"init_lr": 0.0003, "gamma": 0.0003, "power": 0.75}}
    print config["loss"]
    transfer_classification(config, 'res50_real_300')








