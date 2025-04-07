import os
import pickle
import logging
import asyncio
import numpy as np
from typing import Dict, List, Optional, Any, Union
from datetime import datetime

from backend.core.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)


class AIModel:
    """
    Base class for AI models used in the dependency intelligence platform.
    
    This class provides common functionality for loading models,
    making predictions, and managing model lifecycle.
    """
    
    def __init__(self, model_data: Any = None, metadata: Dict[str, Any] = None):
        """
        Initialize the AI model.
        
        Args:
            model_data: The actual model (could be sklearn, tensorflow, etc.)
            metadata: Model metadata
        """
        self.model_data = model_data
        self.metadata = metadata or {}
        self.last_used = datetime.now()
        
    @classmethod
    def load_model(cls, model_path: str) -> 'AIModel':
        """
        Load a model from disk.
        
        Args:
            model_path: Path to the saved model
            
        Returns:
            Loaded model instance
            
        Raises:
            FileNotFoundError: If the model file doesn't exist
            ValueError: If the model format is invalid
        """
        if not os.path.exists(model_path):
            raise FileNotFoundError(f"Model file not found: {model_path}")
        
        try:
            with open(model_path, 'rb') as f:
                model_dict = pickle.load(f)
                
            if not isinstance(model_dict, dict):
                raise ValueError("Invalid model format: expected dictionary")
                
            # Extract model data and metadata
            model_data = model_dict.get('model')
            metadata = model_dict.get('metadata', {})
            
            if model_data is None:
                raise ValueError("Invalid model format: missing 'model' key")
                
            # Create appropriate model subclass based on type
            model_type = metadata.get('type', 'generic')
            
            if model_type == 'code_transformer':
                return CodeTransformerModel(model_data, metadata)
            elif model_type == 'compatibility_predictor':
                return CompatibilityPredictorModel(model_data, metadata)
            else:
                return AIModel(model_data, metadata)
                
        except Exception as e:
            logger.error(f"Error loading model from {model_path}: {str(e)}")
            raise
    
    def save(self, output_path: str) -> None:
        """
        Save the model to disk.
        
        Args:
            output_path: Path to save the model
            
        Raises:
            IOError: If the model cannot be saved
        """
        # Ensure the directory exists
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        # Update metadata
        self.metadata['last_saved'] = datetime.now().isoformat()
        
        # Prepare model dictionary
        model_dict = {
            'model': self.model_data,
            'metadata': self.metadata
        }
        
        # Save to disk
        try:
            with open(output_path, 'wb') as f:
                pickle.dump(model_dict, f)
                
        except Exception as e:
            logger.error(f"Error saving model to {output_path}: {str(e)}")
            raise IOError(f"Failed to save model: {str(e)}")
    
    async def predict(self, input_data: Any) -> Any:
        """
        Make a prediction using the model.
        
        Args:
            input_data: Input data for prediction
            
        Returns:
            Prediction result
            
        Raises:
            ValueError: If the model is not loaded or input is invalid
        """
        if self.model_data is None:
            raise ValueError("Model not loaded")
            
        self.last_used = datetime.now()
        
        # This is a placeholder - subclasses should implement specific prediction logic
        raise NotImplementedError("Predict method not implemented for base class")


