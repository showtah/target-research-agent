Here's explanation about company research openai agents we will build from now:

# goal 
I want ai agent to deep-search target company information based on my query.
so there's tool calling needed for like target_search, create_query.

I expect this agent as simple one agent, so you don't need to think of handoff, multiagent features, etc...

## workflow for its agent
1. FromUser: they will give the agent a query related to company research.
2. ToAgent(Tool calling): creates queries for next async target_search tool calling, with using create_query_tool
3. toAgent(Tool calling): based on the queries creared, use target_search tool using tavily api(already set at .env)
4. toAgent(Text Generation):after search is done, based on all contexts, creates markdown style summary
5. toAgent(mindmap tree Gen): create json schema to create mindmap including images, images url

# Further Notes:

## create_queries tool 
```
{
  "name": "create_search_queries",
  "description": "Create search queries based on user query.",
  "strict": true,
  "parameters": {
    "type": "object",
    "required": [
      "user_query",
    ],
    "properties": {
      "user_query": {
        "type": "string",
        "description": "The query provided by the user"
      }
    },
    "additionalProperties": false
  }
}
```