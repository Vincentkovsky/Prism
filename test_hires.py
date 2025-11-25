import time
from unstructured.partition.pdf import partition_pdf

# 替换成你实际的文件路径
filename = "backend/bitcoin.pdf" 

print(f"🚀 开始使用 hi_res 策略解析: {filename}")
print("   (这会加载视觉模型，第一次运行可能需要几十秒，请耐心等待...)")

start_time = time.time()

# 核心魔法代码
elements = partition_pdf(
    filename=filename,
    strategy="hi_res",           # <--- 开启计算机视觉模式
    infer_table_structure=True,  # <--- 强制开启表格结构识别
    model_name="yolox",          # 使用 YOLOX 模型进行布局分析
)

end_time = time.time()
print(f"✅ 解析完成！耗时: {end_time - start_time:.2f} 秒")
print(f"📦 总元素数量: {len(elements)}")

print("\n" + "="*50)
print("🔍 重点抽查结果：")
print("="*50)

table_count = 0
footer_count = 0

for i, el in enumerate(elements):
    # 1. 检查表格 (之前的痛点)
    if el.category == "Table":
        table_count += 1
        print(f"\n[发现表格 #{table_count}]")
        print("--- 纯文本内容 (Text) ---")
        print(el.text[:200] + "..." if len(el.text) > 200 else el.text)
        print("\n--- ✅ 结构化内容 (HTML) ---")
        # 这里的 text_as_html 是 RAG 能理解表格结构的关键
        print(el.metadata.text_as_html) 
        print("-" * 30)

    # 2. 检查页脚/页码 (之前的噪音)
    elif el.category == "Footer":
        footer_count += 1
        print(f"🗑️ [检测到页脚/页码] (将被清洗): {el.text}")

    # 3. 检查公式 (之前的乱码)
    # 注意：unstructured 有时把公式归类为 text，有时归类为 Formula
    elif "∑" in el.text or "probability" in el.text: 
        # 简单打印一下看看 Section 11 的公式部分现在的样子
        if len(el.text) < 300: # 只看短的，排除大段正文
            print(f"\n👀 [疑似公式区域]: {el.text}")

print("\n" + "="*50)
print(f"统计: 找到了 {table_count} 个表格, {footer_count} 个页脚噪音。")