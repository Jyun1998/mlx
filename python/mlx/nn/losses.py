# Copyright © 2023 Apple Inc.

import mlx.core as mx
from mlx.nn.layers.base import Module


<<<<<<< HEAD
def _make_loss_module(f):
    def decorator(klass):
        klass.__call__ = lambda self, inputs, targets: f(
            inputs, targets, self.reduction
        )
        return klass

    return decorator


def _reduce(loss: mx.array, reduction: str = "none"):
    if reduction == "mean":
        return mx.mean(loss)
    elif reduction == "sum":
        return mx.sum(loss)
    elif reduction == "none":
        return loss
    else:
        raise ValueError("Invalid reduction. Must be 'none', 'mean', or 'sum'.")


=======
>>>>>>> 18cca64 (Add smoothed L1 loss and enhancements to cross entropy loss  (#166))
def cross_entropy(
    logits: mx.array,
    targets: mx.array,
    weights: mx.array = None,
    axis: int = -1,
    label_smoothing: float = 0.0,
    reduction: str = "none",
) -> mx.array:
    """
    Computes the cross entropy loss.

    Args:
        logits (array): The unnormalized predicted logits.
        targets (array): The target values, as class indices.
        weights (array, optional): Weights for each target. Default: ``None``.
        axis (int, optional): The axis over which to compute softmax. Default: ``-1``.
        label_smoothing (float, optional): Label smoothing factor. Default: ``0``.
        reduction (str, optional): Specifies the reduction to apply to the output:
            ``'none'`` | ``'mean'`` | ``'sum'``. Default: ``'none'``.

    Returns:
        array: The computed cross entropy loss.
    """
    if label_smoothing < 0 or label_smoothing >= 1:
        raise ValueError(f"Label smoothing must in [0, 1), got {label_smoothing}.")

    score = mx.take_along_axis(logits, targets[..., None], axis).squeeze(-1)
    logsumexp_logits = mx.logsumexp(logits, axis=axis)
    if label_smoothing > 0:
        # Adjust the true class score with label smoothing
        adjusted_score = (1 - label_smoothing) * score

        # Calculate the mean logit across the classes for smoothed loss
        mean_logits = logits.mean(axis=axis)
        smoothed_loss = -mean_logits * label_smoothing

        # Combine the adjusted score and smoothed loss with the logsumexp logits
        loss = logsumexp_logits - adjusted_score + smoothed_loss
    else:
        loss = logsumexp_logits - score

    # Apply weights if provided
    if weights is not None:
        if weights.shape != targets.shape:
            raise ValueError(
                f"Weights with shape {weights.shape} is not the same as "
                f"targets with shape {targets.shape}."
            )
        loss *= weights

    # Apply reduction
    return _reduce(loss, reduction)


def binary_cross_entropy(
    logits: mx.array, targets: mx.array, reduction: str = "none"
) -> mx.array:
    """
    Computes the binary cross entropy loss.

    Args:
        logits (array): The unnormalized (pre-sigmoid) predicted logits.
        targets (array): The binary target values in {0, 1}.
        reduction (str, optional): Specifies the reduction to apply to the output:
          ``'none'`` | ``'mean'`` | ``'sum'``. Default: ``'none'``.

    Returns:
        array: The computed binary cross entropy loss.
    Examples:
        >>> import mlx.core as mx
        >>> import mlx.nn as nn
        >>> inputs = mx.array([0.105361, 0.223144, 1.20397, 0.916291])
        >>> targets = mx.array([0, 0, 1, 1])
        >>> loss = nn.losses.binary_cross_entropy(inputs, targets, "mean")
        >>> loss
        array([0.612192], dtype=float32)
    """
    loss = mx.logaddexp(0.0, logits) - targets * logits
    return _reduce(loss, reduction)


def l1_loss(
    predictions: mx.array, targets: mx.array, reduction: str = "mean"
) -> mx.array:
    """
    Computes the L1 loss.

    Args:
        predictions (array): The predicted values.
        targets (array): The target values.
        reduction (str, optional): Specifies the reduction to apply to the output:
          ``'none'`` | ``'mean'`` | ``'sum'``. Default: ``'mean'``.

    Returns:
        array: The computed L1 loss.
    """
    if predictions.shape != targets.shape:
        raise ValueError(
            f"Predictions shape {predictions.shape} does not match "
            f"targets shape {targets.shape}."
        )
    loss = mx.abs(predictions - targets)

    return _reduce(loss, reduction)


def mse_loss(
    predictions: mx.array, targets: mx.array, reduction: str = "mean"
) -> mx.array:
    """
    Computes the mean squared error loss.

    Args:
        predictions (array): The predicted values.
        targets (array): The target values.
        reduction (str, optional): Specifies the reduction to apply to the output:
          ``'none'`` | ``'mean'`` | ``'sum'``. Default: ``'mean'``.

    Returns:
        array: The computed mean squared error loss.
    """
    if predictions.shape != targets.shape:
        raise ValueError(
            f"Predictions shape {predictions.shape} does not match "
            f"targets shape {targets.shape}."
        )

    assert (
        predictions.shape == targets.shape
    ), f"Shape of predictions {predictions.shape} and targets {targets.shape} must match"

    loss = mx.square(predictions - targets)
    return _reduce(loss, reduction)


def nll_loss(
    inputs: mx.array, targets: mx.array, axis: int = -1, reduction: str = "none"
) -> mx.array:
    """
    Computes the negative log likelihood loss.

    Args:
        inputs (array): The predicted distribution in log space.
        targets (array): The target values.
        axis (int, optional): The distribution axis. Default: ``-1``.
        reduction (str, optional): Specifies the reduction to apply to the output:
          ``'none'`` | ``'mean'`` | ``'sum'``. Default: ``'none'``.

    Returns:
        array: The computed NLL loss.
    """
    loss = -mx.take_along_axis(inputs, targets[..., None], axis).squeeze(-1)

    return _reduce(loss, reduction)


def kl_div_loss(
    inputs: mx.array, targets: mx.array, axis: int = -1, reduction: str = "none"
) -> mx.array:
    """
    Computes the Kullback-Leibler divergence loss.

    Computes the following when ``reduction == 'none'``:

    .. code-block:: python

        mx.exp(targets) * (targets - inputs).sum(axis)

    Args:
        inputs (array): Log probabilities for the predicted distribution.
        targets (array): Log probabilities for the target distribution.
        axis (int, optional): The distribution axis. Default: ``-1``.
        reduction (str, optional): Specifies the reduction to apply to the output:
          ``'none'`` | ``'mean'`` | ``'sum'``. Default: ``'none'``.

    Returns:
        array: The computed Kullback-Leibler divergence loss.
    """
    loss = mx.sum(mx.exp(targets) * (targets - inputs), axis)

    return _reduce(loss, reduction)


<<<<<<< HEAD
def hinge_loss(
    predictions: mx.array, targets: mx.array, reduction: str = "none"
) -> mx.array:
    """
    Computes the hinge loss between predictions and targets for binary classification tasks.

    Args:
        predictions (mx.array): The predicted values.
        targets (mx.array): The target values (-1 or 1).
        reduction (str, optional): Specifies the reduction to apply to the output:
          ``'none'`` | ``'mean'`` | ``'sum'``. Default: ``'none'``.

    Returns:
        mx.array: The computed hinge loss.
    """
    loss = mx.maximum(0, 1 - targets * predictions)
    return _reduce(loss, reduction)


def huber_loss(
    predictions: mx.array,
    targets: mx.array,
    delta: float = 1.0,
    reduction: str = "none",
) -> mx.array:
    """
    Computes the Huber loss, a robust loss function for regression tasks.

    Args:
        predictions (mx.array): The predicted values.
        targets (mx.array): The target values.
        delta (float, optional): Threshold for switching between quadratic and linear losses. Default: ``1.0``.
        reduction (str, optional): Specifies the reduction to apply to the output:
          ``'none'`` | ``'mean'`` | ``'sum'``. Default: ``'none'``.

    Returns:
        mx.array: The computed Huber loss.
    """
    error = mx.abs(predictions - targets)
    is_small_error = error < delta
    squared_loss = 0.5 * mx.square(error)
    linear_loss = delta * error - 0.5 * (delta**2)
    loss = mx.where(is_small_error, squared_loss, linear_loss)
    return _reduce(loss, reduction)


def dice_loss(
    inputs: mx.array, targets: mx.array, eps: float = 1e-6, reduction: str = "none"
) -> mx.array:
    """
    Computes the Dice loss, useful for binary segmentation tasks.

    Args:
        inputs (mx.array): Predicted probabilities for each pixel.
        targets (mx.array): The target values (binary labels for each pixel).
        eps (float, optional): Small constant for numerical stability. Default: ``1e-6``.
        reduction (str, optional): Specifies the reduction to apply to the output:
          ``'none'`` | ``'mean'`` | ``'sum'``. Default: ``'none'``.

    Returns:
        mx.array: The computed Dice loss.
    """
    intersection = mx.sum(inputs * targets, axis=1)  # Sum over the feature dimension
    union = mx.sum(inputs, axis=1) + mx.sum(targets, axis=1)
    dice_score = (2.0 * intersection + eps) / (union + eps)
    loss = 1 - dice_score
    return _reduce(loss, reduction)


def focal_loss(
    inputs: mx.array,
    targets: mx.array,
    alpha: float = 0.25,
    gamma: float = 2.0,
    reduction: str = "none",
) -> mx.array:
    """
    Computes the Focal loss, useful for handling class imbalance in binary classification tasks.

    Args:
        inputs (mx.array): Predicted probabilities for the positive class.
        targets (mx.array): The target values (binary).
        alpha (float, optional): Weighting factor for positive examples. Default: ``0.25``.
        gamma (float, optional): Modulating factor for hard examples. Default: ``2.0``.
        reduction (str, optional): Specifies the reduction to apply to the output:
          ``'none'`` | ``'mean'`` | ``'sum'``. Default: ``'none'``.

    Returns:
        mx.array: The computed Focal loss.
    """
    BCE_loss = binary_cross_entropy(inputs, targets)
    pt = mx.exp(-BCE_loss)
    loss = alpha * (1 - pt) ** gamma * BCE_loss
    return _reduce(loss, reduction)


def contrastive_loss(
    embeddings1: mx.array,
    embeddings2: mx.array,
    targets: mx.array,
    margin: float = 1.0,
    reduction: str = "none",
) -> mx.array:
    """
    Computes the Contrastive loss, useful for learning embeddings.

    Args:
        embeddings1 (mx.array): Embeddings for the first set of samples.
        embeddings2 (mx.array): Embeddings for the second set of samples.
        targets (mx.array): The target values (binary labels indicating if pairs are similar or dissimilar).
        margin (float, optional): Margin for dissimilar pairs. Default: ``1.0``.
        reduction (str, optional): Specifies the reduction to apply to the output:
          ``'none'`` | ``'mean'`` | ``'sum'``. Default: ``'none'``.

    Returns:
        mx.array: The computed Contrastive loss.
    """
    distances = mx.sqrt(mx.sum(mx.square(embeddings1 - embeddings2), axis=1))
    loss = targets * distances + (1 - targets) * mx.maximum(0, margin - distances)
    return _reduce(loss, reduction)


def cosine_similarity_loss(
    embeddings1: mx.array,
    embeddings2: mx.array,
    targets: mx.array,
    eps: float = 1e-8,
    margin: float = 0.0,
    reduction: str = "none",
) -> mx.array:
    """
    Computes the Cosine Similarity loss, useful for tasks where the angle between embeddings is important.

    Args:
        embeddings1 (mx.array): Embeddings for the first set of samples.
        embeddings2 (mx.array): Embeddings for the second set of samples.
        targets (mx.array): The target values (cosine similarity between embeddings).
        margin (float, optional): Margin for dissimilar pairs. Default: ``0.0``.
        reduction (str, optional): Specifies the reduction to apply to the output:
          ``'none'`` | ``'mean'`` | ``'sum'``. Default: ``'none'``.

    Returns:
        mx.array: The computed Cosine Similarity loss.
    """
    embeddings1_norm = mx.sqrt(mx.sum(mx.square(embeddings1), axis=1) + eps)
    embeddings2_norm = mx.sqrt(mx.sum(mx.square(embeddings2), axis=1) + eps)

    cos_similarity = mx.sum(embeddings1 * embeddings2, axis=1) / (
        embeddings1_norm * embeddings2_norm
    )
    loss = mx.where(
        targets == 1, 1 - cos_similarity, mx.maximum(0, cos_similarity - margin)
    )
    return _reduce(loss, reduction)
=======
def smooth_l1_loss(
    predictions: mx.array, targets: mx.array, beta: float = 1.0, reduction: str = "mean"
) -> mx.array:
    r"""
    Computes the smooth L1 loss.

    The smooth L1 loss is a variant of the L1 loss which replaces the absolute
    difference with a squared difference when the absolute difference is less
    than ``beta``.

    The formula for the smooth L1 Loss is:

    .. math::

       l =
          \begin{cases}
            0.5 (x - y)^2, & \text{ if } & (x - y) < \beta \\
            |x - y| - 0.5 \beta, &  & \text{otherwise}
          \end{cases}

    Args:
        predictions (array): Predicted values.
        targets (array): Ground truth values.
        beta (float, optional): The threshold after which the loss changes
          from the squared to the absolute difference. Default: ``1.0``.
        reduction (str, optional): Specifies the reduction to apply to the output:
          ``'none'`` | ``'mean'`` | ``'sum'``. Default: ``'mean'``.

    Returns:
        array: The computed smooth L1 loss.
    """
    if predictions.shape != targets.shape:
        raise ValueError(
            f"Predictions shape {predictions.shape} does not match "
            f"targets shape {targets.shape}."
        )

    diff = predictions - targets
    loss = mx.where(
        diff < beta, 0.5 * mx.square(diff) / beta, mx.abs(diff) - 0.5 * beta
    )

    return _reduce(loss, reduction)


def _reduce(loss: mx.array, reduction: str = "none"):
    if reduction == "mean":
        return mx.mean(loss)
    elif reduction == "sum":
        return mx.sum(loss)
    elif reduction == "none":
        return loss
    else:
        raise ValueError("Invalid reduction. Must be 'none', 'mean', or 'sum'.")
>>>>>>> 18cca64 (Add smoothed L1 loss and enhancements to cross entropy loss  (#166))
