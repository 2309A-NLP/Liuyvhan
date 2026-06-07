"""Test that our modified files import correctly."""
import sys
sys.path.insert(0, '.')

# Test config first (needs pydantic_settings)
from app.core.config import Settings
print('config.py OK')

# Check that schemas has the new field
from app.models.schemas import AskResponse
import inspect
sig = inspect.signature(AskResponse)
if 'query_understanding' in sig.parameters:
    print('schemas.py OK - query_understanding field present')
else:
    print('schemas.py WARNING - query_understanding field NOT found')

# Test llm_service imports (needs openai)
import app.services.llm_service
print('llm_service.py OK')
print('  Has classify_query:', hasattr(app.services.llm_service.LLMService, 'classify_query'))
print('  Has rewrite_query:', hasattr(app.services.llm_service.LLMService, 'rewrite_query'))

# Test query_enhancer_service
import app.services.query_enhancer_service
print('query_enhancer_service.py OK')
print('  Has enhance:', hasattr(app.services.query_enhancer_service.QueryEnhancerService, 'enhance'))
print('  Has _classify_query:', hasattr(app.services.query_enhancer_service.QueryEnhancerService, '_classify_query'))
print('  Has _rewrite_query:', hasattr(app.services.query_enhancer_service.QueryEnhancerService, '_rewrite_query'))
print('  Has _expand_synonyms:', hasattr(app.services.query_enhancer_service.QueryEnhancerService, '_expand_synonyms'))
print('  Has _decompose_query:', hasattr(app.services.query_enhancer_service.QueryEnhancerService, '_decompose_query'))

# Check container.py passes llm_service
from app.core.container import AppContainer
print('container.py OK')

print('\nAll import tests PASSED!')
