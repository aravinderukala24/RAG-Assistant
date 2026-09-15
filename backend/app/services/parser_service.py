import ast
import re
from typing import List, Dict, Optional, Any

class ParsedCodeUnit:
    def __init__(
        self,
        name: str,
        unit_type: str,  # "function", "method", "class", "interface", "struct"
        start_line: int,
        end_line: int,
        code: str,
        parent_name: Optional[str] = None,
        docstring: Optional[str] = None
    ):
        self.name = name
        self.unit_type = unit_type
        self.start_line = start_line
        self.end_line = end_line
        self.code = code
        self.parent_name = parent_name
        self.docstring = docstring

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "unit_type": self.unit_type,
            "start_line": self.start_line,
            "end_line": self.end_line,
            "code": self.code,
            "parent_name": self.parent_name,
            "docstring": self.docstring
        }

class ParserService:
    @staticmethod
    def parse_python(code: str, file_path: str = "") -> List[ParsedCodeUnit]:
        """
        Extracts classes, methods, and functions using Python AST.
        """
        units: List[ParsedCodeUnit] = []
        lines = code.splitlines()
        
        try:
            tree = ast.parse(code)
        except Exception:
            # Fallback to regex parser if AST fails
            return ParserService.parse_structural(code, "python")
            
        def get_code_slice(start: int, end: int) -> str:
            # 1-indexed line numbers
            return "\n".join(lines[start - 1 : end])

        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.ClassDef):
                c_start = node.lineno
                c_end = getattr(node, "end_lineno", len(lines))
                c_doc = ast.get_docstring(node)
                
                units.append(
                    ParsedCodeUnit(
                        name=node.name,
                        unit_type="class",
                        start_line=c_start,
                        end_line=c_end,
                        code=get_code_slice(c_start, c_end),
                        docstring=c_doc
                    )
                )
                
                # Extract methods inside class
                for child in node.body:
                    if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        m_start = child.lineno
                        m_end = getattr(child, "end_lineno", m_start)
                        m_doc = ast.get_docstring(child)
                        units.append(
                            ParsedCodeUnit(
                                name=child.name,
                                unit_type="method",
                                start_line=m_start,
                                end_line=m_end,
                                code=get_code_slice(m_start, m_end),
                                parent_name=node.name,
                                docstring=m_doc
                            )
                        )
                        
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                f_start = node.lineno
                f_end = getattr(node, "end_lineno", f_start)
                f_doc = ast.get_docstring(node)
                units.append(
                    ParsedCodeUnit(
                        name=node.name,
                        unit_type="function",
                        start_line=f_start,
                        end_line=f_end,
                        code=get_code_slice(f_start, f_end),
                        docstring=f_doc
                    )
                )
                
        return units

    @staticmethod
    def parse_structural(code: str, language: str) -> List[ParsedCodeUnit]:
        """
        Syntax-aware structural block/brace parser for JS/TS/Java/C/C++/Go.
        Identifies function, class, struct, and interface declarations and their exact line boundaries.
        """
        units: List[ParsedCodeUnit] = []
        lines = code.splitlines()
        num_lines = len(lines)
        if num_lines == 0:
            return units

        # Language-specific patterns
        patterns = []
        if language in ("javascript", "typescript"):
            patterns = [
                # class ClassName
                (r"(?:export\s+)?(?:default\s+)?class\s+([A-Za-z0-9_$]+)", "class"),
                # interface InterfaceName / type TypeName
                (r"(?:export\s+)?interface\s+([A-Za-z0-9_$]+)", "interface"),
                # function functionName(...) or async function functionName(...)
                (r"(?:export\s+)?(?:default\s+)?(?:async\s+)?function\s*([A-Za-z0-9_$]+)?\s*\(", "function"),
                # const/let/var name = (async)? (...) => or function(...)
                (r"(?:export\s+)?(?:const|let|var)\s+([A-Za-z0-9_$]+)\s*=\s*(?:async\s*)?(?:\([^)]*\)|[A-Za-z0-9_$]+)\s*=>", "function"),
                # methodName(...) {
                (r"^\s*(?:async\s+)?([A-Za-z0-9_$]+)\s*\([^)]*\)\s*(?::\s*[^{]+)?\{", "method"),
            ]
        elif language == "java":
            patterns = [
                (r"(?:public|private|protected|static|final|abstract|\s)*class\s+([A-Za-z0-9_]+)", "class"),
                (r"(?:public|private|protected|static|final|\s)*interface\s+([A-Za-z0-9_]+)", "interface"),
                (r"(?:public|private|protected|static|final|synchronized|\s)+[\w<>\[\],\s]+\s+([A-Za-z0-9_]+)\s*\([^)]*\)\s*(?:throws\s+[\w,\s]+)?\{", "method"),
            ]
        elif language == "go":
            patterns = [
                # func (r *Receiver) MethodName(...) ...
                (r"func\s*\([^)]+\)\s*([A-Za-z0-9_]+)\s*\(", "method"),
                # func FunctionName(...) ...
                (r"func\s+([A-Za-z0-9_]+)\s*\(", "function"),
                # type StructName struct
                (r"type\s+([A-Za-z0-9_]+)\s+struct", "struct"),
                # type InterfaceName interface
                (r"type\s+([A-Za-z0-9_]+)\s+interface", "interface"),
            ]
        elif language in ("c", "cpp"):
            patterns = [
                (r"(?:class|struct)\s+([A-Za-z0-9_]+)", "class"),
                # return_type function_name(...) {
                (r"^(?:[\w:*&<>\s]+)\s+([A-Za-z0-9_~]+)\s*\([^;]*\)\s*(?:const)?\s*\{", "function"),
            ]
        else:
            # Generic fallback
            patterns = [
                (r"(?:def|func|function|class|struct)\s+([A-Za-z0-9_]+)", "function"),
            ]

        for i, line in enumerate(lines):
            line_str = line.strip()
            if not line_str or line_str.startswith("//") or line_str.startswith("/*") or line_str.startswith("#"):
                continue

            for pattern, unit_type in patterns:
                match = re.search(pattern, line)
                if match:
                    name = match.group(1) if match.groups() and match.group(1) else f"anonymous_{i+1}"
                    
                    # Find matching brace
                    start_line = i + 1
                    end_line = ParserService._find_block_end(lines, i)
                    
                    unit_code = "\n".join(lines[start_line - 1 : end_line])
                    units.append(
                        ParsedCodeUnit(
                            name=name,
                            unit_type=unit_type,
                            start_line=start_line,
                            end_line=end_line,
                            code=unit_code
                        )
                    )
                    break

        return units

    @staticmethod
    def _find_block_end(lines: List[str], start_idx: int) -> int:
        """
        Finds the line index where the matching brace closes, or ends after a reasonable block.
        """
        brace_count = 0
        found_open = False
        max_idx = min(len(lines), start_idx + 250)
        
        for j in range(start_idx, max_idx):
            line = lines[j]
            # Strip string literals and comments roughly
            clean = re.sub(r'".*?"|\'.*?\'|//.*|/\*.*?\*/', '', line)
            
            for char in clean:
                if char == '{':
                    brace_count += 1
                    found_open = True
                elif char == '}':
                    brace_count -= 1
                    if found_open and brace_count == 0:
                        return j + 1
                        
        # If no braces matched or unclosed, return a heuristic boundary
        return min(len(lines), start_idx + 30)

    @classmethod
    def parse_file(cls, code: str, language: str, file_path: str = "") -> List[ParsedCodeUnit]:
        """
        Dispatches to appropriate parser based on language.
        """
        if language == "python":
            return cls.parse_python(code, file_path)
        else:
            return cls.parse_structural(code, language)
