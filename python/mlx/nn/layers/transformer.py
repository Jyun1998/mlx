# Copyright © 2023 Apple Inc.

import math
from typing import Any, Callable, Optional

import mlx.core as mx
from mlx.nn.layers.activations import relu
from mlx.nn.layers.base import Module
from mlx.nn.layers.dropout import Dropout
from mlx.nn.layers.linear import Linear
from mlx.nn.layers.normalization import LayerNorm


class MultiHeadAttention(Module):
    """Implements the scaled dot product attention with multiple heads.

    Given inputs for queries, keys and values the ``MultiHeadAttention`` produces
    new values by aggregating information from the input values according to
    the similarities of the input queries and keys.

    All inputs as well as the output are linearly projected without biases.

    MultiHeadAttention also expects an additive attention mask that should be
    broadcastable with (batch, num_heads, # queries, # keys). The mask should
    have ``-inf`` or very negative numbers to the positions that should *not* be
    attended to.

    Args:
        dims (int): The model dimensions. If no other dims are provided then
            dims is used for queries, keys, values and the output.
        num_heads (int): How many attention heads to use
        query_input_dims (int, optional): The input dimensions of the queries (default: dims).
        key_input_dims (int, optional): The input dimensions of the keys (default: dims).
        value_input_dims (int, optional): The input dimensions of the values (default: key_input_dims).
        value_dims (int, optional): The dimensions of the values after the projection (default: dims).
        value_output_dims (int, optional): The dimensions the new values will be projected to (default: dims).
    """

    def __init__(
        self,
        dims: int,
        num_heads: int,
        query_input_dims: Optional[int] = None,
        key_input_dims: Optional[int] = None,
        value_input_dims: Optional[int] = None,
        value_dims: Optional[int] = None,
        value_output_dims: Optional[int] = None,
        bias: bool = False,
    ):
        super().__init__()

        if (dims % num_heads) != 0:
            raise ValueError(
                f"The input feature dimensions should be divisible by the number of heads ({dims} % {num_heads}) != 0"
            )

        query_input_dims = query_input_dims or dims
        key_input_dims = key_input_dims or dims
        value_input_dims = value_input_dims or key_input_dims
        value_dims = value_dims or dims
        value_output_dims = value_output_dims or dims

        self.num_heads = num_heads
        self.query_proj = Linear(query_input_dims, dims, bias=bias)
        self.key_proj = Linear(key_input_dims, dims, bias=bias)
        self.value_proj = Linear(value_input_dims, value_dims, bias=bias)
        self.out_proj = Linear(value_dims, value_output_dims, bias=bias)

    def __call__(self, queries, keys, values, mask=None):
        queries = self.query_proj(queries)
        keys = self.key_proj(keys)
        values = self.value_proj(values)

        num_heads = self.num_heads
        B, L, D = queries.shape
        _, S, _ = keys.shape
        queries = queries.reshape(B, L, num_heads, -1).transpose(0, 2, 1, 3)
        keys = keys.reshape(B, S, num_heads, -1).transpose(0, 2, 3, 1)
        values = values.reshape(B, S, num_heads, -1).transpose(0, 2, 1, 3)

        # Dimensions are [batch x num heads x sequence x hidden dim]
        scale = math.sqrt(1 / queries.shape[-1])
        scores = (queries * scale) @ keys
        if mask is not None:
            scores = scores + mask.astype(scores.dtype)
        scores = mx.softmax(scores, axis=-1)
        values_hat = (scores @ values).transpose(0, 2, 1, 3).reshape(B, L, -1)

        return self.out_proj(values_hat)

    @staticmethod
    def create_additive_causal_mask(N: int, dtype: mx.Dtype = mx.float32):
        indices = mx.arange(N)
        mask = indices[:, None] < indices[None]
        # usually inf but 1e9 is as good and softmax(full(1e9)) != nan
        # TODO: Should replace this with finfo(dtype).min
        mask = mask.astype(dtype) * -1e9
        return mask


class TransformerEncoderLayer(Module):
    def __init__(
        self,
        dims: int,
        num_heads: int,
        mlp_dims: Optional[int] = None,
        dropout: float = 0.0,
        activation: Callable[[Any], Any] = relu,
        norm_first: bool = False,
    ):
        super().__init__()
        mlp_dims = mlp_dims or dims * 4
        self.attention = MultiHeadAttention(dims, num_heads)
        self.ln1 = LayerNorm(dims)
        self.ln2 = LayerNorm(dims)
        self.linear1 = Linear(dims, mlp_dims)
        self.linear2 = Linear(mlp_dims, dims)
        self.dropout1 = Dropout(dropout)
        self.dropout2 = Dropout(dropout)
        self.activation = activation
        self.norm_first = norm_first

    def __call__(self, x, mask):
        if self.norm_first:
            y = self.ln1(x)
            y = self.attention(y, y, y, mask)
            y = self.dropout1(y)
            x = x + y

            y = self.ln2(x)
            y = self.linear1(y)
            y = self.activation(y)
            y = self.dropout2(y)
            y = self.linear2(y)
            y = x + y

        else:
            y = self.attention(x, x, x, mask)
            y = self.dropout1(y)
            y = self.ln1(x + y)

            y = self.linear1(y)
            y = self.activation(y)
            y = self.dropout2(y)
            y = self.linear2(y)
            y = self.ln2(x + y)

        return y


