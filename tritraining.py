import argparse
import sklearn.utils
import torch

from dassl.utils import setup_logger, set_random_seed, collect_env_info
from dassl.config import get_cfg_default
from dassl.engine import build_trainer
import copy
import numpy as np
import sklearn
from LAMDA_SSL.Dataset.Vision.CIFAR10 import CIFAR10
from LAMDA_SSL.Evaluation.Classifier.Accuracy import Accuracy

# custom
import datasets.oxford_pets
import datasets.oxford_flowers
import datasets.fgvc_aircraft
import datasets.dtd
import datasets.eurosat
import datasets.stanford_cars
import datasets.food101
import datasets.sun397
import datasets.caltech101
import datasets.ucf101
import datasets.imagenet
import datasets.imagenet_sketch
import datasets.imagenetv2
import datasets.imagenet_a
import datasets.imagenet_r
import datasets.cifar10

import trainers.coop
import trainers.cocoop
import trainers.tri_training
import trainers.zsclip
import trainers.maple
import trainers.vpt
from trainers.tri_training import Tri_Training
import torchvision.transforms as T


def extend_cfg(cfg):
    cfg.TRAINER.MODAL = "classification"
    from yacs.config import CfgNode as CN

    # Config for CoOp
    cfg.TRAINER.COOP = (
        CN()
    )  # 创建一个可用于配置的字典节点，可以看作是一个增强版的 Python 字典，持层次化配置和递归嵌套
    cfg.TRAINER.COOP.N_CTX = 16  # number of context vectors
    cfg.TRAINER.COOP.CSC = False  # class-specific context
    cfg.TRAINER.COOP.CTX_INIT = ""  # initialization words
    cfg.TRAINER.COOP.PREC = "fp16"  # fp16, fp32, amp
    cfg.TRAINER.COOP.CLASS_TOKEN_POSITION = "end"  # 'middle' or 'end' or 'front'

    # Config for CoCoOp
    cfg.TRAINER.COCOOP = CN()
    cfg.TRAINER.COCOOP.N_CTX = 16  # number of context vectors
    cfg.TRAINER.COCOOP.CTX_INIT = ""  # initialization words
    cfg.TRAINER.COCOOP.PREC = "fp16"  # fp16, fp32, amp

    # Config for MaPLe
    cfg.TRAINER.MAPLE = CN()
    cfg.TRAINER.MAPLE.N_CTX = 2  # number of context vectors
    cfg.TRAINER.MAPLE.CTX_INIT = "a photo of a"  # initialization words
    cfg.TRAINER.MAPLE.PREC = "fp16"  # fp16, fp32, amp
    cfg.TRAINER.MAPLE.PROMPT_DEPTH = (
        9  # Max 12, minimum 0, for 1 it will act as shallow MaPLe (J=1)
    )

    # Config for VPT
    cfg.TRAINER.VPT = CN()
    cfg.TRAINER.VPT.N_CTX_VISION = 2  # number of context vectors at the vision branch
    cfg.TRAINER.VPT.CTX_INIT = "a photo of a"  # initialization words
    cfg.TRAINER.VPT.PREC = "fp16"  # fp16, fp32, amp
    cfg.TRAINER.VPT.PROMPT_DEPTH_VISION = (
        1  # if set to 1, will represent shallow vision prompting only
    )

    # 默认的采样设置为 all，可以根据需要进行调整
    cfg.DATASET.SUBSAMPLE_CLASSES = "all"  # all, base or new


def get_dataset():
    dataset = CIFAR10(root="/mnt/hdd/zhurui/data", labeled_size=0.1, shuffle=True)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    labeled_X, labeled_y = dataset.labeled_X, dataset.labeled_y
    labeled_X = torch.tensor(labeled_X, device=device)
    labeled_X = torch.permute(labeled_X, (0, 3, 1, 2))
    labeled_X = T.Resize((224, 224))(labeled_X)
    labeled_y = torch.tensor(labeled_y, device=device)
    unlabeled_X = dataset.unlabeled_X
    unlabeled_X = torch.tensor(unlabeled_X, device=device)
    test_X, test_y = dataset.test_X, dataset.test_y
    test_X = torch.tensor(test_X, device=device)
    test_X = torch.permute(test_X, (0, 3, 1, 2))
    test_X = T.Resize((224, 224))(test_X)
    test_y = torch.tensor(test_y, device=device)
    return labeled_X, labeled_y, unlabeled_X, test_X, test_y


if __name__ == "__main__":
    print("----------Build up cfg----------")
    cfg_coop = get_cfg_default()
    cfg_vpt = get_cfg_default()
    cfg_maple = get_cfg_default()
    extend_cfg(cfg_coop)
    extend_cfg(cfg_vpt)
    extend_cfg(cfg_maple)
    cfg_coop.merge_from_file(
        "/mnt/hdd/zhurui/code/CoOp/configs/trainers/TriTraining/CoOp.yaml"
    )
    cfg_vpt.merge_from_file(
        "/mnt/hdd/zhurui/code/CoOp/configs/trainers/TriTraining/VPT.yaml"
    )
    cfg_maple.merge_from_file(
        "/mnt/hdd/zhurui/code/CoOp/configs/trainers/TriTraining/MaPLe.yaml"
    )
    cfg_coop.freeze()
    cfg_vpt.freeze()
    cfg_maple.freeze()
    print("----------Build up CoOp----------")
    coop = build_trainer(cfg_coop)
    print("----------Build up VPT----------")
    vpt = build_trainer(cfg_vpt)
    print("----------Build up MaPLe----------")
    maple = build_trainer(cfg_maple)

    tri_trainer = Tri_Training(coop, vpt, maple)
    labeled_X, labeled_y, unlabeled_X, test_X, test_y = get_dataset()
    # print(labeled_X.shape)
    # print(len(labeled_y))
    tri_trainer.fit(labeled_X, labeled_y, unlabeled_X)
    y_pred = tri_trainer.predict(test_X)
    acc = Accuracy()
    print(acc.score(y_pred, test_y))
