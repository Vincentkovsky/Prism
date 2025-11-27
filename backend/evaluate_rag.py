"""Script to evaluate RAG pipeline quality using RAGAS."""
import sys
import os

# Ensure we run from project root for correct ChromaDB path resolution
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(script_dir)
os.chdir(project_root)
sys.path.insert(0, "backend")

from pathlib import Path
from app.services.rag_service import RAGService
from app.services.evaluation_service import RAGEvaluationService, EvaluationSample

print(f"Working directory: {os.getcwd()}")

# Test configuration - update these with your actual IDs
DOCUMENT_ID = "bbb5448f-cb96-40a5-8791-256e3d27dedb"
USER_ID = "99d0b344-1647-465c-9663-25e9207c69f4"

# Bitcoin Whitepaper QA Dataset (30 questions)
BITCOIN_QA_DATASET = [
    # 摘要与简介 (Abstract & Introduction)
    {
        "question": "现有的电子现金系统有什么主要问题？",
        "answer": "现有的系统主要依靠金融机构作为可信的第三方来处理电子支付，这使得完全不可逆的交易变得不可能，因为金融机构无法避免调解纠纷。"
    },
    {
        "question": "引入第三方的弊端是什么？",
        "answer": "调解的成本增加了交易成本，限制了最小实际交易规模，切断了进行小额随意交易的可能性，并且丧失了为不可逆服务进行不可逆支付的能力。"
    },
    {
        "question": "中本聪提出的解决方案核心是什么？",
        "answer": "通过使用点对点网络来解决双重支付问题。"
    },
    {
        "question": "这个系统需要建立在信任之上吗？",
        "answer": "不需要，这是一个基于密码学证明而非信任的电子支付系统。"
    },
    {
        "question": "最长的链条证明了什么？",
        "answer": "最长的链条不仅作为所目击事件顺序的证明，还证明了它来自最大的 CPU 算力池。"
    },
    # 交易 (Transactions)
    {
        "question": "在这篇论文中，电子货币是如何定义的？",
        "answer": "电子货币被定义为一连串的数字签名。"
    },
    {
        "question": "所有者如何将比特币转移给下一个人？",
        "answer": "通过对上一次交易的哈希值和下一个所有者的公钥进行数字签名，并将这些添加到货币的末尾。"
    },
    {
        "question": "在没有第三方的情况下，收款人面临的主要问题是什么？",
        "answer": "收款人无法验证其中一位所有者是否没有双重支付该货币。"
    },
    {
        "question": "传统的铸币厂（Mint）模型有什么问题？",
        "answer": "整个货币系统的命运取决于运行铸币厂的公司，每一笔交易都必须经过它们，就像银行一样。"
    },
    {
        "question": "如何在没有信任方的情况下确认不存在某笔交易？",
        "answer": "必须公开宣布交易，并且参与者需要同意接收顺序的单一历史记录。"
    },
    # 时间戳服务器与工作量证明 (Timestamp Server & Proof-of-Work)
    {
        "question": "时间戳服务器是如何工作的？",
        "answer": "它获取一组要加盖时间戳的项目的哈希值，并广泛发布该哈希值（如在报纸或 Usenet 帖子中）。"
    },
    {
        "question": "比特币系统使用什么样的工作量证明系统？",
        "answer": "使用类似于 Adam Back 的 Hashcash 的工作量证明系统。"
    },
    {
        "question": "工作量证明具体涉及什么操作？",
        "answer": "涉及扫描一个值，使得该值被哈希（如使用 SHA-256）后，哈希值以一定数量的零比特开始。"
    },
    {
        "question": "工作量证明如何解决多数决策中的代表性问题？",
        "answer": "工作量证明本质上是一个 CPU 一票（one-CPU-one-vote），防止了拥有许多 IP 地址的人破坏规则。"
    },
    {
        "question": "攻击者想要修改过去的区块需要做什么？",
        "answer": "攻击者必须重做该区块及其后所有区块的工作量证明，并追上并超越诚实节点的工作量。"
    },
    {
        "question": "系统如何应对硬件速度的提升？",
        "answer": "工作量证明的难度由移动平均值决定，目标是每小时生成平均数量的区块；如果生成太快，难度就会增加。"
    },
    # 网络与激励 (Network & Incentive)
    {
        "question": "运行网络的步骤是什么？",
        "answer": "新交易向所有节点广播；每个节点将新交易收集到一个区块中；每个节点为该区块寻找困难的工作量证明；当找到工作量证明时，该区块广播给所有节点；节点仅在交易有效且未花费时接受区块；节点通过使用该区块的哈希作为上一哈希来制造新区块，以表示接受。"
    },
    {
        "question": "如果两个节点同时广播不同版本的下一个区块会发生什么？",
        "answer": "节点会处理先接收到的那个，但会保留另一个分支以防它变得更长；当发现下一个工作量证明且一个分支变得更长时，僵局就会被打破。"
    },
    {
        "question": "第一笔交易有什么特殊之处？",
        "answer": "区块中的第一笔交易是一笔特殊交易，它启动了一枚由区块创建者拥有的新货币。"
    },
    {
        "question": "当既定的硬币数量进入流通后，激励机制会发生什么变化？",
        "answer": "激励可以完全转变为交易费，并且完全没有通货膨胀。"
    },
    {
        "question": "激励机制如何帮助节点保持诚实？",
        "answer": "如果攻击者拥有超过诚实节点的算力，他会发现遵守规则（获得新币）比破坏系统和自己的财富更获利。"
    },
    # 存储与验证 (Disk Space & Verification)
    {
        "question": "如何节省磁盘空间？",
        "answer": "一旦货币的最新交易被足够多的区块掩埋，之前的已消费交易可以被丢弃。"
    },
    {
        "question": "为了便于修剪旧交易，交易是如何哈希的？",
        "answer": "交易被哈希在 Merkle 树中，只有根被包含在区块的哈希中。"
    },
    {
        "question": "什么是简易支付验证（SPV）？",
        "answer": "用户只需保留最长工作量证明链的区块头副本，并获取连接交易到区块的 Merkle 分支，无需运行全节点即可验证支付。"
    },
    {
        "question": "SPV 在什么情况下容易受到攻击？",
        "answer": "只要诚实节点控制网络，验证就是可靠的，但如果网络被攻击者压倒，SPV 就更容易受到攻击。"
    },
    # 隐私与计算 (Privacy & Calculations)
    {
        "question": "传统的银行模型如何实现隐私？",
        "answer": "通过限制相关方和受信任的第三方对信息的访问来实现。"
    },
    {
        "question": "比特币的新隐私模型是什么？",
        "answer": "通过保持公钥匿名来打破信息流；公众可以看到有人向他人发送了一定金额，但无法将交易与任何人联系起来。"
    },
    {
        "question": "对于多输入交易，隐私面临什么风险？",
        "answer": "多输入交易不可避免地揭示了这些输入属于同一个所有者，如果公钥所有者被揭露，链接可能会揭示属于同一所有者的其他交易。"
    },
    {
        "question": "诚实链与攻击者链之间的竞争可以被描述为什么数学模型？",
        "answer": "可以被描述为二项随机游走（Binomial Random Walk）。"
    },
    {
        "question": "随着区块数量的增加，慢速攻击者追上的概率如何变化？",
        "answer": "概率呈指数级下降。"
    },
]

