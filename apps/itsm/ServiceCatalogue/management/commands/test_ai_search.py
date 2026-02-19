"""
Management command to test and debug AI search configuration and connectivity.

Usage:
    python manage.py test_ai_search [--verbose]
"""

from django.core.management.base import BaseCommand
from django.conf import settings
import requests
import json
import sys


class Command(BaseCommand):
    help = 'Test and debug AI search configuration and API connectivity'

    def add_arguments(self, parser):
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Show detailed request/response information',
        )
        parser.add_argument(
            '--language',
            type=str,
            default='en',
            help='Language for AI search test (default: en)',
        )
        parser.add_argument(
            '--model',
            type=str,
            default=None,
            metavar='MODEL_ID',
            help=(
                'Override the AI_SEARCH_MODEL setting for this test run only.  '
                'Useful for trying a different model without editing .env.  '
                'Example: --model deepseek-r1-distill-llama-70b'
            ),
        )

    def handle(self, *args, **options):
        verbose = options['verbose']
        language = options['language']
        model_override = options.get('model')  # None unless --model was passed
        
        self.stdout.write(self.style.MIGRATE_HEADING('\n=== AI Search Configuration Test ===\n'))
        
        # Track overall success
        all_checks_passed = True
        
        # Check 1: AI_SEARCH_ENABLED
        self.stdout.write('1. Checking AI_SEARCH_ENABLED...')
        enabled = getattr(settings, 'AI_SEARCH_ENABLED', False)
        if enabled:
            self.stdout.write(self.style.SUCCESS('   ✓ AI Search is ENABLED'))
        else:
            self.stdout.write(self.style.ERROR('   ✗ AI Search is DISABLED'))
            self.stdout.write(self.style.WARNING('   → Fix: Set AI_SEARCH_ENABLED=True in your .env file'))
            all_checks_passed = False
        
        # Check 2: AI_SEARCH_API_URL
        self.stdout.write('\n2. Checking AI_SEARCH_API_URL...')
        api_url = getattr(settings, 'AI_SEARCH_API_URL', '')
        if api_url:
            self.stdout.write(self.style.SUCCESS(f'   ✓ API URL configured: {api_url}'))
        else:
            self.stdout.write(self.style.ERROR('   ✗ API URL not configured'))
            self.stdout.write(self.style.WARNING('   → Fix: Set AI_SEARCH_API_URL in your .env file'))
            self.stdout.write(self.style.WARNING('   → Example: AI_SEARCH_API_URL=https://kisski-api.gwdg.de/v1/chat/completions'))
            all_checks_passed = False
        
        # Check 3: AI_SEARCH_API_KEY
        self.stdout.write('\n3. Checking AI_SEARCH_API_KEY...')
        api_key = getattr(settings, 'AI_SEARCH_API_KEY', '')
        if api_key:
            # Show only first/last 4 chars for security
            masked_key = f"{api_key[:4]}...{api_key[-4:]}" if len(api_key) > 8 else "***"
            self.stdout.write(self.style.SUCCESS(f'   ✓ API Key configured: {masked_key}'))
        else:
            self.stdout.write(self.style.ERROR('   ✗ API Key not configured'))
            self.stdout.write(self.style.WARNING('   → Fix: Set AI_SEARCH_API_KEY in your .env file'))
            self.stdout.write(self.style.WARNING('   → For KISSKI: Request access at https://kisski.uni-goettingen.de'))
            all_checks_passed = False
        
        # Check 4: AI_SEARCH_MODEL
        self.stdout.write('\n4. Checking AI_SEARCH_MODEL...')
        model = getattr(settings, 'AI_SEARCH_MODEL', '')
        if model_override:
            self.stdout.write(self.style.SUCCESS(f'   ✓ Model configured: {model}'))
            self.stdout.write(self.style.WARNING(
                f'   ⚡ Overriding with --model {model_override} for this test run'
            ))
            model = model_override
        elif model:
            self.stdout.write(self.style.SUCCESS(f'   ✓ Model configured: {model}'))
        else:
            self.stdout.write(self.style.ERROR('   ✗ Model not configured'))
            self.stdout.write(self.style.WARNING('   → Fix: Set AI_SEARCH_MODEL in your .env file'))
            self.stdout.write(self.style.WARNING(
                '   → Example: AI_SEARCH_MODEL=deepseek-r1-distill-llama-70b'
            ))
            all_checks_passed = False
        
        # Check 5: AI_SEARCH_TIMEOUT
        self.stdout.write('\n5. Checking AI_SEARCH_TIMEOUT...')
        timeout = getattr(settings, 'AI_SEARCH_TIMEOUT', 180)
        self.stdout.write(self.style.SUCCESS(f'   ✓ Timeout configured: {timeout} seconds'))
        if timeout < 60:
            self.stdout.write(self.style.WARNING('   ℹ Timeout might be too short for complex queries (recommended: 180)'))
        
        # If basic config is missing, stop here
        if not all([enabled, api_url, api_key, model]):
            self.stdout.write(self.style.ERROR('\n❌ Configuration incomplete. Please fix the issues above.\n'))
            sys.exit(1)
        
        # Build base URL (strip /chat/completions suffix if present)
        base_api_url = api_url.rstrip('/')
        if base_api_url.endswith('/chat/completions'):
            base_api_url = base_api_url[: -len('/chat/completions')]

        # Check 6: Network connectivity test
        self.stdout.write('\n6. Testing network connectivity...')
        try:
            # Use a lightweight unauthenticated GET; a 401/403 still confirms reachability
            response = requests.get(base_api_url, timeout=5)
            self.stdout.write(self.style.SUCCESS(f'   ✓ Network connectivity OK (HTTP {response.status_code})'))
        except requests.exceptions.ConnectionError as e:
            self.stdout.write(self.style.ERROR(f'   ✗ Connection failed: {str(e)}'))
            self.stdout.write(self.style.WARNING('   → Fix: Check if the itsm container has internet access'))
            self.stdout.write(self.style.WARNING('   → Verify docker-compose.yml includes "internet" network for itsm service'))
            self.stdout.write(self.style.WARNING('   → Test: docker exec itsm_app ping -c 1 8.8.8.8'))
            all_checks_passed = False
        except requests.exceptions.Timeout:
            self.stdout.write(self.style.ERROR('   ✗ Connection timeout'))
            self.stdout.write(self.style.WARNING('   → Fix: Check firewall settings or network configuration'))
            all_checks_passed = False
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'   ✗ Network error: {str(e)}'))
            all_checks_passed = False

        # Check 7: Fetch available models and verify configured model is listed
        self.stdout.write('\n7. Fetching available models from API...')
        try:
            headers = {
                'Authorization': f'Bearer {api_key}',
                'Accept': 'application/json',
                'Content-Type': 'application/json',
            }
            models_url = f'{base_api_url}/models'
            self.stdout.write(f'   Requesting: POST {models_url}')
            models_response = requests.post(
                models_url,
                headers=headers,
                timeout=15,
            )

            if models_response.status_code == 200:
                try:
                    models_data = models_response.json()
                    # OpenAI-compatible format: {"object": "list", "data": [{"id": "...", ...}, ...]}
                    model_ids = []
                    if isinstance(models_data, dict) and 'data' in models_data:
                        model_ids = [m.get('id', '') for m in models_data['data'] if m.get('id')]
                    elif isinstance(models_data, list):
                        model_ids = [m.get('id', '') for m in models_data if isinstance(m, dict) and m.get('id')]

                    if model_ids:
                        self.stdout.write(self.style.SUCCESS(f'   ✓ {len(model_ids)} model(s) available:'))
                        for mid in model_ids:
                            marker = '  ← configured' if mid == model else ''
                            self.stdout.write(f'     • {mid}{marker}')
                    else:
                        self.stdout.write(self.style.WARNING('   ⚠ No model IDs found in response'))
                        if verbose:
                            self.stdout.write(f'   Raw response: {models_response.text[:500]}')

                    # Verify the configured model is actually available
                    if model_ids and model not in model_ids:
                        self.stdout.write(self.style.ERROR(
                            f'\n   ✗ Configured model "{model}" is NOT in the list of available models!'
                        ))
                        self.stdout.write(self.style.WARNING(
                            '   → Fix: Update AI_SEARCH_MODEL in your .env file to one of the listed models.'
                        ))
                        all_checks_passed = False
                    elif model in model_ids:
                        self.stdout.write(self.style.SUCCESS(f'   ✓ Configured model "{model}" is available'))

                except (json.JSONDecodeError, KeyError) as e:
                    self.stdout.write(self.style.WARNING(f'   ⚠ Could not parse models response: {e}'))
                    if verbose:
                        self.stdout.write(f'   Raw response: {models_response.text[:500]}')

            elif models_response.status_code == 401:
                self.stdout.write(self.style.ERROR('   ✗ Authentication failed when fetching models (HTTP 401)'))
                self.stdout.write(self.style.WARNING('   → Fix: Check your AI_SEARCH_API_KEY'))
                all_checks_passed = False
            elif models_response.status_code == 404:
                self.stdout.write(self.style.WARNING(
                    f'   ⚠ Models endpoint returned 404 – provider may not support this endpoint'
                ))
                self.stdout.write(self.style.WARNING(
                    f'      URL tried: {models_url}'
                ))
                self.stdout.write(self.style.WARNING(
                    '      Skipping model availability check.'
                ))
            else:
                self.stdout.write(self.style.WARNING(
                    f'   ⚠ Unexpected response from models endpoint (HTTP {models_response.status_code})'
                ))
                if verbose:
                    self.stdout.write(f'   Response: {models_response.text[:300]}')

        except requests.exceptions.Timeout:
            self.stdout.write(self.style.WARNING('   ⚠ Models endpoint timed out – skipping model list check'))
        except requests.exceptions.ConnectionError as e:
            self.stdout.write(self.style.ERROR(f'   ✗ Connection error fetching models: {e}'))
            all_checks_passed = False
        except Exception as e:
            self.stdout.write(self.style.WARNING(f'   ⚠ Could not fetch model list: {e}'))
            if verbose:
                import traceback
                self.stdout.write(traceback.format_exc())

        # Check 8: API authentication and model availability
        self.stdout.write('\n8. Testing API authentication (chat completions)...')
        try:
            headers = {
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json'
            }
            
            # Test with minimal request
            test_payload = {
                'model': model,
                'messages': [
                    {'role': 'user', 'content': 'Test'}
                ],
                'max_tokens': 10
            }
            
            # Construct full endpoint URL from pre-computed base URL
            full_api_url = f"{base_api_url}/chat/completions"
            
            if verbose:
                self.stdout.write(f'\n   Request URL: {full_api_url}')
                self.stdout.write(f'   Request Method: POST')
                self.stdout.write(f'   Request Headers:')
                self.stdout.write(f'     Authorization: Bearer {masked_key}')
                self.stdout.write(f'     Content-Type: application/json')
                self.stdout.write(f'   Request Body:')
                self.stdout.write(f'     {json.dumps(test_payload, indent=6)}')
            
            self.stdout.write(f'   Making request to: {full_api_url}')
            
            response = requests.post(
                full_api_url,
                headers=headers,
                json=test_payload,
                timeout=timeout
            )
            
            # Always show response details on error, even without --verbose
            if response.status_code != 200 or verbose:
                self.stdout.write(f'\n   Response Status: HTTP {response.status_code}')
                if verbose:
                    self.stdout.write(f'   Response Headers: {dict(response.headers)}')
                self.stdout.write(f'   Response Body:')
                # Show full response on error, truncate on verbose success
                max_len = 1000 if response.status_code != 200 else 500
                body = response.text[:max_len]
                if len(response.text) > max_len:
                    body += '...'
                for line in body.split('\n'):
                    self.stdout.write(f'     {line}')
            
            if response.status_code == 200:
                self.stdout.write(self.style.SUCCESS('   ✓ API authentication successful'))
                try:
                    response_data = response.json()
                    if 'choices' in response_data and len(response_data['choices']) > 0:
                        self.stdout.write(self.style.SUCCESS('   ✓ Model is responding correctly'))
                        if verbose:
                            self.stdout.write(f"   Response preview: {response_data['choices'][0].get('message', {}).get('content', '')[:100]}")
                    else:
                        self.stdout.write(self.style.WARNING('   ⚠ Unexpected response format'))
                        self.stdout.write(f'   Response: {response.text[:200]}')
                except json.JSONDecodeError:
                    self.stdout.write(self.style.ERROR('   ✗ Invalid JSON response'))
                    self.stdout.write(f'   Response: {response.text[:200]}')
                    all_checks_passed = False
            
            elif response.status_code == 401:
                self.stdout.write(self.style.ERROR('   ✗ Authentication failed (HTTP 401)'))
                self.stdout.write(self.style.WARNING('   → Fix: Check your AI_SEARCH_API_KEY is correct'))
                self.stdout.write(self.style.WARNING('   → For KISSKI: Verify your API key at https://kisski.uni-goettingen.de'))
                all_checks_passed = False
            
            elif response.status_code == 404:
                self.stdout.write(self.style.ERROR('   ✗ Model or endpoint not found (HTTP 404)'))
                self.stdout.write(self.style.WARNING(f'   → Fix: Check AI_SEARCH_API_URL is correct'))
                self.stdout.write(self.style.WARNING(f'      Current (base): {base_api_url}'))
                self.stdout.write(self.style.WARNING(f'      Testing: {full_api_url}'))
                self.stdout.write(self.style.WARNING(f'   → Fix: AI_SEARCH_API_URL should be base URL (e.g., https://api.example.com/v1)'))
                self.stdout.write(self.style.WARNING(f'   → Fix: Verify model "{model}" is available on this API'))
                self.stdout.write(self.style.WARNING('   → Try: curl -X POST {url} -H "Authorization: Bearer YOUR_KEY" -d \'{"model":"'+model+'","messages":[{"role":"user","content":"test"}]}\''))
                all_checks_passed = False
            
            elif response.status_code == 429:
                self.stdout.write(self.style.ERROR('   ✗ Rate limit exceeded (HTTP 429)'))
                self.stdout.write(self.style.WARNING('   → Wait a moment and try again'))
                self.stdout.write(self.style.WARNING('   → Check your API quota/limits'))
                all_checks_passed = False
            
            elif response.status_code >= 500:
                self.stdout.write(self.style.ERROR(f'   ✗ Server error (HTTP {response.status_code})'))
                self.stdout.write(self.style.WARNING('   → The AI API service might be temporarily down'))
                self.stdout.write(self.style.WARNING('   → Try again later or contact API provider'))
                all_checks_passed = False
            
            else:
                self.stdout.write(self.style.ERROR(f'   ✗ Unexpected HTTP status: {response.status_code}'))
                self.stdout.write(f'   Response: {response.text[:200]}')
                all_checks_passed = False
        
        except requests.exceptions.Timeout:
            self.stdout.write(self.style.ERROR(f'   ✗ API request timeout (>{timeout}s)'))
            self.stdout.write(self.style.WARNING('   → Fix: Increase AI_SEARCH_TIMEOUT in .env file'))
            self.stdout.write(self.style.WARNING('   → Or check if API service is slow/overloaded'))
            all_checks_passed = False
        
        except requests.exceptions.ConnectionError as e:
            self.stdout.write(self.style.ERROR(f'   ✗ Connection error: {str(e)}'))
            self.stdout.write(self.style.WARNING('   → Fix: Verify internet connectivity from container'))
            all_checks_passed = False
        
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'   ✗ Unexpected error: {str(e)}'))
            if verbose:
                import traceback
                self.stdout.write(traceback.format_exc())
            all_checks_passed = False
        
        # Check 9: Prompt files
        self.stdout.write('\n9. Checking AI prompt files...')
        import os
        from pathlib import Path
        
        app_dir = Path(__file__).resolve().parent.parent.parent
        prompts_dir = app_dir / 'ai_prompts'
        step1_prompt = prompts_dir / 'step1_prompt.txt'
        step2_prompt = prompts_dir / 'step2_prompt.txt'
        
        if step1_prompt.exists() and step2_prompt.exists():
            self.stdout.write(self.style.SUCCESS('   ✓ Prompt files found'))
            step1_size = os.path.getsize(step1_prompt)
            step2_size = os.path.getsize(step2_prompt)
            if verbose:
                self.stdout.write(f'   - step1_prompt.txt: {step1_size} bytes')
                self.stdout.write(f'   - step2_prompt.txt: {step2_size} bytes')
        else:
            self.stdout.write(self.style.ERROR('   ✗ Prompt files missing'))
            self.stdout.write(self.style.WARNING(f'   → Expected location: {prompts_dir}'))
            all_checks_passed = False
        
        # Check 10: End-to-end AI search test (if all previous checks passed)
        if all_checks_passed:
            self.stdout.write('\n10. Running end-to-end AI search test...')
            try:
                from ServiceCatalogue.ai_service import AISearchService
                from ServiceCatalogue.models import ServiceRevision
                import datetime
                
                # Check if we have any listed services (same filter as ServiceListedView)
                service_count = (
                    ServiceRevision.objects
                    .filter(listed_from__lte=datetime.date.today())
                    .exclude(listed_until__lt=datetime.date.today())
                    .count()
                )
                if service_count == 0:
                    self.stdout.write(self.style.WARNING('   ⚠ No listed services in database - skipping end-to-end test'))
                    self.stdout.write(self.style.WARNING('   → Add some services with listed_from <= today and listed_until >= today'))
                else:
                    self.stdout.write(f'   Found {service_count} public services in database')
                    
                    # Perform a simple test search
                    ai_service = AISearchService()
                    if model_override:
                        ai_service.model = model_override
                        self.stdout.write(self.style.WARNING(
                            f'   ⚡ End-to-end test using overridden model: {model_override}'
                        ))
                    test_query = "I need help with email problems"
                    
                    self.stdout.write(f'   Testing with query: "{test_query}"')
                    self.stdout.write(f'   Using language: {language}')
                    if verbose:
                        self.stdout.write('   This will perform the full two-step AI search process...')
                        self.stdout.write('')
                    
                    # Run the search (this will actually call the API)
                    # In verbose mode, request the full conversation
                    result = ai_service.perform_search(test_query, language, None, return_conversation=verbose)
                    
                    if verbose and 'conversation' in result:
                        self.stdout.write('')
                        self.stdout.write(self.style.MIGRATE_HEADING('   === AI CONVERSATION ==='))
                        for i, turn in enumerate(result['conversation'], 1):
                            self.stdout.write('')
                            self.stdout.write(self.style.SUCCESS(f'   --- {turn["step"].upper()} ---'))
                            self.stdout.write('')
                            self.stdout.write('   PROMPT SENT TO AI:')
                            self.stdout.write('   ' + '-' * 70)
                            # Show prompt with line breaks for readability
                            for line in turn['prompt'].split('\n'):
                                self.stdout.write(f'   {line}')
                            self.stdout.write('   ' + '-' * 70)
                            self.stdout.write('')
                            self.stdout.write('   AI RESPONSE:')
                            self.stdout.write('   ' + '-' * 70)
                            # Show response with line breaks
                            for line in turn['response'].split('\n'):
                                self.stdout.write(f'   {line}')
                            self.stdout.write('   ' + '-' * 70)
                        self.stdout.write('')
                    
                    if verbose:
                        self.stdout.write('')
                        self.stdout.write(self.style.MIGRATE_HEADING('   === FULL SEARCH RESULT ==='))
                        import json as json_module
                        # Remove conversation from display to avoid duplication
                        display_result = {k: v for k, v in result.items() if k != 'conversation'}
                        self.stdout.write(f'   {json_module.dumps(display_result, indent=2)}')
                        self.stdout.write('')
                    
                    if result.get('success'):
                        self.stdout.write(self.style.SUCCESS('   ✓ End-to-end search completed successfully'))
                        if verbose:
                            self.stdout.write(f'   Step 1 completed: {result.get("step1_completed", False)}')
                            self.stdout.write(f'   Step 2 completed: {result.get("step2_completed", False)}')
                            self.stdout.write(f'   Step 1 only: {result.get("step1_only", False)}')
                            if result.get('step1_only'):
                                self.stdout.write(f'   Message: {result.get("message", "")[:200]}...')
                            else:
                                self.stdout.write(f'   Services checked: {result.get("services_checked", [])}')
                                if result.get('recommended_services'):
                                    self.stdout.write(f'   Recommended services: {len(result["recommended_services"])}')
                                    for svc in result['recommended_services']:
                                        self.stdout.write(f'     - {svc.get("service_key")}: {svc.get("relevance_explanation", "")[:100]}...')
                                if result.get('also_checked'):
                                    self.stdout.write(f'   Also checked: {len(result["also_checked"])} services')
                    else:
                        self.stdout.write(self.style.ERROR('   ✗ End-to-end search failed'))
                        self.stdout.write(self.style.WARNING(f'   Error: {result.get("error", "Unknown error")}'))
                        all_checks_passed = False
                        
            except ImportError as e:
                self.stdout.write(self.style.ERROR(f'   ✗ Import error: {str(e)}'))
                self.stdout.write(self.style.WARNING('   → Ensure ServiceCatalogue app is properly configured'))
                all_checks_passed = False
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'   ✗ End-to-end test failed: {str(e)}'))
                if verbose:
                    import traceback
                    self.stdout.write(traceback.format_exc())
                self.stdout.write(self.style.WARNING('   → Check application logs for details'))
                self.stdout.write(self.style.WARNING('   → Verify AI service configuration and connectivity'))
                all_checks_passed = False
        else:
            self.stdout.write('\n10. Skipping end-to-end test (previous checks failed)')
        
        # Final summary
        self.stdout.write(self.style.MIGRATE_HEADING('\n=== Test Summary ===\n'))
        
        if all_checks_passed:
            self.stdout.write(self.style.SUCCESS('✅ All checks passed! AI Search should work correctly.\n'))
            self.stdout.write('Next steps:')
            self.stdout.write('  - Access AI Search at: /service-catalogue/ai-search/')
            self.stdout.write('  - Monitor logs: docker logs -f itsm_app')
            self.stdout.write('  - Check admin panel for AI search statistics\n')
            sys.exit(0)
        else:
            self.stdout.write(self.style.ERROR('❌ Some checks failed. Please fix the issues above.\n'))
            self.stdout.write('Common solutions:')
            self.stdout.write('  1. Update your .env file with correct AI configuration')
            self.stdout.write('  2. Ensure itsm container has internet access (docker-compose.yml)')
            self.stdout.write('  3. Restart containers: docker compose restart itsm_app')
            self.stdout.write('  4. Check logs: docker logs itsm_app\n')
            sys.exit(1)
