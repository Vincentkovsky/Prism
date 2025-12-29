#!/usr/bin/env python3
"""Test MinerU table extraction after fix."""
import sys

def main():
    sys.path.insert(0, '/Users/vincentjin/CodingProject/Prism')
    
    from pathlib import Path
    from backend.app.services.mineru_parser import parse_pdf_with_mineru, MINERU_AVAILABLE
    
    test_pdf = Path.home() / '2024体检报告.pdf'
    print(f"Testing with: {test_pdf}")
    
    if MINERU_AVAILABLE and test_pdf.exists():
        try:
            result = parse_pdf_with_mineru(test_pdf, backend="pipeline")
            print(f"Backend: {result['backend']}")
            
            # Find table elements
            tables = [e for e in result['elements'] if e['category'] == 'Table']
            print(f"Tables found: {len(tables)}")
            
            # Show first few tables with content
            for i, t in enumerate(tables[:3]):
                print(f"\n=== Table {i+1} (Page {t['metadata'].get('page_number')}) ===")
                text = t['text']
                if text:
                    print(f"Text ({len(text)} chars):")
                    print(text[:600] if len(text) > 600 else text)
                else:
                    print("Text: EMPTY")
                print(f"Has HTML: {'text_as_html' in t['metadata']}")
                
        except Exception as e:
            import traceback
            traceback.print_exc()

if __name__ == '__main__':
    import multiprocessing
    multiprocessing.freeze_support()
    main()
