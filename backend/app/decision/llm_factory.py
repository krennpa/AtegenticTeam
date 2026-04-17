from langchain_core.language_models.chat_models import BaseChatModel
from langchain_google_vertexai import ChatVertexAI
from langchain_openai import ChatOpenAI

from ..core.config import settings


def get_chat_model() -> BaseChatModel:
    provider = (settings.LLM_PROVIDER or "").strip().lower()

    if provider == "vertexai":
        return ChatVertexAI(
            model_name=settings.VERTEX_MODEL,
            temperature=0,
            project=settings.GOOGLE_CLOUD_PROJECT,
        )

    return ChatOpenAI(
        model=settings.OPENAI_MODEL,
        temperature=0,
        api_key=settings.OPENAI_API_KEY,
    )
