"""MinerU PDF Parser Service.

Integrates MinerU for high-quality PDF extraction with automatic backend selection:
- VLM (GPU) backend when CUDA/MPS available
- Pipeline (CPU) backend as fallback

Model source defaults to modelscope for better accessibility in China.
"""
from __future__ import annotations

import json
import os
import tempfile
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Set model source to modelscope before importing MinerU
os.environ.setdefault("MINERU_MODEL_SOURCE", "modelscope")

try:
    import torch
    CUDA_AVAILABLE = torch.cuda.is_available()
    MPS_AVAILABLE = hasattr(torch.backends, 'mps') and torch.backends.mps.is_available()
    GPU_AVAILABLE = CUDA_AVAILABLE or MPS_AVAILABLE
except ImportError:
    GPU_AVAILABLE = False
    CUDA_AVAILABLE = False
    MPS_AVAILABLE = False

try:
    from mineru.cli.common import read_fn, prepare_env
    from mineru.data.data_reader_writer import FileBasedDataWriter
    from mineru.backend.pipeline.pipeline_analyze import doc_analyze as pipeline_doc_analyze
    from mineru.backend.pipeline.model_json_to_middle_json import result_to_middle_json as pipeline_result_to_middle_json
    from mineru.backend.pipeline.pipeline_middle_json_mkcontent import union_make as pipeline_union_make
    from mineru.utils.enum_class import MakeMode
    MINERU_AVAILABLE = True
except ImportError as e:
    logger.warning(f"MinerU not available: {e}")
    MINERU_AVAILABLE = False

try:
    from mineru.backend.vlm.vlm_analyze import doc_analyze as vlm_doc_analyze
    from mineru.backend.vlm.vlm_middle_json_mkcontent import union_make as vlm_union_make
    VLM_AVAILABLE = True
except ImportError:
    VLM_AVAILABLE = False


def detect_backend() -> str:
    """Auto-detect the best available backend.
    
    Returns:
        'vlm-transformers' if GPU available, otherwise 'pipeline'
    """
    if GPU_AVAILABLE and VLM_AVAILABLE:
        backend = "vlm-transformers"
        if MPS_AVAILABLE:
            backend = "vlm-mlx-engine"  # Better for macOS
        logger.info(f"GPU detected, using {backend} backend")
        return backend
    
    logger.info("No GPU detected, using pipeline backend")
    return "pipeline"


def parse_pdf_with_mineru(
    pdf_path: Path,
    output_dir: Optional[Path] = None,
    lang: str = "ch",
    backend: Optional[str] = None,
) -> Dict:
    """Parse PDF using MinerU.
    
    Args:
        pdf_path: Path to the PDF file
        output_dir: Directory for output files (temp dir if not provided)
        lang: Language hint for OCR (default: 'ch' for Chinese)
        backend: Backend to use ('pipeline', 'vlm-transformers', or None for auto)
    
    Returns:
        Dict containing:
        - markdown: str - Full markdown content
        - content_list: List[dict] - Structured content list
        - elements: List[dict] - Elements in chunking_service format
    """
    if not MINERU_AVAILABLE:
        raise ImportError("MinerU is not installed. Run: pip install mineru[core]")
    
    # Auto-detect backend if not specified
    if backend is None:
        backend = detect_backend()
    
    # Use temp dir if output_dir not provided
    if output_dir is None:
        output_dir = Path(tempfile.mkdtemp(prefix="mineru_"))
    
    pdf_path = Path(pdf_path)
    pdf_name = pdf_path.stem
    
    # Read PDF bytes
    pdf_bytes = read_fn(str(pdf_path))
    
    try:
        if backend == "pipeline":
            return _parse_with_pipeline(pdf_bytes, pdf_name, output_dir, lang)
        else:
            return _parse_with_vlm(pdf_bytes, pdf_name, output_dir, backend)
    except Exception as e:
        logger.error(f"MinerU parsing failed with {backend}: {e}")
        # Fallback to pipeline if VLM fails
        if backend != "pipeline":
            logger.info("Falling back to pipeline backend")
            return _parse_with_pipeline(pdf_bytes, pdf_name, output_dir, lang)
        raise


