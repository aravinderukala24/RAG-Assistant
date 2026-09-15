import json
import re
from typing import List, Dict, Any, Optional, Tuple
from ..config import settings
from ..models.schemas import CodeSource, TraceStep

GROUNDED_SYSTEM_PROMPT = """You are an expert Codebase AI Assistant.
Your task is to answer the user's question about a software repository strictly based on the provided retrieved code context.

CRITICAL RULES:
1. ONLY use information explicitly present in the provided Code Snippets.
2. If the snippets do not contain enough information to answer the question with confidence, state clearly: "The retrieved repository files do not provide enough evidence to answer this question."
3. NEVER fabricate file names, function names, class names, line numbers, or code logic.
4. When referencing code, cite the exact file path, function/class name, and line numbers from the context.
5. Provide a clear, direct answer first, followed by a structured explanation.
6. If the question asks about a sequence, lifecycle, or execution flow (or if a flow is clearly evident in the code), provide a sequential list of steps for the execution trace.

Respond in JSON format with the following structure:
{
  "direct_answer": "Concise direct answer to the question",
  "explanation": "Detailed grounded explanation citing specific files and functions",
  "trace_flow": [
    {
      "step_number": 1,
      "title": "Short title (e.g. Receive HTTP POST request)",
      "description": "Brief description of what happens in this step",
      "file_path": "path/to/file.ext",
      "function_name": "functionName",
      "line_range": "10-25"
    }
  ]
}
If no sequential trace is applicable, trace_flow can be an empty list [].
"""

class LLMService:
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or settings.GEMINI_API_KEY
        self.model = settings.LLM_MODEL
        self._client = None

    def _get_client(self):
        if self._client is None:
            if not self.api_key:
                raise ValueError("GEMINI_API_KEY is not configured. Please set GEMINI_API_KEY in .env or environment.")
            from google import genai
            self._client = genai.Client(api_key=self.api_key)
        return self._client

    def generate_grounded_answer(
        self,
        question: str,
        retrieved_chunks: List[Dict[str, Any]],
        repo_name: str
    ) -> Tuple[str, List[TraceStep]]:
        """
        Sends retrieved code snippets to Gemini and parses structured response.
        """
        if not retrieved_chunks:
            return (
                "The repository index did not return any relevant code snippets for your query.",
                []
            )

        client = self._get_client()

        # Build context prompt
        context_blocks = []
        for i, chunk in enumerate(retrieved_chunks, 1):
            file_p = chunk.get("file_path", "unknown")
            func = chunk.get("function_name") or "N/A"
            cls_name = chunk.get("class_name") or "N/A"
            s_line = chunk.get("start_line", 1)
            e_line = chunk.get("end_line", 1)
            lang = chunk.get("language", "text")
            code = chunk.get("source_code", "")

            block = (
                f"--- Snippet #{i} ---\n"
                f"File: {file_p}\n"
                f"Function: {func} | Class: {cls_name}\n"
                f"Lines: {s_line}-{e_line}\n"
                f"Language: {lang}\n"
                f"```{lang}\n{code}\n```\n"
            )
            context_blocks.append(block)

        context_str = "\n".join(context_blocks)

        user_prompt = (
            f"Repository: {repo_name}\n\n"
            f"Retrieved Code Snippets:\n{context_str}\n\n"
            f"User Question:\n{question}\n\n"
            f"Please generate a grounded answer strictly adhering to the JSON schema specified."
        )

        from google.genai import types

        # Attempt with primary model, fallback if needed
        models_to_try = [self.model, settings.FALLBACK_LLM_MODEL]
        last_error = None

        for model_name in models_to_try:
            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=[GROUNDED_SYSTEM_PROMPT, user_prompt],
                    config=types.GenerateContentConfig(
                        temperature=0.2,
                        response_mime_type="application/json"
                    )
                )

                if response.text:
                    parsed_json = self._parse_json_response(response.text)
                    direct = parsed_json.get("direct_answer", "")
                    explanation = parsed_json.get("explanation", "")
                    raw_trace = parsed_json.get("trace_flow", [])

                    # Construct formatted answer text
                    formatted_answer = f"{direct}\n\n{explanation}".strip()
                    if not formatted_answer:
                        formatted_answer = response.text.strip()

                    trace_steps = []
                    if isinstance(raw_trace, list):
                        for item in raw_trace:
                            if isinstance(item, dict) and item.get("title"):
                                trace_steps.append(
                                    TraceStep(
                                        step_number=int(item.get("step_number", len(trace_steps) + 1)),
                                        title=str(item.get("title", "")),
                                        description=str(item.get("description", "")),
                                        file_path=item.get("file_path"),
                                        function_name=item.get("function_name"),
                                        line_range=str(item.get("line_range")) if item.get("line_range") else None
                                    )
                                )

                    return formatted_answer, trace_steps

            except Exception as e:
                last_error = e
                continue

        raise RuntimeError(f"Gemini generation failed: {last_error}")

    def _parse_json_response(self, text: str) -> Dict[str, Any]:
        """
        Cleans and parses JSON output from LLM.
        """
        clean = text.strip()
        # Remove markdown json wrappers if present
        if clean.startswith("```json"):
            clean = clean[7:]
        elif clean.startswith("```"):
            clean = clean[3:]
        if clean.endswith("```"):
            clean = clean[:-3]
        clean = clean.strip()

        try:
            return json.loads(clean)
        except json.JSONDecodeError:
            # Fallback if raw text returned
            return {
                "direct_answer": clean,
                "explanation": "",
                "trace_flow": []
            }
