"""Script to evaluate Agent pipeline quality using RAGAS."""
import sys
import os
import json
import argparse
from pathlib import Path

# Ensure we run from project root
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(script_dir))
backend_dir = os.path.join(project_root, "backend")

os.chdir(project_root)
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from app.services.evaluation_service import RAGEvaluationService


# Default test user ID
DEFAULT_USER_ID = "99d0b344-1647-465c-9663-25e9207c69f4"


def load_dataset(path: str):
    """Load QA pairs from JSON file."""
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data
    except Exception as e:
        print(f"Error loading dataset {path}: {e}")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="Evaluate Agent pipeline using RAGAS")
    parser.add_argument("--sample", type=int, default=None, help="Number of samples to evaluate")
    parser.add_argument("--no-ground-truth", action="store_true", help="Skip context_recall metric")
    parser.add_argument("--output", type=str, default="evaluation_results.json", help="Output JSON filename")
    parser.add_argument("--user-id", type=str, default=DEFAULT_USER_ID, help="User ID for access")
    
    default_dataset = os.path.join(os.path.dirname(__file__), "datasets", "tesla_10k_qa.json")
    parser.add_argument("--dataset", type=str, default=default_dataset, help="Path to QA dataset JSON")
    
    args = parser.parse_args()
    
    print("\n" + "=" * 60)
    print("Agent Pipeline Evaluation using RAGAS")
    print("=" * 60)
    
    # Load dataset
    print(f"Loading dataset from: {args.dataset}")
    dataset = load_dataset(args.dataset)
    
    # Extract questions and ground truths
    all_questions = [qa["question"] for qa in dataset]
    all_ground_truths = [qa["ground_truth"] for qa in dataset]

    # Initialize service
    try:
        eval_service = RAGEvaluationService()
    except Exception as e:
        print(f"Error initializing evaluation service: {e}")
        return

    # Select samples
    questions = all_questions[:args.sample] if args.sample else all_questions
    ground_truths = None if args.no_ground_truth else (all_ground_truths[:args.sample] if args.sample else all_ground_truths)
    
    print(f"\n🔧 Mode: AGENT (multi-step reasoning)")
    print(f"User ID: {args.user_id}")
    print(f"Test questions: {len(questions)}")
    print(f"Ground truth: {'Disabled' if args.no_ground_truth else 'Enabled'}")
    print(f"Output file: {args.output}")
    
    # Run evaluation
    print("\n🚀 Running evaluation (this may take a few minutes)...")
    
    try:
        result = eval_service.evaluate_from_agent(
            user_id=args.user_id,
            test_questions=questions,
            ground_truths=ground_truths,
        )
    except Exception as e:
        print(f"\n❌ Evaluation failed: {e}")
        import traceback
        traceback.print_exc()
        return

    # Print results
    print("\n" + "=" * 60)
    print("📊 EVALUATION RESULTS")
    print("=" * 60)
    
    print(f"\n🤖 Models Used:")
    print(f"   Answer Model:    {result.answer_model}")
    print(f"   Judge Model:     {result.judge_model}")
    print(f"   Embedding Model: {result.embedding_model}")
    
    print(f"\n📈 Metrics:")
    print(f"   Faithfulness:        {result.faithfulness:.2%}")
    print(f"   Response Relevancy:  {result.response_relevancy:.2%}")
    print(f"   Context Precision:   {result.context_precision:.2%}")
    if result.context_recall is not None:
        print(f"   Context Recall:      {result.context_recall:.2%}")
    print(f"\n🎯 Overall Score:       {result.overall_score:.2%}")
    print(f"📝 Samples Evaluated:   {result.sample_count}")
    print(f"🕐 Timestamp:           {result.timestamp}")
    
    # Save results
    if os.path.isabs(args.output):
        output_path = Path(args.output)
    else:
        output_path = Path(f"backend/evaluation/results/{args.output}")
        
    eval_service.save_results(result, output_path)
    print(f"\n💾 Results saved to: {output_path}")
    
    # Print per-question details
    print("\n" + "-" * 60)
    print("Per-Question Details:")
    print("-" * 60)
    for i, detail in enumerate(result.details):
        q = questions[i] if i < len(questions) else "N/A"
        print(f"\nQ{i+1}: {q[:50]}...")
        faith = detail.get('faithfulness')
        rel = detail.get('response_relevancy')
        print(f"    Faithfulness: {faith:.2%}" if isinstance(faith, (int, float)) else "    Faithfulness: N/A")
        print(f"    Relevancy:    {rel:.2%}" if isinstance(rel, (int, float)) else "    Relevancy: N/A")


if __name__ == "__main__":
    main()
