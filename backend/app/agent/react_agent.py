"""
ReAct Agent implementation for the Generic Agentic RAG System.

This module implements the ReAct (Reasoning + Acting) pattern for multi-step
reasoning with tool calling capabilities using native LLM Tool Call / Function Calling.

Requirements:
- 2.2: WHEN the Agent determines a tool is needed, THE Agentic_RAG_System SHALL
       invoke the tool with appropriate parameters and incorporate the result into reasoning.
- 3.1: WHEN a user submits a complex question, THE Agentic_RAG_System SHALL
       decompose it into sub-questions and process them sequentially.
- 3.2: WHILE executing a multi-step plan, THE Agentic_RAG_System SHALL
       maintain conversation state across steps.
- 3.3: THE Agentic_RAG_System SHALL limit the maximum number of reasoning steps
       to 10 to prevent infinite loops.
- 3.4: WHEN all sub-questions are answered, THE Agentic_RAG_System SHALL
       synthesize a final comprehensive answer.
"""

import json
import logging
import time
from datetime import datetime
from typing import Any, AsyncIterator, Dict, List, Optional, Tuple, NamedTuple

from openai import OpenAI

try:
    from google import genai  # type: ignore
    from google.genai import types as genai_types  # type: ignore
except ImportError:  # pragma: no cover
    genai = None
    genai_types = None  # type: ignore

# Add tenacity for smart retries
try:
    from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type, before_sleep_log
    from google.genai.errors import ClientError
except ImportError:
    retry = lambda *args, **kwargs: lambda f: f
    stop_after_attempt = lambda x: x
    wait_exponential = lambda *args, **kwargs: x
    retry_if_exception_type = lambda x: x
    before_sleep_log = lambda logger, level: lambda f: f
    ClientError = Exception

from .types import (
    AgentResponse,
    AgentStreamEvent,
    IntentType,
    ThoughtStep,
)
from .router import IntentRouter
from .tools.registry import ToolRegistry, ToolNotFoundError
from ..core.config import get_settings


from .prompts import REACT_AGENT_SYSTEM_PROMPT


logger = logging.getLogger(__name__)


# Default maximum steps to prevent infinite loops (Requirement 3.3)
DEFAULT_MAX_STEPS = 10


class ToolCall(NamedTuple):
    """Represents a request from the LLM to call a tool."""
    name: str
    arguments: Dict[str, Any]
    id: Optional[str] = None