class TransformerEncoder(Module):
    def __init__(
        self,
        num_layers: int,
        dims: int,
        num_heads: int,
        mlp_dims: Optional[int] = None,
        dropout: float = 0.0,
        activation=relu,
        norm_first: bool = False,
    ):
        super().__init__()
        self.layers = [
            TransformerEncoderLayer(
                dims, num_heads, mlp_dims, dropout, activation, norm_first
            )
            for i in range(num_layers)
        ]
        self.ln = LayerNorm(dims)

    def __call__(self, x, mask):
        for l in self.layers:
            x = l(x, mask)
        x = self.ln(x)

        return x


class TransformerDecoderLayer(Module):
    def __init__(
        self,
        dims: int,
        num_heads: int,
        mlp_dims: Optional[int] = None,
        dropout: float = 0.0,
        activation: Callable[[Any], Any] = relu,
        norm_first: bool = False,
    ):
        super().__init__()
        mlp_dims = mlp_dims or dims * 4
        self.self_attention = MultiHeadAttention(dims, num_heads)
        self.cross_attention = MultiHeadAttention(dims, num_heads)
        self.ln1 = LayerNorm(dims)
        self.ln2 = LayerNorm(dims)
        self.ln3 = LayerNorm(dims)
        self.linear1 = Linear(dims, mlp_dims)
        self.linear2 = Linear(mlp_dims, dims)
        self.dropout1 = Dropout(dropout)
        self.dropout2 = Dropout(dropout)
        self.dropout3 = Dropout(dropout)
        self.activation = activation
        self.norm_first = norm_first

    def __call__(self, x, memory, x_mask, memory_mask):
        if self.norm_first:
            y = self.ln1(x)
            y = self.self_attention(y, y, y, x_mask)
            y = self.dropout1(y)
            x = x + y

            y = self.ln2(x)
            y = self.cross_attention(y, memory, memory, memory_mask)
            y = self.dropout2(y)
            x = x + y

            y = self.ln3(x)
            y = self.linear1(y)
            y = self.activation(y)
            y = self.dropout3(y)
            y = self.linear2(y)
            y = x + y

        else:
            y = self.self_attention(x, x, x, x_mask)
            y = self.dropout1(y)
            x = self.ln1(x + y)

            y = self.cross_attention(y, memory, memory, memory_mask)
            y = self.dropout2(y)
            x = self.ln1(x + y)

            y = self.linear1(x)
            y = self.activation(y)
            y = self.dropout3(y)
            y = self.linear2(y)
            y = self.ln3(x + y)

        return y


class TransformerDecoder(Module):
    def __init__(
        self,
        num_layers: int,
        dims: int,
        num_heads: int,
        mlp_dims: Optional[int] = None,
        dropout: float = 0.0,
        activation=relu,
        norm_first: bool = False,
    ):
        super().__init__()
        self.layers = [
            TransformerDecoderLayer(
                dims, num_heads, mlp_dims, dropout, activation, norm_first
            )
            for i in range(num_layers)
        ]
        self.ln = LayerNorm(dims)

    def __call__(self, x, memory, x_mask, memory_mask):
        for l in self.layers:
            x = l(x, memory, x_mask, memory_mask)
        x = self.ln(x)

        return x


class Transformer(Module):
    """
    Implements a standard Transformer model based on the paper "Attention Is All You Need".

    The Transformer model consists of an encoder and a decoder. The encoder processes
    the input sequence and the decoder generates the output sequence. The interaction
    between encoder and decoder happens through the attention mechanism.

    Args:
        dims (int): The number of expected features in the encoder/decoder inputs  (default: 512)
        num_heads (int): The number of heads in the multi-head attention models (default: 8)
        num_encoder_layers (int): The number of sub-encoder-layers in the Transformer encoder (default: 6)
        num_decoder_layers (int): The number of sub-decoder-layers in the Transformer decoder (default: 6)
        mlp_dims (Optional[int]): The dimensionality of the feedforward network model in each Transformer layer,
                                  Defaults to 4*dims if not provided (default: None)
        dropout (float): The dropout value for Transformer encoder/decoder (default: 0.0)
        activation (Callable[[Any], Any]): the activation function of encoder/decoder intermediate layer (default: relu)
        custom_encoder (Optional[Any]): A custom encoder to replace the standard Transformer encoder (default: None)
        custom_decoder (Optional[Any]): A custom decoder to replace the standard Transformer decoder (default: None)
        norm_first (bool): if ``True``, encoder and decoder layers will perform LayerNorms before
            other attention and feedforward operations, otherwise after (default: False)
    """

    def __init__(
        self,
        dims: int = 512,
        num_heads: int = 8,
        num_encoder_layers: int = 6,
        num_decoder_layers: int = 6,
        mlp_dims: Optional[int] = None,
        dropout: float = 0.0,
        activation: Callable[[Any], Any] = relu,
        custom_encoder: Optional[Any] = None,
        custom_decoder: Optional[Any] = None,
        norm_first: bool = False,
    ):
        super().__init__()
        if custom_encoder is not None:
            self.encoder = custom_encoder
        else:
            self.encoder = TransformerEncoder(
                num_encoder_layers,
                dims,
                num_heads,
                mlp_dims,
                dropout,
                activation,
                norm_first,
            )

        if custom_decoder is not None:
            self.decoder = custom_decoder
        else:
            self.decoder = TransformerDecoder(
                num_decoder_layers,
                dims,
                num_heads,
                mlp_dims,
                dropout,
                activation,
                norm_first,
            )

    def __call__(self, src, tgt, src_mask, tgt_mask, memory_mask):
        memory = self.encoder(src, src_mask)
        output = self.decoder(tgt, memory, tgt_mask, memory_mask)

        return output
