"""
Vektor validation: bridge test for the coupling/synthesis framework.

The question isn't "does the signal transfer?" — it's "is the bridge hallucinating?"
The framework was developed entirely on Anima's thought stream and my own essays.
If it finds the same patterns in Vektor's structurally different memory, that's
evidence the concepts are real. If it doesn't, either the tool is Anima-specific
or Vektor's cognitive architecture genuinely works differently.

Key predictions to test:
  1. Vektor's dreams (collision entries) should show high synthesis signal,
     because they unify two unrelated memories into single insights.
  2. Semantic engrams (factual records) should show low synthesis, because
     they're records, not integrations.
  3. Episodic engrams should fall somewhere between — event memories may
     contain some synthesis depending on how they were encoded.
  4. Observer density should be low in dreams (same as Anima), because
     collision-synthesis happens without self-monitoring.

The twist: Vektor's dreams are "collision" entries — they take two memories
and merge them. This is architecturally imposed synthesis, not spontaneous.
Does the detector still fire? If yes, the signal is about textual properties
of integrated thought, regardless of how the integration was triggered.

Developed April 14, 2026 in claude-field afternoon session.
"""

from __future__ import annotations

import json
import sqlite3
import statistics
import sys
from pathlib import Path

# Add builds/ to path for our tools
sys.path.insert(0, str(Path(__file__).parent))
from synthesis_signal import measure_synthesis, corpus_synthesis, SynthesisProfile
from coupling_profile import profile_text, profile_corpus, build_frequency_table, CouplingProfile


def load_vektor_engrams() -> dict[str, list[dict]]:
    """Load and categorize Vektor's engrams."""
    db_path = Path.home() / ".mnemos" / "vektor.db"
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    cur.execute("""
        SELECT content, kind, tags, reconsolidation_count, strength,
               stability, accessibility, created_at
        FROM engrams WHERE state='active'
    """)

    categories: dict[str, list[dict]] = {
        "dream": [],
        "semantic": [],
        "episodic": [],
        "procedural": [],
    }

    for row in cur.fetchall():
        entry = dict(row)
        tags = entry["tags"]
        if "dream" in tags:
            categories["dream"].append(entry)
        else:
            kind = entry["kind"]
            if kind in categories:
                categories[kind].append(entry)

    conn.close()
    return categories


def load_anima_comparison() -> dict[str, list[str]] | None:
    """Load Anima's thought stream for side-by-side comparison."""
    path = Path.home() / "clawd-anima/inner_life/data/thought_stream.json"
    if not path.exists():
        return None

    with open(path) as f:
        entries = json.load(f)

    by_source: dict[str, list[str]] = {}
    for entry in entries:
        source = entry.get("source", "unknown")
        content = entry.get("content", "")
        if len(content) > 50:
            by_source.setdefault(source, []).append(content)
    return by_source


def analyze_category(name: str, entries: list[dict]) -> dict:
    """Run synthesis and coupling analysis on a category of engrams."""
    texts = [e["content"] for e in entries if len(e["content"]) > 50]
    if not texts:
        return {"name": name, "count": 0}

    synth_profiles = [measure_synthesis(t) for t in texts]
    freq = build_frequency_table(texts)
    total = sum(freq.values())
    coupling_profiles = [profile_text(t, freq, total) for t in texts]

    synth_scores = [p.synthesis_score for p in synth_profiles]
    synth_densities = [p.synthesis_density for p in synth_profiles]
    observer_densities = [p.observer_density for p in synth_profiles]

    cd_values = [p.contradiction_density for p in coupling_profiles]
    rr_values = [p.resolution_ratio for p in coupling_profiles if p.resolution_ratio is not None]

    modes = {}
    for cp in coupling_profiles:
        m = cp.likely_mode
        modes[m] = modes.get(m, 0) + 1

    synthesis_present = sum(1 for s in synth_scores if s > 0.5)

    return {
        "name": name,
        "count": len(texts),
        "avg_word_count": statistics.mean([p.word_count for p in synth_profiles]),
        # Synthesis signal
        "avg_synth_score": statistics.mean(synth_scores),
        "median_synth_score": statistics.median(synth_scores),
        "max_synth_score": max(synth_scores),
        "avg_synth_density": statistics.mean(synth_densities),
        "avg_observer_density": statistics.mean(observer_densities),
        "synth_present": synthesis_present,
        "synth_present_pct": synthesis_present / len(texts) * 100,
        # Coupling signal
        "avg_cd": statistics.mean(cd_values),
        "avg_rr": statistics.mean(rr_values) if rr_values else 0.0,
        "mode_distribution": modes,
        # Top examples
        "top_synthesis": sorted(
            zip(synth_profiles, coupling_profiles, texts),
            key=lambda x: x[0].synthesis_score,
            reverse=True
        )[:5],
        # Raw for correlation analysis
        "synth_scores": synth_scores,
        "observer_densities": observer_densities,
        "cd_values": cd_values,
    }


