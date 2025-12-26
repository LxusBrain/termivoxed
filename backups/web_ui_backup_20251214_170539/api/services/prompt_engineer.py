"""
Prompt Engineering Module - Expert-level prompt crafting for video script generation

This module handles sophisticated prompt engineering for generating video narration scripts.
It dynamically adapts prompts based on:
- Video duration and context
- User intent and style preferences
- Segment timing constraints
- Language-specific characteristics
- Iterative refinement based on validation feedback

The goal is to produce scripts that:
1. Fit precisely within segment durations
2. Match the visual content timing
3. Sound natural when spoken
4. Align with user's creative vision
"""

import re
from typing import List, Dict, Optional, Tuple, Any
from dataclasses import dataclass, field
from enum import Enum

from utils.logger import logger


class VideoType(Enum):
    """Detected or specified video content type"""
    TUTORIAL = "tutorial"
    DOCUMENTARY = "documentary"
    PROMOTIONAL = "promotional"
    VLOG = "vlog"
    EXPLAINER = "explainer"
    STORYTELLING = "storytelling"
    PRODUCT_DEMO = "product_demo"
    EDUCATIONAL = "educational"
    NEWS = "news"
    ENTERTAINMENT = "entertainment"
    UNKNOWN = "unknown"


class PacingStyle(Enum):
    """Narration pacing style"""
    SLOW = "slow"  # ~2.0 words/sec - Dramatic, thoughtful
    MODERATE = "moderate"  # ~2.5 words/sec - Standard narration
    FAST = "fast"  # ~3.0 words/sec - Energetic, excited
    DYNAMIC = "dynamic"  # Varies based on content


@dataclass
class VideoContext:
    """Complete context about the video for intelligent prompt generation"""
    duration: float
    title: Optional[str] = None
    description: Optional[str] = None
    detected_type: VideoType = VideoType.UNKNOWN
    has_dialogue: bool = False
    has_action_scenes: bool = False
    key_moments: List[Tuple[float, str]] = field(default_factory=list)  # (timestamp, description)

    @property
    def duration_category(self) -> str:
        """Categorize video by duration for appropriate pacing"""
        if self.duration <= 15:
            return "micro"  # Very short, punchy content
        elif self.duration <= 60:
            return "short"  # Quick, focused content
        elif self.duration <= 180:
            return "medium"  # Standard content
        elif self.duration <= 600:
            return "long"  # Detailed content
        else:
            return "extended"  # Documentary-style


@dataclass
class StyleProfile:
    """Complete style configuration for script generation"""
    tone: str = "documentary"
    style: str = "narrative"
    audience: str = "general"
    language: str = "en"
    pacing: PacingStyle = PacingStyle.MODERATE
    formality: str = "neutral"  # casual, neutral, formal
    energy: str = "moderate"  # calm, moderate, high

    # Advanced style options
    use_questions: bool = True  # Rhetorical questions
    use_transitions: bool = True  # "Now", "Next", "Let's see"
    use_emphasis: bool = True  # Emphatic language
    avoid_jargon: bool = False  # Simplify technical terms


@dataclass
class SegmentSpec:
    """Specification for a single segment"""
    index: int
    start_time: float
    end_time: float
    description: str = ""
    keywords: List[str] = field(default_factory=list)
    visual_cues: List[str] = field(default_factory=list)  # What's happening visually

    @property
    def duration(self) -> float:
        return self.end_time - self.start_time

    @property
    def target_word_count(self) -> int:
        """Calculate target word count based on duration"""
        return int(self.duration * 2.5)  # ~150 words/minute

    @property
    def word_range(self) -> Tuple[int, int]:
        """Acceptable word count range (±15%)"""
        target = self.target_word_count
        return (int(target * 0.85), int(target * 1.15))


@dataclass
class RefinementFeedback:
    """Feedback from script validation for iterative refinement"""
    segment_index: int
    issue_type: str  # "too_long", "too_short", "pacing", "tone", "clarity"
    current_duration: float
    target_duration: float
    current_word_count: int
    target_word_count: int
    specific_feedback: str
    severity: str = "moderate"  # low, moderate, high


