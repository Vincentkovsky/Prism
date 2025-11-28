"""
Configurable prompt templates for the Agentic RAG system.

This module provides a PromptTemplate class that allows customization of
system and user prompts, replacing hardcoded domain-specific prompts.

**Requirements: 4.3**
"""

from typing import Any, Dict, Optional
from pydantic import BaseModel, Field


class PromptTemplate(BaseModel):
    """
    A configurable prompt template with customizable system and user prompts.
    
    This class allows injection of custom prompts into the RAG pipeline,
    enabling domain-agnostic operation by replacing hardcoded prompts.
    """
    
    name: str = Field(
        description="Unique identifier for the template"
    )
    description: str = Field(
        default="",
        description="Human-readable description of the template's purpose"
    )
    system_prompt: str = Field(
        description="The system prompt that sets the assistant's behavior"
    )
    user_prompt_template: str = Field(
        description="The user prompt template with placeholders for context and question"
    )
    
    def format_user_prompt(self, context: str, question: str, **kwargs: Any) -> str:
        """
        Format the user prompt template with the given context and question.
        
        Args:
            context: The retrieved context from documents
            question: The user's question
            **kwargs: Additional variables to substitute in the template
            
        Returns:
            The formatted user prompt string
        """
        return self.user_prompt_template.format(
            context=context,
            question=question,
            **kwargs
        )
    
    def format_full_prompt(self, context: str, question: str, **kwargs: Any) -> str:
        """
        Format the complete prompt combining system and user prompts.
        
        This is useful for models that don't support separate system/user messages.
        
        Args:
            context: The retrieved context from documents
            question: The user's question
            **kwargs: Additional variables to substitute in the template
            
        Returns:
            The complete formatted prompt string
        """
        user_prompt = self.format_user_prompt(context, question, **kwargs)
        return f"{self.system_prompt}\n\n{user_prompt}"


# Default general-purpose template for document Q&A
DEFAULT_QA_TEMPLATE = PromptTemplate(
    name="default_qa",
    description="Default general-purpose template for document question answering",
    system_prompt=(
        "You are a helpful document assistant. Answer questions based on the provided context. "
        "If the information is not in the context, say so clearly."
    ),
    user_prompt_template=(
        "Context:\n{context}\n\n"
        "Question: {question}\n\n"
        "Please provide a concise and accurate answer based on the context above."
    )
)


# Chinese language template for document Q&A
CHINESE_QA_TEMPLATE = PromptTemplate(
    name="chinese_qa",
    description="Chinese language template for document question answering",
    system_prompt=(
        "你是一个专业的文档助手。请根据提供的上下文回答问题。"
        "如果上下文中没有相关信息，请明确说明。"
    ),
    user_prompt_template=(
        "上下文：\n{context}\n\n"
        "问题：{question}\n\n"
        "请根据上下文提供简洁准确的答案。"
    )
)


class PromptTemplateRegistry:
    """
    Registry for managing prompt templates.
    
    Allows registration and retrieval of prompt templates by name,
    with a default fallback template.
    """
    
    def __init__(self, default_template: Optional[PromptTemplate] = None):
        """
        Initialize the registry with an optional default template.
        
        Args:
            default_template: The template to use when no specific template is requested.
                            Defaults to DEFAULT_QA_TEMPLATE.
        """
        self._templates: Dict[str, PromptTemplate] = {}
        self._default_template = default_template or DEFAULT_QA_TEMPLATE
        
        # Register built-in templates
        self.register(DEFAULT_QA_TEMPLATE)
        self.register(CHINESE_QA_TEMPLATE)
    
    def register(self, template: PromptTemplate) -> None:
        """
        Register a prompt template.
        
        Args:
            template: The template to register
        """
        self._templates[template.name] = template
    
    def get(self, name: str) -> Optional[PromptTemplate]:
        """
        Get a template by name.
        
        Args:
            name: The template name
            
        Returns:
            The template if found, None otherwise
        """
        return self._templates.get(name)
    
    def get_or_default(self, name: Optional[str] = None) -> PromptTemplate:
        """
        Get a template by name, falling back to the default if not found.
        
        Args:
            name: The template name, or None to get the default
            
        Returns:
            The requested template or the default template
        """
        if name is None:
            return self._default_template
        return self._templates.get(name, self._default_template)
    
    def list_templates(self) -> Dict[str, PromptTemplate]:
        """
        List all registered templates.
        
        Returns:
            Dictionary of template name to template
        """
        return dict(self._templates)
    
    def set_default(self, template: PromptTemplate) -> None:
        """
        Set the default template.
        
        Args:
            template: The template to use as default
        """
        self._default_template = template
        # Also register it if not already registered
        if template.name not in self._templates:
            self.register(template)


# Global registry instance
_global_registry: Optional[PromptTemplateRegistry] = None


def get_prompt_registry() -> PromptTemplateRegistry:
    """
    Get the global prompt template registry.
    
    Returns:
        The global PromptTemplateRegistry instance
    """
    global _global_registry
    if _global_registry is None:
        _global_registry = PromptTemplateRegistry()
    return _global_registry