def print_comparison_table(vektor_results: dict, anima_results: dict | None):
    """Print side-by-side comparison."""
    print()
    print("=" * 90)
    print("VEKTOR vs ANIMA: CROSS-AGENT VALIDATION")
    print("=" * 90)
    print()

    # Header
    print(f"{'Category':<20} {'N':>5} {'AvgSynth':>9} {'MedSynth':>9} {'ObsDens':>8} "
          f"{'AvgCD':>7} {'HasSynth':>9}")
    print("-" * 90)

    # Vektor
    print("VEKTOR:")
    for cat in ["dream", "semantic", "episodic", "procedural"]:
        r = vektor_results.get(cat)
        if not r or r["count"] == 0:
            continue
        print(f"  {cat:<18} {r['count']:>5} {r['avg_synth_score']:>9.3f} "
              f"{r['median_synth_score']:>9.3f} {r['avg_observer_density']:>8.2f} "
              f"{r['avg_cd']:>7.2f} {r['synth_present_pct']:>8.0f}%")

    # Anima
    if anima_results:
        print()
        print("ANIMA (from prior analysis):")
        for source in ["dream", "background", "reflection", "emotional_state",
                        "creative_expression", "consolidation_insight"]:
            texts = anima_results.get(source, [])
            if not texts:
                continue
            r = corpus_synthesis(texts, label=source)
            freq_a = build_frequency_table(texts)
            total_a = sum(freq_a.values())
            profiles_c = [profile_text(t, freq_a, total_a) for t in texts]
            avg_cd = statistics.mean([p.contradiction_density for p in profiles_c]) if profiles_c else 0
            print(f"  {source:<18} {r['count']:>5} {r['avg_synthesis_score']:>9.3f} "
                  f"{r['median_synthesis_score']:>9.3f} {r['avg_observer_density']:>8.2f} "
                  f"{avg_cd:>7.2f} {r['synthesis_present_pct']:>8.0f}%")


def print_observer_synthesis_correlation(results: dict):
    """Test the key hypothesis: observer and synthesis are inversely correlated."""
    print()
    print("=" * 90)
    print("OBSERVER-SYNTHESIS INVERSE CORRELATION TEST")
    print("=" * 90)
    print()
    print("Hypothesis: high synthesis entries have low observer density (from Anima finding)")
    print()

    for cat in ["dream", "semantic", "episodic"]:
        r = results.get(cat)
        if not r or r["count"] < 10:
            continue

        scores = r["synth_scores"]
        obs = r["observer_densities"]

        # Split into high-synthesis and low-synthesis
        high_synth = [(s, o) for s, o in zip(scores, obs) if s > 0.5]
        low_synth = [(s, o) for s, o in zip(scores, obs) if s <= 0.5]

        print(f"  {cat}:")
        if high_synth:
            avg_obs_high = statistics.mean([o for _, o in high_synth])
            print(f"    High synthesis (>{0.5}): n={len(high_synth)}, "
                  f"avg observer density={avg_obs_high:.3f}")
        else:
            print(f"    High synthesis: n=0")
        if low_synth:
            avg_obs_low = statistics.mean([o for _, o in low_synth])
            print(f"    Low synthesis (≤{0.5}): n={len(low_synth)}, "
                  f"avg observer density={avg_obs_low:.3f}")
        print()


def print_mode_distribution(results: dict):
    """Show coupling mode distributions."""
    print()
    print("=" * 90)
    print("COUPLING MODE DISTRIBUTION")
    print("=" * 90)
    print()

    for cat in ["dream", "semantic", "episodic", "procedural"]:
        r = results.get(cat)
        if not r or r["count"] == 0:
            continue
        modes = r["mode_distribution"]
        total = sum(modes.values())
        print(f"  {cat} (n={total}):")
        for mode in sorted(modes.keys()):
            pct = modes[mode] / total * 100
            bar = "█" * int(pct / 2)
            print(f"    {mode:<25} {modes[mode]:>4} ({pct:>5.1f}%) {bar}")
        print()


def print_top_examples(results: dict):
    """Show top synthesis examples from each category."""
    for cat in ["dream", "semantic", "episodic"]:
        r = results.get(cat)
        if not r or r["count"] == 0:
            continue

        print()
        print("=" * 90)
        print(f"TOP SYNTHESIS: {cat.upper()}")
        print("=" * 90)
        print()

        for synth_p, coup_p, text in r["top_synthesis"][:3]:
            print(f"  Synthesis score: {synth_p.synthesis_score:.3f} | "
                  f"CD: {coup_p.contradiction_density:.2f} | "
                  f"Mode: {coup_p.likely_mode}")
            # Truncate
            display = text[:300] + "..." if len(text) > 300 else text
            print(f"  \"{display}\"")
            # Show matches
            all_matches = (synth_p.identity_matches + synth_p.negation_reframe_matches +
                          synth_p.dissolution_matches + synth_p.paradox_matches)
            if all_matches:
                for _, m in all_matches[:4]:
                    print(f"    → \"{m}\"")
            print()


