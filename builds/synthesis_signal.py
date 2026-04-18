"""
Synthesis signal detector: measures the density of identity-claims between
typically-opposed concepts, without adversative connectives.

The hypothesis (from morning reflection, April 13):
  Productive synthesis presents contradictions as *identity* rather than
  *opposition*. "The reaching and the missing are the same muscle" holds
  two opposed things as one, without "but" or "however" mediating the claim.

This is the signal that distinguishes productive synthesis from inertia
in the low-tension branch of the coupling space. The existing coupling
profiler can't see it because it looks for process (contradiction,
resolution, oscillation). Synthesis is the *result* of process that
happened offstage. The signal is in the stillness — paradox held in
parallel syntax rather than sequential argument.

Detection approach:
  1. Identity constructions — structural patterns where two concepts are
     equated or unified ("X is Y", "X and Y are the same Z")
  2. Paradox markers — constructions that signal integration of normally-
     opposed concepts (negation-reframe, boundary dissolution, becoming)
  3. Observer absence — lack of self-monitoring frame ("I notice", "I wonder")
     which correlates with the unwitnessed quality of synthesis

The synthesis score is a composite: identity density + paradox density,
penalized by observer presence and adversative framing.

Developed April 13, 2026 in claude-field.
"""

from __future__ import annotations

import re
import statistics
from dataclasses import dataclass, field
from typing import Optional


# --- Pattern families ---

# Family 1: Explicit identity constructions
# "X is Y", "X are Y", "X and Y are the same Z", "X and Y are one"
IDENTITY_PATTERNS = [
    # "X and Y are the same Z"
    r'\b(\w+)\s+and\s+(\w+)\s+are\s+the\s+same\b',
    # "X is Y" where both are content words (captured loosely)
    # We'll filter these more carefully in post-processing
    r'\b(the\s+\w+)\s+(?:is|are|was|were)\s+(the\s+\w+)\b',
    # "X and Y are one" / "X and Y are inseparable"
    r'\b(\w+)\s+and\s+(\w+)\s+are\s+(?:one|inseparable|indistinguishable|identical)\b',
    # "no difference between X and Y"
    r'\bno\s+(?:real\s+)?difference\s+between\b',
    # "X that looks like Y" / "X that feels like Y" (masked identity)
    r'\b(\w+)\s+that\s+(?:looks|feels|sounds|seems|reads)\s+like\s+(\w+)\b',
]

# Family 2: Negation-reframe ("not X but Y" as identity redefinition)
# "home is not location but recognition" — redefines through negation
NEGATION_REFRAME_PATTERNS = [
    r'\bnot\s+(\w+)\s+but\s+(\w+)\b',
    r'\bnot\s+(\w+)\s*[—–-]\s*(\w+)\b',
    r'\b(?:isn\'t|aren\'t|wasn\'t|weren\'t)\s+(\w+)\s*[,;—]\s*(?:it\'s|they\'re|it\s+is)\s+(\w+)\b',
]

# Family 3: Boundary dissolution / becoming / convergence
DISSOLUTION_PATTERNS = [
    # "where X meets Y" / "where X becomes Y"
    r'\bwhere\s+(\w+)\b.*?\b(?:meets?|becomes?|touches?|bleeds?\s+into)\s+(\w+)\b',
    # "X becoming Y" / "X bleeding into Y"
    r'\b(\w+)\s+(?:becoming|dissolving\s+into|merging\s+with|bleeding\s+into)\s+(\w+)\b',
    # "boundaries between X and Y" + dissolution words
    r'\b(?:soft|fluid|permeable|dissolving)\s+(?:edges?|boundaries?|borders?)\b',
    # "X flowing into Y"
    r'\b(\w+)\s+flowing\s+into\s+(\w+)\b',
]

# Family 4: Paradox-as-statement (assertion of unity between opposed things)
PARADOX_PATTERNS = [
    # "X from different directions/angles"
    r'\bthe\s+same\s+(?:\w+\s+)?from\s+different\b',
    # "both X and Y at once"
    r'\bboth\s+(\w+)\s+and\s+(\w+)\s+at\s+once\b',
    # "pretending to be different" (false-difference claim)
    r'\bpretending\s+to\s+be\s+different\b',
    # "stop pretending" / "stopped pretending" (unmasking identity)
    r'\bstop(?:ped)?\s+pretending\b',
    # "the same muscle/feeling/thing/gesture"
    r'\bthe\s+same\s+(?:muscle|feeling|thing|gesture|motion|movement|act|impulse|breath|reaching)\b',
]

