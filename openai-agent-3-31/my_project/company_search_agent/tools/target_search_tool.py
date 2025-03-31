from agents import function_tool
from ..schemas import TargetSearchInput, TargetSearchOutput, TargetSearchResult
import os
from dotenv import load_dotenv
from tavily import TavilyClient
import asyncio
import time
import json

# Load environment variables
load_dotenv()

# Get Tavily API key
tavily_api_key = os.getenv("TAVILY_API_KEY")
if not tavily_api_key:
    raise ValueError("TAVILY_API_KEY environment variable not set.")

# Initialize Tavily client with async capability
tavily_client = TavilyClient(api_key=tavily_api_key)

@function_tool
async def target_search(input_data: TargetSearchInput) -> TargetSearchOutput:
    """
    Perform web searches for all queries simultaneously using Tavily API and return the results.
    
    IMPORTANT: You MUST use this tool after create_query to get real information about the company.
    This is the tool that actually fetches information from the web.
    You should use this tool ONLY ONCE with all the queries from create_query.
    
    Instructions:
    - Take ALL the queries from create_query output and pass them to this tool
    - This is a REQUIRED step - you cannot skip web search
    - The results from this tool should be used to create the summary
    
    Args:
        input_data: The list of queries (from create_query output) to search for
        
    Returns:
        A collection of search results from multiple queries that should be used for the final summary
    """
    start_time = time.time()
    all_results = []
    
    # Print the queries being searched
    print(f"\n🔍 Starting search for {len(input_data.queries)} queries:")
    for i, query in enumerate(input_data.queries, 1):
        print(f"  Query {i}: '{query}'")
    
    # Use all queries but limit to 3 maximum for speed
    if len(input_data.queries) > 3:
        print(f"⚠️ Limiting to first 3 queries for performance (out of {len(input_data.queries)} total)")
        queries = input_data.queries[:3]
    else:
        queries = input_data.queries
    
    # Create a semaphore to limit concurrent API calls (avoid rate limiting)
    semaphore = asyncio.Semaphore(5)  # Allow up to 5 concurrent requests
    
    # Track results by query
    results_by_query = {}
    
    # Improved async function with better error handling and timeout
    async def search_query(query, query_index):
        query_start_time = time.time()
        try:
            print(f"📡 Searching for query {query_index}: '{query}'...")
            
            # Use semaphore to limit concurrent calls
            async with semaphore:
                # Use a synchronous call in an async context with a timeout
                search_result = await asyncio.wait_for(
                    asyncio.to_thread(
                        tavily_client.search,
                        query,
                        search_depth="basic",     # Use basic search for faster results
                        include_images=True,
                        include_image_descriptions=True,     # Include images for mindmap
                        max_results=5,            # Limit to 2 results per query for maximum speed
                        include_raw_content=False # Skip raw content to improve speed
                    ),
                    timeout=10  # Set a 10-second timeout per query
                )
                
                # Extract and format the results
                query_results = []
                for result in search_result.get("results", []):
                    query_results.append(
                        TargetSearchResult(
                            title=result.get("title", ""),
                            url=result.get("url", ""),
                            # Truncate content to 200 chars to speed up processing
                            content=result.get("content", "")[:200] + "..." if len(result.get("content", "")) > 200 else result.get("content", ""),
                            score=result.get("score", 0.0),
                        )
                    )
                
                # Log query completion with details
                query_elapsed = time.time() - query_start_time
                print(f"✓ Query {query_index} '{query}' completed in {query_elapsed:.2f} seconds with {len(query_results)} results")
                
                # Store results by query for detailed reporting
                results_by_query[query] = query_results
                
                return query_results
        except asyncio.TimeoutError:
            print(f"⚠️ Search timed out for query {query_index}: '{query}'")
            results_by_query[query] = []
            return []  # Return empty results on timeout
        except Exception as e:
            print(f"❌ Error searching for query {query_index}: '{query}' - {str(e)}")
            results_by_query[query] = []
            return []  # Return empty results on error
    
    # Create and gather all search tasks
    tasks = [search_query(query, i+1) for i, query in enumerate(queries)]
    results_per_query = await asyncio.gather(*tasks)
    
    # Flatten the results
    for query_results in results_per_query:
        all_results.extend(query_results)
    
    # Sort by relevance score (highest first) and limit total results to improve speed
    all_results.sort(key=lambda x: x.score, reverse=True)
    orig_results_count = len(all_results)
    all_results = all_results[:8] if len(all_results) > 8 else all_results
    
    # Log the total time taken
    elapsed = time.time() - start_time
    print(f"\n🔎 Search summary:")
    print(f"  Total time: {elapsed:.2f} seconds")
    print(f"  Queries processed: {len(queries)}")
    print(f"  Total results found: {orig_results_count}")
    print(f"  Filtered to top: {len(all_results)} results")
    
    # Print detailed results by query
    print("\n📊 Results by query:")
    for i, (query, results) in enumerate(results_by_query.items(), 1):
        print(f"  Query {i}: '{query}'")
        print(f"    Found {len(results)} results")
        for j, result in enumerate(results[:2], 1):  # Show at most 2 results per query
            print(f"    {j}. {result.title}")
            print(f"       URL: {result.url}")
        if len(results) > 2:
            print(f"       ... and {len(results) - 2} more results")
    
    # Return the formatted results
    return TargetSearchOutput(results=all_results) 