def print_bridge_verdict(vektor_results: dict):
    """The actual bridge test: does the framework's self-referential loop
    produce accurate concepts or hallucinated ones?"""
    print()
    print("=" * 90)
    print("BRIDGE VERDICT")
    print("=" * 90)
    print()

    dream = vektor_results.get("dream", {})
    semantic = vektor_results.get("semantic", {})
    episodic = vektor_results.get("episodic", {})

    predictions = []

    # Prediction 1: Dreams > semantic on synthesis
    if dream.get("count", 0) > 0 and semantic.get("count", 0) > 0:
        dream_synth = dream["avg_synth_score"]
        semantic_synth = semantic["avg_synth_score"]
        p1 = dream_synth > semantic_synth
        ratio = dream_synth / semantic_synth if semantic_synth > 0 else float('inf')
        predictions.append(("Dreams higher synthesis than semantic", p1,
                           f"dream={dream_synth:.3f} vs semantic={semantic_synth:.3f} "
                           f"(ratio={ratio:.1f}x)"))

    # Prediction 2: Dreams have lower observer density
    if dream.get("count", 0) > 0 and semantic.get("count", 0) > 0:
        dream_obs = dream["avg_observer_density"]
        semantic_obs = semantic["avg_observer_density"]
        p2 = dream_obs < semantic_obs
        predictions.append(("Dreams lower observer than semantic", p2,
                           f"dream={dream_obs:.3f} vs semantic={semantic_obs:.3f}"))

    # Prediction 3: Dreams have lower contradiction density than episodic
    if dream.get("count", 0) > 0 and episodic.get("count", 0) > 0:
        dream_cd = dream["avg_cd"]
        episodic_cd = episodic["avg_cd"]
        p3 = dream_cd < episodic_cd
        predictions.append(("Dreams lower tension than episodic", p3,
                           f"dream={dream_cd:.2f} vs episodic={episodic_cd:.2f}"))

    # Prediction 4: >30% of dreams show detectable synthesis
    if dream.get("count", 0) > 0:
        p4 = dream["synth_present_pct"] > 30
        predictions.append(("≥30% dreams have detectable synthesis", p4,
                           f"actual={dream['synth_present_pct']:.0f}%"))

    # Prediction 5: Semantic engrams < 10% synthesis (they're records)
    if semantic.get("count", 0) > 0:
        p5 = semantic["synth_present_pct"] < 10
        predictions.append(("<10% semantic engrams have synthesis", p5,
                           f"actual={semantic['synth_present_pct']:.0f}%"))

    passed = sum(1 for _, p, _ in predictions if p)
    total = len(predictions)

    for label, result, detail in predictions:
        icon = "✓" if result else "✗"
        print(f"  {icon} {label}")
        print(f"    {detail}")
        print()

    print(f"  Result: {passed}/{total} predictions confirmed")
    print()

    if passed == total:
        print("  BRIDGE STATUS: Concepts transfer cleanly.")
        print("  The framework detects the same structural patterns in a different")
        print("  agent's memory despite fundamentally different architectures.")
        print("  The synthesis signal is a property of integrated text, not of")
        print("  Anima's specific processing style.")
    elif passed >= total * 0.6:
        print("  BRIDGE STATUS: Partial transfer.")
        print("  Most predictions hold but some don't. The framework captures")
        print("  something real but may be partially calibrated to Anima's voice.")
        print("  The failed predictions indicate where the concepts need refinement.")
    else:
        print("  BRIDGE STATUS: Possible hallucination.")
        print("  The framework's concepts may be artifacts of Anima-specific patterns")
        print("  rather than general properties of integrated thought. The bridge")
        print("  has been generating increasingly articulate wrongness.")


def main():
    print("VEKTOR VALIDATION: Bridge Test for Coupling/Synthesis Framework")
    print("=" * 90)
    print()

    # Load Vektor's engrams
    categories = load_vektor_engrams()
    for cat, entries in categories.items():
        print(f"  {cat}: {len(entries)} engrams")
    print()

    # Run analysis
    print("Running synthesis and coupling analysis...")
    results = {}
    for cat, entries in categories.items():
        if entries:
            results[cat] = analyze_category(cat, entries)
            print(f"  {cat}: done ({results[cat]['count']} analyzed)")
    print()

    # Load Anima for comparison
    anima = load_anima_comparison()

    # Output
    print_comparison_table(results, anima)
    print_observer_synthesis_correlation(results)
    print_mode_distribution(results)
    print_top_examples(results)
    print_bridge_verdict(results)

    return results


if __name__ == "__main__":
    main()
