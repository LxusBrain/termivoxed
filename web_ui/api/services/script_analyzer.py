"""
Script Analyzer - Validation and analysis of generated scripts

This module handles:
- Duration estimation and validation
- Timing fit analysis
- Quality scoring
- Identification of issues requiring refinement
- Suggestions for improvements
"""

import re
from typing import List, Dict, Optional, Tuple, Any
from dataclasses import dataclass, field
from enum import Enum

from utils.logger import logger


class FitStatus(Enum):
    """How well the script fits the segment duration"""
    PERFECT = "perfect"  # Within 5% tolerance
    GOOD = "good"  # Within 15% tolerance
    ACCEPTABLE = "acceptable"  # Within 25% tolerance
    TOO_SHORT = "too_short"  # More than 25% under
    TOO_LONG = "too_long"  # More than 25% over
    CRITICAL = "critical"  # More than 50% off


class IssueType(Enum):
    """Types of issues detected in scripts"""
    DURATION_MISMATCH = "duration_mismatch"
    PACING_ISSUE = "pacing_issue"
    WORD_DENSITY = "word_density"
    SENTENCE_LENGTH = "sentence_length"
    OVERLAP_DETECTED = "overlap_detected"
    GAP_DETECTED = "gap_detected"
    TONE_INCONSISTENT = "tone_inconsistent"
    FILLER_WORDS = "filler_words"
    PRONUNCIATION_RISK = "pronunciation_risk"


@dataclass
class ScriptIssue:
    """Detected issue in a script"""
    issue_type: IssueType
    severity: str  # low, moderate, high, critical
    segment_index: int
    description: str
    current_value: Any
    target_value: Any
    suggestion: str


@dataclass
class SegmentAnalysis:
    """Complete analysis of a single segment's script"""
    segment_index: int
    script: str
    start_time: float
    end_time: float

    # Word and timing analysis
    word_count: int
    target_word_count: int
    estimated_duration: float
    segment_duration: float

    # Fit analysis
    fit_status: FitStatus
    fit_percentage: float  # 100% = perfect fit
    overflow_seconds: float  # Positive = too long, negative = too short

    # Quality metrics
    sentence_count: int
    avg_sentence_length: float
    filler_word_count: int

    # Issues
    issues: List[ScriptIssue] = field(default_factory=list)

    # Computed
    needs_refinement: bool = False
    refinement_priority: int = 0  # Higher = more urgent

    @property
    def summary(self) -> str:
        """Get a human-readable summary"""
        status_emoji = {
            FitStatus.PERFECT: "✓",
            FitStatus.GOOD: "✓",
            FitStatus.ACCEPTABLE: "~",
            FitStatus.TOO_SHORT: "↓",
            FitStatus.TOO_LONG: "↑",
            FitStatus.CRITICAL: "✗",
        }
        emoji = status_emoji.get(self.fit_status, "?")
        return f"[{emoji}] Segment {self.segment_index + 1}: {self.word_count}w/{self.target_word_count}w ({self.fit_status.value})"


@dataclass
class FullAnalysis:
    """Complete analysis of all segments"""
    segments: List[SegmentAnalysis]
    total_scripts: int
    scripts_fitting: int
    scripts_needing_refinement: int

    overall_coverage: float  # Percentage of video covered
    total_script_duration: float
    total_video_duration: float

    all_issues: List[ScriptIssue] = field(default_factory=list)

    # Segment timing issues
    overlapping_segments: List[Tuple[int, int]] = field(default_factory=list)
    gaps: List[Tuple[float, float]] = field(default_factory=list)

    @property
    def all_fit(self) -> bool:
        return self.scripts_needing_refinement == 0

    @property
    def summary(self) -> str:
        """Get a human-readable summary"""
        lines = [
            f"Analysis: {self.scripts_fitting}/{self.total_scripts} scripts fit well",
            f"Coverage: {self.overall_coverage:.1f}% of video",
            f"Script duration: {self.total_script_duration:.1f}s / Video: {self.total_video_duration:.1f}s",
        ]
        if self.overlapping_segments:
            lines.append(f"Overlaps detected: {len(self.overlapping_segments)}")
        if self.gaps:
            lines.append(f"Gaps detected: {len(self.gaps)}")
        return "\n".join(lines)


