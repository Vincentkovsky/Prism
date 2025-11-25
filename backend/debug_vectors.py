# debug_rag.py
import logging
import sys
from app.services.rag_service import RAGService  # 调整导入路径以匹配你的项目结构

# 1. 配置日志输出到控制台，级别设为 DEBUG
logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)
logger = logging.getLogger("app.services.rag")
logger.setLevel(logging.DEBUG)

def debug_main():
    print("🚀 开始初始化 RAG Service...")
    
    # 2. 实例化 Service (根据你的配置调整参数)
    # 如果你是本地 Chroma，确保路径对；如果是 Docker，确保 host/port 对
    rag = RAGService() 
    
    # 模拟数据
    test_user_id = "99d0b344-1647-465c-9663-25e9207c69f4" # 确保数据库里有这个 User
    test_doc_id = "bbb5448f-cb96-40a5-8791-256e3d27dedb"  # 确保数据库里有这个 Doc
    question = "介绍一下这篇文章 v3"

    print(f"\n🔍 正在测试 Document ID: {test_doc_id}")
    
    # 3. 第一步：测试向量检索 (不调用 LLM，省钱且快)
    print("\n--- [Step 1] 测试 get_relevant_chunks ---")
    chunks = rag.get_relevant_chunks(question, test_doc_id, test_user_id, k=5)
    
    if not chunks:
        print("❌ 错误：未检索到任何 Chunks！")
        print("   可能原因：")
        print("   1. Document ID 或 User ID 不匹配")
        print("   2. 数据库为空 (检查 ingest 过程)")
        print("   3. Embedding 模型不一致 (Ingest vs Query)")
        return
    else:
        print(f"✅ 成功检索到 {len(chunks)} 个片段")
        for i, chunk in enumerate(chunks):
            print(f"   [{i}] Distance: {chunk['distance']:.4f} | Section: {chunk['metadata'].get('section_path')}")
            # 打印片段前50个字，确认内容对不对
            print(f"       Text: {chunk['text'][:50]}...")

    # 4. 第二步：测试重排序逻辑
    print("\n--- [Step 2] 测试 rerank_chunks ---")
    reranked = rag.rerank_chunks(question, chunks)
    print(f"✅ 重排序完成，Top 1 来源: {reranked[0]['metadata'].get('section_path')}")

    # 5. 第三步：测试完整流程 (会消耗 API Token)
    print("\n--- [Step 3] 测试完整 query ---")
    try:
        result = rag.query(question, test_doc_id, test_user_id)
        print("\n🤖 LLM 回答:")
        print(result['answer'])
        print(f"\n📊 引用来源: {len(result['sources'])} 个")
    except Exception as e:
        print(f"❌ LLM 生成失败: {e}")

if __name__ == "__main__":
    debug_main()