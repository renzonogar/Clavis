"""
Clavis Password Generator and Strength Estimator
Uses cryptographically secure randomness (secrets module) to generate
high-entropy passwords, passphrases, and evaluate password strength.
"""

from dataclasses import dataclass
import math
import secrets
import string
from typing import Any, Dict, Iterable, List, Mapping, Tuple

LOWERCASE_CHARS = string.ascii_lowercase
UPPERCASE_CHARS = string.ascii_uppercase
DIGIT_CHARS = string.digits
SYMBOL_CHARS = "!@#$%^&*()_+-=[]{}|;:,.<>?"
AMBIGUOUS_CHARS = "0O1lI|"


@dataclass
class GeneratorOptions:
    length: int = 20
    use_lowercase: bool = True
    use_uppercase: bool = True
    use_digits: bool = True
    use_symbols: bool = True
    exclude_ambiguous: bool = True

    def validate(self) -> None:
        if not (8 <= self.length <= 128):
            raise ValueError("Password length must be between 8 and 128 characters.")
        if not any([self.use_lowercase, self.use_uppercase, self.use_digits, self.use_symbols]):
            raise ValueError("At least one character set must be enabled.")


@dataclass(frozen=True)
class PasswordHealthFinding:
    credential_id: str
    title: str
    issues: Tuple[str, ...]


class PasswordGenerator:
    """Generates cryptographically secure passwords and evaluates strength."""

    @classmethod
    def generate(cls, options: GeneratorOptions = GeneratorOptions()) -> str:
        """
        Generates a password using secrets.choice, guaranteeing at least one
        character from each enabled character class.
        """
        options.validate()

        pools = []
        required_chars = []

        def filter_pool(chars: str) -> str:
            if options.exclude_ambiguous:
                return "".join(c for c in chars if c not in AMBIGUOUS_CHARS)
            return chars

        if options.use_lowercase:
            pool = filter_pool(LOWERCASE_CHARS)
            if pool:
                pools.append(pool)
                required_chars.append(secrets.choice(pool))

        if options.use_uppercase:
            pool = filter_pool(UPPERCASE_CHARS)
            if pool:
                pools.append(pool)
                required_chars.append(secrets.choice(pool))

        if options.use_digits:
            pool = filter_pool(DIGIT_CHARS)
            if pool:
                pools.append(pool)
                required_chars.append(secrets.choice(pool))

        if options.use_symbols:
            pool = filter_pool(SYMBOL_CHARS)
            if pool:
                pools.append(pool)
                required_chars.append(secrets.choice(pool))

        full_pool = "".join(pools)
        if not full_pool:
            raise ValueError("Selected character pool is empty after exclusions.")

        # Fill remaining length
        remaining_len = options.length - len(required_chars)
        random_chars = [secrets.choice(full_pool) for _ in range(remaining_len)]

        combined = required_chars + random_chars

        # Cryptographically secure Fisher-Yates shuffle
        for i in range(len(combined) - 1, 0, -1):
            j = secrets.randbelow(i + 1)
            combined[i], combined[j] = combined[j], combined[i]

        return "".join(combined)

    @classmethod
    def estimate_strength(cls, password: str) -> Dict[str, Any]:
        """
        Calculates information entropy and heuristic score.
        Returns:
            - entropy_bits: estimated entropy bits
            - score: 0 to 4 (Very Weak, Weak, Fair, Strong, Very Strong)
            - label: textual rating
            - feedback: explanation and recommendations
            - disclaimer: transparent security limitation notice
        """
        if not password:
            return {
                "entropy_bits": 0.0,
                "score": 0,
                "label": "Empty",
                "feedback": "No password entered.",
                "disclaimer": cls._strength_disclaimer()
            }

        length = len(password)
        pool_size = 0
        has_lower = any(c.islower() for c in password)
        has_upper = any(c.isupper() for c in password)
        has_digit = any(c.isdigit() for c in password)
        has_symbol = any(not c.isalnum() for c in password)

        if has_lower:
            pool_size += 26
        if has_upper:
            pool_size += 26
        if has_digit:
            pool_size += 10
        if has_symbol:
            pool_size += 32

        # Shannon-Hartley entropy estimate
        entropy_bits = length * math.log2(max(pool_size, 2))

        # Penalties for repeated characters and sequences
        unique_chars = len(set(password))
        repetition_penalty = (1.0 - (unique_chars / length)) * 20.0
        adjusted_entropy = max(0.0, entropy_bits - repetition_penalty)

        if length < 8:
            score = 0
            label = "Very Weak"
            feedback = "Password is too short (minimum 8 characters required; 16+ recommended)."
        elif adjusted_entropy < 35:
            score = 1
            label = "Weak"
            feedback = "Password has low entropy. Add uppercase letters, numbers, or symbols."
        elif adjusted_entropy < 60:
            score = 2
            label = "Fair"
            feedback = "Moderate strength. Consider increasing length beyond 16 characters."
        elif adjusted_entropy < 85:
            score = 3
            label = "Strong"
            feedback = "Good entropy and character variety."
        else:
            score = 4
            label = "Very Strong"
            feedback = "High entropy. Excellent resistance against offline brute-force attacks."

        return {
            "entropy_bits": round(adjusted_entropy, 1),
            "score": score,
            "label": label,
            "feedback": feedback,
            "disclaimer": cls._strength_disclaimer()
        }

    @staticmethod
    def _strength_disclaimer() -> str:
        return (
            "NOTICE: Strength ratings are mathematical heuristics based on character pool entropy. "
            "A high score does NOT guarantee security if the password appears in breach databases, "
            "is reused across services, or is intercepted by keyloggers on a compromised host."
        )


def analyze_password_health(
    credentials: Iterable[Mapping[str, Any]]
) -> List[PasswordHealthFinding]:
    active_credentials = [
        credential for credential in credentials
        if not credential.get("is_deleted", False)
    ]
    password_counts: Dict[str, int] = {}
    for credential in active_credentials:
        password = credential["password"]
        password_counts[password] = password_counts.get(password, 0) + 1

    findings = []
    for credential in active_credentials:
        password = credential["password"]
        analysis = PasswordGenerator.estimate_strength(password)
        issues = []
        if analysis["score"] < 2:
            issues.append(f"Weak password (rating: {analysis['label']})")
        elif analysis["score"] == 2:
            issues.append("Could be stronger (rating: Fair)")
        if password_counts[password] > 1:
            issues.append("Reused password")
        if issues:
            findings.append(
                PasswordHealthFinding(
                    credential_id=credential["id"],
                    title=credential["title"],
                    issues=tuple(issues),
                )
            )
    return findings
