import torch
from  torch import Tensor
import  torch.nn.functional as F

def attention(query:Tensor,key:Tensor,value:Tensor,mask:Tensor=None) -> Tensor:
    dim = query.shape[-1] ** 0.5
    socre = torch.matmul(query,key.transpose(-2,-1))
    socre = socre / dim

    if mask is not None:
        socre = socre.masked_fill(mask==0,-1e-9)
    w = F.softmax(socre,dim=-1)
    return torch.matmul(socre,value)