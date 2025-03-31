from agents import function_tool
from ..schemas import CreateQueryOutput
from typing import List
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

@function_tool
async def create_query(query: str, queries: List[str]) -> CreateQueryOutput:
    """
    Create 2-3 focused search queries based on the user's initial query about a company.
    
    IMPORTANT: After using this tool, you MUST pass the generated queries to the target_search tool.
    
    Instructions:
    - Generate ONLY 2-3 specific search queries for maximum efficiency
    - Make each query short and highly targeted
    - Focus on the most important aspects of the company (business model, recent news, key products)
    - Speed is critical - prioritize creating fewer, more effective queries
    - NEXT STEP: After getting these queries, you MUST use the target_search tool with them
    
    Args:
        query: The user's initial query about a company
        queries: The list of generated search queries (2-3 items maximum)
        
    Returns:
        A list of search queries to be passed DIRECTLY to the target_search tool
    """
    # The agent will do the work of generating queries directly through function calling
    # Limit to maximum 3 queries for speed
    if len(queries) > 3:
        queries = queries[:3]
    
    return CreateQueryOutput(queries=queries) 