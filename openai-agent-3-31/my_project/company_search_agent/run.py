import asyncio
import os
import json
import time
import inspect
import re
from dotenv import load_dotenv
from agents import Runner, ItemHelpers
from .agent import company_research_agent
from .tools import create_query, target_search

# Load environment variables
load_dotenv()

# Ensure API key is available
api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    raise ValueError("OPENAI_API_KEY environment variable not set.")

# Ensure Tavily API key is available
tavily_api_key = os.getenv("TAVILY_API_KEY")
if not tavily_api_key:
    raise ValueError("TAVILY_API_KEY environment variable not set.")

# Map tool function names to friendly names
TOOL_NAME_MAP = {
    "create_query": "Create Search Queries",
    "target_search": "Search based on queries"
}

# Track which tools have been called to detect patterns
tool_call_history = []
last_tool_seen = None
tool_usage_count = {"Create Search Queries": 0, "Search based on queries": 0}

def detect_tool_from_event(event):
    """
    Enhanced tool detection from events using multiple methods
    """
    global last_tool_seen
    event_str = str(event)
    event_repr = repr(event)
    
    # Track if we've already seen create_query to help identify subsequent calls
    if last_tool_seen == "Create Search Queries" and "target_search" not in event_str:
        # After create_query, the next tool is likely target_search
        # Keep track of the sequence to improve detection
        potential_target_search = True
    else:
        potential_target_search = False
    
    # Method 1: Direct string matching in event string representation
    if "create_query" in event_str:
        last_tool_seen = "Create Search Queries"
        return "Create Search Queries"
    elif "target_search" in event_str:
        last_tool_seen = "Search based on queries"
        return "Search based on queries"
    
    # Method 2: Check the payload content for hints
    try:
        if hasattr(event, "item"):
            # For tool_call_item, check the function name or arguments
            if hasattr(event.item, "tool_calls") and event.item.tool_calls:
                for tool_call in event.item.tool_calls:
                    if hasattr(tool_call, "function") and hasattr(tool_call.function, "name"):
                        name = tool_call.function.name
                        if name == "create_query":
                            last_tool_seen = "Create Search Queries"
                            return "Create Search Queries"
                        elif name == "target_search":
                            last_tool_seen = "Search based on queries"
                            return "Search based on queries"
                    
                    # Check arguments for clues
                    if hasattr(tool_call, "function") and hasattr(tool_call.function, "arguments"):
                        args = tool_call.function.arguments
                        if isinstance(args, str):
                            # If arguments contain queries array, it's likely target_search
                            if '"queries":' in args:
                                last_tool_seen = "Search based on queries"
                                return "Search based on queries"
            
            # For output, check the content
            if hasattr(event.item, "output") and isinstance(event.item.output, str):
                if '"queries":' in event.item.output and not '"results":' in event.item.output:
                    last_tool_seen = "Create Search Queries" 
                    return "Create Search Queries"
                elif '"results":' in event.item.output:
                    last_tool_seen = "Search based on queries"
                    return "Search based on queries"
                
    except Exception as e:
        # If there's an error in detection, fall back to sequence-based detection
        pass
    
    # Method 3: Sequential heuristic
    # After seeing the first tool (create_query), if we see another tool and don't recognize it,
    # assume it's the target_search tool
    if potential_target_search and len(tool_call_history) > 0 and tool_call_history[-1] == "Create Search Queries":
        last_tool_seen = "Search based on queries"
        return "Search based on queries"
    
    # Default
    return "unknown"

def format_output_json(json_str, max_length=100):
    """Format a JSON string for console output with optional truncation"""
    try:
        data = json.loads(json_str)
        formatted = json.dumps(data, indent=2, ensure_ascii=False)
        if len(formatted) > max_length:
            lines = formatted.split("\n")
            if len(lines) > 10:
                return "\n".join(lines[:5] + ["...", "(output truncated)"] + lines[-3:])
            else:
                return formatted[:max_length] + "... (truncated)"
        return formatted
    except:
        if json_str and len(json_str) > max_length:
            return json_str[:max_length] + "... (truncated)"
        return json_str or "(no output)"