class ReActAgent:
    """
    ReAct Agent implementing reasoning + acting pattern using native Tool Calling.
    
    The agent follows a loop of:
    1. Think - Analyze the current state and decide what to do (LLM call with tools)
    2. Act - Execute a tool if requested
    3. Observe - Process the tool result
    4. Repeat until answer is ready (via 'finish' tool) or max steps reached
    """
    
    SYSTEM_PROMPT = REACT_AGENT_SYSTEM_PROMPT


    def __init__(
        self,
        tool_registry: ToolRegistry,
        router: Optional[IntentRouter] = None,
        max_steps: int = DEFAULT_MAX_STEPS,
        openai_client: Optional[OpenAI] = None,
    ) -> None:
        """
        Initialize the ReAct Agent.
        
        Args:
            tool_registry: Registry of available tools
            router: Intent router for query classification (optional)
            max_steps: Maximum reasoning steps (default: 10, Requirement 3.3)
            openai_client: Optional OpenAI client for LLM calls
        """
        self.tools = tool_registry
        self.router = router
        self.max_steps = max_steps
        self.settings = get_settings()
        
        # Initialize LLM client based on provider
        self.provider = (self.settings.llm_provider or "openai").lower()
        
        if self.provider == "openai":
            self.openai = openai_client or (OpenAI() if self.settings.openai_api_key else None)
            self._gemini_client = None
        else:
            self.openai = None
            self._gemini_client = None
            if genai and self.settings.google_api_key:
                self._gemini_client = genai.Client(api_key=self.settings.google_api_key)
    
    async def run(
        self,
        query: str,
        user_id: str,
        stream: bool = False,
    ) -> AgentResponse:
        """
        Execute the agent reasoning loop using native tool calling.
        """
        start_time = time.perf_counter()
        
        # Check intent if router is available
        if self.router:
            intent = self.router.classify(query)
            if intent.intent == IntentType.DIRECT_ANSWER and intent.confidence >= 0.9:
                answer = self._generate_direct_answer(query)
                return AgentResponse(
                    answer=answer,
                    sources=[],
                    intermediate_steps=[],
                    model_used=self._get_model_name(),
                    total_latency_ms=(time.perf_counter() - start_time) * 1000,
                )
        
        # Initialize state
        intermediate_steps: List[ThoughtStep] = []
        sources: List[Dict[str, Any]] = []
        observations: List[str] = []
        
        # Build initial conversation history
        # Note: We rely on API for tool definitions, so we pass tools during LLM call
        conversation_history = self._build_initial_history(
            query=query,
            user_id=user_id,
        )
        
        # ReAct loop
        step_count = 0
        final_answer: Optional[str] = None
        
        while step_count < self.max_steps:
            step_count += 1
            logger.debug(f"ReAct step {step_count}/{self.max_steps}")
            
            # Get next action from LLM with native tool calling
            thought_process, tool_call = self._call_llm(conversation_history)
            
            thought = thought_process
            action = tool_call.name if tool_call else None
            action_input = tool_call.arguments if tool_call else None
            
            # Create thought step
            step = ThoughtStep(
                thought=thought,
                action=action,
                action_input=action_input,
                observation=None,
            )
            
            # Check for final answer via finish tool or direct response
            if tool_call and tool_call.name == "finish":
                final_answer = tool_call.arguments.get("answer", "")
                intermediate_steps.append(step)
                break
            elif not tool_call:
                # No tool call = possible direct answer or chat
                if not thought: # Empty response
                     thought = "I need to think about this..."
                
                # If the thought looks like an answer and we have no tool call, consider it done
                # But usually specialized models will call 'finish' tool
                # We'll treat this as a thought unless it's very clearly an answer
                conversation_history.append({
                    "role": "assistant",
                    "content": thought,
                })
                conversation_history.append({
                    "role": "user",
                    "content": "Please continue with a tool call or use the 'finish' tool to provide your answer.",
                })
                intermediate_steps.append(step)
                continue

            # Execute tool
            observation = self._execute_tool(
                action=action,
                action_input=action_input,
                user_id=user_id,
            )
            step.observation = observation
            observations.append(observation)
            intermediate_steps.append(step)
            
            # Extract sources
            self._extract_sources(action, observation, sources)
            
            # Add to history
            # For OpenAI, we need to append the tool call message properly
            # For Gemini, it handles it differently, but our abstraction unifies it
            if self.provider == "openai":
                conversation_history.append({
                    "role": "assistant",
                    "content": thought,
                    "tool_calls": [{
                        "id": tool_call.id,
                        "type": "function",
                        "function": {
                            "name": tool_call.name,
                            "arguments": json.dumps(tool_call.arguments)
                        }
                    }]
                })
                conversation_history.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": observation
                })
            else:
                # Gemini simplified history update (abstraction layer handles format)
                conversation_history.append({
                    "role": "model",
                    "parts": [{"function_call": {"name": tool_call.name, "args": tool_call.arguments}}]
                })
                conversation_history.append({
                    "role": "function", # Special role for Gemini in our internal format
                    "name": tool_call.name,
                    "content": observation
                })

        # Synthesize if needed
        if final_answer is None:
            logger.warning(f"Step limit ({self.max_steps}) reached")
            final_answer = self._synthesize_final_answer(query, observations, intermediate_steps)
        
        return AgentResponse(
            answer=final_answer,
            sources=sources,
            intermediate_steps=intermediate_steps,
            model_used=self._get_model_name(),
            total_latency_ms=(time.perf_counter() - start_time) * 1000,
        )
    
    async def stream(
        self,
        query: str,
        user_id: str,
    ) -> AsyncIterator[AgentStreamEvent]:
        """Stream agent execution events using native tool calling."""
        start_time = time.perf_counter()
        
        # Check intent
        if self.router:
            intent = self.router.classify(query)
            if intent.intent == IntentType.DIRECT_ANSWER and intent.confidence >= 0.9:
                yield AgentStreamEvent(
                    event_type="thinking",
                    content="This is a simple greeting, responding directly.",
                )
                answer = self._generate_direct_answer(query)
                yield AgentStreamEvent(
                    event_type="answer",
                    content=answer,
                    metadata={"latency_ms": (time.perf_counter() - start_time) * 1000},
                )
                return
        
        intermediate_steps = []
        sources = []
        observations = []
        
        conversation_history = self._build_initial_history(query=query, user_id=user_id)
        
        step_count = 0
        final_answer = None
        
        while step_count < self.max_steps:
            step_count += 1
            
            yield AgentStreamEvent(
                event_type="thinking",
                content=f"Step {step_count}: Analyzing...",
                metadata={"step": step_count},
            )
            
            # Call LLM
            thought, tool_call = self._call_llm(conversation_history)
            
            if thought:
                yield AgentStreamEvent(
                    event_type="thinking",
                    content=thought,
                    metadata={"step": step_count},
                )
            
            if tool_call:
                if tool_call.name == "finish":
                    final_answer = tool_call.arguments.get("answer", "")
                    yield AgentStreamEvent(
                        event_type="answer",
                        content=final_answer,
                        metadata={
                            "latency_ms": (time.perf_counter() - start_time) * 1000,
                            "sources": sources,
                        },
                    )
                    return
                
                yield AgentStreamEvent(
                    event_type="tool_call",
                    content=f"Calling {tool_call.name}",
                    metadata={"tool": tool_call.name, "input": tool_call.arguments},
                )
                
                observation = self._execute_tool(
                    action=tool_call.name,
                    action_input=tool_call.arguments,
                    user_id=user_id,
                )
                observations.append(observation)
                
                yield AgentStreamEvent(
                    event_type="tool_result",
                    content=observation[:500] + "..." if len(observation) > 500 else observation,
                    metadata={"tool": tool_call.name},
                )
                
                self._extract_sources(tool_call.name, observation, sources)
                
                # Update history
                if self.provider == "openai":
                    conversation_history.append({
                        "role": "assistant",
                        "content": thought,
                        "tool_calls": [{
                            "id": tool_call.id,
                            "type": "function",
                            "function": {
                                "name": tool_call.name,
                                "arguments": json.dumps(tool_call.arguments)
                            }
                        }]
                    })
                    conversation_history.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": observation
                    })
                else:
                    conversation_history.append({
                        "role": "model",
                        "parts": [{"function_call": {"name": tool_call.name, "args": tool_call.arguments}}]
                    })
                    conversation_history.append({
                        "role": "function",
                        "name": tool_call.name,
                        "content": observation
                    })
            else:
                # No tool call - ask for continuation
                conversation_history.append({"role": "assistant", "content": thought})
                conversation_history.append({
                    "role": "user",
                    "content": "Please continue with a tool call or use 'finish'."
                })

        # Synthesize fallback
        yield AgentStreamEvent(
            event_type="thinking",
            content="Reached step limit, synthesizing final answer...",
        )
        final_answer = self._synthesize_final_answer(query, observations, [])
        yield AgentStreamEvent(
            event_type="answer",
            content=final_answer,
            metadata={
                "latency_ms": (time.perf_counter() - start_time) * 1000,
                "sources": sources,
            },
        )

    def _build_initial_history(self, query: str, user_id: str) -> List[Dict[str, Any]]:
        """Build initial history without tools_description injection."""
        current_date = datetime.now().strftime("%Y-%m-%d")
        system_prompt = self.SYSTEM_PROMPT.format(current_date=current_date)
        
        context = f"""
Context:
- User ID: {user_id}
- You will search across all documents belonging to this user
- When using document_search, always include user_id in the action_input

User Question: {query}
"""
        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": context},
        ]

    def _call_llm(self, messages: List[Dict[str, Any]]) -> Tuple[str, Optional[ToolCall]]:
        """Call LLM with tools and return thought and optional tool call."""
        if self.provider == "gemini" and self._gemini_client:
            return self._call_gemini(messages)
        elif self.openai:
            return self._call_openai(messages)
        else:
            raise RuntimeError("No LLM client available")

    def _call_openai(self, messages: List[Dict[str, Any]]) -> Tuple[str, Optional[ToolCall]]:
        """Call OpenAI with native tools."""
        tools = self.tools.to_openai_tools()
        
        response = self.openai.chat.completions.create(
            model=self.settings.openai_model_mini,
            messages=messages,
            tools=tools,
            tool_choice="auto",
            max_tokens=1000,
            temperature=0.3,
        )
        
        msg = response.choices[0].message
        content = msg.content or ""
        
        if msg.tool_calls:
            tc = msg.tool_calls[0]
            return content, ToolCall(
                name=tc.function.name,
                arguments=json.loads(tc.function.arguments),
                id=tc.id
            )
        
        return content, None

    @retry(
        retry=retry_if_exception_type(ClientError),
        wait=wait_exponential(multiplier=2, min=4, max=60),
        stop=stop_after_attempt(5),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True
    )
    def _call_gemini(self, messages: List[Dict[str, Any]]) -> Tuple[str, Optional[ToolCall]]:
        """Call Gemini with native tools."""
        # Convert our message format to Gemini's
        contents = []
        for m in messages:
            role = "user" if m["role"] == "user" else "model"
            if m["role"] == "system":
                 # Gemini sets system instruction via config, but we'll prepend for simplicity here within turns
                 # Or better, use system_instruction if separate. For now, we prepend to first user msg logic earlier
                 # But since we use chat history directly, we need to handle roles correctly.
                 
                 # NOTE: For proper Gemini chat, it's better to use chat session, but here we construct history
                 # Skip system generated earlier, it's in history[0] usually
                 if not contents:
                    role = "user" # Treat system as user instruction for simplicity or handle separately
                    parts = [{"text": m["content"]}]
                    contents.append({"role": role, "parts": parts})
                    continue
            
            if m["role"] == "function": # Tool response
                 contents.append({
                     "role": "function", # Gemini uses 'function' role for response? No, it's part of 'user' turn usually or 'function' role
                     "parts": [{"function_response": {"name": m["name"], "response": {"result": m["content"]}}}]
                 })
                 continue
            
            if "parts" in m: # Already Gemini format
                contents.append({"role": role, "parts": m["parts"]})
            elif "tool_calls" in m: # Previous assistant turn with tool
                parts = []
                if m.get("content"):
                    parts.append({"text": m["content"]})
                # OpenAI format conversion
                tc = m["tool_calls"][0]["function"]
                parts.append({"function_call": {"name": tc["name"], "args": json.loads(tc["arguments"])}})
                contents.append({"role": "model", "parts": parts})
            else:
                contents.append({"role": role, "parts": [{"text": m["content"]}]})

        tools = [genai_types.Tool(function_declarations=self.tools.to_gemini_tools())]
        
        # Proper system instruction separation for Gemini 1.5
        # system_instr = [m["content"] for m in messages if m["role"] == "system"]
        # ... simplifying for this implementation

        response = self._gemini_client.models.generate_content(
            model=self.settings.gemini_model_flash,
            contents=contents,
            config=genai_types.GenerateContentConfig(
                temperature=0.3,
                max_output_tokens=1000,
                tools=tools
            ),
        )

        # Extract
        candidate = response.candidates[0]
        content = ""
        tool_call = None
        
        for part in candidate.content.parts:
            if part.text:
                content += part.text
            if part.function_call:
                tool_call = ToolCall(
                    name=part.function_call.name,
                    arguments=dict(part.function_call.args),
                    id="gemini_id"
                )
        
        return content, tool_call

    def _execute_tool(self, action: str, action_input: Dict[str, Any], user_id: str) -> str:
        """Execute tool safely."""
        try:
            if "user_id" not in action_input:
                action_input["user_id"] = user_id
            
            result = self.tools.invoke(action, **action_input)
            
            if isinstance(result, str):
                return result
            return json.dumps(result, ensure_ascii=False, indent=2)
        except ToolNotFoundError:
            return f"Error: Tool '{action}' not found."
        except Exception as e:
            logger.error(f"Tool {action} failed: {e}", exc_info=True)
            return f"Error: {str(e)}"

    def _extract_sources(self, action: str, observation: str, sources: List[Dict]):
        """Extract sources from tool observations."""
        try:
            if action in ("web_search", "document_search"):
                # Simplified extraction logic
                import json
                data = json.loads(observation) if isinstance(observation, str) else observation
                if isinstance(data, list):
                    start_idx = len(sources) + 1
                    for i, item in enumerate(data):
                         if not isinstance(item, dict): continue
                         sources.append({
                             "documentId": str(start_idx + i),
                             "title": item.get("title") or item.get("document_name", "Untitled"),
                             "textSnippet": (item.get("content") or item.get("text", ""))[:200],
                             "url": item.get("url", ""),
                             "sourceType": "web" if action == "web_search" else "pdf"
                         })
        except:
            pass

    def _generate_direct_answer(self, query: str) -> str:
        """Generate greeting."""
        greetings = {
             "hello": "Hello! How can I help you today?",
             "hi": "Hi there!",
             "how are you": "I'm doing well, thanks!"
        }
        q = query.lower().strip()
        for k, v in greetings.items():
            if k in q: return v
        return "Hello! How can I help?"

    def _synthesize_final_answer(self, query: str, observations: List[str], steps: List[ThoughtStep]) -> str:
        """Synthesize answer if loop limit reached."""
        if not observations: return "I couldn't find enough information."
        
        obs_text = "\n".join(observations)
        messages = [
            {"role": "system", "content": "Synthesize the following information."},
            {"role": "user", "content": f"Query: {query}\n\nInfo:\n{obs_text}"}
        ]
        
        # Simple synthesis call
        thought, _ = self._call_llm(messages)
        return thought

    def _get_model_name(self) -> str:
        return self.settings.gemini_model_flash if self.provider == "gemini" else self.settings.openai_model_mini
