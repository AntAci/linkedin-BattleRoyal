"""Extract structured FighterProfile from raw PDF text using Mistral LLM."""

from langchain_mistralai import ChatMistralAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import PydanticOutputParser

from battle_royal.models.profile import FighterProfile

EXTRACTION_PROMPT = ChatPromptTemplate.from_messages([
    (
        "system",
        "You are an expert CV/resume parser. Extract structured profile "
        "information from the following CV text. Be thorough — capture all "
        "skills, experiences, education, certifications, languages, "
        "publications, awards, and projects mentioned.\n\n"
        "{format_instructions}",
    ),
    (
        "human",
        "Extract the profile from this CV text:\n\n{cv_text}",
    ),
])


def extract_profile(cv_text: str, api_key: str) -> FighterProfile:
    """Parse raw CV text into a structured FighterProfile using Mistral."""
    llm = ChatMistralAI(
        model="mistral-small-latest",
        api_key=api_key,
        temperature=0,
    )

    parser = PydanticOutputParser(pydantic_object=FighterProfile)
    chain = EXTRACTION_PROMPT | llm | parser

    profile = chain.invoke({
        "cv_text": cv_text,
        "format_instructions": parser.get_format_instructions(),
    })

    return profile