class PromptEngineer:
    """
    Expert prompt engineering for video script generation.

    This class crafts sophisticated, context-aware prompts that produce
    high-quality narration scripts matching video timing precisely.
    """

    # Words per second by language (based on TTS characteristics)
    LANGUAGE_WPS = {
        "en": {"slow": 2.0, "moderate": 2.5, "fast": 3.0},
        "es": {"slow": 1.8, "moderate": 2.3, "fast": 2.8},
        "fr": {"slow": 1.9, "moderate": 2.4, "fast": 2.9},
        "de": {"slow": 1.7, "moderate": 2.2, "fast": 2.7},
        "it": {"slow": 1.9, "moderate": 2.4, "fast": 2.9},
        "pt": {"slow": 1.8, "moderate": 2.3, "fast": 2.8},
        "hi": {"slow": 2.3, "moderate": 2.8, "fast": 3.3},
        "zh": {"slow": 2.8, "moderate": 3.5, "fast": 4.2},
        "ja": {"slow": 2.5, "moderate": 3.0, "fast": 3.5},
        "ko": {"slow": 2.3, "moderate": 2.8, "fast": 3.3},
        "ru": {"slow": 1.8, "moderate": 2.3, "fast": 2.8},
        "ar": {"slow": 2.0, "moderate": 2.5, "fast": 3.0},
    }

    # Tone-specific vocabulary and patterns
    TONE_PATTERNS = {
        "documentary": {
            "openers": ["This is", "Here we see", "What unfolds is", "In this moment"],
            "transitions": ["Meanwhile", "As we observe", "Moving forward", "Notably"],
            "emphasis": ["remarkable", "significant", "noteworthy", "essential"],
            "closers": ["This reveals", "Such is the nature of", "And so we find"],
        },
        "casual": {
            "openers": ["So here's", "Check this out", "Now this is", "Here we go"],
            "transitions": ["Okay so", "And now", "Next up", "But wait"],
            "emphasis": ["amazing", "awesome", "cool", "pretty wild"],
            "closers": ["Pretty neat right?", "That's the gist", "And that's that"],
        },
        "professional": {
            "openers": ["We present", "This demonstrates", "Observe how", "Notice the"],
            "transitions": ["Furthermore", "Additionally", "Subsequently", "In turn"],
            "emphasis": ["crucial", "paramount", "strategic", "impactful"],
            "closers": ["This concludes", "In summary", "The key takeaway"],
        },
        "dramatic": {
            "openers": ["Witness", "Behold", "In this crucial moment", "The stage is set"],
            "transitions": ["But then", "Suddenly", "Against all odds", "Yet"],
            "emphasis": ["extraordinary", "unprecedented", "breathtaking", "pivotal"],
            "closers": ["And so it was", "Thus the story unfolds", "Forever changed"],
        },
        "educational": {
            "openers": ["Let's explore", "Today we'll learn", "Consider this", "Here's how"],
            "transitions": ["Now let's look at", "This brings us to", "Building on this"],
            "emphasis": ["important", "key concept", "fundamental", "worth noting"],
            "closers": ["Remember", "The main point is", "To summarize"],
        },
    }

    def __init__(self):
        self.default_style = StyleProfile()

    def get_wps(self, language: str, pacing: PacingStyle) -> float:
        """Get words per second for language and pacing"""
        lang_wps = self.LANGUAGE_WPS.get(language, self.LANGUAGE_WPS["en"])
        pacing_key = pacing.value if pacing != PacingStyle.DYNAMIC else "moderate"
        return lang_wps.get(pacing_key, 2.5)

    def estimate_duration(self, text: str, language: str = "en", pacing: PacingStyle = PacingStyle.MODERATE) -> float:
        """Estimate audio duration for text"""
        word_count = len(text.split())
        wps = self.get_wps(language, pacing)
        return word_count / wps

    def calculate_target_words(self, duration: float, language: str = "en", pacing: PacingStyle = PacingStyle.MODERATE) -> int:
        """Calculate target word count for duration"""
        wps = self.get_wps(language, pacing)
        return int(duration * wps)

    def detect_video_type(self, description: str, title: Optional[str] = None) -> VideoType:
        """Intelligently detect video type from description/title"""
        text = f"{title or ''} {description}".lower()

        type_keywords = {
            VideoType.TUTORIAL: ["how to", "tutorial", "guide", "step by step", "learn", "diy"],
            VideoType.DOCUMENTARY: ["documentary", "history", "nature", "wildlife", "exploration"],
            VideoType.PROMOTIONAL: ["product", "brand", "sale", "offer", "buy", "promo", "ad"],
            VideoType.VLOG: ["vlog", "day in", "my life", "daily", "routine", "travel vlog"],
            VideoType.EXPLAINER: ["explain", "what is", "why", "how does", "understand"],
            VideoType.PRODUCT_DEMO: ["demo", "demonstration", "showcase", "review", "unboxing"],
            VideoType.EDUCATIONAL: ["course", "lesson", "education", "class", "training"],
            VideoType.STORYTELLING: ["story", "tale", "narrative", "journey", "adventure"],
            VideoType.NEWS: ["news", "breaking", "report", "update", "announcement"],
            VideoType.ENTERTAINMENT: ["fun", "comedy", "entertainment", "music", "dance"],
        }

        for vtype, keywords in type_keywords.items():
            if any(kw in text for kw in keywords):
                return vtype

        return VideoType.UNKNOWN

    def analyze_segment_requirements(
        self,
        segments: List[SegmentSpec],
        video_context: VideoContext,
        style: StyleProfile
    ) -> Dict[int, Dict[str, Any]]:
        """Analyze each segment and determine specific requirements"""
        requirements = {}

        for seg in segments:
            target_words = self.calculate_target_words(seg.duration, style.language, style.pacing)
            min_words, max_words = int(target_words * 0.85), int(target_words * 1.15)

            # Determine segment role
            is_intro = seg.start_time == 0 or seg.index == 0
            is_outro = seg.end_time >= video_context.duration * 0.95 or seg.index == len(segments) - 1
            is_transition = not is_intro and not is_outro

            # Adjust for very short or long segments
            if seg.duration < 5:
                pacing_note = "VERY SHORT segment - use punchy, impactful phrases only"
            elif seg.duration < 10:
                pacing_note = "SHORT segment - be concise and direct"
            elif seg.duration > 30:
                pacing_note = "LONGER segment - can develop ideas more fully"
            else:
                pacing_note = "Standard segment length"

            requirements[seg.index] = {
                "target_words": target_words,
                "word_range": (min_words, max_words),
                "is_intro": is_intro,
                "is_outro": is_outro,
                "is_transition": is_transition,
                "pacing_note": pacing_note,
                "duration": seg.duration,
                "timing": f"{seg.start_time:.1f}s - {seg.end_time:.1f}s",
            }

        return requirements

    def build_system_context(self, video_context: VideoContext, style: StyleProfile) -> str:
        """Build the system context/persona for the LLM"""

        tone_guidance = self.TONE_PATTERNS.get(style.tone, self.TONE_PATTERNS["documentary"])

        return f"""You are an expert video narration script writer with years of experience in {style.tone} content creation.

YOUR EXPERTISE:
- Crafting narration that synchronizes perfectly with video timing
- Writing scripts that sound natural when spoken by text-to-speech
- Adapting tone and pacing to match visual content
- Creating engaging content for {style.audience} audiences

YOUR APPROACH:
- Every word must serve a purpose - no filler
- Scripts must fit EXACTLY within the specified duration
- Narration should complement visuals, not describe them literally
- Maintain consistent {style.tone} tone throughout

VOICE CHARACTERISTICS FOR THIS PROJECT:
- Tone: {style.tone.capitalize()}
- Style: {style.style.capitalize()}
- Energy: {style.energy.capitalize()}
- Formality: {style.formality.capitalize()}

VOCABULARY PATTERNS TO USE:
- Openers: {', '.join(tone_guidance['openers'][:3])}
- Transitions: {', '.join(tone_guidance['transitions'][:3])}
- Emphasis words: {', '.join(tone_guidance['emphasis'][:3])}

CRITICAL TIMING RULE:
At ~150 words per minute (2.5 words/second), you must calculate word count precisely:
- 5 seconds = 12-13 words
- 10 seconds = 25 words
- 15 seconds = 37-38 words
- 20 seconds = 50 words
- 30 seconds = 75 words

Your scripts will be converted to audio - they must sound natural when spoken aloud."""

    def build_auto_segment_prompt(
        self,
        video_context: VideoContext,
        style: StyleProfile,
        min_segment_duration: float = 5.0,
        max_segment_duration: float = 30.0,
        custom_instructions: Optional[str] = None
    ) -> str:
        """Build comprehensive prompt for automatic segment generation with scripts"""

        # Calculate optimal segment count
        avg_segment = (min_segment_duration + max_segment_duration) / 2
        suggested_segments = max(1, round(video_context.duration / avg_segment))

        # Build word count reference table specific to this video
        word_count_examples = []
        test_durations = [5, 10, 15, 20, 30]
        for d in test_durations:
            if d <= video_context.duration:
                wc = self.calculate_target_words(d, style.language, style.pacing)
                word_count_examples.append(f"  - {d} seconds = exactly {wc} words")

        # Duration-specific guidance
        if video_context.duration <= 15:
            duration_guidance = """
MICRO-VIDEO STRATEGY (under 15 seconds):
- Create 1-2 impactful segments
- Every word must count - no room for filler
- Focus on ONE key message or hook
- Use punchy, memorable phrases
- Consider if narration is even needed for the entire duration"""
        elif video_context.duration <= 60:
            duration_guidance = """
SHORT-VIDEO STRATEGY (15-60 seconds):
- Create 2-4 focused segments
- Quick hook in the first 3 seconds
- Each segment should have a single clear point
- Fast-paced but not rushed
- End with impact, not fade-out"""
        elif video_context.duration <= 180:
            duration_guidance = """
MEDIUM-VIDEO STRATEGY (1-3 minutes):
- Create 4-8 well-paced segments
- Establish context early
- Build narrative arc: setup → development → payoff
- Include natural pauses between key sections
- Mix segment lengths for rhythm variety"""
        else:
            duration_guidance = """
LONG-VIDEO STRATEGY (over 3 minutes):
- Create distinct chapters/sections
- Include periodic summaries/transitions
- Vary pacing to maintain engagement
- Allow breathing room between intense sections
- Build toward a satisfying conclusion"""

        # Detect content type for specialized guidance
        content_type = self.detect_video_type(video_context.description or "", video_context.title)
        type_guidance = self._get_content_type_guidance(content_type)

        prompt = f"""TASK: Analyze this video and create optimally-timed segments with perfectly-fitted narration scripts.

═══════════════════════════════════════════════════════════════════════════════
VIDEO ANALYSIS
═══════════════════════════════════════════════════════════════════════════════

Title: {video_context.title or 'Untitled Video'}
Total Duration: {video_context.duration:.1f} seconds ({video_context.duration/60:.1f} minutes)
Content Type: {content_type.value.replace('_', ' ').title()}

Description:
{video_context.description or 'No description provided'}

═══════════════════════════════════════════════════════════════════════════════
SEGMENTATION REQUIREMENTS
═══════════════════════════════════════════════════════════════════════════════

Segment Duration Constraints:
- Minimum: {min_segment_duration} seconds per segment
- Maximum: {max_segment_duration} seconds per segment
- Suggested segment count: {suggested_segments} (adjust based on content)
- Total coverage: Should approach but not exceed {video_context.duration:.1f} seconds

{duration_guidance}

═══════════════════════════════════════════════════════════════════════════════
STYLE REQUIREMENTS
═══════════════════════════════════════════════════════════════════════════════

Tone: {style.tone.upper()}
Style: {style.style}
Target Audience: {style.audience}
Language: {style.language.upper()}
Pacing: {style.pacing.value}

{type_guidance}

═══════════════════════════════════════════════════════════════════════════════
CRITICAL: WORD COUNT TO DURATION MAPPING
═══════════════════════════════════════════════════════════════════════════════

For {style.language.upper()} language at {style.pacing.value} pacing:
{chr(10).join(word_count_examples)}

RULE: Count your words BEFORE writing. If segment is 8 seconds, you need EXACTLY 20 words.
Scripts that don't match will be rejected and regenerated.

═══════════════════════════════════════════════════════════════════════════════
YOUR TASK
═══════════════════════════════════════════════════════════════════════════════

1. ANALYZE the video description to understand the content flow
2. IDENTIFY natural breakpoints for segments
3. PLAN segment timing that makes sense for the content
4. WRITE scripts that fit PRECISELY within each segment's duration
5. VERIFY each script's word count matches the target

{f'ADDITIONAL INSTRUCTIONS: {custom_instructions}' if custom_instructions else ''}

═══════════════════════════════════════════════════════════════════════════════
RESPONSE FORMAT (CRITICAL)
═══════════════════════════════════════════════════════════════════════════════

OUTPUT ONLY VALID JSON. Do NOT include:
- NO thinking tags (<think>, </think>)
- NO explanations or commentary
- NO markdown formatting outside the JSON
- NO text before or after the JSON array

Your response must START with [ and END with ]

Each segment must include all fields exactly as shown:

```json
[
  {{
    "name": "Segment Name",
    "start_time": 0.0,
    "end_time": 10.0,
    "description": "Brief description of visual content in this segment",
    "script": "Your narration script here - count: exactly 25 words for 10 seconds",
    "word_count": 25,
    "reasoning": "Why this timing and script works for this content"
  }}
]
```

IMPORTANT:
- "word_count" must be the ACTUAL count of words in your script
- "reasoning" helps you self-verify the script fits
- Scripts must sound natural when spoken aloud
- Adjacent segments should flow smoothly into each other

REMEMBER: Output ONLY the JSON array. Start with [ and end with ]. No other text.

["""

        return prompt

    def build_segment_script_prompt(
        self,
        segments: List[SegmentSpec],
        video_context: VideoContext,
        style: StyleProfile,
        custom_instructions: Optional[str] = None
    ) -> str:
        """Build prompt for generating scripts for predefined segments"""

        requirements = self.analyze_segment_requirements(segments, video_context, style)

        # Build segment specifications
        segment_specs = []
        for seg in segments:
            req = requirements[seg.index]
            min_w, max_w = req['word_range']

            spec = f"""
SEGMENT {seg.index + 1}: "{seg.description or f'Segment at {seg.start_time:.1f}s'}"
  Timing: {seg.start_time:.1f}s → {seg.end_time:.1f}s ({seg.duration:.1f} seconds)
  Target Words: {req['target_words']} (acceptable: {min_w}-{max_w})
  Role: {'INTRODUCTION' if req['is_intro'] else 'CONCLUSION' if req['is_outro'] else 'BODY'}
  Note: {req['pacing_note']}
  {f"Keywords: {', '.join(seg.keywords)}" if seg.keywords else ""}
  {f"Visual cues: {', '.join(seg.visual_cues)}" if seg.visual_cues else ""}"""
            segment_specs.append(spec)

        prompt = f"""Generate narration scripts for the following video segments.

═══════════════════════════════════════════════════════════════════════════════
VIDEO CONTEXT
═══════════════════════════════════════════════════════════════════════════════

{f'Title: {video_context.title}' if video_context.title else ''}
Duration: {video_context.duration:.1f} seconds
{f'Description: {video_context.description}' if video_context.description else ''}

═══════════════════════════════════════════════════════════════════════════════
STYLE
═══════════════════════════════════════════════════════════════════════════════

Tone: {style.tone} | Style: {style.style} | Audience: {style.audience}

═══════════════════════════════════════════════════════════════════════════════
SEGMENTS TO SCRIPT
═══════════════════════════════════════════════════════════════════════════════
{''.join(segment_specs)}

═══════════════════════════════════════════════════════════════════════════════
WORD COUNT REFERENCE
═══════════════════════════════════════════════════════════════════════════════

At 2.5 words/second:
  5 sec = 12-13 words | 10 sec = 25 words | 15 sec = 37 words | 20 sec = 50 words

{f'ADDITIONAL INSTRUCTIONS: {custom_instructions}' if custom_instructions else ''}

═══════════════════════════════════════════════════════════════════════════════
RESPONSE FORMAT
═══════════════════════════════════════════════════════════════════════════════

```json
[
  {{"segment": 1, "script": "Your script here...", "word_count": 25}},
  {{"segment": 2, "script": "Your script here...", "word_count": 38}}
]
```

Generate scripts now:"""

        return prompt

    def build_refinement_prompt(
        self,
        original_script: str,
        feedback: RefinementFeedback,
        style: StyleProfile
    ) -> str:
        """Build prompt for iterative script refinement based on validation feedback"""

        if feedback.issue_type == "too_long":
            action = f"""SHORTEN this script from {feedback.current_word_count} words to approximately {feedback.target_word_count} words.
Keep the core message but:
- Remove filler words and phrases
- Use shorter synonyms
- Combine sentences where possible
- Cut less essential details"""

        elif feedback.issue_type == "too_short":
            action = f"""EXPAND this script from {feedback.current_word_count} words to approximately {feedback.target_word_count} words.
Add substance by:
- Including more descriptive language
- Adding relevant details
- Expanding on key points
- Using transitional phrases"""

        elif feedback.issue_type == "pacing":
            action = f"""ADJUST the pacing of this script.
{feedback.specific_feedback}
Rewrite to create better rhythm and flow."""

        elif feedback.issue_type == "tone":
            action = f"""ADJUST the tone of this script.
Current issue: {feedback.specific_feedback}
Target tone: {style.tone}
Rewrite while maintaining the same length (~{feedback.target_word_count} words)."""

        else:
            action = f"""IMPROVE this script based on feedback:
{feedback.specific_feedback}
Target: ~{feedback.target_word_count} words for {feedback.target_duration:.1f} seconds."""

        prompt = f"""REFINE SCRIPT

ORIGINAL:
"{original_script}"

Current: {feedback.current_word_count} words (~{feedback.current_duration:.1f}s)
Target: {feedback.target_word_count} words (~{feedback.target_duration:.1f}s)

ACTION REQUIRED:
{action}

CONSTRAINTS:
- Maintain {style.tone} tone
- Keep suitable for {style.audience} audience
- Must sound natural when spoken
- Output ONLY the refined script, no explanations

REFINED SCRIPT:"""

        return prompt

    def build_single_segment_suggestion_prompt(
        self,
        segment_spec: SegmentSpec,
        video_context: VideoContext,
        style: StyleProfile,
        user_context: str
    ) -> str:
        """Build prompt for generating a script suggestion for a single segment"""

        target_words = self.calculate_target_words(segment_spec.duration, style.language, style.pacing)

        prompt = f"""Generate a narration script for this specific video segment.

SEGMENT DETAILS:
- Timing: {segment_spec.start_time:.1f}s → {segment_spec.end_time:.1f}s ({segment_spec.duration:.1f} seconds)
- Target word count: {target_words} words (±3 words)
- Position in video: {segment_spec.start_time/video_context.duration*100:.0f}% through

VIDEO CONTEXT:
{f'Title: {video_context.title}' if video_context.title else ''}
Total Duration: {video_context.duration:.1f}s

USER'S REQUEST:
{user_context}

STYLE:
Tone: {style.tone} | Audience: {style.audience}

REQUIREMENTS:
1. Script must be EXACTLY {target_words} words (±3)
2. Must match the {style.tone} tone
3. Should complement what's happening visually
4. Must sound natural when spoken aloud

Write ONLY the script, no explanations:"""

        return prompt

    def _get_content_type_guidance(self, content_type: VideoType) -> str:
        """Get specific guidance based on detected content type"""

        guidance = {
            VideoType.TUTORIAL: """
TUTORIAL CONTENT TIPS:
- Start with the end goal/benefit
- Use clear, action-oriented language
- Number steps when appropriate
- Avoid jargon unless audience is technical
- Include encouragement and reassurance""",

            VideoType.DOCUMENTARY: """
DOCUMENTARY CONTENT TIPS:
- Establish context and significance
- Use evocative, descriptive language
- Let visuals breathe - don't over-narrate
- Build narrative tension where appropriate
- Conclude with reflection or insight""",

            VideoType.PROMOTIONAL: """
PROMOTIONAL CONTENT TIPS:
- Lead with benefits, not features
- Create urgency without being pushy
- Use power words that resonate
- Include clear call-to-action
- Match brand voice consistently""",

            VideoType.VLOG: """
VLOG CONTENT TIPS:
- Keep it conversational and authentic
- Share thoughts and reactions naturally
- Use personal pronouns freely
- Include moments of spontaneity
- Connect directly with viewers""",

            VideoType.PRODUCT_DEMO: """
PRODUCT DEMO TIPS:
- Highlight what the viewer is seeing
- Explain benefits as features are shown
- Use confident, knowledgeable tone
- Address common questions proactively
- End with clear value proposition""",

            VideoType.EDUCATIONAL: """
EDUCATIONAL CONTENT TIPS:
- Break complex ideas into digestible parts
- Use analogies and examples
- Reinforce key concepts
- Pace for understanding, not speed
- Summarize main takeaways""",
        }

        return guidance.get(content_type, """
GENERAL TIPS:
- Match narration to visual rhythm
- Vary sentence length for interest
- Use active voice
- Be specific, not vague
- End segments with purpose""")


# Singleton instance
prompt_engineer = PromptEngineer()
