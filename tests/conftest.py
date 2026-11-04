"""
Test configuration for browser-use.
"""
import logging
import os
import sys

import pytest

# Ensure the project root is in the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Load environment variables
from dotenv import load_dotenv

load_dotenv()

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

import langchain_core.language_models.fake as fake_models
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, ChatResult

if hasattr(fake_models, 'FakeListChatModel'):
	FakeListChatModel = fake_models.FakeListChatModel
else:

	class FakeListChatModel(BaseChatModel):
		def __init__(self, responses: list[str]):
			super().__init__()
			self.responses = responses
			self._response_index = 0

		@property
		def _llm_type(self) -> str:
			return 'fake-list-chat-model'

		def _generate(self, messages, stop=None, run_manager=None, **kwargs):
			if self._response_index >= len(self.responses):
				raise ValueError('No more fake responses available.')
			text = self.responses[self._response_index]
			self._response_index += 1
			generation = ChatGeneration(message=AIMessage(content=text))
			return ChatResult(generations=[generation])

from browser_use.browser.browser import Browser, BrowserConfig
from browser_use.browser.context import BrowserContext


@pytest.fixture(scope="session")
def llm():
    """
    Fixture to provide a ChatOpenAI instance or a mock for testing.
    Uses a mock if OPENAI_API_KEY is not set.
    """
    api_key = os.getenv("OPENAI_API_KEY")
    logger.debug(f"API Key present: {bool(api_key)}")
    if not api_key:
        # Create a mock LLM that always returns a predefined response
        logger.debug("Using FakeListChatModel for testing")
        return FakeListChatModel(
            responses=[
                "Go to a website",
                "Select an option",
                "Perform an action",
                "Test completed"
            ]
        )
    logger.debug("Using actual ChatOpenAI model")
    from langchain_openai import ChatOpenAI
    return ChatOpenAI(model='gpt-4o', api_key=api_key)

@pytest.fixture(scope="session")
def browser():
    """
    Fixture to provide a Browser instance for testing.
    """
    logger.debug("Creating Browser instance for testing")
    return Browser(config=BrowserConfig(headless=True, disable_security=True))

@pytest.fixture(scope="function")
async def browser_context(browser):
    """
    Fixture to provide a BrowserContext instance for testing.
    """
    logger.debug("Creating BrowserContext instance for testing")
    context = BrowserContext(browser=browser)
    yield context
    await context.close()
