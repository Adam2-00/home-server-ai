"""
AI Provider Configuration and Multi-Provider Support
Supports OpenAI, Anthropic Claude, and custom API endpoints
"""
import os
import json
from typing import Dict, Optional, List
from dataclasses import dataclass, asdict


@dataclass
class AIProviderConfig:
    """Configuration for AI provider."""
    provider: str  # 'openai', 'anthropic', 'custom'
    model: str
    api_key: str
    base_url: Optional[str] = None  # For custom endpoints (Ollama, etc.)
    temperature: float = 0.2
    max_tokens: int = 4000
    
    def to_dict(self) -> Dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'AIProviderConfig':
        return cls(**data)


# Provider presets
PROVIDER_PRESETS = {
    'openai': {
        'name': 'OpenAI (GPT-4, GPT-3.5)',
        'models': ['gpt-4o', 'gpt-4o-mini', 'gpt-4-turbo', 'gpt-3.5-turbo'],
        'default_model': 'gpt-4o-mini',
        'base_url': None,
        'env_key': 'OPENAI_API_KEY',
        'docs_url': 'https://platform.openai.com/api-keys'
    },
    'anthropic': {
        'name': 'Anthropic (Claude)',
        'models': ['claude-3-5-sonnet-20241022', 'claude-3-opus-20240229', 'claude-3-haiku-20240307'],
        'default_model': 'claude-3-5-sonnet-20241022',
        'base_url': None,
        'env_key': 'ANTHROPIC_API_KEY',
        'docs_url': 'https://console.anthropic.com/settings/keys'
    },
    'ollama': {
        'name': 'Ollama (Local Models)',
        'models': ['llama3.2', 'mistral', 'codellama', 'phi3'],
        'default_model': 'llama3.2',
        'base_url': 'http://localhost:11434/v1',
        'env_key': None,  # Ollama doesn't need API key by default
        'docs_url': 'https://ollama.com'
    },
    'openrouter': {
        'name': 'OpenRouter (Multiple Models)',
        'models': ['anthropic/claude-3.5-sonnet', 'openai/gpt-4o', 'meta-llama/llama-3.2-70b'],
        'default_model': 'anthropic/claude-3.5-sonnet',
        'base_url': 'https://openrouter.ai/api/v1',
        'env_key': 'OPENROUTER_API_KEY',
        'docs_url': 'https://openrouter.ai/keys'
    },
    'custom': {
        'name': 'Custom Endpoint',
        'models': ['custom-model'],
        'default_model': 'custom-model',
        'base_url': '',  # User must provide
        'env_key': 'CUSTOM_API_KEY',
        'docs_url': None
    }
}


def get_ai_config_from_env() -> Optional[AIProviderConfig]:
    """Try to detect AI configuration from environment variables."""
    # Check OpenAI
    if os.getenv('OPENAI_API_KEY'):
        return AIProviderConfig(
            provider='openai',
            model='gpt-4o-mini',
            api_key=os.getenv('OPENAI_API_KEY'),
            base_url=None
        )
    
    # Check Anthropic
    if os.getenv('ANTHROPIC_API_KEY'):
        return AIProviderConfig(
            provider='anthropic',
            model='claude-3-5-sonnet-20241022',
            api_key=os.getenv('ANTHROPIC_API_KEY'),
            base_url=None
        )
    
    # Check OpenRouter
    if os.getenv('OPENROUTER_API_KEY'):
        return AIProviderConfig(
            provider='openrouter',
            model='anthropic/claude-3.5-sonnet',
            api_key=os.getenv('OPENROUTER_API_KEY'),
            base_url='https://openrouter.ai/api/v1'
        )
    
    # Check Ollama
    if os.getenv('OLLAMA_HOST') or os.path.exists('/usr/local/bin/ollama'):
        return AIProviderConfig(
            provider='ollama',
            model='llama3.2',
            api_key='ollama',  # Ollama accepts any key
            base_url=os.getenv('OLLAMA_HOST', 'http://localhost:11434/v1')
        )
    
    return None


