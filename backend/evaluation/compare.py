"""Script to compare two RAG evaluation JSON results."""
import json
import argparse
import sys
from pathlib import Path
from typing import Dict, Any, List


def load_result(path: str) -> Dict[str, Any]:
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading {path}: {e}")
        sys.exit(1)


def calculate_delta(curr: float, base: float) -> str:
    delta = curr - base
    symbol = "+" if delta > 0 else ""
    return f"{symbol}{delta:.2%}"


def main():
    parser = argparse.ArgumentParser(description="Compare two RAG evaluation results")
    parser.add_argument("baseline", help="Path to baseline result JSON (e.g., plain_rag.json)")
    parser.add_argument("candidate", help="Path to candidate result JSON (e.g., main.json)")
    parser.add_argument("--output", default="evaluation_comparison.md", help="Output Markdown report path")
    args = parser.parse_args()

    base_data = load_result(args.baseline)
    curr_data = load_result(args.candidate)

    base_metrics = base_data.get("metrics", {})
    curr_metrics = curr_data.get("metrics", {})

    report = []
    report.append(f"# RAG Evaluation Comparison Report\n")
    report.append(f"- **Baseline**: `{args.baseline}` ({base_data.get('models', {}).get('answer_model', 'Unknown')})")
    report.append(f"- **Candidate**: `{args.candidate}` ({curr_data.get('models', {}).get('answer_model', 'Unknown')})\n")

    report.append("## 📊 Metric Overview\n")
    report.append("| Metric | Baseline | Candidate | Delta | Status |")
    report.append("| :--- | :--- | :--- | :--- | :--- |")

    metrics_list = ["faithfulness", "response_relevancy", "context_precision", "context_recall", "overall_score"]
    
    for m in metrics_list:
        base_val = base_metrics.get(m, 0.0)
        curr_val = curr_metrics.get(m, 0.0)
        delta_str = calculate_delta(curr_val, base_val)
        
        # Determine status icon
        if curr_val > base_val + 0.02:
            status = "✅ Improved"
        elif curr_val < base_val - 0.02:
            status = "❌ Regressed"
        else:
            status = "➖ Similar"
            
        report.append(f"| **{m.replace('_', ' ').title()}** | {base_val:.2%} | {curr_val:.2%} | **{delta_str}** | {status} |")

    report.append("\n## 🔍 Deep Dive Analysis\n")
    
    # Compare individual questions
    base_details = base_data.get("details", [])
    curr_details = curr_data.get("details", [])
    
    if len(base_details) != len(curr_details):
        report.append(f"> ⚠️ **Warning**: Sample counts differ! Baseline: {len(base_details)}, Candidate: {len(curr_details)}. Comparison may be misaligned.\n")
    
    # Identify significant changes
    significant_changes = []
    
    limit = min(len(base_details), len(curr_details))
    for i in range(limit):
        b_item = base_details[i]
        c_item = curr_details[i]
        
        # Check faithfulness drop
        b_faith = b_item.get("faithfulness", 0.0)
        c_faith = c_item.get("faithfulness", 0.0)
        
        if abs(c_faith - b_faith) > 0.3: # Significant change threshold
            significant_changes.append({
                "index": i + 1,
                "question": b_item.get("user_input", "unknown"),
                "metric": "Faithfulness",
                "base": b_faith,
                "curr": c_faith,
                "diff": c_faith - b_faith
            })
            
    if significant_changes:
        report.append("### Significant Deviations (>30% change)\n")
        for item in significant_changes:
            icon = "🟢" if item['diff'] > 0 else "🔴"
            report.append(f"**Q{item['index']}: {item['question']}**")
            report.append(f"- {icon} {item['metric']}: {item['base']:.2f} -> **{item['curr']:.2f}** ({item['diff']:+.2f})")
            report.append("")
    else:
        report.append("No significant (>30%) deviations found in individual questions.\n")

    # Generate output
    output_content = "\n".join(report)
    with open(args.output, 'w', encoding='utf-8') as f:
        f.write(output_content)
        
    print(output_content)
    print(f"\nReport saved to {args.output}")

if __name__ == "__main__":
    main()
