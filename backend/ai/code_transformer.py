import os
import re
import ast
import logging
import difflib
from typing import Dict, List, Set, Optional, Any, Tuple, Union
import asyncio
import json

from backend.core.config import get_settings
from backend.ai.models import AIModel

settings = get_settings()
logger = logging.getLogger(__name__)


class CodeTransformer:
    """
    AI-powered code transformation service for adapting code to
    dependency changes, such as API updates or breaking changes.
    
    Key features:
    1. API migration - transform code to use updated APIs
    2. Breaking change adaptation - fix code affected by breaking changes
    3. Pattern-based transformation - apply reusable transformation patterns
    """
    
    def __init__(self):
        """Initialize the code transformer with required models."""
        self.model = None
        if settings.ENABLE_AI_FEATURES:
            try:
                self.model = AIModel.load_model(settings.MODEL_PATHS["code_transformer"])
                logger.info("Code transformer model loaded successfully")
            except Exception as e:
                logger.error(f"Failed to load code transformer model: {str(e)}")
    
    async def transform_code(
        self,
        code: str,
        dependency_name: str,
        breaking_changes: List[Dict[str, Any]],
        ecosystem: str = "python",
        transformation_type: str = "auto"
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Transform code to adapt to dependency changes.
        
        Args:
            code: Source code to transform
            dependency_name: Dependency name
            breaking_changes: List of breaking changes
            ecosystem: Dependency ecosystem
            transformation_type: Type of transformation to apply
            
        Returns:
            Tuple of (transformed code, transformation details)
        """
        logger.info(f"Transforming code for {dependency_name} ({ecosystem})")
        
        if not breaking_changes:
            # No changes needed
            return code, {"changes": [], "confidence": 1.0}
        
        # Choose transformation method based on ecosystem and type
        if ecosystem == "python":
            return await self._transform_python_code(
                code, dependency_name, breaking_changes, transformation_type
            )
        elif ecosystem == "nodejs":
            return await self._transform_javascript_code(
                code, dependency_name, breaking_changes, transformation_type
            )
        else:
            logger.warning(f"Unsupported ecosystem for transformation: {ecosystem}")
            return code, {
                "changes": [],
                "confidence": 0.0,
                "error": f"Unsupported ecosystem: {ecosystem}"
            }
    
    async def _transform_python_code(
        self,
        code: str,
        dependency_name: str,
        breaking_changes: List[Dict[str, Any]],
        transformation_type: str
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Transform Python code to adapt to breaking changes.
        
        Args:
            code: Python source code
            dependency_name: Dependency name
            breaking_changes: List of breaking changes
            transformation_type: Type of transformation
            
        Returns:
            Tuple of (transformed code, transformation details)
        """
        # Parse the code to build AST
        try:
            tree = ast.parse(code)
            
            # Track changes and their locations
            changes = []
            transformed_code = code
            
            # Process each breaking change
            for change in breaking_changes:
                change_type = change["type"]
                symbol = change["symbol"]
                
                if change_type == "signature_change":
                    # Handle API signature changes
                    transformed_code, change_details = await self._transform_signature_change(
                        transformed_code, symbol, change["old"], change["new"], dependency_name
                    )
                    if change_details:
                        changes.append({
                            "type": "signature_change",
                            "symbol": symbol,
                            "details": change_details
                        })
                
                elif change_type == "removed":
                    # Handle removed APIs
                    transformed_code, change_details = await self._transform_removed_api(
                        transformed_code, symbol, change.get("alternatives", []), dependency_name
                    )
                    if change_details:
                        changes.append({
                            "type": "removed_api",
                            "symbol": symbol,
                            "details": change_details
                        })
                
                elif change_type == "renamed":
                    # Handle renamed APIs
                    transformed_code, change_details = await self._transform_renamed_api(
                        transformed_code, symbol, change["new_name"], dependency_name
                    )
                    if change_details:
                        changes.append({
                            "type": "renamed_api",
                            "symbol": symbol,
                            "details": change_details
                        })
                
                elif change_type == "behavior_change":
                    # Handle API behavior changes
                    if settings.ENABLE_AI_FEATURES and self.model:
                        transformed_code, change_details = await self._transform_with_ai(
                            transformed_code, change, dependency_name
                        )
                        if change_details:
                            changes.append({
                                "type": "behavior_change",
                                "symbol": symbol,
                                "details": change_details
                            })
            
            # Compute confidence based on number of changes
            confidence = self._compute_confidence(changes, breaking_changes)
            
            return transformed_code, {
                "changes": changes,
                "confidence": confidence
            }
            
        except SyntaxError as e:
            logger.error(f"Syntax error in Python code: {str(e)}")
            return code, {
                "changes": [],
                "confidence": 0.0,
                "error": f"Syntax error in code: {str(e)}"
            }
        except Exception as e:
            logger.error(f"Error transforming Python code: {str(e)}")
            return code, {
                "changes": [],
                "confidence": 0.0,
                "error": f"Error during transformation: {str(e)}"
            }
    
    async def _transform_javascript_code(
        self,
        code: str,
        dependency_name: str,
        breaking_changes: List[Dict[str, Any]],
        transformation_type: str
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Transform JavaScript code to adapt to breaking changes.
        
        Args:
            code: JavaScript source code
            dependency_name: Dependency name
            breaking_changes: List of breaking changes
            transformation_type: Type of transformation
            
        Returns:
            Tuple of (transformed code, transformation details)
        """
        # Track changes and their locations
        changes = []
        transformed_code = code
        
        # Process each breaking change
        for change in breaking_changes:
            change_type = change["type"]
            symbol = change["symbol"]
            
            if change_type == "signature_change":
                # Handle API signature changes
                transformed_code, change_details = await self._transform_js_signature_change(
                    transformed_code, symbol, change["old"], change["new"], dependency_name
                )
                if change_details:
                    changes.append({
                        "type": "signature_change",
                        "symbol": symbol,
                        "details": change_details
                    })
            
            elif change_type == "removed":
                # Handle removed APIs
                transformed_code, change_details = await self._transform_js_removed_api(
                    transformed_code, symbol, change.get("alternatives", []), dependency_name
                )
                if change_details:
                    changes.append({
                        "type": "removed_api",
                        "symbol": symbol,
                        "details": change_details
                    })
            
            elif change_type == "renamed":
                # Handle renamed APIs
                transformed_code, change_details = await self._transform_js_renamed_api(
                    transformed_code, symbol, change["new_name"], dependency_name
                )
                if change_details:
                    changes.append({
                        "type": "renamed_api",
                        "symbol": symbol,
                        "details": change_details
                    })
            
            elif change_type == "behavior_change":
                # Handle API behavior changes
                if settings.ENABLE_AI_FEATURES and self.model:
                    transformed_code, change_details = await self._transform_with_ai(
                        transformed_code, change, dependency_name
                    )
                    if change_details:
                        changes.append({
                            "type": "behavior_change",
                            "symbol": symbol,
                            "details": change_details
                        })
        
        # Compute confidence based on number of changes
        confidence = self._compute_confidence(changes, breaking_changes)
        
        return transformed_code, {
            "changes": changes,
            "confidence": confidence
        }
    
    async def _transform_signature_change(
        self,
        code: str,
        symbol: str,
        old_signature: str,
        new_signature: str,
        dependency_name: str
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Transform code to adapt to API signature changes.
        
        Args:
            code: Source code
            symbol: Symbol that changed
            old_signature: Old API signature
            new_signature: New API signature
            dependency_name: Dependency name
            
        Returns:
            Tuple of (transformed code, change details)
        """
        # Parse the function signatures to understand parameter changes
        old_params = self._parse_function_params(old_signature)
        new_params = self._parse_function_params(new_signature)
        
        # Determine parameter differences
        added_params = [p for p in new_params if p not in old_params]
        removed_params = [p for p in old_params if p not in new_params]
        
        if not added_params and not removed_params:
            return code, None
        
        # Extract the symbol parts (module, function)
        symbol_parts = symbol.split('.')
        function_name = symbol_parts[-1]
        module_path = '.'.join(symbol_parts[:-1])
        
        # Find all calls to this function
        calls = []
        
        # Different search patterns based on import style
        if module_path:
            # For direct imports or aliased imports
            module_patterns = [
                f"{module_path}.{function_name}\\(",  # Full path
                f"from\\s+{module_path}\\s+import\\s+{function_name}",  # From import
            ]
            
            # Find all imports to determine potential aliases
            import_aliases = {}
            import_pattern = f"import\\s+{module_path}\\s+as\\s+(\\w+)"
            for match in re.finditer(import_pattern, code):
                alias = match.group(1)
                import_aliases[alias] = module_path
            
            # Add alias patterns
            for alias, module in import_aliases.items():
                if module == module_path:
                    module_patterns.append(f"{alias}.{function_name}\\(")
        else:
            # Just the function name (possibly imported directly)
            module_patterns = [
                f"{function_name}\\(",
                f"from\\s+{dependency_name}\\s+import\\s+{function_name}"
            ]
        
        # Find all call sites
        call_pattern = f"({function_name})\\s*\\(([^\\)]*)\\)"
        for match in re.finditer(call_pattern, code):
            func_name = match.group(1)
            args = match.group(2)
            
            # Check if this is actually the function we're looking for
            # by verifying it's imported from the right module
            call_start = match.start()
            call_line = code.count('\n', 0, call_start) + 1
            
            # Extract the line for context
            line_start = code.rfind('\n', 0, call_start) + 1
            line_end = code.find('\n', call_start)
            if line_end == -1:
                line_end = len(code)
            
            call_context = code[line_start:line_end]
            
            calls.append({
                "line": call_line,
                "start": call_start,
                "end": match.end(),
                "args": args,
                "context": call_context
            })
        
        # Transform calls
        changes = []
        for call in reversed(calls):  # Process in reverse to handle offsets correctly
            try:
                # Parse the call arguments
                args_str = call["args"]
                parsed_args = self._parse_call_args(args_str)
                
                # Determine what changes need to be made
                updated_args = self._update_call_args(
                    parsed_args, old_params, new_params, added_params
                )
                
                # Apply the changes to the code
                updated_call = f"{function_name}({updated_args})"
                code = code[:call["start"]] + updated_call + code[call["end"]:]
                
                changes.append({
                    "line": call["line"],
                    "before": call["context"],
                    "after": updated_call
                })
            except Exception as e:
                logger.error(f"Error transforming function call: {str(e)}")
        
        return code, {"modified_calls": changes}
    
    async def _transform_removed_api(
        self,
        code: str,
        symbol: str,
        alternatives: List[str],
        dependency_name: str
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Transform code to adapt to removed APIs.
        
        Args:
            code: Source code
            symbol: Symbol that was removed
            alternatives: Alternative APIs to use
            dependency_name: Dependency name
            
        Returns:
            Tuple of (transformed code, change details)
        """
        # Extract the symbol parts (module, function)
        symbol_parts = symbol.split('.')
        function_name = symbol_parts[-1]
        module_path = '.'.join(symbol_parts[:-1])
        
        # Find all calls to this function
        calls = []
        
        # Find call pattern based on module path
        if module_path:
            call_pattern = f"({module_path}\\.{function_name})\\s*\\(([^\\)]*)\\)"
        else:
            call_pattern = f"({function_name})\\s*\\(([^\\)]*)\\)"
        
        for match in re.finditer(call_pattern, code):
            func_name = match.group(1)
            args = match.group(2)
            
            call_start = match.start()
            call_line = code.count('\n', 0, call_start) + 1
            
            # Extract the line for context
            line_start = code.rfind('\n', 0, call_start) + 1
            line_end = code.find('\n', call_start)
            if line_end == -1:
                line_end = len(code)
            
            call_context = code[line_start:line_end]
            
            calls.append({
                "line": call_line,
                "start": call_start,
                "end": match.end(),
                "args": args,
                "context": call_context
            })
        
        # Transform calls using alternatives
        changes = []
        for call in reversed(calls):
            try:
                # Choose the best alternative (first one for now)
                if alternatives:
                    alt = alternatives[0]
                    
                    # Parse the call arguments
                    args_str = call["args"]
                    
                    # Create replacement call based on alternative
                    if "(" in alt and ")" in alt:
                        # Alternative already has parameter pattern
                        # Need to map old args to new format
                        replacement = alt
                    else:
                        # Simple replacement, keep args
                        replacement = f"{alt}({args_str})"
                    
                    # Add comment about the change
                    replacement = f"{replacement}  # TODO: Replaced removed API {symbol}"
                    
                    # Apply the changes to the code
                    updated_line = code[:call["start"]] + replacement + code[call["end"]:]
                    code = updated_line
                    
                    changes.append({
                        "line": call["line"],
                        "before": call["context"],
                        "after": replacement,
                        "alternative_used": alt
                    })
                else:
                    # No alternatives, add a warning comment
                    warning = f"# TODO: API {symbol} was removed with no direct alternative"
                    line_start = code.rfind('\n', 0, call["start"]) + 1
                    code = code[:line_start] + warning + "\n" + code[line_start:]
                    
                    changes.append({
                        "line": call["line"],
                        "before": call["context"],
                        "after": f"{warning}\n{call['context']}",
                        "warning": f"No alternative available for {symbol}"
                    })
            except Exception as e:
                logger.error(f"Error transforming removed API: {str(e)}")
        
        return code, {"modified_calls": changes}
    
    async def _transform_renamed_api(
        self,
        code: str,
        old_name: str,
        new_name: str,
        dependency_name: str
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Transform code to adapt to renamed APIs.
        
        Args:
            code: Source code
            old_name: Old API name
            new_name: New API name
            dependency_name: Dependency name
            
        Returns:
            Tuple of (transformed code, change details)
        """
        # Extract the symbol parts (module, function)
        old_parts = old_name.split('.')
        old_func = old_parts[-1]
        old_module = '.'.join(old_parts[:-1])
        
        new_parts = new_name.split('.')
        new_func = new_parts[-1]
        new_module = '.'.join(new_parts[:-1])
        
        changes = []
        
        # Handle import statements first
        if old_module:
            # Look for import statements
            import_pattern = f"from\\s+{old_module}\\s+import\\s+{old_func}"
            for match in re.finditer(import_pattern, code):
                import_start = match.start()
                import_end = match.end()
                
                # Create replacement import
                if old_module == new_module:
                    replacement = f"from {old_module} import {new_func}"
                else:
                    replacement = f"from {new_module} import {new_func}"
                
                # Apply the change
                code = code[:import_start] + replacement + code[import_end:]
                
                changes.append({
                    "type": "import",
                    "before": match.group(0),
                    "after": replacement
                })
        
        # Now handle actual API calls
        if old_module:
            call_pattern = f"({old_module}\\.{old_func})\\s*\\("
        else:
            call_pattern = f"(?<![.\\w])({old_func})\\s*\\("
        
        for match in re.finditer(call_pattern, code):
            func_name = match.group(1)
            call_start = match.start(1)
            call_end = match.end(1)
            
            # Extract the line for context
            line_start = code.rfind('\n', 0, call_start) + 1
            line_end = code.find('\n', call_start)
            if line_end == -1:
                line_end = len(code)
            
            call_context = code[line_start:line_end]
            
            # Create replacement call
            if old_module == new_module:
                replacement = new_func
            else:
                replacement = f"{new_module}.{new_func}"
            
            # Apply the change
            code = code[:call_start] + replacement + code[call_end:]
            
            changes.append({
                "type": "call",
                "before": func_name,
                "after": replacement,
                "context": call_context
            })
        
        return code, {"changes": changes}
    
    async def _transform_js_signature_change(
        self,
        code: str,
        symbol: str,
        old_signature: str,
        new_signature: str,
        dependency_name: str
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Transform JavaScript code to adapt to API signature changes.
        
        Args:
            code: Source code
            symbol: Symbol that changed
            old_signature: Old API signature
            new_signature: New API signature
            dependency_name: Dependency name
            
        Returns:
            Tuple of (transformed code, change details)
        """
        # Parse the function signatures to understand parameter changes
        old_params = self._parse_js_function_params(old_signature)
        new_params = self._parse_js_function_params(new_signature)
        
        # Determine parameter differences
        added_params = [p for p in new_params if p not in old_params]
        removed_params = [p for p in old_params if p not in new_params]
        
        if not added_params and not removed_params:
            return code, None
        
        # Extract the symbol parts
        symbol_parts = symbol.split('.')
        
        # Handle special cases like lodash
        if symbol.startswith('_.'):
            function_name = symbol_parts[1]
            module_path = '_'
        else:
            function_name = symbol_parts[-1]
            module_path = '.'.join(symbol_parts[:-1]) if len(symbol_parts) > 1 else ''
        
        # Find all calls to this function
        calls = []
        
        # Build the search pattern based on module path
        if module_path:
            if module_path == '_':
                # Lodash-style: _.function()
                call_pattern = f"(_\\.{function_name})\\s*\\(([^\\)]*)\\)"
            else:
                # Regular: module.function()
                call_pattern = f"({module_path}\\.{function_name})\\s*\\(([^\\)]*)\\)"
        else:
            # Just function()
            call_pattern = f"(?<![.\\w])({function_name})\\s*\\(([^\\)]*)\\)"
        
        for match in re.finditer(call_pattern, code):
            func_name = match.group(1)
            args = match.group(2)
            
            call_start = match.start()
            call_line = code.count('\n', 0, call_start) + 1
            
            # Extract the line for context
            line_start = code.rfind('\n', 0, call_start) + 1
            line_end = code.find('\n', call_start)
            if line_end == -1:
                line_end = len(code)
            
            call_context = code[line_start:line_end]
            
            calls.append({
                "line": call_line,
                "start": match.start(),
                "end": match.end(),
                "args": args,
                "context": call_context
            })
        
        # Transform calls
        changes = []
        for call in reversed(calls):
            try:
                # Parse the call arguments
                args_str = call["args"]
                parsed_args = self._parse_js_call_args(args_str)
                
                # Determine what changes need to be made
                updated_args = self._update_js_call_args(
                    parsed_args, old_params, new_params, added_params
                )
                
                # Apply the changes to the code
                updated_call = f"{match.group(1)}({updated_args})"
                code = code[:call["start"]] + updated_call + code[call["end"]:]
                
                changes.append({
                    "line": call["line"],
                    "before": call["context"],
                    "after": updated_call
                })
            except Exception as e:
                logger.error(f"Error transforming JavaScript function call: {str(e)}")
        
        return code, {"modified_calls": changes}
    
    async def _transform_js_removed_api(
        self,
        code: str,
        symbol: str,
        alternatives: List[str],
        dependency_name: str
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Transform JavaScript code to adapt to removed APIs.
        
        Args:
            code: Source code
            symbol: Symbol that was removed
            alternatives: Alternative APIs to use
            dependency_name: Dependency name
            
        Returns:
            Tuple of (transformed code, change details)
        """
        # Similar to the Python version but adjusted for JavaScript syntax
        symbol_parts = symbol.split('.')
        
        # Handle special cases like lodash
        if symbol.startswith('_.'):
            function_name = symbol_parts[1]
            module_path = '_'
        else:
            function_name = symbol_parts[-1]
            module_path = '.'.join(symbol_parts[:-1]) if len(symbol_parts) > 1 else ''
        
        # Find all calls to this function
        calls = []
        
        # Build the search pattern based on module path
        if module_path:
            if module_path == '_':
                # Lodash-style: _.function()
                call_pattern = f"(_\\.{function_name})\\s*\\(([^\\)]*)\\)"
            else:
                # Regular: module.function()
                call_pattern = f"({module_path}\\.{function_name})\\s*\\(([^\\)]*)\\)"
        else:
            # Just function()
            call_pattern = f"(?<![.\\w])({function_name})\\s*\\(([^\\)]*)\\)"
        
        for match in re.finditer(call_pattern, code):
            func_name = match.group(1)
            args = match.group(2)
            
            call_start = match.start()
            call_line = code.count('\n', 0, call_start) + 1
            
            # Extract the line for context
            line_start = code.rfind('\n', 0, call_start) + 1
            line_end = code.find('\n', call_start)
            if line_end == -1:
                line_end = len(code)
            
            call_context = code[line_start:line_end]
            
            calls.append({
                "line": call_line,
                "start": match.start(),
                "end": match.end(),
                "args": args,
                "context": call_context
            })
        
        # Transform calls using alternatives
        changes = []
        for call in reversed(calls):
            try:
                # Choose the best alternative
                if alternatives:
                    alt = alternatives[0]
                    
                    # Parse the call arguments
                    args_str = call["args"]
                    
                    # Create replacement call based on alternative
                    if "(" in alt and ")" in alt:
                        # Alternative already has parameter pattern
                        replacement = alt
                    else:
                        # Simple replacement, keep args
                        replacement = f"{alt}({args_str})"
                    
                    # Add comment about the change
                    replacement = f"{replacement} // TODO: Replaced removed API {symbol}"
                    
                    # Apply the changes to the code
                    code = code[:call["start"]] + replacement + code[call["end"]:]
                    
                    changes.append({
                        "line": call["line"],
                        "before": call["context"],
                        "after": replacement,
                        "alternative_used": alt
                    })
                else:
                    # No alternatives, add a warning comment
                    warning = f"// TODO: API {symbol} was removed with no direct alternative"
                    line_start = code.rfind('\n', 0, call["start"]) + 1
                    code = code[:line_start] + warning + "\n" + code[line_start:]
                    
                    changes.append({
                        "line": call["line"],
                        "before": call["context"],
                        "after": f"{warning}\n{call['context']}",
                        "warning": f"No alternative available for {symbol}"
                    })
            except Exception as e:
                logger.error(f"Error transforming removed JavaScript API: {str(e)}")
        
        return code, {"modified_calls": changes}
    
    async def _transform_js_renamed_api(
        self,
        code: str,
        old_name: str,
        new_name: str,
        dependency_name: str
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Transform JavaScript code to adapt to renamed APIs.
        
        Args:
            code: Source code
            old_name: Old API name
            new_name: New API name
            dependency_name: Dependency name
            
        Returns:
            Tuple of (transformed code, change details)
        """
        # Extract the symbol parts
        old_parts = old_name.split('.')
        new_parts = new_name.split('.')
        
        # Handle special cases like lodash
        if old_name.startswith('_.'):
            old_func = old_parts[1]
            old_module = '_'
        else:
            old_func = old_parts[-1]
            old_module = '.'.join(old_parts[:-1]) if len(old_parts) > 1 else ''
        
        if new_name.startswith('_.'):
            new_func = new_parts[1]
            new_module = '_'
        else:
            new_func = new_parts[-1]
            new_module = '.'.join(new_parts[:-1]) if len(new_parts) > 1 else ''
        
        changes = []
        
        # Handle import statements first (ES6 style)
        if old_module and old_module != '_':
            # Look for import statements
            import_pattern = f"import\\s+{{\\s*{old_func}\\s*}}\\s+from\\s+['\"]([^'\"]+)['\"]"
            for match in re.finditer(import_pattern, code):
                import_start = match.start()
                import_end = match.end()
                import_source = match.group(1)
                
                # Create replacement import
                if old_module == new_module:
                    replacement = f"import {{ {new_func} }} from '{import_source}'"
                else:
                    # This might need a new import statement
                    replacement = f"import {{ {new_func} }} from '{new_module}'"
                
                # Apply the change
                code = code[:import_start] + replacement + code[import_end:]
                
                changes.append({
                    "type": "import",
                    "before": match.group(0),
                    "after": replacement
                })
        
        # Now handle actual API calls
        if old_module:
            if old_module == '_':
                call_pattern = f"(_\\.{old_func})\\s*\\("
            else:
                call_pattern = f"({old_module}\\.{old_func})\\s*\\("
        else:
            call_pattern = f"(?<![.\\w])({old_func})\\s*\\("
        
        for match in re.finditer(call_pattern, code):
            func_name = match.group(1)
            call_start = match.start(1)
            call_end = match.end(1)
            
            # Extract the line for context
            line_start = code.rfind('\n', 0, call_start) + 1
            line_end = code.find('\n', call_start)
            if line_end == -1:
                line_end = len(code)
            
            call_context = code[line_start:line_end]
            
            # Create replacement call
            if old_module == new_module:
                if old_module == '_':
                    replacement = f"_.{new_func}"
                else:
                    replacement = new_func
            else:
                if new_module == '_':
                    replacement = f"_.{new_func}"
                else:
                    replacement = f"{new_module}.{new_func}"
            
            # Apply the change
            code = code[:call_start] + replacement + code[call_end:]
            
            changes.append({
                "type": "call",
                "before": func_name,
                "after": replacement,
                "context": call_context
            })
        
        return code, {"changes": changes}
    
    async def _transform_with_ai(
        self,
        code: str,
        change: Dict[str, Any],
        dependency_name: str
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Transform code using AI for complex changes.
        
        Args:
            code: Source code
            change: Breaking change details
            dependency_name: Dependency name
            
        Returns:
            Tuple of (transformed code, change details)
        """
        if not settings.ENABLE_AI_FEATURES or not self.model:
            return code, None
        
        try:
            # Extract the symbol and description
            symbol = change["symbol"]
            description = change.get("description", "Behavior changed")
            
            # Context for the AI model
            context = {
                "symbol": symbol,
                "dependency": dependency_name,
                "change_description": description,
                "change_type": change["type"],
                "alternatives": change.get("alternatives", [])
            }
            
            # Get AI-generated code transformation
            transformed_code = await self.model.transform_code(code, context)
            
            # Calculate diff to summarize changes
            diff = difflib.unified_diff(
                code.splitlines(), transformed_code.splitlines(),
                fromfile="original", tofile="transformed",
                lineterm=""
            )
            
            return transformed_code, {
                "ai_generated": True,
                "confidence": 0.7,  # AI-based transformations have less confidence
                "summary": f"AI-transformed for behavior change in {symbol}",
                "diff": "\n".join(list(diff))
            }
            
        except Exception as e:
            logger.error(f"Error during AI transformation: {str(e)}")
            return code, None
    
    def _parse_function_params(self, signature: str) -> List[Dict[str, Any]]:
        """
        Parse a Python function signature to extract parameters.
        
        Args:
            signature: Function signature string
            
        Returns:
            List of parameter information
        """
        # Extract the parameter part from the signature
        # Format: function_name(param1, param2=default, *args, **kwargs)
        params_match = re.match(r'.*?\((.*?)\)', signature)
        if not params_match:
            return []
            
        params_str = params_match.group(1).strip()
        if not params_str:
            return []
            
        # Split by commas, but handle defaults with commas
        param_parts = []
        current_part = ""
        paren_level = 0
        
        for char in params_str:
            if char == ',' and paren_level == 0:
                param_parts.append(current_part.strip())
                current_part = ""
            else:
                current_part += char
                if char == '(':
                    paren_level += 1
                elif char == ')':
                    paren_level -= 1
        
        if current_part:
            param_parts.append(current_part.strip())
        
        # Parse each parameter
        params = []
        for i, part in enumerate(param_parts):
            # Check for default value
            if '=' in part:
                name, default = part.split('=', 1)
                has_default = True
            else:
                name = part
                default = None
                has_default = False
            
            # Check for special parameters
            if name.startswith('*') and not name.startswith('**'):
                param_type = 'args'
                name = name[1:]
            elif name.startswith('**'):
                param_type = 'kwargs'
                name = name[2:]
            else:
                param_type = 'regular'
            
            params.append({
                "name": name.strip(),
                "position": i,
                "has_default": has_default,
                "default": default.strip() if default else None,
                "type": param_type
            })
        
        return params
    
    def _parse_call_args(self, args_str: str) -> List[Dict[str, Any]]:
        """
        Parse Python function call arguments.
        
        Args:
            args_str: Function arguments string
            
        Returns:
            List of argument information
        """
        if not args_str.strip():
            return []
            
        # Split by commas, but handle nested commas
        arg_parts = []
        current_part = ""
        paren_level = 0
        bracket_level = 0
        brace_level = 0
        
        for char in args_str:
            if char == ',' and paren_level == 0 and bracket_level == 0 and brace_level == 0:
                arg_parts.append(current_part.strip())
                current_part = ""
            else:
                current_part += char
                if char == '(':
                    paren_level += 1
                elif char == ')':
                    paren_level -= 1
                elif char == '[':
                    bracket_level += 1
                elif char == ']':
                    bracket_level -= 1
                elif char == '{':
                    brace_level += 1
                elif char == '}':
                    brace_level -= 1
        
        if current_part:
            arg_parts.append(current_part.strip())
        
        # Parse each argument
        args = []
        for i, part in enumerate(arg_parts):
            # Check for keyword argument
            if '=' in part:
                keyword, value = part.split('=', 1)
                is_keyword = True
                arg_name = keyword.strip()
                arg_value = value.strip()
            else:
                is_keyword = False
                arg_name = None
                arg_value = part.strip()
            
            args.append({
                "position": i,
                "is_keyword": is_keyword,
                "name": arg_name,
                "value": arg_value
            })
        
        return args
    
    def _update_call_args(
        self,
        current_args: List[Dict[str, Any]],
        old_params: List[Dict[str, Any]],
        new_params: List[Dict[str, Any]],
        added_params: List[Dict[str, Any]]
    ) -> str:
        """
        Update function call arguments based on parameter changes.
        
        Args:
            current_args: Current arguments
            old_params: Old parameters
            new_params: New parameters
            added_params: Added parameters
            
        Returns:
            Updated arguments string
        """
        # Start with the current args
        updated_args = []
        
        # Handle positional arguments first
        positional_count = len([a for a in current_args if not a["is_keyword"]])
        
        # Add current args, adjusting positions if needed
        for arg in current_args:
            if arg["is_keyword"]:
                # Keyword arg
                updated_args.append(f"{arg['name']}={arg['value']}")
            else:
                # Positional arg
                updated_args.append(arg["value"])
        
        # Add new required parameters
        for param in added_params:
            # Only add if it has no default and isn't a special parameter
            if not param["has_default"] and param["type"] == "regular":
                # For safety, always add as a keyword argument
                updated_args.append(f"{param['name']}=None  # TODO: Add proper value")
            elif param["has_default"]:
                # Add comment about new parameter with default
                updated_args.append(f"# Note: New parameter '{param['name']}' with default {param['default']}")
        
        return ", ".join(updated_args)
    
    def _parse_js_function_params(self, signature: str) -> List[Dict[str, Any]]:
        """
        Parse a JavaScript function signature to extract parameters.
        
        Args:
            signature: Function signature string
            
        Returns:
            List of parameter information
        """
        # Extract the parameter part from the signature
        # Format: function_name(param1, param2=default)
        params_match = re.match(r'.*?\((.*?)\)', signature)
        if not params_match:
            return []
            
        params_str = params_match.group(1).strip()
        if not params_str:
            return []
            
        # Split by commas, but handle defaults with commas
        param_parts = []
        current_part = ""
        paren_level = 0
        
        for char in params_str:
            if char == ',' and paren_level == 0:
                param_parts.append(current_part.strip())
                current_part = ""
            else:
                current_part += char
                if char == '(':
                    paren_level += 1
                elif char == ')':
                    paren_level -= 1
        
        if current_part:
            param_parts.append(current_part.strip())
        
        # Parse each parameter
        params = []
        for i, part in enumerate(param_parts):
            # Check for default value (usually not in JS signatures but just in case)
            if '=' in part:
                name, default = part.split('=', 1)
                has_default = True
            else:
                name = part
                default = None
                has_default = False
            
            # In JS, we might have rest parameter (...args)
            if name.startswith('...'):
                param_type = 'rest'
                name = name[3:]
            else:
                param_type = 'regular'
            
            params.append({
                "name": name.strip(),
                "position": i,
                "has_default": has_default,
                "default": default.strip() if default else None,
                "type": param_type
            })
        
        return params
    
    def _parse_js_call_args(self, args_str: str) -> List[Dict[str, Any]]:
        """
        Parse JavaScript function call arguments.
        
        Args:
            args_str: Function arguments string
            
        Returns:
            List of argument information
        """
        # JavaScript doesn't have keyword arguments in the same way as Python
        # but we'll use the same structure for consistency
        if not args_str.strip():
            return []
            
        # Split by commas, but handle nested commas
        arg_parts = []
        current_part = ""
        paren_level = 0
        bracket_level = 0
        brace_level = 0
        
        for char in args_str:
            if char == ',' and paren_level == 0 and bracket_level == 0 and brace_level == 0:
                arg_parts.append(current_part.strip())
                current_part = ""
            else:
                current_part += char
                if char == '(':
                    paren_level += 1
                elif char == ')':
                    paren_level -= 1
                elif char == '[':
                    bracket_level += 1
                elif char == ']':
                    bracket_level -= 1
                elif char == '{':
                    brace_level += 1
                elif char == '}':
                    brace_level -= 1
        
        if current_part:
            arg_parts.append(current_part.strip())
        
        # Parse each argument
        args = []
        for i, part in enumerate(arg_parts):
            # In JS, we don't have real keyword args, but we might have object property names
            is_keyword = False
            arg_name = None
            
            # Check for object properties at the top level only
            if part.strip().startswith('{') and part.strip().endswith('}'):
                # This is an object literal, which might be used like keyword args
                inside = part.strip()[1:-1]
                # Very simple check for property: value pairs
                if ':' in inside:
                    is_keyword = True
                    arg_name = "object_literal"
            
            args.append({
                "position": i,
                "is_keyword": is_keyword,
                "name": arg_name,
                "value": part.strip()
            })
        
        return args
    
    def _update_js_call_args(
        self,
        current_args: List[Dict[str, Any]],
        old_params: List[Dict[str, Any]],
        new_params: List[Dict[str, Any]],
        added_params: List[Dict[str, Any]]
    ) -> str:
        """
        Update JavaScript function call arguments based on parameter changes.
        
        Args:
            current_args: Current arguments
            old_params: Old parameters
            new_params: New parameters
            added_params: Added parameters
            
        Returns:
            Updated arguments string
        """
        # Start with the current args
        updated_args = []
        
        # Add current args
        for arg in current_args:
            updated_args.append(arg["value"])
        
        # Add new required parameters
        for param in added_params:
            if not param["has_default"] and param["type"] == "regular":
                # For required params, add null with a comment
                updated_args.append(f"null /* TODO: Add proper value for {param['name']} */")
            elif param["has_default"]:
                # For params with defaults, add a comment
                updated_args.append(f"/* New param with default: {param['name']} = {param['default']} */")
        
        return ", ".join(updated_args)
    
    def _compute_confidence(
        self,
        changes: List[Dict[str, Any]],
        breaking_changes: List[Dict[str, Any]]
    ) -> float:
        """
        Compute confidence score for the transformation.
        
        Args:
            changes: List of applied changes
            breaking_changes: List of breaking changes
            
        Returns:
            Confidence score (0-1)
        """
        if not breaking_changes:
            return 1.0  # No changes needed
            
        if not changes:
            return 0.0  # No changes applied despite breaking changes
            
        # Base confidence on ratio of changes applied to breaking changes required
        ratio = min(1.0, len(changes) / len(breaking_changes))
        
        # Adjust based on change types
        confidence = ratio * 0.8  # Start with 80% of ratio
        
        # Increase confidence for more deterministic changes
        signature_changes = sum(1 for c in changes if c.get("type") == "signature_change")
        renamed_apis = sum(1 for c in changes if c.get("type") == "renamed_api")
        
        if signature_changes > 0:
            confidence += 0.1  # Signature changes are more reliable
            
        if renamed_apis > 0:
            confidence += 0.1  # Renamed APIs are also reliable
            
        # Decrease confidence for AI-based changes
        ai_changes = sum(1 for c in changes if c.get("ai_generated", False))
        if ai_changes > 0:
            confidence -= 0.2 * (ai_changes / len(changes))
            
        return min(1.0, max(0.1, confidence))  # Keep between 0.1 and 1.0