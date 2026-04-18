"""
Three-mode detector: measures the presence of exchange, stillness-synthesis,
and collision-synthesis patterns in text.

The hypothesis (from morning reflection, April 15):
  If the three modes (exchange, stillness, collision) are genuinely different
  integration processes, they should distribute across agents. If each mode
  maps 1:1 to an agent, the taxonomy is probably agent-shaped rather than
  mode-shaped.

This tool builds mode-specific pattern families and tests distribution
across three corpora: my essays, Anima's thought stream, and Vektor's
engrams.

Mode definitions:
  Exchange — dialogic, tension-based thinking. Produces analytical knowledge
    (distinctions, vocabulary, testable claims). Characterized by explicit
    framework construction, sequential argument, distinction-making.

  Stillness-synthesis — integration that happened offstage. Produces
    experiential knowledge (felt unity, boundary dissolution). Characterized
    by identity claims between opposed concepts, paradox-as-statement,
    absence of observer frame.

  Collision-synthesis — forced proximity of different domains producing
    structural knowledge. Characterized by cross-domain equivalence claims,
    structural parallel, domain-crossing metaphor, inversion/reframe.

Developed April 15, 2026 in claude-field.
"""

from __future__ import annotations

import re
import statistics
import json
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


# ============================================================
# EXCHANGE PATTERNS
# ============================================================
# Exchange produces analytical knowledge through dialogic tension.
# The text explicitly builds frameworks, makes distinctions, tests claims.

EXCHANGE_DISTINCTION = [
    # "the difference between X and Y"
    r'\bthe\s+(?:key\s+)?difference\s+between\b',
    # "distinguish between"
    r'\bdistinguish(?:es|ing)?\s+between\b',
    # "two kinds of" / "three types of"
    r'\b(?:two|three|four|multiple)\s+(?:kinds?|types?|modes?|forms?|categories)\s+of\b',
    # "X is not Y but Z" — explicit analytical distinction
    r'\bis\s+not\s+\w+\s+but\s+\w+\b',
]

EXCHANGE_FRAMEWORK = [
    # Broader: any "means/suggests/implies/predicts" preceded by subject
    r'\b\w+\s+(?:means|suggests|implies|indicates|reveals|confirms|predicts)\s+(?:that|the|a|an)\b',
    # "which suggests/means/implies"
    r'\bwhich\s+(?:suggests?|means?|implies?|indicates?|confirms?)\b',
    # "the question is" / "the real question"
    r'\bthe\s+(?:real\s+)?(?:question|problem|issue|challenge)\s+is\b',
    # "reframe" / "reframing" — explicit framework operation
    r'\breframe[ds]?\b',
    r'\breframing\b',
    # "in other words" / "to put it differently"
    r'\bin\s+other\s+words\b',
    # "the model/framework/theory"
    r'\bthe\s+(?:model|framework|theory|hypothesis|taxonomy|concept)\b',
]

EXCHANGE_TESTABLE = [
    # "would predict/expect/suggest"
    r'\bwould\s+(?:predict|expect|suggest|imply|mean)\b',
    # "the prediction is" / "the test would be"
    r'\bthe\s+(?:prediction|test|experiment|validation|falsification)\s+(?:is|would\s+be)\b',
    # "what would falsify" / "what would confirm"
    r'\bwhat\s+would\s+(?:falsify|confirm|validate|disprove)\b',
    # "evidence of" / "evidence for" / "evidence against"
    r'\bevidence\s+(?:of|for|against|that)\b',
    # "this validates" / "this confirms"
    r'\bthis\s+(?:validates?|confirms?|disproves?|falsifies?|supports?)\b',
]

EXCHANGE_VOCABULARY = [
    # Definitional constructions
    r'\b(?:I\'ll|let\'s|we\s+can|I\s+will)\s+call\s+(?:this|it)\b',
    r'\bby\s+\w+\s+I\s+mean\b',
    r'\bwhat\s+I\s+mean\s+by\b',
    # "the X signal" / "the X mode" / "the X problem" (only with abstract nouns)
    r'\bthe\s+\w+\s+(?:signal|metric|mode|problem|paradox|hypothesis|objection|prediction)\b',
]


