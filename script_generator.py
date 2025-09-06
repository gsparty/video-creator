# script_generator.py
"""
Generate a 15-30s short script for a topic.
Usage:
    python script_generator.py "Huge football upset today — Ronaldo shocked fans"
Outputs trimmed script to stdout and returns it from generate_script().
Optional: if OPENAI_API_KEY is set and `openai` is installed, will try to use it.
"""

import os
import textwrap
import sys

OPENAI_KEY = os.environ.get("OPENAI_API_KEY")


def _fallback_script(topic: str) -> str:
    # A more informative fallback template (3 short sentences)
    topic = topic.strip()
    return (
        f"{topic}. Quick recap: What happened in one line. Why it matters right now — key consequence. "
        f"A surprising stat or quick quote to hook viewers. Call to action: comment your take."
    )


def generate_script(topic: str, max_words: int = 60) -> str:
    topic = topic.strip()
    if not topic:
        return _fallback_script("Unknown topic")

    # Try OpenAI if key exists and library available
    if OPENAI_KEY:
        try:
            import openai
            openai.api_key = OPENAI_KEY
            prompt = (
                f"You are a short-form video script writer. Produce a 15-30 second, punchy, "
                f"3-sentence script about this topic. Keep it concrete and specific. Max {max_words} words.\n\nTopic: {topic}"
            )
            resp = openai.Completion.create(
                engine="gpt-4o-mini" if "gpt-4o-mini" in openai.Engine.list() else "text-davinci-003",
                prompt=prompt,
                max_tokens=180,
                temperature=0.6,
            )
            text = resp.choices[0].text.strip()
            # basic sanitize: fallback if too short/long
            if len(text.split()) < 6 or len(text.split()) > max_words:
                return _fallback_script(topic)
            return text
        except Exception:
            # any failure -> fallback template
            return _fallback_script(topic)
    else:
        return _fallback_script(topic)


if __name__ == "__main__":
    if len(sys.argv) >= 2:
        topic = " ".join(sys.argv[1:])
        s = generate_script(topic)
        print("Generated Script:\n")
        print(textwrap.fill(s, width=80))
    else:
        print("Usage: python script_generator.py \"Your topic here\"")
