"""
FlyRank Organic SEO Audit & Refresh Triager (MVP Agent)
Author: Oluomachukwu Emenike
"""

import sys
import argparse
from pathlib import Path
import numpy as np
import pandas as pd


class SEOAuditAgent:
    def __init__(self, data_path: str, output_dir: str = "work/outputs"):
        self.data_path = Path(data_path)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.receipt_path = self.output_dir / "agent_audit_receipt.md"

    def tool_validate_hygiene(self, df: pd.DataFrame) -> pd.DataFrame:
        print("[TOOL 1: Validate Hygiene] Checking data contract...")
        forbidden = ["trend_direction", "trend_pct", "impressions_last_30d", "clicks_last_30d"]
        found_forbidden = [c for c in forbidden if c in df.columns]
        if found_forbidden:
            print(f"  [GUARDRAIL] Quarantined post-window leakage columns: {found_forbidden}")

        df["has_position_data"] = (df["avg_position"] > 0).astype(int)
        df["clean_position"] = df["avg_position"].replace(0, np.nan)
        median_pos = df["clean_position"].median()
        df["clean_position"] = df["clean_position"].fillna(median_pos)
        print(f"  [HYGIENE PASS] Replaced 0s in avg_position with median: {median_pos:.1f}")

        for col in ["ctr", "impressions_90d", "word_count"]:
            if col in df.columns:
                df[f"has_{col}"] = df[col].notna().astype(int)
                df[col] = df[col].fillna(df[col].median())

        return df

    def tool_compute_triage(self, df: pd.DataFrame) -> pd.DataFrame:
        print("[TOOL 2: Scoring Engine] Calculating cohort benchmarks & missed clicks...")
        def cohort_ctr(pos):
            if pos <= 3: return 2.71
            elif pos <= 5: return 0.23
            elif pos <= 10: return 0.14
            elif pos <= 20: return 0.10
            elif pos <= 50: return 0.03
            else: return 0.00

        df["expected_ctr"] = df["clean_position"].apply(cohort_ctr)
        vol_threshold = df["impressions_90d"].quantile(0.60)
        mask = (
            (df["clean_position"] >= 1.0) &
            (df["clean_position"] <= 10.0) &
            (df["impressions_90d"] >= vol_threshold) &
            (df["ctr"] < df["expected_ctr"])
        )

        candidates = df[mask].copy()
        candidates["missed_clicks"] = (
            (candidates["expected_ctr"] - candidates["ctr"]).clip(lower=0) / 100.0
        ) * candidates["impressions_90d"]

        max_missed = candidates["missed_clicks"].max()
        candidates["priority_score"] = ((candidates["missed_clicks"] / (max_missed + 1e-9)) * 100.0).round(2)
        candidates["recommended_action"] = "OPTIMIZE_METADATA_SNIPPET"
        candidates["reason_code"] = "HIGH_IMP_LOW_CTR_PAGE1"

        return candidates.sort_values(by="priority_score", ascending=False).reset_index(drop=True)

    def tool_generate_receipt(self, ranked_df: pd.DataFrame) -> Path:
        print("[TOOL 3: File Output] Generating markdown audit receipt...")
        top_picks = ranked_df.head(5)

        lines = [
            "# FlyRank Autonomous Audit Receipt",
            "**Audit Status:** Execution Successful",
            f"**Total High-Impact Queue Size:** {len(ranked_df):,} URLs",
            "",
            "## Top Prioritized URLs for Refresh",
            "",
            "| Content ID | Clean Pos | 90d Impressions | Observed CTR | Expected CTR | Priority Score | Action |",
            "|---|---|---|---|---|---|---|",
        ]

        for _, r in top_picks.iterrows():
            cid = str(r.get("content_id", "N/A"))
            lines.append(
                f"| {cid} | {r['clean_position']:.1f} | {int(r['impressions_90d']):,} | "
                f"{r['ctr']:.2f}% | {r['expected_ctr']:.2f}% | {r['priority_score']} | `{r['recommended_action']}` |"
            )

        lines.extend([
            "",
            "## Skepticism & Verification Notes",
            "- **SERP Layout Distortion:** High-ranking pages must be visually checked for AI Overviews or ad clusters before rewriting snippets.",
            "- **Intent Divergence:** Keywords with informational or competitor navigational intent will naturally depress CTR.",
            "- **Human-in-the-Loop Safe Mode:** 0 autonomous CMS modifications performed. All suggested actions require human approval.",
            "",
            "```json",
            "{\n  \"status\": \"AUDIT_COMPLETE\",\n  \"top_asset\": \"" + str(top_picks.iloc[0]['content_id']) + "\",\n  \"highest_score\": " + str(top_picks.iloc[0]['priority_score']) + "\n}",
            "```"
        ])

        self.receipt_path.write_text("\n".join(lines), encoding="utf-8")
        print(f"  [SUCCESS] Written audit receipt to {self.receipt_path}")
        return self.receipt_path

    def run(self):
        print("=== INITIALIZING FLYRANK TRIAGER AGENT ===")
        if not self.data_path.exists():
            print(f"[ERROR] Source dataset not found: {self.data_path}")
            sys.exit(1)

        raw_df = pd.read_csv(self.data_path)
        print(f"[DATA INTAKE] Ingested {len(raw_df):,} rows from {self.data_path}")
        clean_df = self.tool_validate_hygiene(raw_df)
        ranked_df = self.tool_compute_triage(clean_df)
        out_file = self.tool_generate_receipt(ranked_df)
        print("=== AGENT RUN COMPLETED SUCCESSFULLY ===")
        print(f"Audit report available at: {out_file}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run FlyRank Triage Agent")
    parser.add_argument("--data", default="data/raw/content_refresh_anonymized.csv", help="Path to input data CSV")
    args = parser.parse_args()

    agent = SEOAuditAgent(data_path=args.data)
    agent.run()