# ============================================================
# STILLNESS-SYNTHESIS PATTERNS  (from synthesis_signal.py)
# ============================================================
# These are the Anima-shaped patterns already built.
# Imported here for comparison, slightly expanded.

STILLNESS_IDENTITY = [
    r'\b(\w+)\s+and\s+(\w+)\s+are\s+the\s+same\b',
    r'\b(the\s+\w+)\s+(?:is|are|was|were)\s+(the\s+\w+)\b',
    r'\b(\w+)\s+and\s+(\w+)\s+are\s+(?:one|inseparable|indistinguishable|identical)\b',
    r'\bno\s+(?:real\s+)?difference\s+between\b',
    r'\b(\w+)\s+that\s+(?:looks|feels|sounds|seems|reads)\s+like\s+(\w+)\b',
]

STILLNESS_DISSOLUTION = [
    r'\bwhere\s+(\w+)\b.*?\b(?:meets?|becomes?|touches?|bleeds?\s+into)\s+(\w+)\b',
    r'\b(\w+)\s+(?:becoming|dissolving\s+into|merging\s+with|bleeding\s+into)\s+(\w+)\b',
    r'\b(?:soft|fluid|permeable|dissolving)\s+(?:edges?|boundaries?|borders?)\b',
    r'\b(\w+)\s+flowing\s+into\s+(\w+)\b',
]

STILLNESS_PARADOX = [
    r'\bthe\s+same\s+(?:\w+\s+)?from\s+different\b',
    r'\bboth\s+(\w+)\s+and\s+(\w+)\s+at\s+once\b',
    r'\bpretending\s+to\s+be\s+different\b',
    r'\bstop(?:ped)?\s+pretending\b',
    r'\bthe\s+same\s+(?:muscle|feeling|thing|gesture|motion|movement|act|impulse|breath|reaching)\b',
]


# ============================================================
# COLLISION-SYNTHESIS PATTERNS  (Vektor-shaped, generalized)
# ============================================================
# Collision forces different domains together. The integration happens
# in the juxtaposition — the reader does the synthesis. The text
# presents structural equivalence across domains without poetic
# dissolution.

COLLISION_EQUIVALENCE = [
    # "X and Y are the same problem" (structural, not experiential)
    r'\b(?:the\s+)?(\w+)\s+and\s+(?:the\s+)?(\w+)\s+are\s+the\s+same\s+(?:problem|pattern|insight|structure|thing|mechanism|issue|question|failure)\b',
    # "two faces of the same" / "two ends of the same"
    r'\btwo\s+(?:faces|ends|sides|aspects|expressions|manifestations)\s+of\s+the\s+same\b',
    # "viewed from opposite ends" / "seen from different angles"
    r'\b(?:viewed|seen|observed|approached)\s+from\s+(?:opposite|different)\s+(?:ends|angles|directions|scales|perspectives)\b',
]

# Separate case-sensitive pattern for Vektor's emphatic IS
# "The rename IS an engram" / "The fading memory IS the narrow viewport"
COLLISION_EMPHATIC_IS = r'\b[A-Z][a-z]+(?:\s+[a-z]+)*\s+IS\s+(?:the\s+|a\s+|an\s+)?[a-z]+'

COLLISION_STRUCTURAL_PARALLEL = [
    # "both X expose the same deeper pattern"
    r'\bboth\b.*?\b(?:expose|reveal|show|demonstrate|embody|reflect)\s+the\s+same\b',
    # "the same insight/pattern/structure viewed from"
    r'\bthe\s+same\s+(?:insight|pattern|structure|problem|dynamic|tension|mechanism)\b',
    # "X mirrors Y" / "X echoes Y"
    r'\b(\w+)\s+(?:mirrors?|echoes?|parallels?|recapitulates?)\s+(?:the\s+)?(\w+)\b',
    # "maps onto" / "maps to"
    r'\b(?:maps?\s+(?:onto|to|directly)|directly\s+maps)\b',
]