async def run_with_progress(user_query, log_intervals=[10, 25, 40, 60]):
    """
    Run the agent with progress logging at specified intervals and tool event tracking
    Args:
        user_query: The query to pass to the agent
        log_intervals: List of seconds at which to log progress messages
    """
    # Reset tool call history and usage count
    global tool_call_history, last_tool_seen, tool_usage_count
    tool_call_history = []
    last_tool_seen = None
    tool_usage_count = {"Create Search Queries": 0, "Search based on queries": 0}
    
    # Start the agent task with streaming
    streaming_result = Runner.run_streamed(company_research_agent, user_query)
    
    # Set up interval tasks for logging
    start_time = time.time()
    log_done = {interval: False for interval in log_intervals}
    search_reminder_shown = False
    
    # Create a task to track time separately from the events
    async def time_tracker():
        nonlocal search_reminder_shown
        while True:
            # Check elapsed time
            elapsed = time.time() - start_time
            
            # Log at intervals if needed
            for interval in log_intervals:
                if elapsed > interval and not log_done[interval]:
                    print(f"\n⏳ Still researching... (taking longer than {interval} seconds)")
                    log_done[interval] = True
            
            # After 15 seconds, if we've seen create_query but not target_search, show a reminder
            if elapsed > 15 and not search_reminder_shown and "Create Search Queries" in tool_call_history and "Search based on queries" not in tool_call_history:
                print("\n🔍 The agent is now searching the web for information...")
                search_reminder_shown = True
            
            # Short sleep to prevent tight loop
            await asyncio.sleep(0.5)
    
    # Start the time tracker
    time_tracker_task = asyncio.create_task(time_tracker())
    
    # Track tool usage
    create_query_seen = False
    search_seen = False
    last_queries = []
    first_tool_complete = False
    
    try:
        # Process streaming events
        async for event in streaming_result.stream_events():
            # Skip events that don't have the expected structure
            if not hasattr(event, "type"):
                continue
                
            # Handle different event types
            if event.type == "raw_response_event":
                # Process raw response events if needed
                # For now, just skip these events
                continue
                
            # Continue only with run_item_stream_event
            if event.type != "run_item_stream_event" or not hasattr(event, "item"):
                continue
            
            # Get the item type
            item_type = getattr(event.item, "type", "unknown")
            
            # For tool calling events
            if item_type == "tool_call_item":
                # Determine the specific tool being called
                tool_name = detect_tool_from_event(event)
                
                # If this is the second tool call and the first one was create_query,
                # assume this is target_search regardless of what the detection says
                if first_tool_complete and len(tool_call_history) == 1 and tool_call_history[0] == "Create Search Queries":
                    tool_name = "Search based on queries"
                
                # Check for repeated tool usage and show a warning
                if tool_name in tool_usage_count:
                    tool_usage_count[tool_name] += 1
                    if tool_usage_count[tool_name] > 1:
                        print(f"\n⚠️ Warning: {tool_name} is being used more than once (usage #{tool_usage_count[tool_name]}).")
                        print("Each tool should be used exactly once for optimal performance.")
                
                # Get input parameters if available
                tool_input = None
                try:
                    if hasattr(event.item, "tool_calls") and event.item.tool_calls:
                        tool_input = event.item.tool_calls[0].function.arguments
                    elif hasattr(event.item, "function") and hasattr(event.item.function, "arguments"):
                        tool_input = event.item.function.arguments
                except:
                    pass
                
                # Track which tool we've seen
                if tool_name == "Create Search Queries":
                    create_query_seen = True
                elif tool_name == "Search based on queries":
                    search_seen = True
                
                # Add to call history for pattern detection
                if tool_name != "unknown" and tool_name not in tool_call_history:
                    tool_call_history.append(tool_name)
                
                # Print the tool call with input parameters if available
                print(f"\n🔧 Tool calling: {tool_name}... (use #{tool_usage_count.get(tool_name, 0)})")
                if tool_input:
                    print(f"📥 INPUT:")
                    print(f"```json\n{format_output_json(tool_input)}\n```")
            
            # For tool output events
            elif item_type == "tool_call_output_item":
                # Get the output from the item
                output = getattr(event.item, "output", None)
                
                # Determine which tool generated this output
                tool_name = detect_tool_from_event(event)
                
                # For the second tool output, if we've already seen create_query and 
                # the first tool was completed, assume this is target_search
                if first_tool_complete and create_query_seen and not search_seen:
                    tool_name = "Search based on queries"
                
                # First tool completed flag for better sequencing
                first_tool_complete = True
                
                # Process create_query output
                if tool_name == "Create Search Queries" or (not search_seen and "queries" in str(output) and not "results" in str(output)):
                    try:
                        if output:
                            output_data = json.loads(output)
                            queries = output_data.get("queries", [])
                            print(f"✓ Create query completed with {len(queries)} search queries:")
                            for i, q in enumerate(queries, 1):
                                print(f"  {i}. {q}")
                            # Detailed output
                            print(f"📤 OUTPUT:")
                            print(f"```json\n{format_output_json(output)}\n```")
                            # Save queries for next tool detection
                            last_queries = queries
                            # Mark create_query as seen
                            create_query_seen = True
                            
                            # Encourage using target_search right after
                            if len(queries) > 0:
                                print(f"\n➡️ Next step: Pass ALL {len(queries)} queries to target_search tool in one call.")
                        else:
                            print(f"✓ Create query completed (no output)")
                    except:
                        print(f"✓ Create query completed")
                        if output:
                            print(f"📤 OUTPUT: {str(output)[:100]}")
                
                # Process target_search output
                elif tool_name == "Search based on queries" or "results" in str(output) or (create_query_seen and first_tool_complete):
                    try:
                        result_count = 0
                        if output:
                            output_data = json.loads(output)
                            results = output_data.get("results", [])
                            result_count = len(results)
                            
                            if result_count > 0:
                                print(f"✓ Web search completed with {result_count} results:")
                                # Show a short preview of each result
                                for i, result in enumerate(results[:3], 1):
                                    title = result.get("title", "No title")
                                    url = result.get("url", "No URL")
                                    content_preview = result.get("content", "")[:100]
                                    if content_preview:
                                        content_preview += "..." if len(result.get("content", "")) > 100 else ""
                                    print(f"  {i}. {title}")
                                    print(f"     URL: {url}")
                                    print(f"     Preview: {content_preview}")
                                
                                if result_count > 3:
                                    print(f"     ... and {result_count - 3} more results")
                                
                                # Detailed output (truncated for readability)
                                print(f"📤 OUTPUT (truncated):")
                                print(f"```json\n{format_output_json(output, max_length=500)}\n```")
                                
                                # Remind to generate final output
                                print(f"\n➡️ Next step: Generate summary and mindmap based on these search results.")
                            else:
                                print(f"✓ Web search completed with no results")
                        else:
                            print(f"✓ Web search completed with results")
                        
                        # Mark search as seen
                        search_seen = True
                        # Add to call history if not already there
                        if "Search based on queries" not in tool_call_history:
                            tool_call_history.append("Search based on queries")
                            
                    except Exception as e:
                        print(f"✓ Web search completed with results")
                        if output:
                            print(f"📤 OUTPUT: (error parsing JSON: {str(e)})")
                            print(f"{str(output)[:200]}...")
                
                else:
                    print(f"✓ Tool completed: {tool_name}")
                    if output:
                        print(f"📤 OUTPUT:\n{str(output)[:200]}...")
        
        # Since streaming is done, return the streaming_result itself
        time_tracker_task.cancel()
        
        return streaming_result
        
    except Exception as e:
        print(f"\n❌ An error occurred: {str(e)}")
        time_tracker_task.cancel()
        return None