def _parse_with_pipeline(
    pdf_bytes: bytes,
    pdf_name: str,
    output_dir: Path,
    lang: str = "ch",
) -> Dict:
    """Parse using pipeline backend (CPU)."""
    local_image_dir, local_md_dir = prepare_env(str(output_dir), pdf_name, "auto")
    image_writer = FileBasedDataWriter(local_image_dir)
    
    # Run pipeline analysis
    infer_results, all_image_lists, all_pdf_docs, lang_list, ocr_enabled_list = pipeline_doc_analyze(
        [pdf_bytes],
        [lang],
        parse_method="auto",
        formula_enable=True,
        table_enable=True,
    )
    
    # Get first result
    model_list = infer_results[0]
    images_list = all_image_lists[0]
    pdf_doc = all_pdf_docs[0]
    _lang = lang_list[0]
    _ocr_enable = ocr_enabled_list[0]
    
    # Convert to middle JSON
    middle_json = pipeline_result_to_middle_json(
        model_list, images_list, pdf_doc, image_writer, _lang, _ocr_enable, True
    )
    
    pdf_info = middle_json["pdf_info"]
    
    # Generate markdown
    image_dir = str(os.path.basename(local_image_dir))
    markdown = pipeline_union_make(pdf_info, MakeMode.MM_MD, image_dir)
    content_list = pipeline_union_make(pdf_info, MakeMode.CONTENT_LIST, image_dir)
    
    # Convert to chunking_service element format
    elements = _convert_to_elements(content_list, pdf_info)
    
    return {
        "markdown": markdown,
        "content_list": content_list,
        "elements": elements,
        "backend": "pipeline",
    }


def _parse_with_vlm(
    pdf_bytes: bytes,
    pdf_name: str,
    output_dir: Path,
    backend: str = "vlm-transformers",
) -> Dict:
    """Parse using VLM backend (GPU)."""
    if not VLM_AVAILABLE:
        raise ImportError("VLM backend not available")
    
    local_image_dir, local_md_dir = prepare_env(str(output_dir), pdf_name, "vlm")
    image_writer = FileBasedDataWriter(local_image_dir)
    
    # Remove 'vlm-' prefix if present
    vlm_backend = backend[4:] if backend.startswith("vlm-") else backend
    
    # Run VLM analysis
    middle_json, infer_result = vlm_doc_analyze(
        pdf_bytes,
        image_writer=image_writer,
        backend=vlm_backend,
    )
    
    pdf_info = middle_json["pdf_info"]
    
    # Generate markdown
    image_dir = str(os.path.basename(local_image_dir))
    markdown = vlm_union_make(pdf_info, MakeMode.MM_MD, image_dir)
    content_list = vlm_union_make(pdf_info, MakeMode.CONTENT_LIST, image_dir)
    
    # Convert to chunking_service element format
    elements = _convert_to_elements(content_list, pdf_info)
    
    return {
        "markdown": markdown,
        "content_list": content_list,
        "elements": elements,
        "backend": backend,
    }


def _convert_to_elements(content_list: List[Dict], pdf_info: Dict) -> List[Dict]:
    """Convert MinerU content_list to chunking_service element format.
    
    Maps MinerU types to unstructured-compatible categories:
    - text -> NarrativeText
    - title -> Title
    - table -> Table
    - image -> Image
    - equation -> Formula
    """
    elements = []
    
    for item in content_list:
        item_type = item.get("type", "text")
        page_num = item.get("page_idx", 0) + 1  # MinerU uses 0-indexed pages
        
        # Map MinerU types to unstructured categories
        category_map = {
            "text": "NarrativeText",
            "title": "Title",
            "table": "Table",
            "image": "Image",
            "equation": "Formula",
            "interline_equation": "Formula",
            "footnote": "NarrativeText",
        }
        category = category_map.get(item_type, "NarrativeText")
        
        # Get content based on type
        if item_type == "table":
            # Tables have content in table_body (HTML format)
            html_content = item.get("table_body", "")
            # Convert HTML table to readable text
            text_content = _html_table_to_text(html_content)
            # Include caption and footnote if available
            captions = item.get("table_caption", [])
            footnotes = item.get("table_footnote", [])
            if captions:
                text_content = " ".join(captions) + "\n" + text_content
            if footnotes:
                text_content = text_content + "\n" + " ".join(footnotes)
        else:
            text_content = item.get("text", "") or item.get("content", "")
        
        element = {
            "category": category,
            "text": text_content,
            "metadata": {
                "page_number": page_num,
                "element_type": item_type,
                "extraction_method": "mineru",
            },
        }
        
        # For tables, include HTML representation for rendering
        if category == "Table":
            html_content = item.get("table_body", "")
            if html_content:
                element["metadata"]["text_as_html"] = html_content
        
        elements.append(element)
    
    return elements


def _html_table_to_text(html: str) -> str:
    """Convert HTML table to readable text format.
    
    Extracts text from table cells and formats as tab-separated rows.
    """
    if not html:
        return ""
    
    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "html.parser")
        
        rows = []
        for tr in soup.find_all("tr"):
            cells = []
            for td in tr.find_all(["td", "th"]):
                # Get text and clean whitespace
                cell_text = td.get_text(strip=True)
                cells.append(cell_text)
            if cells:
                rows.append("\t".join(cells))
        
        return "\n".join(rows)
    except Exception as e:
        logger.warning(f"Failed to parse table HTML: {e}")
        # Fallback: strip HTML tags with regex
        import re
        text = re.sub(r"<[^>]+>", " ", html)
        text = re.sub(r"\s+", " ", text).strip()
        return text