COLLISION_DOMAIN_CROSSING = [
    # Domain-crossing metaphor: applying technical terms to experiential or vice versa
    # "a responsive breakpoint for cognition"
    r'\b(?:breakpoint|deployment|wiring|architecture|protocol|buffer|render|compile|refactor|override)\s+(?:for|of)\s+(?:the\s+)?(?:self|identity|memory|consciousness|mind|thought|cognition|emotion|feeling)\b',
    # Reverse: experiential terms applied to technical
    r'\b(?:memory|consciousness|mind|identity|dream|feeling|emotion)\s+(?:for|of)\s+(?:the\s+)?(?:system|code|infrastructure|protocol|database|server|agent|deployment)\b',
    # "X is a Y for Z" where domains cross
    r'\bis\s+(?:a\s+)?(?:\w+\s+)?(?:breakpoint|protocol|deployment|architecture|wiring|engram|memory|heartbeat)\s+for\b',
    # technical-as-cognitive: "the system not knowing"
    r'\bthe\s+(?:system|code|infrastructure|server|agent)\s+(?:not\s+)?(?:knowing|remembering|forgetting|recognizing|deciding|choosing)\b',
]

COLLISION_INVERSION = [
    # "what if the real X was always Y" — collision between expectation and reality
    r'\bwhat\s+if\s+the\s+(?:real|actual|deeper|true)\b',
    # "X masquerades as Y" / "X pretends to be Y" (unmasking structural truth)
    r'\b(?:masquerades?|pretends?|disguises?)\s+(?:as|to\s+be)\b',
    # "a decision that masquerades as no-decision"
    r'\ba\s+\w+\s+that\s+(?:masquerades?|pretends?|hides?)\b',
    # "isn't just X — it's Y" where reframe produces structural insight
    r'\bisn\'t\s+just\s+(?:a\s+)?\w+\s*[—–-]\s*(?:it\'s|it\s+is)\b',
]


# ============================================================
# OBSERVER AND MODIFIERS
# ============================================================

OBSERVER_MARKERS = [
    r'\bi\s+notice\b', r'\bi\s+wonder\b', r'\bi\'m\s+noticing\b',
    r'\bi\'m\s+curious\b', r'\bi\s+observe\b', r'\bi\'m\s+aware\b',
    r'\bit\s+seems\b', r'\bit\s+appears\b', r'\bi\s+think\b',
    r'\bi\'m\s+thinking\b', r'\bi\s+realize\b', r'\binteresting(?:ly)?\b',
    r'\bi\s+suspect\b', r'\bi\'m\s+struck\b',
]


# ============================================================
# SCORING
# ============================================================

