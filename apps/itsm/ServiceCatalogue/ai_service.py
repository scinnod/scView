# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2024-2026 David Kleinhans, Jade University of Applied Sciences
"""
AI-Assisted Service Search Module

This module provides functionality for AI-assisted service search using OpenAI-compatible APIs.
It implements a two-step process:
1. Initial evaluation: Determine if user's problem is IT-related and identify candidate services
2. Detailed evaluation: Analyze candidate services in detail and provide recommendations

The module is designed to work with KISSKI AI (University of Göttingen) or any OpenAI-compatible API.
"""

import json
import time
import datetime
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import logging
import requests

from django.conf import settings
from django.utils.translation import get_language, gettext as _
from django.utils import translation

from modeltranslation.utils import build_localized_fieldname
from ServiceCatalogue.models import ServiceRevision, AISearchLog, Service, ServiceCategory

logger = logging.getLogger(__name__)


class AISearchService:
    """Service class for AI-assisted service catalogue search."""
    
    def __init__(self):
        self.api_url = getattr(settings, 'AI_SEARCH_API_URL')
        self.api_key = getattr(settings, 'AI_SEARCH_API_KEY')
        self.model = getattr(settings, 'AI_SEARCH_MODEL')
        self.timeout = getattr(settings, 'AI_SEARCH_TIMEOUT')
        self.enabled = getattr(settings, 'AI_SEARCH_ENABLED')
        
        # Load prompts
        self.prompts_dir = Path(__file__).parent / 'ai_prompts'
        self.step1_prompt_template = self._load_prompt('step1_prompt.txt')
        self.step2_prompt_template = self._load_prompt('step2_prompt.txt')
    
    def _load_prompt(self, filename: str) -> str:
        """Load a prompt template from the ai_prompts directory."""
        prompt_path = self.prompts_dir / filename
        try:
            with open(prompt_path, 'r', encoding='utf-8') as f:
                return f.read()
        except FileNotFoundError:
            logger.error(f"Prompt file not found: {prompt_path}")
            raise
    
    def is_enabled(self) -> bool:
        """Check if AI search is properly configured and enabled."""
        return (
            self.enabled and 
            self.api_url is not None and 
            self.api_key is not None
        )
    
    def _call_openai_api(self, messages: List[Dict], temperature: float = 0.7) -> Tuple[str, Optional[int]]:
        """
        Make a call to the OpenAI-compatible API.
        
        Args:
            messages: List of message dicts with 'role' and 'content'
            temperature: Sampling temperature
            
        Returns:
            Tuple of (response_text, tokens_used)
        """
        headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json',
        }
        
        payload = {
            'model': self.model,
            'messages': messages,
            'temperature': temperature,
        }
        
        try:
            response = requests.post(
                f'{self.api_url}/chat/completions',
                headers=headers,
                json=payload,
                timeout=self.timeout
            )
            response.raise_for_status()
            
            data = response.json()
            content = data['choices'][0]['message']['content']
            tokens = data.get('usage', {}).get('total_tokens', None)
            
            return content, tokens
            
        except requests.exceptions.Timeout:
            logger.error("AI API request timed out")
            raise TimeoutError(_("AI API request timed out"))
        except requests.exceptions.RequestException as e:
            logger.error(f"AI API request failed: {e}")
            raise
    
    def _get_categories_info(self, user_language: str) -> List[Dict]:
        """
        Get information about service categories that have currently listed services.
        
        Args:
            user_language: Language code (e.g., 'de', 'en')
            
        Returns:
            List of dicts with category information (deduplicated)
        """
        # Activate user's language for modeltranslation fallback
        current_language = translation.get_language()
        translation.activate(user_language)
        
        # Get categories that have at least one listed service revision
        categories_with_services = (
            ServiceCategory.objects
            .filter(
                service__servicerevision__listed_from__lte=datetime.date.today()
            )
            .exclude(
                service__servicerevision__listed_until__lt=datetime.date.today()
            )
            .distinct()
            .order_by('order')
        )
        
        categories = []
        seen_acronyms = set()  # Track acronyms to avoid duplicates
        
        for category in categories_with_services:
            # Skip if we've already added this category
            if category.acronym in seen_acronyms:
                continue
            seen_acronyms.add(category.acronym)
            
            # Access fields directly - modeltranslation handles fallback
            categories.append({
                'acronym': category.acronym,
                'name': category.name,  # modeltranslation handles fallback
                'description': category.description if hasattr(category, 'description') else '',
            })
        
        # Restore original language
        translation.activate(current_language)
        
        return categories
    
    def _get_listed_services(self, user_language: str) -> List[Dict]:
        """
        Get currently listed services (at Service level, not Revision level).
        
        This returns unique services without version information, as step 1
        operates at the service level to determine relevance.
        
        Args:
            user_language: Language code (e.g., 'de', 'en')
            
        Returns:
            List of dicts with service information (deduplicated)
        """
        # Activate user's language for modeltranslation fallback
        current_language = translation.get_language()
        translation.activate(user_language)
        
        # Get services that have at least one currently listed revision
        # Work at Service level, not Revision level
        services_with_listed_revisions = (
            Service.objects
            .filter(
                servicerevision__listed_from__lte=datetime.date.today()
            )
            .exclude(
                servicerevision__listed_until__lt=datetime.date.today()
            )
            .select_related('category')
            .distinct()
            .order_by('category__order', 'order')
        )
        
        services = []
        seen_keys = set()  # Track keys to avoid duplicates
        
        for service in services_with_listed_revisions:
            # Build service key without version (category-acronym format)
            service_key = f"{service.category.acronym}-{service.acronym}"
            
            # Skip if we've already added this service
            if service_key in seen_keys:
                continue
            seen_keys.add(service_key)
            
            # Access fields directly - modeltranslation handles fallback
            services.append({
                'key': service_key,
                'name': service.name,  # modeltranslation handles fallback
                'purpose': service.purpose,  # modeltranslation handles fallback
            })
        
        # Restore original language
        translation.activate(current_language)
        
        return services
    
    def _get_service_details(self, service_keys: List[str], user_language: str) -> Dict[str, Dict]:
        """
        Get detailed information about specific services.
        
        For step 2, we retrieve ALL currently listed revisions of the identified services.
        This includes different versions of the same service, as they may have different
        descriptions, availability periods, and features that the AI should differentiate.
        
        SECURITY: Only public fields are retrieved and sent to the AI.
        Internal fields (description_internal, responsible, submitted, available_from, etc.)
        are NEVER included. Field visibility settings from settings.py are strictly respected.
        
        TRANSLATION: This method activates the user's language to ensure modeltranslation's
        fallback system works correctly (MODELTRANSLATION_FALLBACK_LANGUAGES).
        
        Args:
            service_keys: List of service keys (format: CATEGORY-ACRONYM, without version)
            user_language: Language code
            
        Returns:
            Dict mapping service revision keys (with version) to their detailed information
        """
        # Activate the user's language so modeltranslation fallback works correctly
        # This ensures we get: user_lang -> fallback_lang1 -> fallback_lang2 -> base
        # instead of just: user_lang -> base
        current_language = translation.get_language()
        translation.activate(user_language)
        
        services_details = {}
        
        for key in service_keys:
            # Parse the service key (format: CATEGORY-ACRONYM, without version)
            try:
                parts = key.split('-', 1)
                if len(parts) != 2:
                    logger.warning(f"Invalid service key format: {key}")
                    continue
                
                category_acronym, service_acronym = parts
                
                # Find ALL currently listed revisions for this service
                # Different versions may have different content and availability
                revisions = (
                    ServiceRevision.objects
                    .filter(listed_from__lte=datetime.date.today())
                    .exclude(listed_until__lt=datetime.date.today())
                    .filter(
                        service__category__acronym=category_acronym,
                        service__acronym=service_acronym
                    )
                    .select_related('service', 'service__category')
                    .order_by('-version')  # Most recent version first
                )
                
                if not revisions.exists():
                    logger.warning(f"No currently listed revisions found for service {key}")
                    continue
                
                # Process ALL revisions (not just the first one)
                # This allows the AI to differentiate between versions
                for revision in revisions:
                    # Use revision.key which includes version: CATEGORY-ACRONYM-VERSION
                    revision_key = revision.key
                    
                    # SECURITY: Explicit allowlist of public fields that can be sent to AI
                    # Only retrieve and include fields that are meant to be public
                    # Internal fields (description_internal, responsible, submitted, etc.) are NEVER included
                    
                    # Access fields directly - modeltranslation handles fallback automatically
                    # since we've activated the user's language above
                    # Fallback chain: user_language -> MODELTRANSLATION_FALLBACK_LANGUAGES -> base field
                    
                    # Initialize with always-public core fields
                    service_detail = {
                        'key': revision_key,  # Includes version: CATEGORY-ACRONYM-VERSION
                        'name': revision.service.name,  # modeltranslation handles: name_xx -> name_de -> name_en -> name
                        'category': revision.service.category.name,
                        'purpose': revision.service.purpose,  # modeltranslation handles fallback
                        'description': revision.description,  # modeltranslation handles fallback
                        'version': revision.version,
                    }
                    
                    # Add availability information - critical for AI to prefer long-term solutions
                    if revision.listed_from:
                        service_detail['listed_from'] = revision.listed_from.isoformat()
                    if revision.listed_until:
                        service_detail['listed_until'] = revision.listed_until.isoformat()
                    
                    # Add optional public fields only if they are enabled in settings
                    # This respects field visibility configuration
                    if settings.SERVICECATALOGUE_FIELD_REQUIREMENTS:
                        requirements = revision.requirements  # modeltranslation handles fallback
                        if requirements:
                            service_detail['requirements'] = requirements
                    
                    if settings.SERVICECATALOGUE_FIELD_USAGE_INFORMATION:
                        usage_info = revision.usage_information  # modeltranslation handles fallback
                        if usage_info:
                            service_detail['usage_information'] = usage_info
                    
                    if settings.SERVICECATALOGUE_FIELD_DETAILS:
                        details = revision.details  # modeltranslation handles fallback
                        if details:
                            service_detail['details'] = details
                    
                    if settings.SERVICECATALOGUE_FIELD_OPTIONS:
                        options = revision.options  # modeltranslation handles fallback
                        if options:
                            service_detail['options'] = options
                    
                    if settings.SERVICECATALOGUE_FIELD_SERVICE_LEVEL:
                        service_level = revision.service_level  # modeltranslation handles fallback
                        if service_level:
                            service_detail['service_level'] = service_level
                    
                    # Add public contact fields (these are shown in public service catalog)
                    if revision.contact:
                        service_detail['contact'] = revision.contact
                    if revision.url:
                        service_detail['url'] = revision.url
                    
                    services_details[revision_key] = service_detail
                
            except Exception as e:
                logger.error(f"Error looking up service {key}: {str(e)}")
                continue
        
        # Restore original language
        translation.activate(current_language)
        
        return services_details
    
    def _format_categories_list(self, categories: List[Dict]) -> str:
        """Format categories list for the AI prompt."""
        if not categories:
            return "No categories available."
        
        lines = []
        for category in categories:
            lines.append(f"- Acronym: {category['acronym']}")
            lines.append(f"  Name: {category['name']}")
            if category.get('description'):
                lines.append(f"  Description: {category['description']}")
            lines.append("")
        return "\n".join(lines)
    
    def _format_services_list(self, services: List[Dict]) -> str:
        """Format services list for the AI prompt."""
        lines = []
        for service in services:
            lines.append(f"- Key: {service['key']}")
            lines.append(f"  Name: {service['name']}")
            lines.append(f"  Purpose: {service['purpose']}")
            lines.append("")
        return "\n".join(lines)
    
    def _format_services_details(self, services_details: Dict[str, Dict]) -> str:
        """Format detailed services information for the AI prompt."""
        lines = []
        for key, details in services_details.items():
            lines.append(f"=== {details['name']} ({key}) ===")
            lines.append(f"Category: {details['category']}")
            lines.append(f"Version: {details['version']}")
            
            # Show availability period - important for AI to prefer long-term solutions
            if 'listed_from' in details:
                lines.append(f"Listed from: {details['listed_from']}")
            if 'listed_until' in details:
                lines.append(f"Listed until: {details['listed_until']}")
            
            lines.append(f"\nPurpose: {details['purpose']}")
            lines.append(f"\nDescription:\n{details['description']}")
            
            if 'requirements' in details:
                lines.append(f"\nRequirements:\n{details['requirements']}")
            if 'usage_information' in details:
                lines.append(f"\nUsage Information:\n{details['usage_information']}")
            if 'details' in details:
                lines.append(f"\nDetails:\n{details['details']}")
            if 'options' in details:
                lines.append(f"\nOptions:\n{details['options']}")
            if 'contact' in details:
                lines.append(f"\nContact: {details['contact']}")
            if 'url' in details:
                lines.append(f"\nURL: {details['url']}")
            
            lines.append("\n" + "="*80 + "\n")
        
        return "\n".join(lines)
    
    def _extract_json_from_response(self, response: str) -> str:
        """
        Extract JSON from AI response, handling markdown code blocks and reasoning tags.
        
        AI models often wrap JSON in:
        - Markdown code blocks: ```json {...} ```
        - Reasoning tags (deepseek-r1): <think>...</think>{...}
        
        This function extracts the actual JSON content.
        """
        response = response.strip()
        
        # Remove <think>...</think> blocks (deepseek-r1 reasoning model)
        response = re.sub(r'<think>.*?</think>', '', response, flags=re.DOTALL)
        response = response.strip()
        
        # Check if response is wrapped in markdown code blocks
        if response.startswith('```'):
            # Find the first newline (end of opening ```)
            first_newline = response.find('\n')
            if first_newline != -1:
                # Find the closing ```
                closing_idx = response.rfind('```')
                if closing_idx != -1 and closing_idx > first_newline:
                    # Extract content between markers
                    response = response[first_newline + 1:closing_idx].strip()
        
        # Try to find JSON object boundaries if extraction failed
        if not response or response[0] not in ('{', '['):
            # Look for first { or [
            start_idx = response.find('{')
            if start_idx == -1:
                start_idx = response.find('[')
            
            if start_idx != -1:
                # Find matching closing brace
                if response[start_idx] == '{':
                    end_char = '}'
                else:
                    end_char = ']'
                
                # Find last occurrence of closing character
                end_idx = response.rfind(end_char)
                if end_idx > start_idx:
                    response = response[start_idx:end_idx + 1]
        
        return response
    
    def perform_search(self, user_input: str, user_language: str, user=None, progress_callback=None, return_conversation=False) -> Dict:
        """
        Perform the two-step AI-assisted search process.
        
        Args:
            user_input: The user's problem description
            user_language: Language code for responses
            user: Django user object (optional, for logging)
            progress_callback: Optional callback function to update progress (called with status string)
            return_conversation: If True, include full conversation in the result (for debugging)
            
        Returns:
            Dict with search results and metadata
        """
        start_time = time.time()
        log_entry = AISearchLog(user=user)
        conversation = []  # Track conversation for debugging
        
        try:
            # Step 1: Initial evaluation
            logger.info("Starting AI search step 1: Initial evaluation")
            
            if progress_callback:
                progress_callback('step1')
            
            # Get categories and services information
            categories = self._get_categories_info(user_language)
            services = self._get_listed_services(user_language)
            
            # Map language code to full language name
            language_names = {
                'en': 'English',
                'de': 'German (Deutsch)',
                'fr': 'French (Français)',
                'es': 'Spanish (Español)',
            }
            language_name = language_names.get(user_language, user_language.upper())
            
            categories_list_text = self._format_categories_list(categories)
            services_list_text = self._format_services_list(services)
            
            step1_prompt = self.step1_prompt_template.format(
                language_name=language_name,
                categories_list=categories_list_text,
                services_list=services_list_text,
                user_input=user_input
            )
            
            messages = [
                {'role': 'system', 'content': step1_prompt}
            ]
            
            if return_conversation:
                conversation.append({
                    'step': 'step1',
                    'prompt': step1_prompt,
                    'messages': messages.copy()
                })
            
            step1_response, tokens1 = self._call_openai_api(messages, temperature=0.3)
            log_entry.tokens_used_step1 = tokens1
            log_entry.step1_completed = True
            
            if return_conversation:
                conversation[-1]['response'] = step1_response
            
            # Parse step 1 response
            try:
                # Extract JSON from response (handles markdown code blocks)
                json_content = self._extract_json_from_response(step1_response)
                
                if not json_content:
                    logger.error(f"Empty JSON content after extraction. Original response: {step1_response[:1000]}")
                    raise ValueError(_("AI returned an empty response"))
                
                step1_data = json.loads(json_content)
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse step 1 response as JSON")
                logger.error(f"Original response: {step1_response[:1000]}")
                logger.error(f"Extracted JSON content: {json_content[:1000] if json_content else 'EMPTY'}")
                logger.error(f"JSON decode error: {str(e)}")
                raise ValueError(_("AI response was not valid JSON. The AI may need to be instructed to return JSON format."))
            
            services_to_check = step1_data.get('services_to_check', [])
            log_entry.services_requested = services_to_check
            
            # If no services to check, return step 1 result
            if not services_to_check:
                log_entry.step2_needed = False
                log_entry.duration_seconds = time.time() - start_time
                log_entry.save()
                
                result = {
                    'success': True,
                    'step1_only': True,
                    'step1_completed': True,
                    'step2_completed': False,
                    'message': step1_data.get('preliminary_note', ''),
                    'is_it_related': step1_data.get('is_it_related', False),
                    'log_id': log_entry.id
                }
                
                if return_conversation:
                    result['conversation'] = conversation
                    
                return result
            
            # Step 2: Detailed evaluation
            logger.info(f"Starting AI search step 2: Detailed evaluation of {len(services_to_check)} services")
            log_entry.step2_needed = True
            
            if progress_callback:
                progress_callback('step2')
            
            services_details = self._get_service_details(services_to_check, user_language)
            services_details_text = self._format_services_details(services_details)
            
            # Map language code to full language name (same as step 1)
            language_names = {
                'en': 'English',
                'de': 'German (Deutsch)',
                'fr': 'French (Français)',
                'es': 'Spanish (Español)',
            }
            language_name = language_names.get(user_language, user_language.upper())
            
            step2_prompt = self.step2_prompt_template.format(
                language_name=language_name,
                user_input=user_input,
                services_to_check=', '.join(services_to_check),
                services_details=services_details_text
            )
            
            # Include conversation history
            messages = [
                {'role': 'system', 'content': step1_prompt},
                {'role': 'assistant', 'content': step1_response},
                {'role': 'user', 'content': step2_prompt}
            ]
            
            if return_conversation:
                conversation.append({
                    'step': 'step2',
                    'prompt': step2_prompt,
                    'messages': messages.copy()
                })
            
            step2_response, tokens2 = self._call_openai_api(messages, temperature=0.3)
            log_entry.tokens_used_step2 = tokens2
            
            if return_conversation:
                conversation[-1]['response'] = step2_response
            
            # Parse step 2 response
            try:
                # Extract JSON from response (handles markdown code blocks)
                json_content = self._extract_json_from_response(step2_response)
                step2_data = json.loads(json_content)
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse step 2 response as JSON: {step2_response[:500]}")
                logger.error(f"JSON decode error: {str(e)}")
                raise ValueError(_("AI response was not valid JSON"))
            
            # Extract recommended service keys and enrich with names/versions
            recommended_services = step2_data.get('recommended_services', [])
            log_entry.services_recommended = [s['service_key'] for s in recommended_services]
            
            # Enrich recommended services with name and version from services_details
            for service in recommended_services:
                service_key = service.get('service_key', '')
                if service_key in services_details:
                    service['service_name'] = services_details[service_key].get('name', service_key)
                    service['service_version'] = services_details[service_key].get('version', '')
            
            # Enrich also_checked services with name and version
            also_checked = step2_data.get('also_checked', [])
            for service in also_checked:
                service_key = service.get('service_key', '')
                if service_key in services_details:
                    service['service_name'] = services_details[service_key].get('name', service_key)
                    service['service_version'] = services_details[service_key].get('version', '')
            
            log_entry.duration_seconds = time.time() - start_time
            log_entry.save()
            
            result = {
                'success': True,
                'step1_only': False,
                'step1_completed': True,
                'step2_completed': True,
                'services_checked': services_to_check,
                'overall_assessment': step2_data.get('overall_assessment', ''),
                'recommended_services': recommended_services,
                'also_checked': also_checked,
                'log_id': log_entry.id
            }
            
            if return_conversation:
                result['conversation'] = conversation
                
            return result
            
        except Exception as e:
            logger.exception("Error during AI search")
            log_entry.error_occurred = True
            log_entry.error_message = str(e)
            log_entry.duration_seconds = time.time() - start_time
            log_entry.save()
            
            return {
                'success': False,
                'error': str(e),
                'log_id': log_entry.id
            }