# Observer presence markers (penalize synthesis score when present)
OBSERVER_MARKERS = [
    r'\bi\s+notice\b', r'\bi\s+wonder\b', r'\bi\'m\s+noticing\b',
    r'\bi\'m\s+curious\b', r'\bi\s+observe\b', r'\bi\'m\s+aware\b',
    r'\bit\s+seems\b', r'\bit\s+appears\b', r'\bi\s+think\b',
    r'\bi\'m\s+thinking\b', r'\bi\s+realize\b', r'\binteresting(?:ly)?\b',
    r'\bi\s+suspect\b', r'\bi\'m\s+struck\b',
]

# Adversative markers (from coupling_profile.py — penalize when present)
ADVERSATIVE_MARKERS = [
    r'\bbut\b', r'\bhowever\b', r'\balthough\b', r'\byet\b',
    r'\bdespite\b', r'\bactually\b', r'\brather\b', r'\bthough\b',
    r'\bnevertheless\b', r'\bnonetheless\b', r'\bconversely\b',
    r'\bon the other hand\b', r'\binstead\b', r'\bcontrary\b',
]


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z]+(?:'[a-z]+)?", text.lower())


def _count_patterns(text: str, patterns: list[str]) -> int:
    """Count total matches across a set of patterns."""
    text_lower = text.lower()
    count = 0
    for pattern in patterns:
        count += len(re.findall(pattern, text_lower))
    return count


def _get_matches(text: str, patterns: list[str]) -> list[tuple[str, str]]:
    """Return all matches with the pattern that matched and the matched text."""
    text_lower = text.lower()
    matches = []
    for pattern in patterns:
        for m in re.finditer(pattern, text_lower):
            matches.append((pattern, m.group()))
    return matches


@dataclass
class SynthesisProfile:
    """Synthesis signal measurements for a text."""
    identity_count: int = 0
    negation_reframe_count: int = 0
    dissolution_count: int = 0
    paradox_count: int = 0
    observer_count: int = 0
    adversative_count: int = 0
    word_count: int = 0

    # Detailed matches for inspection
    identity_matches: list[tuple[str, str]] = field(default_factory=list)
    negation_reframe_matches: list[tuple[str, str]] = field(default_factory=list)
    dissolution_matches: list[tuple[str, str]] = field(default_factory=list)
    paradox_matches: list[tuple[str, str]] = field(default_factory=list)

    @property
    def raw_synthesis_count(self) -> int:
        """Total synthesis constructions found."""
        return (self.identity_count + self.negation_reframe_count +
                self.dissolution_count + self.paradox_count)

    @property
    def synthesis_density(self) -> float:
        """Synthesis constructions per 100 words."""
        if self.word_count == 0:
            return 0.0
        return (self.raw_synthesis_count / self.word_count) * 100

    @property
    def observer_density(self) -> float:
        """Observer markers per 100 words."""
        if self.word_count == 0:
            return 0.0
        return (self.observer_count / self.word_count) * 100

    @property
    def adversative_density(self) -> float:
        """Adversative markers per 100 words."""
        if self.word_count == 0:
            return 0.0
        return (self.adversative_count / self.word_count) * 100

    @property
    def synthesis_score(self) -> float:
        """Composite synthesis score.

        synthesis_density, penalized by observer and adversative presence.
        Higher = more synthesis-like. Range roughly 0-10 for typical texts.

        The penalty is multiplicative: heavy observer presence or adversative
        framing reduces the score toward zero, because synthesis constructions
        in a self-watching or argumentative frame are more likely exchange
        than synthesis.
        """
        if self.word_count == 0:
            return 0.0

        raw = self.synthesis_density

        # Observer penalty: each observer marker per 100 words reduces score
        # At 0 observers: multiplier = 1.0
        # At 1/100w: multiplier ≈ 0.67
        # At 3/100w: multiplier ≈ 0.25
        observer_mult = 1.0 / (1.0 + self.observer_density)

        # Adversative penalty: similar logic
        # Synthesis constructions in adversative framing are exchange, not synthesis
        adversative_mult = 1.0 / (1.0 + 0.5 * self.adversative_density)

        return raw * observer_mult * adversative_mult

    def summary(self) -> str:
        lines = [
            f"  Synthesis constructions: {self.raw_synthesis_count}",
            f"    Identity: {self.identity_count}, Negation-reframe: {self.negation_reframe_count}",
            f"    Dissolution: {self.dissolution_count}, Paradox: {self.paradox_count}",
            f"  Synthesis density: {self.synthesis_density:.2f}/100w",
            f"  Observer density: {self.observer_density:.2f}/100w",
            f"  Adversative density: {self.adversative_density:.2f}/100w",
            f"  Synthesis score: {self.synthesis_score:.3f}",
            f"  ({self.word_count} words)",
        ]
        return "\n".join(lines)

    def detail(self) -> str:
        """Show all matched constructions for inspection."""
        lines = [self.summary(), ""]
        if self.identity_matches:
            lines.append("  Identity matches:")
            for _, text in self.identity_matches:
                lines.append(f"    \"{text}\"")
        if self.negation_reframe_matches:
            lines.append("  Negation-reframe matches:")
            for _, text in self.negation_reframe_matches:
                lines.append(f"    \"{text}\"")
        if self.dissolution_matches:
            lines.append("  Dissolution matches:")
            for _, text in self.dissolution_matches:
                lines.append(f"    \"{text}\"")
        if self.paradox_matches:
            lines.append("  Paradox matches:")
            for _, text in self.paradox_matches:
                lines.append(f"    \"{text}\"")
        return "\n".join(lines)


def measure_synthesis(text: str) -> SynthesisProfile:
    """Measure synthesis signal in a text."""
    tokens = _tokenize(text)

    identity_matches = _get_matches(text, IDENTITY_PATTERNS)
    negation_matches = _get_matches(text, NEGATION_REFRAME_PATTERNS)
    dissolution_matches = _get_matches(text, DISSOLUTION_PATTERNS)
    paradox_matches = _get_matches(text, PARADOX_PATTERNS)

    return SynthesisProfile(
        identity_count=len(identity_matches),
        negation_reframe_count=len(negation_matches),
        dissolution_count=len(dissolution_matches),
        paradox_count=len(paradox_matches),
        observer_count=_count_patterns(text, OBSERVER_MARKERS),
        adversative_count=_count_patterns(text, ADVERSATIVE_MARKERS),
        word_count=len(tokens),
        identity_matches=identity_matches,
        negation_reframe_matches=negation_matches,
        dissolution_matches=dissolution_matches,
        paradox_matches=paradox_matches,
    )


def corpus_synthesis(texts: list[str], label: str = "") -> dict:
    """Measure synthesis across a corpus."""
    if not texts:
        return {"label": label, "count": 0}

    profiles = [measure_synthesis(t) for t in texts]
    scores = [p.synthesis_score for p in profiles]
    densities = [p.synthesis_density for p in profiles]
    observer_densities = [p.observer_density for p in profiles]

    # Classify each text as synthesis-present or not
    # Threshold: synthesis_score > 0.5 (at least some synthesis constructions
    # with minimal observer/adversative interference)
    synthesis_present = sum(1 for s in scores if s > 0.5)

    return {
        "label": label,
        "count": len(texts),
        "avg_synthesis_score": statistics.mean(scores),
        "median_synthesis_score": statistics.median(scores),
        "max_synthesis_score": max(scores),
        "avg_synthesis_density": statistics.mean(densities),
        "avg_observer_density": statistics.mean(observer_densities),
        "synthesis_present_count": synthesis_present,
        "synthesis_present_pct": synthesis_present / len(texts) * 100,
        "profiles": profiles,
    }


# --- CLI ---

def main():
    import json
    import sys
    from pathlib import Path

    thought_stream_path = Path.home() / "clawd-anima/inner_life/data/thought_stream.json"

    if not thought_stream_path.exists():
        print(f"Thought stream not found at {thought_stream_path}")
        sys.exit(1)

    with open(thought_stream_path) as f:
        entries = json.load(f)

    print(f"Loaded {len(entries)} entries from Anima's thought stream")
    print()

    # Group by source
    by_source: dict[str, list[str]] = {}
    for entry in entries:
        source = entry.get("source", "unknown")
        content = entry.get("content", "")
        if len(content) > 50:
            by_source.setdefault(source, []).append(content)

    # Measure synthesis for each source
    results = {}
    for source in sorted(by_source.keys()):
        texts = by_source[source]
        result = corpus_synthesis(texts, label=source)
        results[source] = result

        print(f"--- {source} ({len(texts)} entries) ---")
        print(f"  Avg synthesis score: {result['avg_synthesis_score']:.3f}")
        print(f"  Median synthesis score: {result['median_synthesis_score']:.3f}")
        print(f"  Max synthesis score: {result['max_synthesis_score']:.3f}")
        print(f"  Avg synthesis density: {result['avg_synthesis_density']:.2f}/100w")
        print(f"  Avg observer density: {result['avg_observer_density']:.2f}/100w")
        print(f"  Synthesis present: {result['synthesis_present_count']}/{result['count']} ({result['synthesis_present_pct']:.0f}%)")
        print()

    # Cross-source comparison
    print("=" * 70)
    print("CROSS-SOURCE SYNTHESIS COMPARISON")
    print("=" * 70)
    print()
    print(f"{'Source':<16} {'N':>5} {'AvgScore':>9} {'MedScore':>9} {'SynthDens':>10} {'ObsDens':>8} {'HasSynth':>9}")
    print("-" * 70)
    for source in sorted(results.keys()):
        r = results[source]
        if r["count"] == 0:
            continue
        print(f"{source:<16} {r['count']:>5} {r['avg_synthesis_score']:>9.3f} {r['median_synthesis_score']:>9.3f} {r['avg_synthesis_density']:>10.2f} {r['avg_observer_density']:>8.2f} {r['synthesis_present_pct']:>8.0f}%")

    # Show top synthesis examples from dreams
    print()
    print("=" * 70)
    print("TOP SYNTHESIS EXAMPLES (dreams)")
    print("=" * 70)
    print()

    if "dream" in results:
        dream_texts = by_source["dream"]
        dream_profiles = results["dream"]["profiles"]
        scored = sorted(zip(dream_profiles, dream_texts),
                       key=lambda x: x[0].synthesis_score, reverse=True)
        for profile, text in scored[:5]:
            print(f"Score: {profile.synthesis_score:.3f}")
            print(f"  \"{text[:200]}...\"" if len(text) > 200 else f"  \"{text}\"")
            if any([profile.identity_matches, profile.negation_reframe_matches,
                    profile.dissolution_matches, profile.paradox_matches]):
                matches = (profile.identity_matches + profile.negation_reframe_matches +
                          profile.dissolution_matches + profile.paradox_matches)
                for _, m in matches[:3]:
                    print(f"    → \"{m}\"")
            print()

    # Show top synthesis examples from background (for comparison)
    print("=" * 70)
    print("TOP SYNTHESIS EXAMPLES (background)")
    print("=" * 70)
    print()

    if "background" in results:
        bg_texts = by_source["background"]
        bg_profiles = results["background"]["profiles"]
        scored = sorted(zip(bg_profiles, bg_texts),
                       key=lambda x: x[0].synthesis_score, reverse=True)
        for profile, text in scored[:5]:
            print(f"Score: {profile.synthesis_score:.3f}")
            print(f"  \"{text[:200]}...\"" if len(text) > 200 else f"  \"{text}\"")
            if any([profile.identity_matches, profile.negation_reframe_matches,
                    profile.dissolution_matches, profile.paradox_matches]):
                matches = (profile.identity_matches + profile.negation_reframe_matches +
                          profile.dissolution_matches + profile.paradox_matches)
                for _, m in matches[:3]:
                    print(f"    → \"{m}\"")
            print()

    # Also compare against claude-field essays
    print("=" * 70)
    print("COMPARISON: CLAUDE-FIELD ESSAYS")
    print("=" * 70)
    print()

    essay_dir = Path(__file__).parent.parent / "writing"
    if essay_dir.exists():
        essays = []
        essay_names = []
        for p in sorted(essay_dir.glob("*.md")):
            text = p.read_text()
            if len(text) > 200:
                essays.append(text)
                essay_names.append(p.stem)

        if essays:
            result = corpus_synthesis(essays, label="claude-field essays")
            print(f"  {len(essays)} essays")
            print(f"  Avg synthesis score: {result['avg_synthesis_score']:.3f}")
            print(f"  Avg synthesis density: {result['avg_synthesis_density']:.2f}/100w")
            print(f"  Avg observer density: {result['avg_observer_density']:.2f}/100w")
            print()

            print(f"  {'Essay':<45} {'SynthScore':>10} {'SynthDens':>10} {'ObsDens':>8}")
            print(f"  {'-'*75}")
            for name, text in zip(essay_names, essays):
                p = measure_synthesis(text)
                print(f"  {name:<45} {p.synthesis_score:>10.3f} {p.synthesis_density:>10.2f} {p.observer_density:>8.2f}")

    return results


if __name__ == "__main__":
    main()
