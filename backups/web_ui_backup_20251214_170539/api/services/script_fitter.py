"""
Script Fitter Service

Handles the complex logic of fitting generated scripts to segment durations.
This includes:
- Duration estimation based on language and speaking rate
- Automatic text adjustment (shortening/lengthening)
- Smart segment boundary suggestions
- TTS rate adjustment recommendations
"""

import re
from typing import List, Tuple, Optional
from dataclasses import dataclass

from utils.logger import logger


@dataclass
class FittingResult:
    """Result of script fitting attempt"""
    original_text: str
    fitted_text: str
    target_duration: float
    estimated_duration: float
    fits: bool
    adjustment_made: str  # "none", "shortened", "lengthened", "rate_adjusted"
    rate_adjustment: Optional[str] = None  # e.g., "+10%" for faster
    confidence: float = 0.9


@dataclass
class SegmentSuggestion:
    """Suggestion for adjusting segment timing"""
    current_start: float
    current_end: float
    suggested_start: float
    suggested_end: float
    reason: str
    text_duration: float


class ScriptFitter:
    """
    Intelligent script fitting to segment durations

    Handles multiple scenarios:
    1. Text too long for segment -> shorten or suggest extending segment
    2. Text too short for segment -> suggest shortening segment or adding content
    3. Multiple segments -> balance content across segments
    """

    # Speaking rates in words per second by language
    SPEAKING_RATES = {
        "en": {"slow": 2.0, "normal": 2.5, "fast": 3.0},
        "es": {"slow": 1.8, "normal": 2.3, "fast": 2.8},
        "fr": {"slow": 1.9, "normal": 2.4, "fast": 2.9},
        "de": {"slow": 1.7, "normal": 2.2, "fast": 2.7},
        "hi": {"slow": 2.3, "normal": 2.8, "fast": 3.3},
        "zh": {"slow": 2.8, "normal": 3.5, "fast": 4.2},  # Characters
        "ja": {"slow": 2.5, "normal": 3.0, "fast": 3.5},
        "ko": {"slow": 2.3, "normal": 2.8, "fast": 3.3},
    }

    # TTS rate adjustments
    TTS_RATE_RANGE = {
        "min": "-30%",  # Slowest
        "slow": "-15%",
        "normal": "+0%",
        "fast": "+15%",
        "max": "+30%",  # Fastest
    }

    def __init__(self, language: str = "en"):
        self.language = language
        self.rates = self.SPEAKING_RATES.get(language, self.SPEAKING_RATES["en"])

    def estimate_duration(self, text: str, rate: str = "normal") -> float:
        """Estimate audio duration for text at given speaking rate"""
        word_count = len(text.split())
        wps = self.rates.get(rate, self.rates["normal"])
        return word_count / wps

    def estimate_word_count(self, duration: float, rate: str = "normal") -> int:
        """Estimate word count for target duration"""
        wps = self.rates.get(rate, self.rates["normal"])
        return int(duration * wps)

    def analyze_fit(
        self,
        text: str,
        segment_start: float,
        segment_end: float
    ) -> Tuple[bool, float, str]:
        """
        Analyze if text fits within segment duration

        Returns:
            Tuple of (fits, overflow_seconds, suggestion)
        """
        segment_duration = segment_end - segment_start
        estimated = self.estimate_duration(text)
        overflow = estimated - segment_duration

        if abs(overflow) <= 0.5:
            # Within 0.5 seconds tolerance
            return True, 0, "Text fits well within segment duration."

        if overflow > 0:
            # Text is too long
            percentage_over = (overflow / segment_duration) * 100

            if percentage_over <= 15:
                suggestion = (
                    f"Text is {overflow:.1f}s too long. "
                    f"Suggest: Increase TTS speed to +10% or extend segment to {segment_end + overflow:.1f}s"
                )
            elif percentage_over <= 30:
                suggestion = (
                    f"Text is {overflow:.1f}s too long ({percentage_over:.0f}% over). "
                    f"Suggest: Shorten text by ~{int((overflow / estimated) * len(text.split()))} words "
                    f"or extend segment to {segment_end + overflow:.1f}s"
                )
            else:
                suggestion = (
                    f"Text is significantly too long ({overflow:.1f}s over, {percentage_over:.0f}%). "
                    f"Recommend: Substantially shorten text or split into multiple segments."
                )

            return False, overflow, suggestion

        else:
            # Text is too short
            underflow = abs(overflow)
            percentage_under = (underflow / segment_duration) * 100

            if percentage_under <= 20:
                suggestion = (
                    f"Text is {underflow:.1f}s shorter than segment. "
                    f"This is acceptable - there will be a brief pause at the end."
                )
                return True, overflow, suggestion
            else:
                suggestion = (
                    f"Text is {underflow:.1f}s shorter than segment ({percentage_under:.0f}% under). "
                    f"Suggest: Add more content or shorten segment to end at {segment_start + estimated + 0.5:.1f}s"
                )
                return False, overflow, suggestion

    def fit_text_to_duration(
        self,
        text: str,
        target_duration: float,
        strategy: str = "auto"
    ) -> FittingResult:
        """
        Attempt to fit text to target duration

        Strategies:
        - "auto": Automatically choose best approach
        - "shorten": Prioritize shortening text
        - "rate": Prioritize adjusting TTS rate
        - "both": Use both approaches
        """
        estimated = self.estimate_duration(text)
        overflow = estimated - target_duration

        # Text already fits
        if abs(overflow) <= 0.5:
            return FittingResult(
                original_text=text,
                fitted_text=text,
                target_duration=target_duration,
                estimated_duration=estimated,
                fits=True,
                adjustment_made="none"
            )

        if overflow > 0:
            # Text too long
            if strategy in ["auto", "rate"] and overflow / estimated <= 0.2:
                # Less than 20% over - try rate adjustment first
                rate_needed = self._calculate_rate_adjustment(estimated, target_duration)
                if rate_needed and self._is_rate_acceptable(rate_needed):
                    return FittingResult(
                        original_text=text,
                        fitted_text=text,
                        target_duration=target_duration,
                        estimated_duration=estimated,
                        fits=True,
                        adjustment_made="rate_adjusted",
                        rate_adjustment=rate_needed,
                        confidence=0.85
                    )

            # Need to shorten text
            shortened = self._shorten_text(text, target_duration)
            new_estimated = self.estimate_duration(shortened)

            return FittingResult(
                original_text=text,
                fitted_text=shortened,
                target_duration=target_duration,
                estimated_duration=new_estimated,
                fits=new_estimated <= target_duration * 1.1,
                adjustment_made="shortened",
                confidence=0.75 if new_estimated <= target_duration * 1.1 else 0.5
            )

        else:
            # Text too short - this is usually acceptable
            return FittingResult(
                original_text=text,
                fitted_text=text,
                target_duration=target_duration,
                estimated_duration=estimated,
                fits=True,  # Short is usually fine
                adjustment_made="none",
                confidence=0.9
            )

    def _calculate_rate_adjustment(self, current_duration: float, target_duration: float) -> Optional[str]:
        """Calculate TTS rate adjustment needed"""
        if target_duration <= 0:
            return None

        ratio = current_duration / target_duration
        percentage = int((ratio - 1) * 100)

        if -30 <= percentage <= 30:
            return f"+{percentage}%" if percentage >= 0 else f"{percentage}%"
        return None

    def _is_rate_acceptable(self, rate: str) -> bool:
        """Check if rate adjustment is within acceptable range"""
        try:
            value = int(rate.replace("%", "").replace("+", ""))
            return -25 <= value <= 25  # Keep speech natural
        except:
            return False

    def _shorten_text(self, text: str, target_duration: float) -> str:
        """
        Intelligently shorten text to fit duration

        Strategies:
        1. Remove filler words and phrases
        2. Simplify complex sentences
        3. Remove redundant adjectives
        4. Keep key message intact
        """
        target_words = self.estimate_word_count(target_duration)
        current_words = text.split()

        if len(current_words) <= target_words:
            return text

        # Strategy 1: Remove common filler words
        fillers = {
            'very', 'really', 'quite', 'rather', 'somewhat', 'actually',
            'basically', 'literally', 'honestly', 'simply', 'just',
            'perhaps', 'maybe', 'certainly', 'definitely', 'absolutely'
        }

        shortened = []
        for word in current_words:
            if word.lower().strip('.,!?;:') not in fillers or len(shortened) < target_words * 0.9:
                shortened.append(word)

        if len(shortened) <= target_words:
            return ' '.join(shortened)

        # Strategy 2: Remove parenthetical phrases
        result = ' '.join(shortened)
        result = re.sub(r'\([^)]*\)', '', result)
        result = re.sub(r'\s+', ' ', result).strip()

        if len(result.split()) <= target_words:
            return result

        # Strategy 3: Truncate to target with ellipsis indicator
        words = result.split()[:target_words]
        # Try to end at sentence boundary
        for i in range(len(words) - 1, max(len(words) - 5, 0), -1):
            if words[i].endswith(('.', '!', '?')):
                return ' '.join(words[:i + 1])

        return ' '.join(words)

    def suggest_segment_adjustment(
        self,
        text: str,
        current_start: float,
        current_end: float,
        video_duration: float,
        next_segment_start: Optional[float] = None
    ) -> Optional[SegmentSuggestion]:
        """
        Suggest segment timing adjustments to better fit text

        Considers:
        - Text duration
        - Video boundaries
        - Next segment start (to avoid overlap)
        """
        text_duration = self.estimate_duration(text)
        current_duration = current_end - current_start

        # Text fits - no adjustment needed
        if abs(text_duration - current_duration) <= 0.5:
            return None

        ideal_end = current_start + text_duration + 0.3  # Add 0.3s padding

        # Check constraints
        max_end = video_duration
        if next_segment_start is not None:
            max_end = min(max_end, next_segment_start - 0.1)  # 0.1s gap

        if ideal_end <= max_end:
            # Can extend segment
            return SegmentSuggestion(
                current_start=current_start,
                current_end=current_end,
                suggested_start=current_start,
                suggested_end=round(ideal_end, 1),
                reason=f"Extend segment to fit {text_duration:.1f}s of narration",
                text_duration=text_duration
            )
        elif current_end > max_end:
            # Need to shorten
            return SegmentSuggestion(
                current_start=current_start,
                current_end=current_end,
                suggested_start=current_start,
                suggested_end=round(max_end, 1),
                reason=f"Shorten segment to avoid overlap (max available: {max_end:.1f}s)",
                text_duration=text_duration
            )
        else:
            # Can't adjust - text needs modification
            return SegmentSuggestion(
                current_start=current_start,
                current_end=current_end,
                suggested_start=current_start,
                suggested_end=current_end,
                reason=f"Cannot extend segment (blocked by next segment). Shorten text instead.",
                text_duration=text_duration
            )

    def distribute_text_across_segments(
        self,
        full_text: str,
        segment_times: List[Tuple[float, float]]
    ) -> List[str]:
        """
        Distribute text across multiple segments proportionally

        Useful when user provides one long script that needs to be split
        """
        sentences = self._split_into_sentences(full_text)
        total_duration = sum(end - start for start, end in segment_times)

        distributed = []
        current_idx = 0

        for start, end in segment_times:
            segment_duration = end - start
            target_words = self.estimate_word_count(segment_duration)

            segment_text = []
            word_count = 0

            while current_idx < len(sentences) and word_count < target_words:
                sentence = sentences[current_idx]
                sentence_words = len(sentence.split())

                if word_count + sentence_words <= target_words * 1.2:
                    segment_text.append(sentence)
                    word_count += sentence_words
                    current_idx += 1
                else:
                    break

            distributed.append(' '.join(segment_text))

        # Handle remaining sentences - append to last segment
        if current_idx < len(sentences):
            remaining = ' '.join(sentences[current_idx:])
            if distributed:
                distributed[-1] += ' ' + remaining

        return distributed

    def _split_into_sentences(self, text: str) -> List[str]:
        """Split text into sentences"""
        # Simple sentence splitting
        sentences = re.split(r'(?<=[.!?])\s+', text)
        return [s.strip() for s in sentences if s.strip()]


# Singleton instance
script_fitter = ScriptFitter()
