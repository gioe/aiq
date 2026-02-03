"""
EAP (Expected A Posteriori) ability estimation for Computerized Adaptive Testing.

Implements Bayesian posterior mean estimation of ability (theta) using numerical
quadrature over the 2PL IRT model. EAP is robust to extreme response patterns
(all correct/incorrect) that cause MLE to fail, making it the standard choice
for CAT ability estimation (Bock & Mislevy, 1982).

Formula:
    theta_hat = integral(theta * L(theta) * prior(theta)) / integral(L(theta) * prior(theta))

Where L(theta) = product of P(response_i | theta, a_i, b_i) for all administered items.
"""

import logging
import math
from typing import List, Tuple

logger = logging.getLogger(__name__)

# Quadrature configuration
QUADRATURE_POINTS = 61  # Number of integration points
QUADRATURE_RANGE = (-4.0, 4.0)  # Theta range for numerical integration


def estimate_ability_eap(
    responses: List[Tuple[float, float, bool]],
    prior_mean: float = 0.0,
    prior_sd: float = 1.0,
) -> Tuple[float, float]:
    """
    Estimate ability using Expected A Posteriori (EAP) with numerical quadrature.

    Uses the 2PL IRT model:
        P(theta) = 1 / (1 + exp(-a * (theta - b)))

    The EAP estimate is the posterior mean:
        theta_hat = E[theta | responses] = sum(theta_i * p(theta_i | responses))

    Standard error is the posterior standard deviation:
        SE = sqrt(Var[theta | responses])

    Args:
        responses: List of (discrimination, difficulty, is_correct) tuples.
            - discrimination (a): Item discrimination parameter (must be > 0)
            - difficulty (b): Item difficulty parameter
            - is_correct: Whether the response was correct
        prior_mean: Mean of the Gaussian prior on theta.
            Use 0.0 for new users, previous theta for returning users.
        prior_sd: Standard deviation of the Gaussian prior on theta.
            Use 1.0 for new users.

    Returns:
        Tuple of (theta_estimate, standard_error).
        - theta_estimate: Posterior mean of the ability distribution
        - standard_error: Posterior SD, quantifying estimation uncertainty

    Raises:
        ValueError: If any discrimination parameter is not positive.
    """
    # Edge case: no responses — return the prior
    if not responses:
        return (prior_mean, prior_sd)

    # Validate discrimination parameters
    for i, (a, b, correct) in enumerate(responses):
        if a <= 0:
            raise ValueError(
                f"Discrimination parameter must be positive, got {a} for response {i}"
            )

    # Build quadrature grid: evenly spaced points over [-4, 4]
    theta_min, theta_max = QUADRATURE_RANGE
    n_points = QUADRATURE_POINTS
    step = (theta_max - theta_min) / (n_points - 1)
    theta_points = [theta_min + step * i for i in range(n_points)]

    # Compute log-prior at each quadrature point
    # log N(theta | mu, sigma^2) = -0.5*log(2*pi*sigma^2) - (theta-mu)^2 / (2*sigma^2)
    log_two_pi = math.log(2.0 * math.pi)
    variance = prior_sd**2
    log_norm_const = -0.5 * log_two_pi - 0.5 * math.log(variance)
    log_priors = [
        log_norm_const - (theta - prior_mean) ** 2 / (2.0 * variance)
        for theta in theta_points
    ]

    # Compute log-likelihood at each quadrature point
    log_likelihoods = _compute_log_likelihoods(theta_points, responses)

    # Compute unnormalized log-posterior: log p(theta|data) = log prior + log likelihood
    log_posteriors = [lp + ll for lp, ll in zip(log_priors, log_likelihoods)]

    # Normalize using log-sum-exp for numerical stability
    max_log_post = max(log_posteriors)
    posteriors = [math.exp(lp - max_log_post) for lp in log_posteriors]
    posterior_sum = sum(posteriors)

    # Degenerate case: all posteriors collapsed to zero
    if posterior_sum == 0.0:
        logger.warning(
            "Posterior collapsed to zero at all quadrature points. "
            "Returning prior estimate."
        )
        return (prior_mean, prior_sd)

    # Normalize to probability distribution
    posterior_probs = [p / posterior_sum for p in posteriors]

    # EAP estimate: E[theta | data] = sum(theta_i * p_i)
    theta_hat = sum(theta * prob for theta, prob in zip(theta_points, posterior_probs))

    # Posterior variance: Var[theta | data] = sum((theta_i - theta_hat)^2 * p_i)
    posterior_variance = sum(
        (theta - theta_hat) ** 2 * prob
        for theta, prob in zip(theta_points, posterior_probs)
    )

    # Standard error is sqrt(posterior variance)
    se = math.sqrt(posterior_variance)

    return (theta_hat, se)


def _compute_log_likelihoods(
    theta_points: List[float],
    responses: List[Tuple[float, float, bool]],
) -> List[float]:
    """
    Compute the log-likelihood of the response vector at each quadrature point.

    Uses numerically stable log-sigmoid computation to avoid overflow/underflow
    with extreme logit values.

    Args:
        theta_points: Quadrature grid values.
        responses: List of (a, b, is_correct) tuples.

    Returns:
        List of log-likelihood values, one per quadrature point.
    """
    log_likelihoods = []
    for theta in theta_points:
        log_lik = 0.0
        for a, b, is_correct in responses:
            logit = a * (theta - b)

            # Numerically stable computation of log P(correct) and log P(incorrect)
            # P(correct | theta) = sigmoid(logit) = 1 / (1 + exp(-logit))
            # log P(correct)   = -log(1 + exp(-logit))   for logit >= 0
            #                   = logit - log(1 + exp(logit))  for logit < 0
            # log P(incorrect) = -logit - log(1 + exp(-logit)) for logit >= 0
            #                   = -log(1 + exp(logit))         for logit < 0
            if logit >= 0:
                log_1_plus_exp = math.log(1.0 + math.exp(-logit))
                log_p_correct = -log_1_plus_exp
                log_p_incorrect = -logit - log_1_plus_exp
            else:
                log_1_plus_exp = math.log(1.0 + math.exp(logit))
                log_p_correct = logit - log_1_plus_exp
                log_p_incorrect = -log_1_plus_exp

            if is_correct:
                log_lik += log_p_correct
            else:
                log_lik += log_p_incorrect

        log_likelihoods.append(log_lik)

    return log_likelihoods