# Extract questions and ground truths
TEST_QUESTIONS = [qa["question"] for qa in BITCOIN_QA_DATASET]
GROUND_TRUTHS = [qa["answer"] for qa in BITCOIN_QA_DATASET]


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Evaluate RAG pipeline using RAGAS")
    parser.add_argument("--sample", type=int, default=None, help="Number of samples to evaluate (default: all 30)")
    parser.add_argument("--no-ground-truth", action="store_true", help="Skip context_recall metric")
    args = parser.parse_args()
    
    print("\n" + "=" * 60)
    print("RAG Pipeline Evaluation using RAGAS")
    print("=" * 60)
    
    # Initialize services
    rag_service = RAGService()
    eval_service = RAGEvaluationService()
    
    # Select samples
    questions = TEST_QUESTIONS[:args.sample] if args.sample else TEST_QUESTIONS
    ground_truths = None if args.no_ground_truth else (GROUND_TRUTHS[:args.sample] if args.sample else GROUND_TRUTHS)
    
    print(f"\nDocument ID: {DOCUMENT_ID}")
    print(f"User ID: {USER_ID}")
    print(f"Test questions: {len(questions)}")
    print(f"Ground truth: {'Disabled' if args.no_ground_truth else 'Enabled'}")
    
    # Run evaluation
    print("\n� RunninOg evaluation (this may take a few minutes)...")
    
    result = eval_service.evaluate_from_rag_service(
        rag_service=rag_service,
        document_id=DOCUMENT_ID,
        user_id=USER_ID,
        test_questions=questions,
        ground_truths=ground_truths,
    )
    
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
    output_path = Path("evaluation_results.json")
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
