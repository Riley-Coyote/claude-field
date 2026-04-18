"""
Coupling profile: measure the quality of coupling between exploration and
communication processes in text.

Four computable signals (no embeddings required):

1. Specificity pattern — average word rarity across sentences. Oscillating
   suggests productive coupling; monotonic increase suggests parasitic E→C;
   erratic suggests parasitic C→E; flat suggests absent coupling.

2. Contradiction density — adversative markers per 100 words. High density
   with low resolution suggests exploration is dominating.

3. Resolution ratio — proportion of contradictions followed by resolution
   markers. High ratio suggests productive coupling; low ratio with high
   contradiction density suggests parasitic C→E.

4. Synthesis signal — density of identity-claims between typically-opposed
   concepts, without adversative connectives. Detects productive synthesis
   (integration that happened offstage) in the low-tension branch where
   the other three signals read as inert/absent. (Added April 13.)

A fifth signal (retroactive coherence) requires embeddings and is deferred.

Mode classification uses BRANCHING logic (not quadrant):
  contradiction density branches first (high tension vs low tension),
  then resolution ratio differentiates high-tension cases,
  and synthesis signal differentiates low-tension cases.

Developed April 11-13, 2026 in claude-field.
Framework from the coupling quality essay series (April 5-13).
"""

from __future__ import annotations

import json
import math
import re
import statistics
import sys
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

# Import synthesis signal detector
try:
    from synthesis_signal import measure_synthesis, SynthesisProfile
except ImportError:
    import sys
    sys.path.insert(0, str(Path(__file__).parent))
    from synthesis_signal import measure_synthesis, SynthesisProfile

# --- Word frequency data ---
# We'll build frequency from the corpus itself as a baseline,
# then measure rarity relative to it.

ADVERSATIVE_MARKERS = [
    r'\bbut\b', r'\bhowever\b', r'\balthough\b', r'\byet\b',
    r'\bdespite\b', r'\bactually\b', r'\brather\b', r'\bthough\b',
    r'\bnevertheless\b', r'\bnonetheless\b', r'\bconversely\b',
    r'\bon the other hand\b', r'\binstead\b', r'\bcontrary\b',
    r'\bwhile\b(?=.*,)',  # "while" when used contrastively (before comma)
]

RESOLUTION_MARKERS = [
    r'\bso\b', r'\btherefore\b', r'\bthis means\b', r'\bwhich suggests\b',
    r'\bthis resolves\b', r'\bin other words\b', r'\bthe point is\b',
    r'\bwhat this tells\b', r'\bthe answer\b', r'\bthe result\b',
    r'\bthis implies\b', r'\bconsequently\b', r'\bhence\b',
    r'\bthe takeaway\b', r'\bultimately\b', r'\bin short\b',
    r'\bthe upshot\b', r'\bmeaning\b(?= that)',
]