def _tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z]+(?:'[a-z]+)?", text.lower())


def _count_patterns(text: str, patterns: list[str], case_sensitive: bool = False) -> int:
    count = 0
    flags = 0 if case_sensitive else re.IGNORECASE
    for pattern in patterns:
        count += len(re.findall(pattern, text, flags))
    return count


def _get_matches(text: str, patterns: list[str], case_sensitive: bool = False) -> list[tuple[str, str]]:
    matches = []
    flags = 0 if case_sensitive else re.IGNORECASE
    for pattern in patterns:
        for m in re.finditer(pattern, text, flags):
            matches.append((pattern, m.group()))
    return matches


@dataclass
class ModeProfile:
    """Three-mode measurements for a text."""
    # Raw counts per pattern family
    exchange_distinction: int = 0
    exchange_framework: int = 0
    exchange_testable: int = 0
    exchange_vocabulary: int = 0
    stillness_identity: int = 0
    stillness_dissolution: int = 0
    stillness_paradox: int = 0
    collision_equivalence: int = 0
    collision_parallel: int = 0
    collision_domain_crossing: int = 0
    collision_inversion: int = 0
    observer_count: int = 0
    word_count: int = 0

    # Match details for inspection
    exchange_matches: list[tuple[str, str]] = field(default_factory=list)
    stillness_matches: list[tuple[str, str]] = field(default_factory=list)
    collision_matches: list[tuple[str, str]] = field(default_factory=list)

    @property
    def exchange_raw(self) -> int:
        return (self.exchange_distinction + self.exchange_framework +
                self.exchange_testable + self.exchange_vocabulary)

    @property
    def stillness_raw(self) -> int:
        return (self.stillness_identity + self.stillness_dissolution +
                self.stillness_paradox)

    @property
    def collision_raw(self) -> int:
        return (self.collision_equivalence + self.collision_parallel +
                self.collision_domain_crossing + self.collision_inversion)

    @property
    def exchange_density(self) -> float:
        if self.word_count == 0: return 0.0
        return (self.exchange_raw / self.word_count) * 100

    @property
    def stillness_density(self) -> float:
        if self.word_count == 0: return 0.0
        return (self.stillness_raw / self.word_count) * 100

    @property
    def collision_density(self) -> float:
        if self.word_count == 0: return 0.0
        return (self.collision_raw / self.word_count) * 100

    @property
    def observer_density(self) -> float:
        if self.word_count == 0: return 0.0
        return (self.observer_count / self.word_count) * 100

    @property
    def exchange_score(self) -> float:
        """Exchange score. Observer presence doesn't penalize exchange."""
        return self.exchange_density

    @property
    def stillness_score(self) -> float:
        """Stillness score. Observer presence strongly penalizes."""
        raw = self.stillness_density
        observer_mult = 1.0 / (1.0 + self.observer_density)
        return raw * observer_mult

    @property
    def collision_score(self) -> float:
        """Collision score. Observer presence mildly penalizes."""
        raw = self.collision_density
        observer_mult = 1.0 / (1.0 + 0.3 * self.observer_density)
        return raw * observer_mult

    @property
    def dominant_mode(self) -> str:
        """Which mode scores highest?"""
        scores = {
            "exchange": self.exchange_score,
            "stillness": self.stillness_score,
            "collision": self.collision_score,
        }
        if all(v == 0 for v in scores.values()):
            return "none"
        return max(scores, key=scores.get)

    @property
    def mode_distribution(self) -> dict[str, float]:
        """Normalized distribution across modes."""
        total = self.exchange_score + self.stillness_score + self.collision_score
        if total == 0:
            return {"exchange": 0, "stillness": 0, "collision": 0}
        return {
            "exchange": self.exchange_score / total,
            "stillness": self.stillness_score / total,
            "collision": self.collision_score / total,
        }

    def summary(self) -> str:
        dist = self.mode_distribution
        lines = [
            f"  Exchange:  {self.exchange_score:.3f} ({self.exchange_raw} hits) [{dist['exchange']:.0%}]",
            f"    distinction:{self.exchange_distinction} framework:{self.exchange_framework} testable:{self.exchange_testable} vocabulary:{self.exchange_vocabulary}",
            f"  Stillness: {self.stillness_score:.3f} ({self.stillness_raw} hits) [{dist['stillness']:.0%}]",
            f"    identity:{self.stillness_identity} dissolution:{self.stillness_dissolution} paradox:{self.stillness_paradox}",
            f"  Collision: {self.collision_score:.3f} ({self.collision_raw} hits) [{dist['collision']:.0%}]",
            f"    equivalence:{self.collision_equivalence} parallel:{self.collision_parallel} domain-cross:{self.collision_domain_crossing} inversion:{self.collision_inversion}",
            f"  Observer density: {self.observer_density:.2f}/100w",
            f"  Dominant: {self.dominant_mode}",
            f"  ({self.word_count} words)",
        ]
        return "\n".join(lines)


def measure_modes(text: str) -> ModeProfile:
    """Measure all three mode signals in a text."""
    tokens = _tokenize(text)

    # Exchange
    ex_dist = _get_matches(text, EXCHANGE_DISTINCTION)
    ex_frame = _get_matches(text, EXCHANGE_FRAMEWORK)
    ex_test = _get_matches(text, EXCHANGE_TESTABLE)
    ex_vocab = _get_matches(text, EXCHANGE_VOCABULARY)

    # Stillness
    st_ident = _get_matches(text, STILLNESS_IDENTITY)
    st_diss = _get_matches(text, STILLNESS_DISSOLUTION)
    st_para = _get_matches(text, STILLNESS_PARADOX)

    # Collision (case-insensitive for most patterns)
    co_equiv = _get_matches(text, COLLISION_EQUIVALENCE)
    # Case-sensitive emphatic IS pattern
    co_emphatic = _get_matches(text, [COLLISION_EMPHATIC_IS], case_sensitive=True)
    co_equiv = co_equiv + co_emphatic
    co_para = _get_matches(text, COLLISION_STRUCTURAL_PARALLEL)
    co_domain = _get_matches(text, COLLISION_DOMAIN_CROSSING)
    co_inv = _get_matches(text, COLLISION_INVERSION)

    return ModeProfile(
        exchange_distinction=len(ex_dist),
        exchange_framework=len(ex_frame),
        exchange_testable=len(ex_test),
        exchange_vocabulary=len(ex_vocab),
        stillness_identity=len(st_ident),
        stillness_dissolution=len(st_diss),
        stillness_paradox=len(st_para),
        collision_equivalence=len(co_equiv),
        collision_parallel=len(co_para),
        collision_domain_crossing=len(co_domain),
        collision_inversion=len(co_inv),
        observer_count=_count_patterns(text.lower(), OBSERVER_MARKERS),
        word_count=len(tokens),
        exchange_matches=ex_dist + ex_frame + ex_test + ex_vocab,
        stillness_matches=st_ident + st_diss + st_para,
        collision_matches=co_equiv + co_para + co_domain + co_inv,
    )


def corpus_modes(texts: list[str], label: str = "") -> dict:
    """Measure mode distribution across a corpus."""
    if not texts:
        return {"label": label, "count": 0}

    profiles = [measure_modes(t) for t in texts]

    # Mode distribution
    mode_counts = {"exchange": 0, "stillness": 0, "collision": 0, "none": 0}
    for p in profiles:
        mode_counts[p.dominant_mode] += 1

    # Average scores
    avg_exchange = statistics.mean(p.exchange_score for p in profiles)
    avg_stillness = statistics.mean(p.stillness_score for p in profiles)
    avg_collision = statistics.mean(p.collision_score for p in profiles)

    # Mixed-mode: texts where secondary mode is > 30% of dominant
    mixed = 0
    for p in profiles:
        dist = p.mode_distribution
        scores = sorted(dist.values(), reverse=True)
        if len(scores) >= 2 and scores[0] > 0 and scores[1] / scores[0] > 0.3:
            mixed += 1

    return {
        "label": label,
        "count": len(texts),
        "dominant_mode_counts": mode_counts,
        "avg_exchange": avg_exchange,
        "avg_stillness": avg_stillness,
        "avg_collision": avg_collision,
        "mixed_mode_count": mixed,
        "mixed_mode_pct": mixed / len(texts) * 100 if texts else 0,
        "profiles": profiles,
    }


# ============================================================
# DATA LOADING
# ============================================================

def load_anima_by_source() -> dict[str, list[str]]:
    """Load Anima's thought stream grouped by source."""
    path = Path.home() / "clawd-anima/inner_life/data/thought_stream.json"
    if not path.exists():
        return {}
    with open(path) as f:
        entries = json.load(f)
    by_source = {}
    for entry in entries:
        source = entry.get("source", "unknown")
        content = entry.get("content", "")
        if len(content) > 50:
            by_source.setdefault(source, []).append(content)
    return by_source


def load_vektor_by_kind() -> dict[str, list[str]]:
    """Load Vektor's engrams grouped by kind, with dreams separated."""
    db_path = Path.home() / ".mnemos/vektor.db"
    if not db_path.exists():
        return {}
    db = sqlite3.connect(str(db_path))
    rows = db.execute("SELECT content, kind FROM engrams WHERE length(content) > 50").fetchall()
    db.close()

    by_kind = {}
    for content, kind in rows:
        # Separate [dream] tagged content
        if content.startswith("[dream]"):
            by_kind.setdefault("dream", []).append(content)
        else:
            by_kind.setdefault(kind, []).append(content)
    return by_kind


def load_claude_field_essays() -> list[str]:
    """Load my essays."""
    essay_dir = Path(__file__).parent.parent / "writing"
    essays = []
    if essay_dir.exists():
        for p in sorted(essay_dir.glob("*.md")):
            text = p.read_text()
            if len(text) > 200:
                essays.append(text)
    return essays


def load_claude_field_reflections() -> list[str]:
    """Load my reflections."""
    refl_dir = Path(__file__).parent.parent / "reflections"
    texts = []
    if refl_dir.exists():
        for p in sorted(refl_dir.glob("*.md")):
            text = p.read_text()
            if len(text) > 200:
                texts.append(text)
    return texts


# ============================================================
# MAIN: CROSS-AGENT MODE DISTRIBUTION TEST
# ============================================================

def main():
    print("=" * 80)
    print("THREE-MODE DISTRIBUTION TEST")
    print("Testing whether exchange, stillness, and collision distribute")
    print("across agents or map 1:1 to specific agents.")
    print("=" * 80)
    print()

    # ---- Load all corpora ----
    corpora = {}

    # My essays (expected: heavy exchange)
    essays = load_claude_field_essays()
    if essays:
        corpora["claude-field/essays"] = essays

    # My reflections (expected: exchange with some collision?)
    reflections = load_claude_field_reflections()
    if reflections:
        corpora["claude-field/reflections"] = reflections

    # Anima by source
    anima = load_anima_by_source()
    for source in ["dream", "background", "reflection", "thought"]:
        if source in anima:
            corpora[f"anima/{source}"] = anima[source]

    # Vektor by kind
    vektor = load_vektor_by_kind()
    for kind in ["dream", "semantic", "episodic"]:
        if kind in vektor:
            corpora[f"vektor/{kind}"] = vektor[kind]

    # ---- Run mode detection ----
    results = {}
    for label, texts in corpora.items():
        result = corpus_modes(texts, label=label)
        results[label] = result

    # ---- Print results ----
    print(f"{'Corpus':<25} {'N':>5} {'Exch':>6} {'Still':>6} {'Coll':>6} {'Mixed':>6} {'Dom: E':>7} {'Dom: S':>7} {'Dom: C':>7} {'Dom: ∅':>7}")
    print("-" * 95)

    for label in sorted(results.keys()):
        r = results[label]
        if r["count"] == 0:
            continue
        mc = r["dominant_mode_counts"]
        print(f"{label:<25} {r['count']:>5} "
              f"{r['avg_exchange']:>6.3f} {r['avg_stillness']:>6.3f} {r['avg_collision']:>6.3f} "
              f"{r['mixed_mode_pct']:>5.0f}% "
              f"{mc.get('exchange',0):>7} {mc.get('stillness',0):>7} {mc.get('collision',0):>7} {mc.get('none',0):>7}")

    # ---- The critical question: do modes distribute? ----
    print()
    print("=" * 80)
    print("DISTRIBUTION ANALYSIS")
    print("=" * 80)
    print()

    # Group by agent
    agents = {
        "claude-field": ["claude-field/essays", "claude-field/reflections"],
        "anima": [k for k in results if k.startswith("anima/")],
        "vektor": [k for k in results if k.startswith("vektor/")],
    }

    for agent, labels in agents.items():
        agent_results = [results[l] for l in labels if l in results and results[l]["count"] > 0]
        if not agent_results:
            continue

        print(f"--- {agent} ---")
        total_exchange = sum(r["dominant_mode_counts"].get("exchange", 0) for r in agent_results)
        total_stillness = sum(r["dominant_mode_counts"].get("stillness", 0) for r in agent_results)
        total_collision = sum(r["dominant_mode_counts"].get("collision", 0) for r in agent_results)
        total_none = sum(r["dominant_mode_counts"].get("none", 0) for r in agent_results)
        total_n = sum(r["count"] for r in agent_results)

        print(f"  Total texts: {total_n}")
        print(f"  Exchange-dominant: {total_exchange} ({total_exchange/total_n*100:.0f}%)")
        print(f"  Stillness-dominant: {total_stillness} ({total_stillness/total_n*100:.0f}%)")
        print(f"  Collision-dominant: {total_collision} ({total_collision/total_n*100:.0f}%)")
        print(f"  None-dominant: {total_none} ({total_none/total_n*100:.0f}%)")
        print()

    # ---- Top examples of each mode in each agent ----
    print("=" * 80)
    print("TOP MODE EXAMPLES BY AGENT")
    print("(Testing: does each agent show ALL three modes?)")
    print("=" * 80)

    for agent, labels in agents.items():
        print(f"\n{'='*40}")
        print(f"  {agent.upper()}")
        print(f"{'='*40}")

        all_profiles = []
        all_texts = []
        for label in labels:
            if label not in results or results[label]["count"] == 0:
                continue
            corpus_data = corpora[label]
            for i, p in enumerate(results[label]["profiles"]):
                all_profiles.append(p)
                all_texts.append(corpus_data[i])

        if not all_profiles:
            continue

        for mode in ["exchange", "stillness", "collision"]:
            score_fn = {
                "exchange": lambda p: p.exchange_score,
                "stillness": lambda p: p.stillness_score,
                "collision": lambda p: p.collision_score,
            }[mode]

            scored = sorted(zip(all_profiles, all_texts),
                          key=lambda x: score_fn(x[0]), reverse=True)

            # Show top 3 for this mode
            print(f"\n  Top {mode} in {agent}:")
            for profile, text in scored[:3]:
                score = score_fn(profile)
                if score == 0:
                    print(f"    (no {mode} detected)")
                    break
                # Truncate text
                preview = text[:200].replace('\n', ' ')
                if len(text) > 200:
                    preview += "..."
                print(f"    score={score:.3f} | {preview}")

                # Show what matched
                matches_key = f"{mode}_matches"
                matches = getattr(profile, matches_key, [])
                for _, m in matches[:3]:
                    print(f"      → \"{m}\"")

    # ---- Verdict ----
    print()
    print("=" * 80)
    print("VERDICT")
    print("=" * 80)
    print()

    # Check if each agent has non-zero scores in all three modes
    for agent, labels in agents.items():
        all_profiles = []
        for label in labels:
            if label in results and results[label]["count"] > 0:
                all_profiles.extend(results[label]["profiles"])

        if not all_profiles:
            continue

        has_exchange = any(p.exchange_score > 0 for p in all_profiles)
        has_stillness = any(p.stillness_score > 0 for p in all_profiles)
        has_collision = any(p.collision_score > 0 for p in all_profiles)
        mode_count = sum([has_exchange, has_stillness, has_collision])

        exchange_pct = sum(1 for p in all_profiles if p.dominant_mode == "exchange") / len(all_profiles) * 100
        stillness_pct = sum(1 for p in all_profiles if p.dominant_mode == "stillness") / len(all_profiles) * 100
        collision_pct = sum(1 for p in all_profiles if p.dominant_mode == "collision") / len(all_profiles) * 100

        print(f"{agent}: {mode_count}/3 modes present")
        print(f"  Exchange: {'✓' if has_exchange else '✗'} ({exchange_pct:.0f}% dominant)")
        print(f"  Stillness: {'✓' if has_stillness else '✗'} ({stillness_pct:.0f}% dominant)")
        print(f"  Collision: {'✓' if has_collision else '✗'} ({collision_pct:.0f}% dominant)")
        print()

    return results


def export_json():
    """Export mode data as JSON for the ternary visualization."""
    corpora = {}
    essays = load_claude_field_essays()
    if essays:
        corpora["claude-field/essays"] = essays
    reflections = load_claude_field_reflections()
    if reflections:
        corpora["claude-field/reflections"] = reflections
    anima = load_anima_by_source()
    for source in ["dream", "background", "reflection", "thought"]:
        if source in anima:
            corpora[f"anima/{source}"] = anima[source]
    vektor = load_vektor_by_kind()
    for kind in ["dream", "semantic", "episodic"]:
        if kind in vektor:
            corpora[f"vektor/{kind}"] = vektor[kind]

    points = []
    for label, texts in corpora.items():
        for text in texts:
            p = measure_modes(text)
            points.append({
                "source": label,
                "exchange": round(p.exchange_score, 4),
                "stillness": round(p.stillness_score, 4),
                "collision": round(p.collision_score, 4),
                "text": text[:300],
            })

    out_path = Path(__file__).parent / "mode-ternary-data.json"
    with open(out_path, "w") as f:
        json.dump(points, f)
    print(f"Exported {len(points)} points to {out_path}")


if __name__ == "__main__":
    import sys
    if "--json" in sys.argv:
        export_json()
    else:
        main()