class ScriptAnalyzer:
    """
    Comprehensive script analysis for validation and refinement guidance.

    Analyzes scripts for:
    - Duration fit (will the audio match the segment?)
    - Quality issues (filler words, sentence structure)
    - Timing issues (overlaps, gaps)
    - Refinement suggestions
    """

    # Words per second by language
    LANGUAGE_WPS = {
        "en": 2.5,
        "es": 2.3,
        "fr": 2.4,
        "de": 2.2,
        "it": 2.4,
        "pt": 2.3,
        "hi": 2.8,
        "zh": 3.5,
        "ja": 3.0,
        "ko": 2.8,
    }

    # Common filler words to detect
    FILLER_WORDS = {
        "en": ["very", "really", "quite", "rather", "actually", "basically",
               "literally", "honestly", "simply", "just", "perhaps", "maybe",
               "certainly", "definitely", "absolutely", "essentially", "incredibly",
               "totally", "obviously", "clearly"],
        "es": ["muy", "realmente", "bastante", "básicamente", "literalmente"],
        "fr": ["très", "vraiment", "assez", "fondamentalement", "littéralement"],
    }

    # Words that might cause TTS pronunciation issues
    PRONUNCIATION_RISKS = {
        "en": ["etc", "vs", "ie", "eg", "i.e.", "e.g.", "&"],
    }

    def __init__(self, language: str = "en"):
        self.language = language
        self.wps = self.LANGUAGE_WPS.get(language, 2.5)
        self.filler_words = self.FILLER_WORDS.get(language, self.FILLER_WORDS["en"])
        self.pronunciation_risks = self.PRONUNCIATION_RISKS.get(language, [])

    def estimate_duration(self, text: str) -> float:
        """Estimate audio duration for text"""
        word_count = len(text.split())
        return word_count / self.wps

    def count_words(self, text: str) -> int:
        """Count words in text"""
        return len(text.split())

    def calculate_target_words(self, duration: float) -> int:
        """Calculate target word count for duration"""
        return int(duration * self.wps)

    def analyze_segment(
        self,
        script: str,
        start_time: float,
        end_time: float,
        segment_index: int = 0
    ) -> SegmentAnalysis:
        """Analyze a single segment's script"""

        segment_duration = end_time - start_time
        word_count = self.count_words(script)
        target_word_count = self.calculate_target_words(segment_duration)
        estimated_duration = self.estimate_duration(script)

        # Calculate fit
        overflow_seconds = estimated_duration - segment_duration
        fit_percentage = 100 - abs(overflow_seconds / segment_duration * 100) if segment_duration > 0 else 0

        # Determine fit status
        if abs(overflow_seconds) <= segment_duration * 0.05:
            fit_status = FitStatus.PERFECT
        elif abs(overflow_seconds) <= segment_duration * 0.15:
            fit_status = FitStatus.GOOD
        elif abs(overflow_seconds) <= segment_duration * 0.25:
            fit_status = FitStatus.ACCEPTABLE
        elif abs(overflow_seconds) > segment_duration * 0.50:
            fit_status = FitStatus.CRITICAL
        elif overflow_seconds > 0:
            fit_status = FitStatus.TOO_LONG
        else:
            fit_status = FitStatus.TOO_SHORT

        # Sentence analysis
        sentences = self._split_sentences(script)
        sentence_count = len(sentences)
        avg_sentence_length = word_count / sentence_count if sentence_count > 0 else 0

        # Filler word analysis
        filler_count = self._count_filler_words(script)

        # Build issues list
        issues = []

        # Duration mismatch issue
        if fit_status in [FitStatus.TOO_LONG, FitStatus.TOO_SHORT, FitStatus.CRITICAL]:
            issues.append(ScriptIssue(
                issue_type=IssueType.DURATION_MISMATCH,
                severity="critical" if fit_status == FitStatus.CRITICAL else "high",
                segment_index=segment_index,
                description=f"Script {'exceeds' if overflow_seconds > 0 else 'falls short of'} segment duration by {abs(overflow_seconds):.1f}s",
                current_value=estimated_duration,
                target_value=segment_duration,
                suggestion=f"{'Shorten' if overflow_seconds > 0 else 'Extend'} script by ~{abs(word_count - target_word_count)} words"
            ))

        # Sentence length issues
        if avg_sentence_length > 25:
            issues.append(ScriptIssue(
                issue_type=IssueType.SENTENCE_LENGTH,
                severity="moderate",
                segment_index=segment_index,
                description="Sentences are too long for natural speech",
                current_value=avg_sentence_length,
                target_value=15,
                suggestion="Break long sentences into shorter ones for better pacing"
            ))

        # Filler word issues
        if filler_count > 2:
            issues.append(ScriptIssue(
                issue_type=IssueType.FILLER_WORDS,
                severity="low",
                segment_index=segment_index,
                description=f"Script contains {filler_count} filler words",
                current_value=filler_count,
                target_value=0,
                suggestion="Remove unnecessary filler words for tighter narration"
            ))

        # Very short segment issues
        if segment_duration < 3 and word_count > 8:
            issues.append(ScriptIssue(
                issue_type=IssueType.WORD_DENSITY,
                severity="high",
                segment_index=segment_index,
                description="Too many words for very short segment",
                current_value=word_count,
                target_value=self.calculate_target_words(segment_duration),
                suggestion="Use punchy, minimal text for segments under 3 seconds"
            ))

        # Pronunciation risks
        pronunciation_issues = self._find_pronunciation_risks(script)
        if pronunciation_issues:
            issues.append(ScriptIssue(
                issue_type=IssueType.PRONUNCIATION_RISK,
                severity="low",
                segment_index=segment_index,
                description=f"Contains terms that may not TTS well: {', '.join(pronunciation_issues)}",
                current_value=pronunciation_issues,
                target_value=[],
                suggestion="Replace abbreviations with full words for TTS clarity"
            ))

        # Determine if refinement is needed
        needs_refinement = any(
            issue.severity in ["high", "critical"]
            for issue in issues
        )

        # Calculate refinement priority
        refinement_priority = sum(
            3 if issue.severity == "critical" else
            2 if issue.severity == "high" else
            1 if issue.severity == "moderate" else 0
            for issue in issues
        )

        return SegmentAnalysis(
            segment_index=segment_index,
            script=script,
            start_time=start_time,
            end_time=end_time,
            word_count=word_count,
            target_word_count=target_word_count,
            estimated_duration=estimated_duration,
            segment_duration=segment_duration,
            fit_status=fit_status,
            fit_percentage=max(0, fit_percentage),
            overflow_seconds=overflow_seconds,
            sentence_count=sentence_count,
            avg_sentence_length=avg_sentence_length,
            filler_word_count=filler_count,
            issues=issues,
            needs_refinement=needs_refinement,
            refinement_priority=refinement_priority
        )

    def analyze_all_segments(
        self,
        segments: List[Dict[str, Any]],
        video_duration: float
    ) -> FullAnalysis:
        """
        Analyze all segments for comprehensive validation.

        Args:
            segments: List of dicts with keys: script, start_time, end_time
            video_duration: Total video duration in seconds
        """

        analyses = []
        all_issues = []

        for i, seg in enumerate(segments):
            analysis = self.analyze_segment(
                script=seg.get("script", ""),
                start_time=seg.get("start_time", 0),
                end_time=seg.get("end_time", 0),
                segment_index=i
            )
            analyses.append(analysis)
            all_issues.extend(analysis.issues)

        # Check for overlapping segments
        overlapping = []
        for i in range(len(analyses) - 1):
            if analyses[i].end_time > analyses[i + 1].start_time:
                overlapping.append((i, i + 1))
                all_issues.append(ScriptIssue(
                    issue_type=IssueType.OVERLAP_DETECTED,
                    severity="high",
                    segment_index=i,
                    description=f"Segment {i+1} overlaps with segment {i+2}",
                    current_value=analyses[i].end_time,
                    target_value=analyses[i + 1].start_time,
                    suggestion=f"Adjust segment {i+1} to end before {analyses[i + 1].start_time:.1f}s"
                ))

        # Check for gaps between segments
        gaps = []
        for i in range(len(analyses) - 1):
            gap = analyses[i + 1].start_time - analyses[i].end_time
            if gap > 2.0:  # Significant gap
                gaps.append((analyses[i].end_time, analyses[i + 1].start_time))
                all_issues.append(ScriptIssue(
                    issue_type=IssueType.GAP_DETECTED,
                    severity="low",
                    segment_index=i,
                    description=f"{gap:.1f}s gap between segments {i+1} and {i+2}",
                    current_value=gap,
                    target_value=0,
                    suggestion="Consider adding narration or extending adjacent segments"
                ))

        # Check for content extending beyond video
        if analyses and analyses[-1].end_time > video_duration:
            all_issues.append(ScriptIssue(
                issue_type=IssueType.DURATION_MISMATCH,
                severity="critical",
                segment_index=len(analyses) - 1,
                description=f"Content extends {analyses[-1].end_time - video_duration:.1f}s beyond video end",
                current_value=analyses[-1].end_time,
                target_value=video_duration,
                suggestion="Shorten or remove the last segment"
            ))

        # Calculate overall metrics
        total_script_duration = sum(a.estimated_duration for a in analyses)
        total_covered_duration = sum(a.segment_duration for a in analyses)
        overall_coverage = (total_covered_duration / video_duration * 100) if video_duration > 0 else 0

        scripts_fitting = sum(
            1 for a in analyses
            if a.fit_status in [FitStatus.PERFECT, FitStatus.GOOD, FitStatus.ACCEPTABLE]
        )
        scripts_needing_refinement = sum(1 for a in analyses if a.needs_refinement)

        return FullAnalysis(
            segments=analyses,
            total_scripts=len(analyses),
            scripts_fitting=scripts_fitting,
            scripts_needing_refinement=scripts_needing_refinement,
            overall_coverage=min(overall_coverage, 100),
            total_script_duration=total_script_duration,
            total_video_duration=video_duration,
            all_issues=all_issues,
            overlapping_segments=overlapping,
            gaps=gaps
        )

    def get_refinement_suggestions(
        self,
        analysis: SegmentAnalysis
    ) -> Dict[str, Any]:
        """Get specific refinement suggestions for a segment"""

        suggestions = {
            "segment_index": analysis.segment_index,
            "current_script": analysis.script,
            "needs_refinement": analysis.needs_refinement,
            "actions": []
        }

        if analysis.fit_status == FitStatus.TOO_LONG:
            words_to_cut = analysis.word_count - analysis.target_word_count
            suggestions["actions"].append({
                "action": "shorten",
                "target_words": analysis.target_word_count,
                "words_to_cut": words_to_cut,
                "tip": f"Remove ~{words_to_cut} words. Focus on cutting filler and condensing phrases."
            })

        elif analysis.fit_status == FitStatus.TOO_SHORT:
            words_to_add = analysis.target_word_count - analysis.word_count
            suggestions["actions"].append({
                "action": "expand",
                "target_words": analysis.target_word_count,
                "words_to_add": words_to_add,
                "tip": f"Add ~{words_to_add} words. Expand descriptions or add context."
            })

        if analysis.filler_word_count > 0:
            suggestions["actions"].append({
                "action": "remove_fillers",
                "filler_count": analysis.filler_word_count,
                "tip": "Remove unnecessary filler words for tighter narration."
            })

        if analysis.avg_sentence_length > 20:
            suggestions["actions"].append({
                "action": "break_sentences",
                "avg_length": analysis.avg_sentence_length,
                "tip": "Break long sentences for better pacing and breath points."
            })

        return suggestions

    def calculate_adjustment_for_timing(
        self,
        current_script: str,
        target_duration: float
    ) -> Dict[str, Any]:
        """Calculate what adjustment is needed to fit target duration"""

        current_duration = self.estimate_duration(current_script)
        current_words = self.count_words(current_script)
        target_words = self.calculate_target_words(target_duration)

        diff_seconds = current_duration - target_duration
        diff_words = current_words - target_words

        if abs(diff_seconds) <= 0.5:
            action = "none"
            adjustment = "Script fits well"
        elif diff_seconds > 0:
            action = "shorten"
            adjustment = f"Remove ~{diff_words} words ({diff_seconds:.1f}s)"
        else:
            action = "extend"
            adjustment = f"Add ~{abs(diff_words)} words ({abs(diff_seconds):.1f}s)"

        return {
            "action": action,
            "adjustment": adjustment,
            "current_duration": current_duration,
            "target_duration": target_duration,
            "current_words": current_words,
            "target_words": target_words,
            "diff_seconds": diff_seconds,
            "diff_words": diff_words,
            "percentage_off": (abs(diff_seconds) / target_duration * 100) if target_duration > 0 else 0
        }

    def _split_sentences(self, text: str) -> List[str]:
        """Split text into sentences"""
        sentences = re.split(r'(?<=[.!?])\s+', text)
        return [s.strip() for s in sentences if s.strip()]

    def _count_filler_words(self, text: str) -> int:
        """Count filler words in text"""
        text_lower = text.lower()
        count = 0
        for filler in self.filler_words:
            count += len(re.findall(r'\b' + re.escape(filler) + r'\b', text_lower))
        return count

    def _find_pronunciation_risks(self, text: str) -> List[str]:
        """Find words that might cause TTS pronunciation issues"""
        found = []
        for risk in self.pronunciation_risks:
            if risk.lower() in text.lower():
                found.append(risk)
        return found


# Singleton instance
script_analyzer = ScriptAnalyzer()
