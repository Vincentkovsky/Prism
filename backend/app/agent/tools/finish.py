"""
Finish Tool for the Agent.

A special tool that allows the agent to signal completion and provide a final answer.
This is used in the native Tool Call pattern to structurally indicate when reasoning is complete.
"""

from ..types import Tool, ToolSchema


def create_finish_tool() -> Tool:
    """Create a finish tool for the agent to signal completion.
    
    This tool is called by the agent when it has gathered enough information
    to provide a final answer. The tool simply returns the answer as-is,
    allowing the ReAct loop to detect completion and extract the final response.
    
    Returns:
        A Tool instance configured for signaling completion
    """
    
    def finish(answer: str, **kwargs) -> str:
        """Signal that the agent has completed reasoning and has a final answer.
        
        Args:
            answer: The final answer to the user's question, with citations
            
        Returns:
            The answer as-is (pass-through)
        """
        return answer
    
    schema = ToolSchema(
        name="finish",
        description=(
            "Call this tool when you have gathered enough information to provide "
            "a comprehensive final answer to the user's question. "
            "Your answer should be well-formatted and include [[citation:N]] references "
            "for specific facts from retrieved sources."
        ),
        parameters={
            "type": "object",
            "properties": {
                "answer": {
                    "type": "string",
                    "description": (
                        "The final answer to the user's question. "
                        "Must be comprehensive, well-structured, and include citations "
                        "in the format [[citation:N]] where N corresponds to the source number."
                    ),
                },
            },
        },
        required=["answer"],
    )
    
    return Tool(schema=schema, handler=finish)