async def main():
    """
    Main function to run the company research agent.
    """
    print("🔍 Company Research Assistant")
    print("------------------------")
    print("This agent will research a company based on your query and provide a detailed summary.")
    print("Each tool will be used exactly once in sequence:")
    print("1. Create Search Queries → 2. Search based on queries → 3. Generate output")
    print("\nExample queries: 'Tell me about Tesla's recent activities', 'Research Amazon's business model'\n")
    
    # Get user input
    user_query = input("Enter your company research query: ")
    
    print("\n⏳ Researching... (this may take a few seconds)")
    
    # Start timing
    start_time = time.time()
    
    # Run the agent with progress logging
    result = await run_with_progress(user_query)
    
    # If result is None, the operation failed
    if result is None:
        return
    
    # Calculate elapsed time
    elapsed_time = time.time() - start_time
    
    # Get the structured output - directly access final_output from the result object
    output = result.final_output
    
    # Show tool usage summary
    tools_used = set(tool_call_history)
    tools_str = ", ".join(tools_used) if tools_used else "None detected"
    
    print(f"\n✅ Research complete in {elapsed_time:.1f} seconds!")
    print(f"🔧 Tools used: {tools_str}")
    
    # Check if both tools were used exactly once and in order
    expected_usage = ["Create Search Queries", "Search based on queries"]
    if tool_call_history == expected_usage:
        print(f"✅ Perfect tool usage: Each tool was used exactly once in the correct order.")
    else:
        print(f"⚠️ Tool usage was not optimal: {', '.join(tool_call_history)}")
        print(f"   Expected: {', '.join(expected_usage)}")
    
    # Display the usage count
    for tool, count in tool_usage_count.items():
        print(f"   {tool}: used {count} time(s)")
    
    # Display the results directly without saving to files
    print("\n📝 SUMMARY:")
    print("===========")
    print(output.markdown_summary)
    
    print("\n🌳 MINDMAP:")
    print("===========")
    print(json.dumps(output.mindmap.model_dump(), indent=2))

if __name__ == "__main__":
    asyncio.run(main()) 