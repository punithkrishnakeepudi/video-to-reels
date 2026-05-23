"""
AI-powered caption generation service.

Supports multiple providers:
- OpenAI (GPT-4o mini, etc.)
- Anthropic (Claude)
- Local Ollama (Llama 3, etc.)
- Falls back to template-based captions if no AI provider is configured
"""

import json
import re
from typing import Optional
from backend.config import settings


class CaptionService:
    """Generates captions and hashtags for reel segments using AI."""

    STYLE_PROMPTS = {
        "engaging": (
            "Write an engaging, curiosity-driven caption that hooks viewers "
            "in the first line. Use emojis naturally. Keep it under 150 words."
        ),
        "professional": (
            "Write a professional, polished caption with clear value proposition. "
            "Use minimal emojis. Focus on expertise and credibility. Keep it under 120 words."
        ),
        "humorous": (
            "Write a funny, witty caption that entertains the audience. "
            "Use emojis and relatable humor. Keep it under 100 words."
        ),
        "inspirational": (
            "Write an uplifting, motivational caption that inspires action. "
            "Use emojis and powerful language. Keep it under 120 words."
        ),
        "educational": (
            "Write an educational caption that teaches something valuable. "
            "Use bullet points or numbered tips if helpful. Keep it under 150 words."
        ),
    }

    DEFAULT_HASHTAGS = [
        "#reels", "#viral", "#trending", "#explore", "#fyp",
        "#instagram", "#contentcreator", "#socialmedia",
    ]

    def __init__(self):
        self.provider = settings.CAPTION_PROVIDER

    def generate_caption(
        self,
        segment_index: int,
        total_segments: int,
        video_topic: str = "",
        style: str = "engaging",
        custom_prompt: Optional[str] = None,
    ) -> tuple[str, str]:
        """
        Generate a caption and hashtags for a video segment.

        Returns:
            Tuple of (caption_text, hashtags_string)
        """
        if self.provider == "openai" and settings.OPENAI_API_KEY:
            return self._generate_with_openai(segment_index, total_segments, video_topic, style, custom_prompt)
        elif self.provider == "anthropic" and settings.ANTHROPIC_API_KEY:
            return self._generate_with_anthropic(segment_index, total_segments, video_topic, style, custom_prompt)
        elif self.provider == "ollama":
            return self._generate_with_ollama(segment_index, total_segments, video_topic, style, custom_prompt)
        else:
            return self._generate_template(segment_index, total_segments, video_topic)

    def _build_prompt(
        self,
        segment_index: int,
        total_segments: int,
        video_topic: str,
        style: str,
        custom_prompt: Optional[str] = None,
    ) -> str:
        """Build the prompt for caption generation."""
        style_instruction = self.STYLE_PROMPTS.get(style, self.STYLE_PROMPTS["engaging"])
        if custom_prompt:
            style_instruction = custom_prompt

        part_info = f" (Part {segment_index + 1} of {total_segments})" if total_segments > 1 else ""

        return (
            f"You are a social media expert creating Instagram Reel captions. "
            f"Generate a caption and relevant hashtags for a video segment{part_info}.\n\n"
            f"Video topic/context: {video_topic or 'Not specified — make it broadly engaging'}\n\n"
            f"Style guidance: {style_instruction}\n\n"
            f"Requirements:\n"
            f"1. Write ONLY a JSON object with keys 'caption' (string) and 'hashtags' (list of strings)\n"
            f"2. If this is part of a series (Part X of Y), reference it naturally\n"
            f"3. Include 8-12 relevant, trending hashtags\n"
            f"4. The caption should be scroll-stopping and drive engagement\n"
            f"5. Do NOT wrap the JSON in markdown code blocks\n\n"
            f"Return ONLY valid JSON like: {{\"caption\": \"Your caption here\", \"hashtags\": [\"#tag1\", \"#tag2\"]}}"
        )

    def _parse_ai_response(self, text: str) -> tuple[str, str]:
        """Parse AI response to extract caption and hashtags."""
        # Try to extract JSON from the response
        json_match = re.search(r'\{[^{}]*"caption"[^{}]*"hashtags"[^{}]*\}', text, re.DOTALL)
        if json_match:
            try:
                data = json.loads(json_match.group())
                caption = data.get("caption", "").strip()
                hashtags = " ".join(data.get("hashtags", []))
                return caption, hashtags
            except (json.JSONDecodeError, KeyError):
                pass

        # Fallback: use the whole text as caption with default hashtags
        # Clean the text
        caption = re.sub(r'```json\s*|\s*```', '', text).strip()
        # Extract any hashtags from the text
        found_hashtags = re.findall(r'#[a-zA-Z0-9_]+', caption)
        extra_tags = [t for t in found_hashtags if t not in self.DEFAULT_HASHTAGS]
        hashtags = " ".join(self.DEFAULT_HASHTAGS[:5] + extra_tags[:5])
        # Remove hashtags from caption for cleaner output
        caption = re.sub(r'#[a-zA-Z0-9_]+\s*', '', caption).strip()

        return caption or "Check out this amazing reel! 🔥", hashtags or " ".join(self.DEFAULT_HASHTAGS[:8])

    def _generate_with_openai(
        self, segment_index: int, total_segments: int,
        video_topic: str, style: str, custom_prompt: Optional[str] = None,
    ) -> tuple[str, str]:
        try:
            import openai
            client = openai.OpenAI(api_key=settings.OPENAI_API_KEY)
            prompt = self._build_prompt(segment_index, total_segments, video_topic, style, custom_prompt)

            response = client.chat.completions.create(
                model=settings.OPENAI_MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.8,
                max_tokens=300,
            )
            text = response.choices[0].message.content or ""
            return self._parse_ai_response(text)
        except Exception as e:
            print(f"OpenAI caption generation failed: {e}")
            return self._generate_template(segment_index, total_segments, video_topic)

    def _generate_with_anthropic(
        self, segment_index: int, total_segments: int,
        video_topic: str, style: str, custom_prompt: Optional[str] = None,
    ) -> tuple[str, str]:
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
            prompt = self._build_prompt(segment_index, total_segments, video_topic, style, custom_prompt)

            response = client.messages.create(
                model=settings.ANTHROPIC_MODEL,
                max_tokens=300,
                temperature=0.8,
                messages=[{"role": "user", "content": prompt}],
            )
            text = response.content[0].text if response.content else ""
            return self._parse_ai_response(text)
        except Exception as e:
            print(f"Anthropic caption generation failed: {e}")
            return self._generate_template(segment_index, total_segments, video_topic)

    def _generate_with_ollama(
        self, segment_index: int, total_segments: int,
        video_topic: str, style: str, custom_prompt: Optional[str] = None,
    ) -> tuple[str, str]:
        try:
            import httpx
            prompt = self._build_prompt(segment_index, total_segments, video_topic, style, custom_prompt)

            response = httpx.post(
                f"{settings.OLLAMA_BASE_URL}/api/chat",
                json={
                    "model": settings.OLLAMA_MODEL,
                    "messages": [{"role": "user", "content": prompt}],
                    "stream": False,
                    "options": {"temperature": 0.8},
                },
                timeout=60,
            )
            response.raise_for_status()
            data = response.json()
            text = data.get("message", {}).get("content", "")
            return self._parse_ai_response(text)
        except Exception as e:
            print(f"Ollama caption generation failed: {e}")
            return self._generate_template(segment_index, total_segments, video_topic)

    def _generate_template(
        self, segment_index: int, total_segments: int, video_topic: str
    ) -> tuple[str, str]:
        """Fallback template-based captions when AI is unavailable."""
        part_suffix = f" — Part {segment_index + 1}/{total_segments}" if total_segments > 1 else ""
        caption = (
            f"🔥 This will blow your mind{part_suffix}! "
            f"Watch till the end for the full experience. "
            f"Drop a comment and follow for more amazing content like this! 🚀"
        )
        hashtags = " ".join(self.DEFAULT_HASHTAGS + [
            "#viralvideo", "#trendingreels", "#instagood",
            "#explorepage", "#foryou", "#contentcreator",
        ])
        return caption, hashtags