class CodeTransformerModel(AIModel):
    """
    AI model for code transformation between dependency versions.
    """
    
    async def transform_code(
        self,
        code: str,
        context: Dict[str, Any]
    ) -> str:
        """
        Transform code to adapt to dependency changes.
        
        Args:
            code: Source code to transform
            context: Transformation context (change details)
            
        Returns:
            Transformed code
        """
        if self.model_data is None:
            logger.warning("Model not loaded, returning original code")
            return code
            
        self.last_used = datetime.now()
        
        # In a real implementation, this would use the model to transform code
        # For now, we'll use a simple rule-based approach
        
        try:
            # Extract context information
            dependency = context.get("dependency", "")
            symbol = context.get("symbol", "")
            change_description = context.get("change_description", "")
            change_type = context.get("change_type", "")
            alternatives = context.get("alternatives", [])
            
            transformed_code = code
            
            # Apply simple transformations based on change type
            if change_type == "removed" and symbol and alternatives:
                # Replace removed API with alternative
                alt = alternatives[0] if alternatives else ""
                if alt and symbol:
                    # Simple string replacement - this is a naive approach
                    transformed_code = transformed_code.replace(symbol, alt)
                    
                    # Add comment explaining the change
                    comment = f"// Replaced removed API {symbol} with {alt}" if ".js" in context.get("file_type", "") else f"# Replaced removed API {symbol} with {alt}"
                    transformed_code = transformed_code.replace(alt, f"{alt} {comment}")
            
            elif change_type == "behavior_change" and symbol:
                # Add comment about behavior change
                comment = f"// CAUTION: Behavior changed in {symbol}: {change_description}" if ".js" in context.get("file_type", "") else f"# CAUTION: Behavior changed in {symbol}: {change_description}"
                
                # Find all occurrences of the symbol
                import re
                for match in re.finditer(re.escape(symbol), transformed_code):
                    pos = match.start()
                    line_start = transformed_code.rfind('\n', 0, pos) + 1
                    line_end = transformed_code.find('\n', pos)
                    if line_end == -1:
                        line_end = len(transformed_code)
                        
                    # Insert comment on the line before
                    transformed_code = transformed_code[:line_start] + comment + '\n' + transformed_code[line_start:]
                    
                    # Only add comment to first occurrence
                    break
            
            return transformed_code
            
        except Exception as e:
            logger.error(f"Error during code transformation: {str(e)}")
            # In case of error, return the original code
            return code
    
    async def predict(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Make a prediction using the code transformer model.
        
        Args:
            input_data: Dictionary with code and context
            
        Returns:
            Transformation result
        """
        if 'code' not in input_data or 'context' not in input_data:
            raise ValueError("Input must contain 'code' and 'context' keys")
            
        code = input_data['code']
        context = input_data['context']
        
        transformed_code = await self.transform_code(code, context)
        
        return {
            'transformed_code': transformed_code,
            'original_code': code,
            'context': context,
            'has_changes': transformed_code != code
        }


class CompatibilityPredictorModel(AIModel):
    """
    AI model for predicting compatibility between dependency versions.
    """
    
    async def predict_breaking_changes(
        self,
        input_data: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Predict breaking changes between dependency versions.
        
        Args:
            input_data: Dictionary with dependency info
            
        Returns:
            List of predicted breaking changes
        """
        if self.model_data is None:
            logger.warning("Model not loaded, returning empty predictions")
            return []
            
        self.last_used = datetime.now()
        
        # In a real implementation, this would use the trained model to predict
        # For now, we'll return mock predictions based on version difference
        
        try:
            # Extract input data
            dependency = input_data.get("dependency", "")
            ecosystem = input_data.get("ecosystem", "")
            current_version = input_data.get("current_version", "")
            target_version = input_data.get("target_version", "")
            
            # Parse version components
            def parse_version(version):
                try:
                    parts = version.replace('v', '').split('.')
                    return [int(p) for p in parts[:3]]
                except (ValueError, IndexError):
                    return [0, 0, 0]
            
            current_parts = parse_version(current_version)
            target_parts = parse_version(target_version)
            
            # Calculate version difference to determine breaking changes
            predictions = []
            
            # Major version increase - likely breaking changes
            if target_parts[0] > current_parts[0]:
                predictions.append({
                    "type": "behavior_change",
                    "symbol": f"{dependency}.api",
                    "description": f"API behavior likely changed in major version {target_parts[0]}",
                    "impact": "high",
                    "confidence": 0.7
                })
                
                predictions.append({
                    "type": "removed",
                    "symbol": f"{dependency}.legacyMethod",
                    "description": f"Legacy methods likely removed in version {target_parts[0]}",
                    "impact": "high",
                    "confidence": 0.6
                })
                
            # Minor version increase - possible new features or mild breaking changes
            elif target_parts[1] > current_parts[1]:
                predictions.append({
                    "type": "feature_change",
                    "symbol": f"{dependency}.featureMethod",
                    "description": f"Feature behavior may have changed in minor version {target_parts[1]}",
                    "impact": "medium",
                    "confidence": 0.5
                })
                
            # Add ecosystem-specific predictions
            if ecosystem == "python":
                if target_parts[0] > current_parts[0]:
                    predictions.append({
                        "type": "parameter_change",
                        "symbol": f"{dependency}.main_function",
                        "description": "Function parameters may have changed in the new major version",
                        "impact": "medium",
                        "confidence": 0.6
                    })
            elif ecosystem == "nodejs":
                if target_parts[0] > current_parts[0]:
                    predictions.append({
                        "type": "promises_change",
                        "symbol": f"{dependency}.asyncMethod",
                        "description": "Callback APIs may have been converted to Promises",
                        "impact": "high",
                        "confidence": 0.65
                    })
            
            return predictions
            
        except Exception as e:
            logger.error(f"Error predicting breaking changes: {str(e)}")
            return []
    
    async def predict(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Make a prediction using the compatibility predictor model.
        
        Args:
            input_data: Dictionary with dependency info
            
        Returns:
            Compatibility prediction result
        """
        breaking_changes = await self.predict_breaking_changes(input_data)
        
        result = {
            'breaking_changes': breaking_changes,
            'input_data': input_data,
            'compatibility_score': self._calculate_compatibility_score(breaking_changes),
            'confidence': self._calculate_confidence(breaking_changes)
        }
        
        return result
    
    def _calculate_compatibility_score(self, breaking_changes: List[Dict[str, Any]]) -> float:
        """Calculate compatibility score based on breaking changes."""
        if not breaking_changes:
            return 1.0
            
        # Start with a base score
        score = 1.0
        
        # Reduce score based on impact of breaking changes
        for change in breaking_changes:
            impact = change.get("impact", "low")
            if impact == "high":
                score -= 0.2
            elif impact == "medium":
                score -= 0.1
            else:
                score -= 0.05
        
        # Ensure score is within bounds
        return max(0.1, min(1.0, score))
    
    def _calculate_confidence(self, breaking_changes: List[Dict[str, Any]]) -> float:
        """Calculate confidence in the prediction."""
        if not breaking_changes:
            return 0.5
            
        # Average the confidence of all breaking changes
        confidences = [change.get("confidence", 0.5) for change in breaking_changes]
        return sum(confidences) / len(confidences)