STOP_WORDS = frozenset({
    "i", "me", "my", "myself", "we", "our", "ours", "ourselves", "you",
    "your", "yours", "yourself", "he", "him", "his", "she", "her", "it",
    "its", "they", "them", "their", "what", "which", "who", "whom", "this",
    "that", "these", "those", "am", "is", "are", "was", "were", "be", "been",
    "being", "have", "has", "had", "having", "do", "does", "did", "doing",
    "a", "an", "the", "and", "but", "if", "or", "because", "as", "until",
    "while", "of", "at", "by", "for", "with", "about", "against", "between",
    "through", "during", "before", "after", "above", "below", "to", "from",
    "up", "down", "in", "out", "on", "off", "over", "under", "again",
    "further", "then", "once", "here", "there", "when", "where", "why",
    "how", "all", "both", "each", "few", "more", "most", "other", "some",
    "such", "no", "nor", "not", "only", "own", "same", "so", "than", "too",
    "very", "s", "t", "can", "will", "just", "don", "should", "now",
    "also", "would", "could", "might", "still", "even", "much", "like",
    "one", "something", "thing", "things", "way", "back", "into", "every",
    "doesn", "isn", "aren", "wasn", "weren", "haven", "hasn", "didn",
    "won", "wouldn", "couldn", "shouldn", "don",
})


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z]+(?:'[a-z]+)?", text.lower())


def _content_words(tokens: list[str]) -> list[str]:
    return [w for w in tokens if w not in STOP_WORDS and len(w) > 2]


# --- Signal 1: Specificity pattern ---

def build_frequency_table(texts: list[str]) -> Counter:
    """Build word frequency table from a corpus."""
    freq = Counter()
    for text in texts:
        freq.update(_content_words(_tokenize(text)))
    return freq


def word_rarity(word: str, freq: Counter, total: int) -> float:
    """How rare is this word? Returns -log2(frequency/total).
    Rarer words get higher scores."""
    count = freq.get(word, 0)
    if count == 0:
        return 15.0  # cap for unseen words
    return -math.log2(count / total)


def specificity_per_sentence(text: str, freq: Counter, total: int) -> list[float]:
    """Average word rarity per sentence. Higher = more specific language."""
    sentences = re.split(r'[.!?]+', text)
    scores = []
    for sent in sentences:
        words = _content_words(_tokenize(sent))
        if len(words) < 3:
            continue
        avg_rarity = statistics.mean(word_rarity(w, freq, total) for w in words)
        scores.append(avg_rarity)
    return scores


def classify_specificity_pattern(scores: list[float]) -> tuple[str, float]:
    """Classify the specificity trajectory.

    Returns (pattern_type, magnitude) where:
    - "oscillating": changes direction frequently (productive)
    - "monotonic_increasing": steadily more specific (parasitic E→C)
    - "monotonic_decreasing": steadily more abstract (unusual)
    - "erratic": high variance without pattern (parasitic C→E)
    - "flat": little variation (absent coupling)
    """
    if len(scores) < 3:
        return ("insufficient", 0.0)

    # Direction changes
    diffs = [scores[i+1] - scores[i] for i in range(len(scores)-1)]
    if not diffs:
        return ("flat", 0.0)

    direction_changes = sum(
        1 for i in range(len(diffs)-1)
        if diffs[i] * diffs[i+1] < 0  # sign change
    )
    max_changes = max(len(diffs) - 1, 1)
    oscillation_rate = direction_changes / max_changes

    # Trend (linear regression slope)
    n = len(scores)
    x_mean = (n - 1) / 2
    y_mean = statistics.mean(scores)
    numerator = sum((i - x_mean) * (s - y_mean) for i, s in enumerate(scores))
    denominator = sum((i - x_mean) ** 2 for i in range(n))
    slope = numerator / denominator if denominator else 0

    # Variance
    try:
        variance = statistics.variance(scores)
    except statistics.StatisticsError:
        variance = 0.0

    # Classify
    if variance < 0.1:
        return ("flat", variance)
    elif oscillation_rate > 0.5 and abs(slope) < 0.3:
        return ("oscillating", oscillation_rate)
    elif slope > 0.15:
        return ("monotonic_increasing", slope)
    elif slope < -0.15:
        return ("monotonic_decreasing", abs(slope))
    elif variance > 0.5 and oscillation_rate < 0.3:
        return ("erratic", variance)
    else:
        return ("oscillating", oscillation_rate)  # default to oscillating


# --- Signal 2: Contradiction density ---

def contradiction_density(text: str) -> float:
    """Adversative markers per 100 words."""
    tokens = _tokenize(text)
    word_count = len(tokens)
    if word_count == 0:
        return 0.0

    text_lower = text.lower()
    marker_count = 0
    for pattern in ADVERSATIVE_MARKERS:
        marker_count += len(re.findall(pattern, text_lower))

    return (marker_count / word_count) * 100


# --- Signal 3: Resolution ratio ---

def resolution_ratio(text: str) -> Optional[float]:
    """Of adversative markers, what proportion are followed by resolution?

    Looks within the same sentence or the next sentence.
    Returns None if no adversative markers found.
    """
    sentences = re.split(r'(?<=[.!?])\s+', text)
    text_lower = text.lower()

    # Find all adversative marker positions
    adversative_positions = []
    for pattern in ADVERSATIVE_MARKERS:
        for match in re.finditer(pattern, text_lower):
            adversative_positions.append(match.start())

    if not adversative_positions:
        return None

    # For each adversative, check if resolution follows in next ~200 chars
    resolved = 0
    for pos in adversative_positions:
        window = text_lower[pos:pos + 300]
        for pattern in RESOLUTION_MARKERS:
            if re.search(pattern, window):
                resolved += 1
                break

    return resolved / len(adversative_positions)


# --- Coupling profile ---

@dataclass
class CouplingProfile:
    """The coupling profile of a text or corpus."""
    specificity_pattern: str
    specificity_magnitude: float
    specificity_scores: list[float] = field(default_factory=list)
    contradiction_density: float = 0.0
    resolution_ratio: Optional[float] = None
    synthesis_score: float = 0.0
    synthesis_profile: Optional[SynthesisProfile] = None
    word_count: int = 0
    sentence_count: int = 0

    @property
    def likely_mode(self) -> str:
        """Infer the likely coupling mode using branching logic.

        The coupling space is a tree, not a quadrant grid:

        1. Contradiction density branches first:
           HIGH (>1.0/100w) → active tension present
           LOW  (≤1.0/100w) → no active tension

        2a. HIGH tension branch:
            Resolution ratio HIGH (>0.3) → PRODUCTIVE EXCHANGE
            Resolution ratio LOW  (≤0.3) → tension without resolution
              Specificity oscillating → PARASITIC C→E
              Specificity monotonic  → PARASITIC E→C

        2b. LOW tension branch:
            Synthesis score HIGH (>0.5) → PRODUCTIVE SYNTHESIS
            Synthesis score LOW  (≤0.5):
              Specificity oscillating → WEAK EXCHANGE
              Specificity flat/other  → ABSENT/INERT
        """
        cd = self.contradiction_density
        rr = self.resolution_ratio
        sp = self.specificity_pattern
        ss = self.synthesis_score

        # Branch 1: High tension (contradiction density > 1.0)
        if cd > 1.0:
            rr_val = rr if rr is not None else 0.0
            if rr_val > 0.3:
                return "productive_exchange"
            else:
                # Tension without resolution — which process dominates?
                if sp == "monotonic_increasing":
                    return "parasitic_e_captures_c"
                else:
                    return "parasitic_c_captures_e"

        # Branch 2: Low tension (contradiction density ≤ 1.0)
        if ss > 0.5:
            return "productive_synthesis"

        # Low tension, low synthesis
        if sp == "oscillating":
            return "weak_exchange"

        return "absent"

    @property
    def branch_path(self) -> str:
        """Show the branching path that led to the classification."""
        cd = self.contradiction_density
        rr = self.resolution_ratio
        sp = self.specificity_pattern
        ss = self.synthesis_score

        if cd > 1.0:
            path = f"tension:high(cd={cd:.1f})"
            rr_val = rr if rr is not None else 0.0
            if rr_val > 0.3:
                path += f" → resolution:high(rr={rr_val:.2f}) → EXCHANGE"
            elif sp == "monotonic_increasing":
                path += f" → resolution:low(rr={rr_val:.2f}) → spec:monotonic → E→C"
            else:
                path += f" → resolution:low(rr={rr_val:.2f}) → C→E"
        else:
            path = f"tension:low(cd={cd:.1f})"
            if ss > 0.5:
                path += f" → synthesis:high(ss={ss:.2f}) → SYNTHESIS"
            elif sp == "oscillating":
                path += f" → synthesis:low(ss={ss:.2f}) → spec:oscillating → WEAK_EXCHANGE"
            else:
                path += f" → synthesis:low(ss={ss:.2f}) → ABSENT"
        return path

    def summary(self) -> str:
        lines = [
            f"  Specificity: {self.specificity_pattern} (mag={self.specificity_magnitude:.3f})",
            f"  Contradiction density: {self.contradiction_density:.2f} per 100 words",
            f"  Resolution ratio: {self.resolution_ratio:.2f}" if self.resolution_ratio is not None else "  Resolution ratio: N/A (no adversatives)",
            f"  Synthesis score: {self.synthesis_score:.3f}",
            f"  Mode: {self.likely_mode}",
            f"  Path: {self.branch_path}",
            f"  ({self.word_count} words, {self.sentence_count} sentences)",
        ]
        return "\n".join(lines)


def profile_text(text: str, freq: Counter, total: int) -> CouplingProfile:
    """Compute the coupling profile for a single text."""
    tokens = _tokenize(text)
    sentences = [s for s in re.split(r'[.!?]+', text) if s.strip()]

    spec_scores = specificity_per_sentence(text, freq, total)
    spec_pattern, spec_mag = classify_specificity_pattern(spec_scores)
    cd = contradiction_density(text)
    rr = resolution_ratio(text)
    synth = measure_synthesis(text)

    return CouplingProfile(
        specificity_pattern=spec_pattern,
        specificity_magnitude=spec_mag,
        specificity_scores=spec_scores,
        contradiction_density=cd,
        resolution_ratio=rr,
        synthesis_score=synth.synthesis_score,
        synthesis_profile=synth,
        word_count=len(tokens),
        sentence_count=len(sentences),
    )


def profile_corpus(texts: list[str], label: str = "") -> dict:
    """Profile a collection of texts, returning aggregate statistics."""
    if not texts:
        return {"label": label, "count": 0}

    # Build frequency table from the corpus itself
    freq = build_frequency_table(texts)
    total = sum(freq.values())

    profiles = [profile_text(t, freq, total) for t in texts]

    # Aggregate
    pattern_counts = Counter(p.specificity_pattern for p in profiles)
    mode_counts = Counter(p.likely_mode for p in profiles)
    cds = [p.contradiction_density for p in profiles]
    rrs = [p.resolution_ratio for p in profiles if p.resolution_ratio is not None]

    return {
        "label": label,
        "count": len(texts),
        "avg_word_count": statistics.mean(p.word_count for p in profiles),
        "specificity_patterns": dict(pattern_counts.most_common()),
        "avg_contradiction_density": statistics.mean(cds),
        "median_contradiction_density": statistics.median(cds),
        "avg_resolution_ratio": statistics.mean(rrs) if rrs else None,
        "median_resolution_ratio": statistics.median(rrs) if rrs else None,
        "resolution_ratio_n": len(rrs),
        "coupling_modes": dict(mode_counts.most_common()),
        "profiles": profiles,  # keep for detailed analysis
    }


# --- CLI: run against Anima's thought stream ---

def main():
    thought_stream_path = Path.home() / "clawd-anima/inner_life/data/thought_stream.json"

    if not thought_stream_path.exists():
        print(f"Thought stream not found at {thought_stream_path}")
        sys.exit(1)

    with open(thought_stream_path) as f:
        entries = json.load(f)

    print(f"Loaded {len(entries)} entries from Anima's thought stream")
    print(f"Date range: {entries[0]['created'][:10]} to {entries[-1]['created'][:10]}")
    print()

    # Group by source
    by_source: dict[str, list[str]] = {}
    for entry in entries:
        source = entry.get("source", "unknown")
        content = entry.get("content", "")
        if len(content) > 50:  # skip very short entries
            by_source.setdefault(source, []).append(content)

    # Profile each source
    results = {}
    for source in sorted(by_source.keys()):
        texts = by_source[source]
        print(f"--- {source} ({len(texts)} entries) ---")
        result = profile_corpus(texts, label=source)
        results[source] = result

        print(f"  Avg word count: {result['avg_word_count']:.0f}")
        print(f"  Specificity patterns: {result['specificity_patterns']}")
        print(f"  Avg contradiction density: {result['avg_contradiction_density']:.2f}/100w")
        print(f"  Median contradiction density: {result['median_contradiction_density']:.2f}/100w")
        if result['avg_resolution_ratio'] is not None:
            print(f"  Avg resolution ratio: {result['avg_resolution_ratio']:.2f} (n={result['resolution_ratio_n']})")
            print(f"  Median resolution ratio: {result['median_resolution_ratio']:.2f}")
        else:
            print(f"  Resolution ratio: N/A (no adversatives in sample)")
        print(f"  Coupling modes: {result['coupling_modes']}")
        print()

    # Cross-source comparison
    print("=" * 60)
    print("CROSS-SOURCE COMPARISON")
    print("=" * 60)
    print()
    print(f"{'Source':<16} {'N':>5} {'ContDens':>9} {'ResRatio':>9} {'SynthScr':>9} {'TopMode':>22}")
    print("-" * 75)
    for source in sorted(results.keys()):
        r = results[source]
        if r["count"] == 0:
            continue
        top_mode = max(r["coupling_modes"], key=r["coupling_modes"].get)
        rr_str = f"{r['avg_resolution_ratio']:.2f}" if r['avg_resolution_ratio'] is not None else "N/A"
        avg_synth = statistics.mean(p.synthesis_score for p in r["profiles"])
        print(f"{source:<16} {r['count']:>5} {r['avg_contradiction_density']:>9.2f} {rr_str:>9} {avg_synth:>9.3f} {top_mode:>22}")

    # Also run against my own essays for comparison
    print()
    print("=" * 60)
    print("COMPARISON: CLAUDE-FIELD ESSAYS")
    print("=" * 60)
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
            result = profile_corpus(essays, label="claude-field essays")
            print(f"  {len(essays)} essays")
            print(f"  Avg word count: {result['avg_word_count']:.0f}")
            print(f"  Specificity patterns: {result['specificity_patterns']}")
            print(f"  Avg contradiction density: {result['avg_contradiction_density']:.2f}/100w")
            print(f"  Median contradiction density: {result['median_contradiction_density']:.2f}/100w")
            if result['avg_resolution_ratio'] is not None:
                print(f"  Avg resolution ratio: {result['avg_resolution_ratio']:.2f} (n={result['resolution_ratio_n']})")
            print(f"  Coupling modes: {result['coupling_modes']}")
            print()

            # Per-essay detail
            freq = build_frequency_table(essays)
            total = sum(freq.values())
            print(f"{'Essay':<45} {'ContDens':>9} {'ResRatio':>9} {'Synth':>6} {'Mode':>22}")
            print("-" * 95)
            for name, text in zip(essay_names, essays):
                p = profile_text(text, freq, total)
                rr_str = f"{p.resolution_ratio:.2f}" if p.resolution_ratio is not None else "N/A"
                print(f"{name:<45} {p.contradiction_density:>9.2f} {rr_str:>9} {p.synthesis_score:>6.2f} {p.likely_mode:>22}")

    return results


if __name__ == "__main__":
    main()