def prompt_for_ai_config() -> Optional[AIProviderConfig]:
    """Interactive prompt to configure AI provider."""
    print("\n🤖 AI Configuration")
    print("The setup assistant can use AI to create custom installation plans.")
    print("You can use OpenAI, Anthropic Claude, or local models via Ollama.\n")
    
    print("Available providers:")
    for key, preset in PROVIDER_PRESETS.items():
        print(f"  {key:12} - {preset['name']}")
    
    print("\nSelect a provider (or press Enter to skip AI and use templates):")
    choice = input("> ").strip().lower()
    
    if not choice:
        print("   Skipping AI configuration. Will use template plans.")
        return None
    
    if choice not in PROVIDER_PRESETS:
        print(f"   Unknown provider '{choice}'. Using OpenAI as default.")
        choice = 'openai'
    
    preset = PROVIDER_PRESETS[choice]
    
    # Show available models
    print(f"\nAvailable models for {preset['name']}:")
    for i, model in enumerate(preset['models'], 1):
        default_marker = " (default)" if model == preset['default_model'] else ""
        print(f"  {i}. {model}{default_marker}")
    
    print("\nSelect model (number or name, Enter for default):")
    model_choice = input("> ").strip()
    
    if model_choice.isdigit():
        idx = int(model_choice) - 1
        if 0 <= idx < len(preset['models']):
            model = preset['models'][idx]
        else:
            model = preset['default_model']
    elif model_choice:
        model = model_choice
    else:
        model = preset['default_model']
    
    # Get API key
    if preset['env_key']:
        env_value = os.getenv(preset['env_key'])
        if env_value:
            print(f"\n✓ Found {preset['env_key']} in environment")
            api_key = env_value
        else:
            print(f"\nEnter your API key for {preset['name']}:")
            print(f"  (Get one at: {preset['docs_url']})")
            api_key = input("> ").strip()
    else:
        api_key = 'not-needed'
    
    # Get base URL for custom endpoints
    base_url = preset['base_url']
    if choice == 'custom' or not base_url:
        print(f"\nEnter the API base URL (e.g., http://localhost:11434/v1):")
        custom_url = input("> ").strip()
        if custom_url:
            base_url = custom_url
    
    config = AIProviderConfig(
        provider=choice,
        model=model,
        api_key=api_key,
        base_url=base_url
    )
    
    print(f"\n✓ AI configured: {preset['name']} with {model}")
    return config


def create_ai_client(config: AIProviderConfig):
    """Create appropriate AI client based on configuration."""
    if config.provider == 'anthropic':
        try:
            import anthropic
            return anthropic.Anthropic(api_key=config.api_key)
        except ImportError:
            print("   Warning: anthropic package not installed. Run: pip install anthropic")
            return None
    else:
        # OpenAI-compatible API (OpenAI, Ollama, OpenRouter, custom)
        try:
            from openai import OpenAI
            client_kwargs = {'api_key': config.api_key}
            if config.base_url:
                client_kwargs['base_url'] = config.base_url
            return OpenAI(**client_kwargs)
        except ImportError:
            print("   Warning: openai package not installed. Run: pip install openai")
            return None


def call_ai_with_config(
    config: AIProviderConfig,
    system_prompt: str,
    user_prompt: str,
    expect_json: bool = True
) -> Optional[Dict]:
    """Call AI with the configured provider."""
    client = create_ai_client(config)
    if not client:
        return None
    
    try:
        if config.provider == 'anthropic':
            # Anthropic uses different API structure
            message = client.messages.create(
                model=config.model,
                max_tokens=config.max_tokens,
                temperature=config.temperature,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}]
            )
            content = message.content[0].text
        else:
            # OpenAI-compatible API
            response_format = {"type": "json_object"} if expect_json else None
            
            response = client.chat.completions.create(
                model=config.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=config.temperature,
                max_tokens=config.max_tokens,
                response_format=response_format
            )
            content = response.choices[0].message.content
        
        if expect_json:
            return json.loads(content)
        return {"content": content}
        
    except Exception as e:
        print(f"   AI API error ({config.provider}): {e}")
        return None
